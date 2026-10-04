"""Config loading must honour every setting (invariant 4: honest configuration).

``AgentConfig.load()`` used to copy a fixed list of keys from the YAML file, so settings such as
``semantic_memory`` or ``feature_flags`` were silently dropped. These tests pin the fix.
"""

import logging
from pathlib import Path

import pytest
import yaml

from cortex.config import AgentConfig

REPO_ROOT = Path(__file__).resolve().parents[3]

# One non-default sample per setting that AgentConfig.to_dict() exposes. A new setting added to
# to_dict() without a sample here fails test_every_setting_has_a_sample, which is the point:
# every setting needs a test that proves it takes effect.
SAMPLES = {
    "model": "llama3",
    "permission_mode": "plan",
    "max_iterations": 7,
    "max_iterations_continue_default": True,
    "max_iterations_continue_amount": 3,
    "max_tokens": 12345,
    "keep_recent_messages": 5,
    "auto_save": True,
    "output_format": "json",
    "hooks": [{"event": "PreToolUse", "type": "log"}],
    "hooks_enabled": False,
    "tools_disabled": ["web_search"],
    "tools_plugins": ["my_plugins.custom_tools"],
    "subagent_max_iterations": 4,
    "subagent_allowed_tools": ["grep"],
    "provider": "ollama",
    "timeouts": {"git": 99},
    "tool_timeouts": {"grep": 5},
    "session_retention": {"max_count": 3},
    "error_recovery": {"enable_smart_recovery": False},
    "file_cache": {"enabled": False},
    "transactions": {"max_backups": 2},
    "checkpoints": {"keep": 3},
    "command_sandbox": {"network": False},
    "ollama": {"num_ctx": 8192},
    "routing": {"enabled": True},
    "semantic_memory": {"enabled": True},
    "profiling": {"enabled": True},
    "feature_flags": {"rust_search": True},
    "services": {"enabled": True},
    "enable_planning": True,
    "enable_layered_memory": True,
    "enable_metacognition": True,
}


def _load(tmp_path, data) -> AgentConfig:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data))
    return AgentConfig.load(path)


def test_every_setting_has_a_sample():
    assert set(AgentConfig().to_dict()) == set(SAMPLES)


@pytest.mark.parametrize("key", sorted(SAMPLES))
def test_setting_in_yaml_takes_effect(tmp_path, monkeypatch, key):
    for var in ("CORTEX_MODEL", "CORTEX_MODE", "CORTEX_PROVIDER", "CORTEX_OUTPUT_FORMAT"):
        monkeypatch.delenv(var, raising=False)
    value = SAMPLES[key]

    loaded = _load(tmp_path, {key: value}).to_dict()[key]

    if isinstance(value, dict):
        # Dict settings merge over their defaults, so the sample keys must carry through.
        assert {k: loaded[k] for k in value} == value
    else:
        assert loaded == value


def test_semantic_memory_can_be_enabled_from_yaml(tmp_path):
    config = _load(tmp_path, {"semantic_memory": {"enabled": True, "collection_name": "mine"}})
    assert config.semantic_memory["enabled"] is True
    assert config.semantic_memory["collection_name"] == "mine"


def test_features_section_maps_to_feature_flags(tmp_path):
    config = _load(tmp_path, {"features": {"rust_search": True}})
    assert config.feature_flags["rust_search"] is True


def test_tools_section_maps_to_plugins_and_disabled(tmp_path):
    config = _load(
        tmp_path, {"tools": {"plugins": ["a.b"], "disabled": ["web_search"], "enabled": []}}
    )
    assert config.tools_plugins == ["a.b"]
    assert config.tools_disabled == ["web_search"]


def test_empty_tools_section_is_ignored(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("model: llama3\ntools:\n  # only comments here\n")
    assert AgentConfig.load(path).model == "llama3"


def test_unknown_key_is_reported(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="cortex.config"):
        _load(tmp_path, {"modle": "typo"})
    assert "modle" in caplog.text


def test_environment_overrides_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTEX_MODEL", "from-env")
    assert _load(tmp_path, {"model": "from-file"}).model == "from-env"


def test_shipped_default_yaml_loads_cleanly(caplog, monkeypatch):
    monkeypatch.delenv("CORTEX_MODEL", raising=False)
    monkeypatch.delenv("CORTEX_MODE", raising=False)
    with caplog.at_level(logging.WARNING, logger="cortex.config"):
        config = AgentConfig.load(REPO_ROOT / "config" / "default.yaml")
    assert "unknown" not in caplog.text.lower()
    assert config.feature_flags["rust_search"] is False
    assert config.permission_mode == "normal"
    assert config.parallel_execution["enabled"] is True
