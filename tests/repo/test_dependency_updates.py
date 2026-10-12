"""Dependabot keeps dependencies current, and is the only update bot."""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RENOVATE_CONFIGS = ["renovate.json", "renovate.json5", ".github/renovate.json",
                    ".github/renovate.json5", ".gitlab/renovate.json",
                    ".gitlab/renovate.json5", ".renovaterc", ".renovaterc.json",
                    ".renovaterc.json5"]


def _updates():
    config = yaml.safe_load((REPO_ROOT / ".github" / "dependabot.yml").read_text())
    return {u["package-ecosystem"]: u for u in config["updates"]}


def test_dependabot_updates_python_and_actions_weekly():
    updates = _updates()

    assert set(updates) == {"uv", "github-actions"}
    for update in updates.values():
        assert update["directory"] == "/"
        assert update["schedule"]["interval"] == "weekly"


def test_published_lower_bounds_are_never_raised():
    """Raising a lower bound in pyproject.toml narrows what users can install."""
    assert _updates()["uv"]["versioning-strategy"] == "widen"


def test_updates_are_grouped_and_titled_as_conventional_commits():
    uv, actions = _updates()["uv"], _updates()["github-actions"]

    assert uv["groups"]["patch"]["update-types"] == ["patch"]
    assert actions["groups"]["github-actions"]["update-types"] == ["minor", "patch"]
    assert uv["commit-message"] == {"prefix": "chore", "include": "scope"}
    assert actions["commit-message"]["prefix"] == "ci"


def test_only_one_update_bot_is_configured():
    assert not [p for p in RENOVATE_CONFIGS if (REPO_ROOT / p).exists()]
