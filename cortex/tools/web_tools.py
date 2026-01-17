"""Web tools for fetching and searching web content"""

import re
import logging
import hashlib
import html
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
from urllib.parse import urlparse, urljoin
import json

from .base import Tool
from ..utils.errors import create_error_response, create_success_response, ErrorType

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    BeautifulSoup = None

try:
    import html2text

    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False
    html2text = None

try:
    from ddgs import DDGS

    HAS_DUCKDUCKGO_SEARCH = True
except ImportError:
    HAS_DUCKDUCKGO_SEARCH = False
    DDGS = None


class WebFetchCache:
    """Simple in-memory cache for web fetches with TTL."""

    def __init__(self, ttl_minutes: int = 15):
        self.ttl = timedelta(minutes=ttl_minutes)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _get_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached content if not expired."""
        key = self._get_key(url)
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() - entry["timestamp"] < self.ttl:
                return entry["data"]
            else:
                del self._cache[key]
        return None

    def set(self, url: str, data: Dict[str, Any]) -> None:
        """Cache content with timestamp."""
        key = self._get_key(url)
        self._cache[key] = {"data": data, "timestamp": datetime.now()}

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


# Global cache instance
_fetch_cache = WebFetchCache()


class WebFetchTool(Tool):
    """
    Fetch and process web content.

    Features:
    - Fetch URL content
    - Convert HTML to markdown
    - Process with optional prompt
    - 15-minute cache for repeated requests
    - Handle redirects
    """

    timeout_category = "network"
    default_timeout = 30

    # User agent to avoid blocks
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def execute(
        self,
        url: str,
        prompt: str = "",
        use_cache: bool = True,
        max_content_length: int = 50000,
    ) -> Dict[str, Any]:
        """
        Fetch content from a URL and optionally process it.

        Args:
            url: The URL to fetch
            prompt: Optional prompt describing what to extract/analyze
            use_cache: Use cached content if available (default: True)
            max_content_length: Maximum content length to return (default: 50000)

        Returns:
            Standardized response with fetched content
        """
        # Check dependencies
        if not HAS_REQUESTS:
            return create_error_response(
                "requests library not installed. Run: pip install requests",
                ErrorType.EXECUTION,
                {"missing_dependency": "requests"},
            )

        # Validate URL
        if not url:
            return create_error_response("URL is required", ErrorType.VALIDATION, {"url": url})

        # Ensure URL has scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed = urlparse(url)
        if not parsed.netloc:
            return create_error_response(f"Invalid URL: {url}", ErrorType.VALIDATION, {"url": url})

        if self.console:
            self.console.print(f"[cyan]Fetching:[/cyan] {url}")

        # Check cache
        if use_cache:
            cached = _fetch_cache.get(url)
            if cached:
                return create_success_response(
                    {
                        "url": url,
                        "content": cached["content"][:max_content_length],
                        "title": cached.get("title", ""),
                        "cached": True,
                        "content_type": cached.get("content_type", ""),
                    }
                )

        try:
            # Fetch URL
            response = requests.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.get_timeout(),
                allow_redirects=True,
            )

            # Check for redirect to different host
            final_url = response.url
            if urlparse(final_url).netloc != parsed.netloc:
                return create_success_response(
                    {
                        "url": url,
                        "redirect_url": final_url,
                        "redirected": True,
                        "message": f"Redirected to different host: {final_url}. Make a new request with this URL.",
                    }
                )

            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()

            # Handle different content types
            if "application/json" in content_type:
                try:
                    json_data = response.json()
                    content = json.dumps(json_data, indent=2)
                    title = "JSON Response"
                except json.JSONDecodeError:
                    content = response.text
                    title = "Response"
            elif "text/html" in content_type:
                content, title = self._process_html(response.text, url)
            elif "text/plain" in content_type or "text/markdown" in content_type:
                content = response.text
                title = parsed.path.split("/")[-1] or "Text Content"
            else:
                # For other types, try to get text
                try:
                    content = response.text
                    title = parsed.path.split("/")[-1] or "Content"
                except (UnicodeDecodeError, AttributeError):
                    return create_error_response(
                        f"Cannot process content type: {content_type}",
                        ErrorType.VALIDATION,
                        {"url": url, "content_type": content_type},
                    )

            # Truncate if needed
            truncated = len(content) > max_content_length
            if truncated:
                content = content[:max_content_length] + "\n\n[Content truncated...]"

            # Cache the result
            cache_data = {
                "content": content,
                "title": title,
                "content_type": content_type,
            }
            _fetch_cache.set(url, cache_data)

            # Removed console output for fetched content to reduce clutter

            result = {
                "url": final_url,
                "content": content,
                "title": title,
                "content_type": content_type,
                "truncated": truncated,
                "cached": False,
            }

            # Add prompt context if provided
            if prompt:
                result["prompt"] = prompt
                result["instruction"] = f"Analyze the content above based on: {prompt}"

            return create_success_response(result)

        except requests.exceptions.Timeout:
            return create_error_response(
                f"Request timed out after {self.get_timeout()} seconds",
                ErrorType.TIMEOUT,
                {"url": url},
                retryable=True,
            )
        except requests.exceptions.TooManyRedirects:
            return create_error_response("Too many redirects", ErrorType.EXECUTION, {"url": url})
        except requests.exceptions.SSLError as e:
            return create_error_response(f"SSL error: {e}", ErrorType.SECURITY, {"url": url})
        except requests.exceptions.RequestException as e:
            return create_error_response(
                f"Request failed: {e}", ErrorType.NETWORK, {"url": url}, retryable=True
            )
        except Exception as e:
            logger.exception(f"WebFetch error for {url}")
            return create_error_response(
                f"Failed to fetch URL: {e}", ErrorType.EXECUTION, {"url": url}
            )

    def _process_html(self, html: str, base_url: str) -> tuple:
        """
        Process HTML content to markdown.

        Args:
            html: Raw HTML content
            base_url: Base URL for resolving relative links

        Returns:
            Tuple of (markdown_content, title)
        """
        title = "Web Page"

        if HAS_BS4:
            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title_tag = soup.find("title")
            if title_tag:
                title = html.unescape(title_tag.get_text(strip=True))

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()

            # Try html2text for better markdown conversion
            if HAS_HTML2TEXT:
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.ignore_images = True
                h.body_width = 0  # No wrapping
                h.ignore_emphasis = False
                content = h.handle(str(soup))
            else:
                # Fallback: extract text with basic formatting
                content = self._basic_html_to_text(soup)
        else:
            # No BeautifulSoup - basic text extraction
            content = self._strip_html_tags(html)
            # Try to extract title
            title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()

        # Clean up content
        content = self._clean_content(content)

        return content, title

    def _basic_html_to_text(self, soup) -> str:
        """Basic HTML to text conversion using BeautifulSoup."""
        lines = []

        for element in soup.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "code"]
        ):
            tag = element.name
            text = element.get_text(strip=True)

            if not text:
                continue

            if tag.startswith("h"):
                level = int(tag[1])
                lines.append(f"{'#' * level} {text}\n")
            elif tag == "li":
                lines.append(f"- {text}")
            elif tag in ("pre", "code"):
                lines.append(f"```\n{text}\n```")
            else:
                lines.append(text)

        return "\n\n".join(lines)

    def _strip_html_tags(self, html: str) -> str:
        """Strip HTML tags for basic text extraction."""
        # Remove script/style content
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Remove tags
        html = re.sub(r"<[^>]+>", " ", html)
        # Decode entities
        html = html.replace("&nbsp;", " ").replace("&amp;", "&")
        html = html.replace("&lt;", "<").replace("&gt;", ">")
        return html

    def _clean_content(self, content: str) -> str:
        """Clean up extracted content."""
        # Remove excessive whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" {2,}", " ", content)
        # Remove empty lines at start/end
        content = content.strip()
        return content


class WebSearchTool(Tool):
    """
    Search the web for information.

    Uses DuckDuckGo Search API (no API key required).
    """

    timeout_category = "network"
    default_timeout = 30

    def execute(
        self,
        query: str,
        max_results: int = 10,
        allowed_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Search the web for information.

        Args:
            query: Search query
            max_results: Maximum number of results (default: 10)
            allowed_domains: Only include results from these domains
            blocked_domains: Exclude results from these domains

        Returns:
            Standardized response with search results
        """
        if not HAS_DUCKDUCKGO_SEARCH:
            return create_error_response(
                "duckduckgo-search library not installed. Run: pip install duckduckgo-search",
                ErrorType.EXECUTION,
                {"missing_dependency": "duckduckgo-search"},
            )

        if not query or len(query.strip()) < 2:
            return create_error_response(
                "Search query must be at least 2 characters", ErrorType.VALIDATION, {"query": query}
            )

        if self.console:
            self.console.print(f"[cyan]Searching:[/cyan] {query}")

        try:
            # Use DDGS API for search
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            # Convert results to expected format
            formatted_results = []
            for result in results:
                url = result.get("href", "")
                title = html.unescape(result.get("title", ""))
                snippet = html.unescape(result.get("body", ""))

                # Filter by domain if specified
                if url:
                    domain = urlparse(url).netloc.lower()

                    if allowed_domains:
                        if not any(d.lower() in domain for d in allowed_domains):
                            continue

                    if blocked_domains:
                        if any(d.lower() in domain for d in blocked_domains):
                            continue

                    formatted_results.append(
                        {
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                        }
                    )

            if not formatted_results:
                return create_success_response(
                    {
                        "query": query,
                        "results": [],
                        "result_count": 0,
                        "message": "No results found",
                    }
                )

            if self.console:
                self.console.print(f"[green]Found {len(formatted_results)} results[/green]")
                for r in formatted_results[:3]:
                    title_display = html.unescape(r['title'][:50])
                    self.console.print(f"  [dim]- {title_display}...[/dim]")

            return create_success_response(
                {
                    "query": query,
                    "results": formatted_results,
                    "result_count": len(formatted_results),
                }
            )

        except Exception as e:
            logger.exception(f"WebSearch error for query: {query}")
            return create_error_response(
                f"Search failed: {e}", ErrorType.EXECUTION, {"query": query}
            )




def clear_fetch_cache() -> None:
    """Clear the web fetch cache."""
    _fetch_cache.clear()
