"""Tests for Output Formatters"""

import pytest
import json
from io import StringIO

from cortex.output import (
    OutputFormat,
    OutputFormatter,
    TextFormatter,
    JSONFormatter,
    StreamJSONFormatter,
    create_formatter,
)


class TestOutputFormat:
    """Test OutputFormat enum"""

    def test_format_values(self):
        """Test enum values"""
        assert OutputFormat.TEXT.value == "text"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.STREAM_JSON.value == "stream-json"

    def test_from_string(self):
        """Test creating from string"""
        assert OutputFormat("text") == OutputFormat.TEXT
        assert OutputFormat("json") == OutputFormat.JSON
        assert OutputFormat("stream-json") == OutputFormat.STREAM_JSON


class TestTextFormatter:
    """Test TextFormatter class"""

    def test_format_response(self):
        """Test formatting response"""
        formatter = TextFormatter()
        response = {"content": "Hello, world!"}

        result = formatter.format_response(response)
        assert result == "Hello, world!"

    def test_format_response_empty(self):
        """Test formatting empty response"""
        formatter = TextFormatter()
        response = {}

        result = formatter.format_response(response)
        assert result == ""

    def test_format_tool_result_success(self):
        """Test formatting successful tool result"""
        formatter = TextFormatter()
        result = {"success": True, "data": "test"}

        formatted = formatter.format_tool_result("test_tool", result)
        assert "test_tool" in formatted
        assert "Success" in formatted

    def test_format_tool_result_failure(self):
        """Test formatting failed tool result"""
        formatter = TextFormatter()
        result = {"success": False, "error": "Test error"}

        formatted = formatter.format_tool_result("test_tool", result)
        assert "test_tool" in formatted
        assert "Error" in formatted
        assert "Test error" in formatted

    def test_format_error(self):
        """Test formatting error"""
        formatter = TextFormatter()

        formatted = formatter.format_error("Something went wrong", "execution")
        assert "EXECUTION" in formatted
        assert "Something went wrong" in formatted

    def test_format_tool_call(self):
        """Test formatting tool call"""
        formatter = TextFormatter()

        formatted = formatter.format_tool_call("read_file", {"path": "test.txt"})
        assert "read_file" in formatted
        assert "test.txt" in formatted


class TestJSONFormatter:
    """Test JSONFormatter class"""

    def test_format_response(self):
        """Test formatting response as JSON"""
        stream = StringIO()
        formatter = JSONFormatter(stream=stream)

        response = {"content": "Test response", "tool_calls": None}
        formatted = formatter.format_response(response)

        # Should be valid JSON
        data = json.loads(formatted)
        assert data["type"] == "response"
        assert data["content"] == "Test response"
        assert "timestamp" in data

    def test_format_tool_result(self):
        """Test formatting tool result as JSON"""
        stream = StringIO()
        formatter = JSONFormatter(stream=stream)

        result = {"success": True, "data": "test"}
        formatted = formatter.format_tool_result("test_tool", result)

        data = json.loads(formatted)
        assert data["type"] == "tool_result"
        assert data["tool_name"] == "test_tool"
        assert data["success"] is True
        assert data["result"] == result

    def test_format_error(self):
        """Test formatting error as JSON"""
        stream = StringIO()
        formatter = JSONFormatter(stream=stream)

        formatted = formatter.format_error("Test error", "validation", {"field": "path"})

        data = json.loads(formatted)
        assert data["type"] == "error"
        assert data["error"] == "Test error"
        assert data["error_type"] == "validation"
        assert data["context"]["field"] == "path"

    def test_format_tool_call(self):
        """Test formatting tool call as JSON"""
        stream = StringIO()
        formatter = JSONFormatter(stream=stream)

        formatted = formatter.format_tool_call(
            "write_file", {"path": "test.txt", "content": "test"}
        )

        data = json.loads(formatted)
        assert data["type"] == "tool_call"
        assert data["tool_name"] == "write_file"
        assert data["arguments"]["path"] == "test.txt"

    def test_write(self):
        """Test write method"""
        stream = StringIO()
        formatter = JSONFormatter(stream=stream)

        formatter.write('{"test": "data"}')

        stream.seek(0)
        content = stream.read()
        assert content == '{"test": "data"}\n'

    def test_pretty_print(self):
        """Test pretty print option"""
        stream = StringIO()
        formatter = JSONFormatter(stream=stream, pretty=True)

        formatted = formatter.format_response({"content": "test"})

        # Pretty printed JSON should have newlines
        assert "\n" in formatted


