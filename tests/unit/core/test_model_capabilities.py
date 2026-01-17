"""Tests for model capabilities module."""

import pytest
from cortex.core.model_capabilities import (
    get_model_profile,
    get_prompt_style,
    get_max_tools,
    get_context_window,
    supports_json_mode,
    list_all_profiles,
    get_models_by_capability,
    ModelProfile,
    PromptStyle,
    CapabilityLevel,
    DEFAULT_PROFILE,
)


class TestGetModelProfile:
    """Tests for get_model_profile function."""

    def test_exact_match(self):
        """Test exact model name match."""
        profile = get_model_profile("llama3.2")
        assert profile.name == "Llama 3.2"
        assert profile.prompt_style == PromptStyle.CONCISE

    def test_claude_profile(self):
        """Test Claude model profile."""
        profile = get_model_profile("claude-3-5-sonnet")
        assert profile.name == "Claude 3.5 Sonnet"
        assert profile.tool_following == CapabilityLevel.EXCELLENT
        assert profile.context_window == 200000

    def test_gpt4_profile(self):
        """Test GPT-4 model profile."""
        profile = get_model_profile("gpt-4-turbo")
        assert profile.name == "GPT-4 Turbo"
        assert profile.supports_json_mode is True
        assert profile.max_tools_per_prompt == 128

    def test_prefix_match(self):
        """Test prefix matching for model names."""
        profile = get_model_profile("llama3.2:latest")
        assert "Llama" in profile.name

    def test_ollama_prefix_stripped(self):
        """Test that ollama/ prefix is stripped."""
        profile = get_model_profile("ollama/llama3.2")
        assert "Llama" in profile.name

    def test_family_pattern_match(self):
        """Test family pattern matching."""
        profile = get_model_profile("some-llama-variant")
        assert profile.prompt_style in (PromptStyle.CONCISE, PromptStyle.DETAILED)

    def test_unknown_model_returns_default(self):
        """Test that unknown models return default profile."""
        profile = get_model_profile("completely-unknown-model-xyz")
        assert profile.name == "Unknown Model"
        assert profile.prompt_style == PromptStyle.CONCISE


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_prompt_style(self):
        """Test get_prompt_style function."""
        style = get_prompt_style("claude-3-5-sonnet")
        assert style == PromptStyle.DETAILED

        style = get_prompt_style("mistral")
        assert style == PromptStyle.EXPLICIT

    def test_get_max_tools(self):
        """Test get_max_tools function."""
        max_tools = get_max_tools("claude-3-5-sonnet")
        assert max_tools == 64

        max_tools = get_max_tools("mistral")
        assert max_tools == 10

    def test_get_context_window(self):
        """Test get_context_window function."""
        context = get_context_window("claude-3-5-sonnet")
        assert context == 200000

        context = get_context_window("llama2")
        assert context == 4096

    def test_supports_json_mode(self):
        """Test supports_json_mode function."""
        assert supports_json_mode("claude-3-5-sonnet") is True
        assert supports_json_mode("llama3.2") is False


class TestListAndFilter:
    """Tests for listing and filtering profiles."""

    def test_list_all_profiles(self):
        """Test list_all_profiles returns all profile names."""
        profiles = list_all_profiles()
        assert isinstance(profiles, list)
        assert len(profiles) > 10
        assert "llama3.2" in profiles
        assert "claude-3-5-sonnet" in profiles

    def test_get_models_by_capability(self):
        """Test filtering models by capability."""
        models = get_models_by_capability(
            min_tool_following=CapabilityLevel.EXCELLENT,
            min_reasoning=CapabilityLevel.EXCELLENT,
        )
        assert "claude-3-5-sonnet" in models
        assert "gpt-4-turbo" in models
        # Smaller models should not be included
        assert "mistral" not in models

    def test_get_models_moderate_capability(self):
        """Test filtering for moderate capability."""
        models = get_models_by_capability(
            min_tool_following=CapabilityLevel.MODERATE,
            min_reasoning=CapabilityLevel.MODERATE,
        )
        # Should include more models
        assert len(models) > 5


class TestModelProfile:
    """Tests for ModelProfile dataclass."""

    def test_to_dict(self):
        """Test ModelProfile.to_dict method."""
        profile = get_model_profile("llama3.2")
        profile_dict = profile.to_dict()

        assert isinstance(profile_dict, dict)
        assert profile_dict["name"] == "Llama 3.2"
        assert profile_dict["prompt_style"] == "concise"
        assert "context_window" in profile_dict
        assert "tool_following" in profile_dict


class TestDefaultProfile:
    """Tests for default profile behavior."""

    def test_default_profile_values(self):
        """Test DEFAULT_PROFILE has sensible defaults."""
        assert DEFAULT_PROFILE.context_window == 4096
        assert DEFAULT_PROFILE.prompt_style == PromptStyle.CONCISE
        assert DEFAULT_PROFILE.max_tools_per_prompt == 15
        assert DEFAULT_PROFILE.supports_json_mode is False
