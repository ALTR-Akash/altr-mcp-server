import urllib.parse

from altr_mcp.utils import api
from altr_mcp.settings import get_settings


def _base():
    return get_settings().dam_alerting_base_url


def _quote(value: str) -> str:
    return urllib.parse.quote(value, safe='')


async def list_rules(auth, params: dict) -> dict:
    url = f"{_base()}/rules"
    return await api.request("GET", url, auth, params)


async def create_rule(auth, data: dict) -> dict:
    url = f"{_base()}/rules"
    return await api.request("POST", url, auth, {}, data)


async def get_rule(auth, rule_id: str) -> dict:
    url = f"{_base()}/rules/{_quote(rule_id)}"
    return await api.request("GET", url, auth, {})


async def update_rule(auth, rule_id: str, data: dict) -> dict:
    url = f"{_base()}/rules/{_quote(rule_id)}"
    return await api.request("PATCH", url, auth, {}, data)


async def delete_rule(auth, rule_id: str) -> dict:
    url = f"{_base()}/rules/{_quote(rule_id)}"
    return await api.request("DELETE", url, auth, {})


async def list_alerts(auth, params: dict) -> dict:
    url = f"{_base()}/alerts"
    return await api.request("GET", url, auth, params)


async def get_alert(auth, alert_id: str) -> dict:
    url = f"{_base()}/alerts/{_quote(alert_id)}"
    return await api.request("GET", url, auth, {})


async def acknowledge_alert(auth, alert_id: str, data: dict) -> dict:
    url = f"{_base()}/alerts/{_quote(alert_id)}/acknowledge"
    return await api.request("PATCH", url, auth, {}, data)


async def list_comments(auth, alert_id: str, params: dict) -> dict:
    url = f"{_base()}/alerts/{_quote(alert_id)}/comments"
    return await api.request("GET", url, auth, params)


async def create_comment(auth, alert_id: str, data: dict) -> dict:
    url = f"{_base()}/alerts/{_quote(alert_id)}/comments"
    return await api.request("POST", url, auth, {}, data)
