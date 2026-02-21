"""Unit tests for tool call validation utilities."""

import json
import pytest
from cortex.utils.tool_call_validation import (
    normalize_tool_call_id,
    normalize_tool_call_arguments,
    validate_tool_call_data,
)


class TestNormalizeToolCallId:
    """Tests for normalize_tool_call_id function."""

    def test_string_id_returned_as_is(self):
        """Test that valid string IDs are returned unchanged."""
        assert normalize_tool_call_id("call_123") == "call_123"
        assert normalize_tool_call_id("abc-def-ghi") == "abc-def-ghi"
        assert normalize_tool_call_id("toolu_abc123") == "toolu_abc123"

    def test_integer_id_converted_to_string(self):
        """Test that integer IDs are converted to strings."""
        assert normalize_tool_call_id(123) == "123"
        assert normalize_tool_call_id(0) == "0"
        assert normalize_tool_call_id(-1) == "-1"
        assert normalize_tool_call_id(999999) == "999999"

    def test_none_id_generates_fallback(self):
        """Test that None IDs generate a fallback ID."""
        result = normalize_tool_call_id(None)
        assert result.startswith("call_")
        assert len(result) > 5

    def test_empty_string_id_generates_fallback(self):
        """Test that empty string IDs generate a fallback ID."""
        result = normalize_tool_call_id("")
        assert result.startswith("call_")
        assert len(result) > 5

    def test_custom_fallback_prefix(self):
        """Test custom fallback prefix for generated IDs."""
        result = normalize_tool_call_id(None, fallback_prefix="tool")
        assert result.startswith("tool_")

        result = normalize_tool_call_id("", fallback_prefix="custom")
        assert result.startswith("custom_")

    def test_unexpected_type_generates_fallback(self):
        """Test that unexpected types generate a fallback ID."""
        result = normalize_tool_call_id([1, 2, 3])
        assert result.startswith("call_")

        result = normalize_tool_call_id({"id": "test"})
        assert result.startswith("call_")

    def test_fallback_ids_are_unique(self):
        """Test that generated fallback IDs are unique."""
        ids = [normalize_tool_call_id(None) for _ in range(100)]
        assert len(ids) == len(set(ids))  # All unique


class TestNormalizeToolCallArguments:
    """Tests for normalize_tool_call_arguments function."""

    def test_valid_json_string_returned_as_is(self):
        """Test that valid JSON strings are returned unchanged."""
        assert normalize_tool_call_arguments('{"key": "value"}') == '{"key": "value"}'
        assert normalize_tool_call_arguments("{}") == "{}"
        assert normalize_tool_call_arguments('{"a": 1, "b": true}') == '{"a": 1, "b": true}'

    def test_empty_string_returns_empty_object(self):
        """Test that empty strings return '{}'."""
        assert normalize_tool_call_arguments("") == "{}"

    def test_whitespace_only_returns_empty_object(self):
        """Test that whitespace-only strings return '{}'."""
        assert normalize_tool_call_arguments("   ") == "{}"
        assert normalize_tool_call_arguments("\n\t") == "{}"

    def test_none_returns_empty_object(self):
        """Test that None returns '{}'."""
        assert normalize_tool_call_arguments(None) == "{}"

    def test_dict_serialized_to_json(self):
        """Test that dicts are serialized to JSON."""
        result = normalize_tool_call_arguments({"key": "value"})
        assert json.loads(result) == {"key": "value"}

        result = normalize_tool_call_arguments({"path": "/test/file.py"})
        assert json.loads(result) == {"path": "/test/file.py"}

    def test_invalid_json_returns_empty_object(self):
        """Test that invalid JSON returns '{}'."""
        assert normalize_tool_call_arguments("not json") == "{}"
        assert normalize_tool_call_arguments("{invalid}") == "{}"
        assert normalize_tool_call_arguments("{'single': 'quotes'}") == "{}"

    def test_unexpected_type_returns_empty_object(self):
        """Test that unexpected types return '{}'."""
        assert normalize_tool_call_arguments(123) == "{}"
        assert normalize_tool_call_arguments([1, 2, 3]) == "{}"


class TestValidateToolCallData:
    """Tests for validate_tool_call_data function."""

    def test_complete_valid_data(self):
        """Test validation of complete valid tool call data."""
        data = {
            "id": "call_123",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"path": "test.txt"}'},
        }
        result = validate_tool_call_data(data)

        assert result["id"] == "call_123"
        assert result["type"] == "function"
        assert result["function"]["name"] == "read_file"
        assert result["function"]["arguments"] == '{"path": "test.txt"}'

    def test_integer_id_normalized(self):
        """Test that integer IDs are normalized to strings."""
        data = {"id": 42, "function": {"name": "test", "arguments": "{}"}}
        result = validate_tool_call_data(data)
        assert result["id"] == "42"

    def test_none_id_generates_fallback(self):
        """Test that None IDs generate fallback IDs with index."""
        data = {"id": None, "function": {"name": "test", "arguments": "{}"}}
        result = validate_tool_call_data(data, index=5)
        assert result["id"].startswith("call_5_")

    def test_empty_arguments_normalized(self):
        """Test that empty arguments are normalized to '{}'."""
        data = {"id": "1", "function": {"name": "test", "arguments": ""}}
        result = validate_tool_call_data(data)
        assert result["function"]["arguments"] == "{}"

    def test_none_arguments_normalized(self):
        """Test that None arguments are normalized to '{}'."""
        data = {"id": "1", "function": {"name": "test", "arguments": None}}
        result = validate_tool_call_data(data)
        assert result["function"]["arguments"] == "{}"

    def test_missing_function_data(self):
        """Test handling of missing function data."""
        data = {"id": "1"}
        result = validate_tool_call_data(data)
        assert result["function"]["name"] == ""
        assert result["function"]["arguments"] == "{}"

    def test_none_function_data(self):
        """Test handling of None function data."""
        data = {"id": "1", "function": None}
        result = validate_tool_call_data(data)
        assert result["function"]["name"] == ""
        assert result["function"]["arguments"] == "{}"

    def test_preserves_index(self):
        """Test that index field is preserved when present."""
        data = {"id": "1", "index": 3, "function": {"name": "test", "arguments": "{}"}}
        result = validate_tool_call_data(data)
        assert result["index"] == 3

    def test_default_type(self):
        """Test that type defaults to 'function' when missing."""
        data = {"id": "1", "function": {"name": "test", "arguments": "{}"}}
        result = validate_tool_call_data(data)
        assert result["type"] == "function"

    def test_kimi_k2_style_integer_id(self):
        """Test handling of Kimi K2.5 style integer IDs."""
        # Kimi K2.5 returns integer IDs via OpenRouter
        data = {
            "id": 12345,
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"path": "README.md"}'},
        }
        result = validate_tool_call_data(data)
        assert result["id"] == "12345"
        assert isinstance(result["id"], str)

    def test_streaming_tool_call_with_index(self):
        """Test handling of streaming tool calls with index field."""
        data = {
            "id": "call_1",
            "index": 0,
            "type": "function",
            "function": {"name": "edit", "arguments": ""},  # Often empty in first chunk
        }
        result = validate_tool_call_data(data, index=0)
        assert result["id"] == "call_1"
        assert result["index"] == 0
        assert result["function"]["arguments"] == "{}"