class TestStreamJSONFormatter:
    """Test StreamJSONFormatter class"""

    def test_stream_start(self):
        """Test stream start event"""
        stream = StringIO()
        formatter = StreamJSONFormatter(stream=stream)

        formatter.stream_start("response", {"model": "test"})

        stream.seek(0)
        content = stream.read()
        data = json.loads(content.strip())

        assert data["type"] == "stream_start"
        assert data["event"] == "response"
        assert data["metadata"]["model"] == "test"

    def test_stream_chunk(self):
        """Test streaming chunks"""
        stream = StringIO()
        formatter = StreamJSONFormatter(stream=stream)

        formatter.stream_chunk({"content": "Hello"}, "response")

        stream.seek(0)
        content = stream.read()
        data = json.loads(content.strip())

        assert data["type"] == "chunk"
        assert data["event"] == "response"
        assert data["data"]["content"] == "Hello"

    def test_stream_end(self):
        """Test stream end event"""
        stream = StringIO()
        formatter = StreamJSONFormatter(stream=stream)

        formatter.stream_end("response", {"total_tokens": 100})

        stream.seek(0)
        content = stream.read()
        data = json.loads(content.strip())

        assert data["type"] == "stream_end"
        assert data["event"] == "response"
        assert data["summary"]["total_tokens"] == 100

    def test_stream_error(self):
        """Test streaming error"""
        stream = StringIO()
        formatter = StreamJSONFormatter(stream=stream)

        formatter.stream_error("Connection failed", "network", "response")

        stream.seek(0)
        content = stream.read()
        data = json.loads(content.strip())

        assert data["type"] == "stream_error"
        assert data["event"] == "response"
        assert data["error"] == "Connection failed"
        assert data["error_type"] == "network"

    def test_full_streaming_session(self):
        """Test a complete streaming session"""
        stream = StringIO()
        formatter = StreamJSONFormatter(stream=stream)

        # Simulate streaming session
        formatter.stream_start("response")
        formatter.stream_chunk({"content": "Hello"})
        formatter.stream_chunk({"content": " world"})
        formatter.stream_end("response", {"total_chunks": 2})

        # Parse all lines
        stream.seek(0)
        lines = stream.read().strip().split("\n")
        assert len(lines) == 4

        events = [json.loads(line) for line in lines]
        assert events[0]["type"] == "stream_start"
        assert events[1]["type"] == "chunk"
        assert events[2]["type"] == "chunk"
        assert events[3]["type"] == "stream_end"


class TestCreateFormatter:
    """Test create_formatter factory function"""

    def test_create_text_formatter(self):
        """Test creating text formatter"""
        formatter = create_formatter(OutputFormat.TEXT)
        assert isinstance(formatter, TextFormatter)

    def test_create_json_formatter(self):
        """Test creating JSON formatter"""
        formatter = create_formatter(OutputFormat.JSON)
        assert isinstance(formatter, JSONFormatter)

    def test_create_stream_json_formatter(self):
        """Test creating stream JSON formatter"""
        formatter = create_formatter(OutputFormat.STREAM_JSON)
        assert isinstance(formatter, StreamJSONFormatter)

    def test_create_json_formatter_with_options(self):
        """Test creating JSON formatter with options"""
        stream = StringIO()
        formatter = create_formatter(OutputFormat.JSON, stream=stream, pretty=True)

        assert isinstance(formatter, JSONFormatter)
        assert formatter.stream is stream
        assert formatter.pretty is True

    def test_create_invalid_format(self):
        """Test creating formatter with invalid format"""
        with pytest.raises(ValueError):
            create_formatter("invalid_format")
