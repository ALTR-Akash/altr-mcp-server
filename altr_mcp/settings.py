from functools import lru_cache
from typing import Literal, Optional

import httpx
from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
    )

    # Required — startup fails with ValidationError if missing
    org_id: str
    mapi_key: SecretStr
    mapi_secret: SecretStr

    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "console"  # "console" or "json"
    # Total attempts per API call, not retries on top of the first, so 1
    # means "try once, never retry". 0 or less is rejected rather than
    # silently behaving like 1.
    max_retries: int = Field(default=3, ge=1)
    disable_retry: bool = False
    # Per-request timeout in seconds, covering connect, read, write and
    # pool acquisition.
    #
    # allow_inf_nan=False on both: pydantic accepts "inf" as a valid float,
    # and an infinite ceiling silently removes the bound it exists to
    # impose.
    request_timeout: float = Field(default=30.0, gt=0, allow_inf_nan=False)
    # Ceiling on a server-sent Retry-After. The value is server-controlled
    # and every attempt still counts against max_retries, so an unbounded
    # one would park the call with nothing to end it.
    #
    # gt=0 rather than ge=0: 0 reads as "ignore Retry-After" but would
    # clamp every one to zero, turning a rate-limit response into
    # max_retries immediate retries. Set DISABLE_RETRY to stop retrying.
    max_retry_after: float = Field(default=60.0, gt=0, allow_inf_nan=False)

    # Transport configuration
    # MCP_TRANSPORT — "stdio", "sse", "streamable-http"
    mcp_transport: Literal["stdio", "sse", "streamable-http"] = "stdio"
    # MCP_HOST — bind address for HTTP transports
    mcp_host: str = "0.0.0.0"
    # MCP_PORT — port for HTTP transports
    mcp_port: int = 8000
    # RESTRICTED_TOOLS — comma-separated tool names
    restricted_tools: Optional[str] = None

    # URL overrides with production defaults
    altr_api_base_url: str = "https://api.live.altr.com"
    altr_altrnet_base_url: str = "https://altrnet.live.altr.com"
    altr_classification_base_url: Optional[str] = None
    altr_sc_control_base_url: Optional[str] = None
    altr_service_user_base_url: Optional[str] = None
    altr_audit_report_base_url: Optional[str] = None
    altr_vault_base_url: Optional[str] = None
    altr_critical_base_url: Optional[str] = None
    altr_kma_base_url: Optional[str] = None
    altr_dam_alerting_base_url: Optional[str] = None

    @computed_field
    @property
    def classification_base_url(self) -> str:
        if self.altr_classification_base_url:
            return self.altr_classification_base_url
        return f"https://{self.org_id}.classification.live.altr.com"

    @computed_field
    @property
    def sc_control_base_url(self) -> str:
        if self.altr_sc_control_base_url:
            return self.altr_sc_control_base_url
        return f"https://{self.org_id}.sc-control.live.altr.com"

    @computed_field
    @property
    def service_user_base_url(self) -> str:
        if self.altr_service_user_base_url:
            return self.altr_service_user_base_url
        return f"https://{self.org_id}.service-user.live.altr.com"

    @computed_field
    @property
    def audit_report_base_url(self) -> str:
        if self.altr_audit_report_base_url:
            return self.altr_audit_report_base_url
        return f"https://{self.org_id}.audit-report.live.altr.com/v1"

    @computed_field
    @property
    def vault_base_url(self) -> str:
        if self.altr_vault_base_url:
            return self.altr_vault_base_url
        return f"https://{self.org_id}.vault.live.altr.com/api/v2"

    @computed_field
    @property
    def critical_base_url(self) -> str:
        if self.altr_critical_base_url:
            return self.altr_critical_base_url
        return f"https://{self.org_id}.critical.live.altr.com/v2"

    @computed_field
    @property
    def kma_base_url(self) -> str:
        if self.altr_kma_base_url:
            return self.altr_kma_base_url
        return f"https://{self.org_id}.kma.live.altr.com/v1"

    @computed_field
    @property
    def dam_alerting_base_url(self) -> str:
        if self.altr_dam_alerting_base_url:
            return self.altr_dam_alerting_base_url
        return f"https://{self.org_id}.dam-alerting.live.altr.com/v1/dam-alerting"

    @property
    def auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(
            username=self.mapi_key.get_secret_value(),
            password=self.mapi_secret.get_secret_value(),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
