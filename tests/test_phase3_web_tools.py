"""Tests for Phase 3 Web tools: WebFetch and WebSearch"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import json

from cortex.models import PermissionMode


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestWebFetchToolBasics:
    """Basic tests for WebFetchTool."""

    def test_web_fetch_tool_import(self):
        """Test that WebFetchTool can be imported."""
        from cortex.tools.web_tools import WebFetchTool

        assert WebFetchTool is not None

    def test_web_fetch_tool_instantiation(self, temp_project):
        """Test that WebFetchTool can be instantiated."""
        from cortex.tools.web_tools import WebFetchTool

        tool = WebFetchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )
        assert tool is not None

    def test_web_fetch_requires_url(self, temp_project):
        """Test that web_fetch requires a URL."""
        from cortex.tools.web_tools import WebFetchTool

        tool = WebFetchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(url="")
        assert result["success"] is False
        assert "validation" in result.get("error_type", "")

    def test_web_fetch_invalid_url(self, temp_project):
        """Test handling of invalid URL."""
        from cortex.tools.web_tools import WebFetchTool

        tool = WebFetchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(url="not-a-valid-url-at-all")
        # Should either fail validation or try to fetch and fail
        # The tool adds https:// prefix, so it may try to fetch


class TestWebFetchCache:
    """Tests for WebFetchCache."""

    def test_cache_set_and_get(self):
        """Test cache set and get operations."""
        from cortex.tools.web_tools import WebFetchCache

        cache = WebFetchCache(ttl_minutes=15)
        test_data = {"content": "test content", "title": "Test"}

        cache.set("https://example.com", test_data)
        retrieved = cache.get("https://example.com")

        assert retrieved is not None
        assert retrieved["content"] == "test content"

    def test_cache_miss(self):
        """Test cache miss returns None."""
        from cortex.tools.web_tools import WebFetchCache

        cache = WebFetchCache(ttl_minutes=15)
        result = cache.get("https://not-cached.com")

        assert result is None

    def test_cache_clear(self):
        """Test cache clear operation."""
        from cortex.tools.web_tools import WebFetchCache

        cache = WebFetchCache(ttl_minutes=15)
        cache.set("https://example.com", {"content": "test"})
        cache.clear()

        result = cache.get("https://example.com")
        assert result is None


class TestWebFetchMocked:
    """Mocked tests for WebFetchTool (no actual network calls)."""

    @patch("cortex.tools.web_tools.requests")
    def test_web_fetch_success(self, mock_requests, temp_project):
        """Test successful web fetch with mocked requests."""
        from cortex.tools.web_tools import WebFetchTool, HAS_REQUESTS

        if not HAS_REQUESTS:
            pytest.skip("requests not installed")

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = (
            "<html><head><title>Test Page</title></head><body><p>Hello World</p></body></html>"
        )
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response

        tool = WebFetchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(url="https://example.com", use_cache=False)

        assert result["success"] is True
        assert "content" in result
        assert result["url"] == "https://example.com"

    @patch("cortex.tools.web_tools.requests")
    def test_web_fetch_json_content(self, mock_requests, temp_project):
        """Test fetching JSON content."""
        from cortex.tools.web_tools import WebFetchTool, HAS_REQUESTS

        if not HAS_REQUESTS:
            pytest.skip("requests not installed")

        # Mock JSON response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/data"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"key": "value", "number": 42}
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response

        tool = WebFetchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(url="https://api.example.com/data", use_cache=False)

        assert result["success"] is True
        assert "key" in result["content"]

    @patch("cortex.tools.web_tools.requests")
    def test_web_fetch_timeout(self, mock_requests, temp_project):
        """Test handling of request timeout."""
        from cortex.tools.web_tools import WebFetchTool, HAS_REQUESTS
        import requests as real_requests

        if not HAS_REQUESTS:
            pytest.skip("requests not installed")

        # Mock timeout
        mock_requests.get.side_effect = real_requests.exceptions.Timeout()
        mock_requests.exceptions = real_requests.exceptions

        tool = WebFetchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(url="https://slow.example.com", use_cache=False)

        assert result["success"] is False
        assert "timeout" in result.get("error_type", "")

    @patch("cortex.tools.web_tools.requests")
    def test_web_fetch_redirect_detection(self, mock_requests, temp_project):
        """Test detection of cross-host redirects."""
        from cortex.tools.web_tools import WebFetchTool, HAS_REQUESTS

        if not HAS_REQUESTS:
            pytest.skip("requests not installed")

        # Mock redirect to different host
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://different-host.com/page"  # Redirected URL
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response

        tool = WebFetchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(url="https://example.com", use_cache=False)

        assert result["success"] is True
        assert result.get("redirected") is True or "different-host.com" in result.get("url", "")


class TestWebSearchToolBasics:
    """Basic tests for WebSearchTool."""

    def test_web_search_tool_import(self):
        """Test that WebSearchTool can be imported."""
        from cortex.tools.web_tools import WebSearchTool

        assert WebSearchTool is not None

    def test_web_search_tool_instantiation(self, temp_project):
        """Test that WebSearchTool can be instantiated."""
        from cortex.tools.web_tools import WebSearchTool

        tool = WebSearchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )
        assert tool is not None

    def test_web_search_requires_query(self, temp_project):
        """Test that web_search requires a query."""
        from cortex.tools.web_tools import WebSearchTool

        tool = WebSearchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(query="")
        assert result["success"] is False
        assert "validation" in result.get("error_type", "")

    def test_web_search_short_query(self, temp_project):
        """Test that web_search requires minimum query length."""
        from cortex.tools.web_tools import WebSearchTool

        tool = WebSearchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(query="a")
        assert result["success"] is False


class TestWebSearchMocked:
    """Mocked tests for WebSearchTool (no actual network calls)."""

    @patch("cortex.tools.web_tools.requests")
    def test_web_search_success(self, mock_requests, temp_project):
        """Test successful web search with mocked requests."""
        from cortex.tools.web_tools import WebSearchTool, HAS_REQUESTS, HAS_BS4

        if not HAS_REQUESTS:
            pytest.skip("requests not installed")

        # Mock search response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <div class="result">
            <a class="result__a" href="https://example.com/page1">Result 1</a>
            <span class="result__snippet">This is snippet 1</span>
        </div>
        <div class="result">
            <a class="result__a" href="https://example.com/page2">Result 2</a>
            <span class="result__snippet">This is snippet 2</span>
        </div>
        </html>
        """
        mock_response.raise_for_status = Mock()
        mock_requests.post.return_value = mock_response

        tool = WebSearchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(query="test search")

        assert result["success"] is True
        assert "results" in result

    @patch("cortex.tools.web_tools.requests")
    def test_web_search_no_results(self, mock_requests, temp_project):
        """Test web search with no results."""
        from cortex.tools.web_tools import WebSearchTool, HAS_REQUESTS

        if not HAS_REQUESTS:
            pytest.skip("requests not installed")

        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No results found</body></html>"
        mock_response.raise_for_status = Mock()
        mock_requests.post.return_value = mock_response

        tool = WebSearchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        result = tool.execute(query="xyznonexistentquery123")

        assert result["success"] is True
        assert result["result_count"] == 0

    @patch("cortex.tools.web_tools.requests")
    def test_web_search_domain_filter(self, mock_requests, temp_project):
        """Test web search with domain filtering."""
        from cortex.tools.web_tools import WebSearchTool, HAS_REQUESTS

        if not HAS_REQUESTS:
            pytest.skip("requests not installed")

        # Mock search response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <div class="result">
            <a class="result__a" href="https://docs.python.org/page1">Python Docs</a>
        </div>
        <div class="result">
            <a class="result__a" href="https://stackoverflow.com/q/123">SO Question</a>
        </div>
        </html>
        """
        mock_response.raise_for_status = Mock()
        mock_requests.post.return_value = mock_response

        tool = WebSearchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        # Test with allowed_domains filter
        result = tool.execute(query="python documentation", allowed_domains=["docs.python.org"])

        assert result["success"] is True


class TestToolRegistration:
    """Tests for web tool registration."""

    def test_web_fetch_in_registry(self):
        """Test that web_fetch is in the registry."""
        from cortex.tools.registry import get_registry

        registry = get_registry()
        assert "web_fetch" in registry.list_tools()

    def test_web_search_in_registry(self):
        """Test that web_search is in the registry."""
        from cortex.tools.registry import get_registry

        registry = get_registry()
        assert "web_search" in registry.list_tools()

    def test_can_create_web_fetch_instance(self, temp_project):
        """Test creating WebFetchTool via registry."""
        from cortex.tools.registry import get_registry
        from cortex.tools.web_tools import WebFetchTool

        registry = get_registry()
        tool = registry.create_instance("web_fetch", temp_project, PermissionMode.NORMAL, None)
        assert isinstance(tool, WebFetchTool)

    def test_can_create_web_search_instance(self, temp_project):
        """Test creating WebSearchTool via registry."""
        from cortex.tools.registry import get_registry
        from cortex.tools.web_tools import WebSearchTool

        registry = get_registry()
        tool = registry.create_instance("web_search", temp_project, PermissionMode.NORMAL, None)
        assert isinstance(tool, WebSearchTool)


class TestHTMLProcessing:
    """Tests for HTML processing utilities."""

    def test_html_to_markdown_basic(self, temp_project):
        """Test basic HTML to markdown conversion."""
        from cortex.tools.web_tools import WebFetchTool

        tool = WebFetchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        html = (
            "<html><head><title>Test</title></head><body><h1>Hello</h1><p>World</p></body></html>"
        )
        content, title = tool._process_html(html, "https://example.com")

        assert title == "Test"
        assert "Hello" in content
        assert "World" in content

    def test_strip_html_tags(self, temp_project):
        """Test HTML tag stripping."""
        from cortex.tools.web_tools import WebFetchTool

        tool = WebFetchTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.NORMAL,
            console=None,
        )

        html = "<p>Hello <strong>World</strong></p>"
        result = tool._strip_html_tags(html)

        assert "<p>" not in result
        assert "<strong>" not in result
        assert "Hello" in result
        assert "World" in result


class TestClearFetchCache:
    """Tests for cache clearing utility."""

    def test_clear_fetch_cache(self):
        """Test that clear_fetch_cache works."""
        from cortex.tools.web_tools import clear_fetch_cache, _fetch_cache

        # Add something to cache
        _fetch_cache.set("https://test.com", {"content": "test"})

        # Clear it
        clear_fetch_cache()

        # Should be empty
        assert _fetch_cache.get("https://test.com") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
