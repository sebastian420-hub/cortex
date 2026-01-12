# Phase 4: Extended Features Specifications

## Overview

This document contains specifications for extended features that enhance Cortex with web capabilities, multimodal support, and the Model Context Protocol (MCP).

---

## 4.1 Web Search and Fetch

### Purpose

Allow the agent to search the web and fetch content from URLs to answer questions requiring up-to-date information.

### Architecture

```
cortex/tools/
├── web_tools.py          # Web search and fetch tools
└── web/
    ├── __init__.py
    ├── search.py         # Search engine integration
    ├── fetch.py          # URL fetching and processing
    ├── cache.py          # Response caching
    └── sanitizer.py      # HTML to markdown conversion
```

### Web Search Tool

```python
# cortex/tools/web_tools.py

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from .base import Tool


@dataclass
class SearchResult:
    """A single search result"""
    title: str
    url: str
    snippet: str
    source: str


class WebSearchTool(Tool):
    """
    Search the web for information.

    Uses configurable search backends:
    - DuckDuckGo (default, no API key required)
    - Google Custom Search (requires API key)
    - Brave Search (requires API key)
    """

    name = "web_search"
    description = "Search the web for up-to-date information"

    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
                "minLength": 2
            },
            "allowed_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Only include results from these domains"
            },
            "blocked_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exclude results from these domains"
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 10,
                "description": "Maximum number of results to return"
            }
        },
        "required": ["query"]
    }

    def __init__(
        self,
        *args,
        search_backend: str = "duckduckgo",
        api_key: Optional[str] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.search_backend = search_backend
        self.api_key = api_key
        self._searcher = self._create_searcher()

    def _create_searcher(self):
        """Create search backend"""
        from .web.search import DuckDuckGoSearcher, GoogleSearcher, BraveSearcher

        searchers = {
            "duckduckgo": DuckDuckGoSearcher,
            "google": lambda: GoogleSearcher(self.api_key),
            "brave": lambda: BraveSearcher(self.api_key)
        }

        factory = searchers.get(self.search_backend, DuckDuckGoSearcher)
        return factory() if callable(factory) else factory

    def execute(
        self,
        query: str,
        allowed_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """Execute web search"""
        try:
            results = self._searcher.search(
                query,
                max_results=max_results
            )

            # Filter by domain
            if allowed_domains:
                results = [
                    r for r in results
                    if any(d in r.url for d in allowed_domains)
                ]

            if blocked_domains:
                results = [
                    r for r in results
                    if not any(d in r.url for d in blocked_domains)
                ]

            return {
                "success": True,
                "query": query,
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet
                    }
                    for r in results
                ],
                "result_count": len(results)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "execution",
                "retryable": True
            }
```

### Search Backends

```python
# cortex/tools/web/search.py

from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass
import urllib.parse


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = ""


class SearchBackend(ABC):
    """Base class for search backends"""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        pass


class DuckDuckGoSearcher(SearchBackend):
    """DuckDuckGo search (no API key required)"""

    def __init__(self):
        try:
            from duckduckgo_search import DDGS
            self.ddgs = DDGS()
        except ImportError:
            raise ImportError(
                "duckduckgo-search package required. "
                "Install with: pip install duckduckgo-search"
            )

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        results = self.ddgs.text(query, max_results=max_results)

        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
                source="duckduckgo"
            )
            for r in results
        ]


class GoogleSearcher(SearchBackend):
    """Google Custom Search (requires API key)"""

    def __init__(self, api_key: str, cx: Optional[str] = None):
        self.api_key = api_key
        self.cx = cx or os.environ.get("GOOGLE_SEARCH_CX")

        if not self.api_key or not self.cx:
            raise ValueError(
                "Google Custom Search requires API key and CX ID. "
                "Set GOOGLE_API_KEY and GOOGLE_SEARCH_CX environment variables."
            )

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        import requests

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": min(max_results, 10)
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source="google"
            )
            for item in data.get("items", [])
        ]


class BraveSearcher(SearchBackend):
    """Brave Search API"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        import requests

        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"X-Subscription-Token": self.api_key}
        params = {"q": query, "count": max_results}

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                source="brave"
            ))

        return results[:max_results]
```

### Web Fetch Tool

```python
# cortex/tools/web_tools.py (continued)

class WebFetchTool(Tool):
    """
    Fetch and process content from a URL.

    Features:
    - HTML to markdown conversion
    - Content summarization
    - Response caching
    - Redirect handling
    """

    name = "web_fetch"
    description = "Fetch content from a URL and process it"

    schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "format": "uri",
                "description": "The URL to fetch"
            },
            "prompt": {
                "type": "string",
                "description": "What information to extract from the page"
            },
            "include_links": {
                "type": "boolean",
                "default": False,
                "description": "Include links in the extracted content"
            }
        },
        "required": ["url", "prompt"]
    }

    def __init__(
        self,
        *args,
        cache_ttl_minutes: int = 15,
        max_content_length: int = 50000,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.cache_ttl_minutes = cache_ttl_minutes
        self.max_content_length = max_content_length
        self._cache: Dict[str, Tuple[str, datetime]] = {}

    def execute(
        self,
        url: str,
        prompt: str,
        include_links: bool = False
    ) -> Dict[str, Any]:
        """Fetch and process URL content"""
        from .web.fetch import fetch_url, convert_html_to_markdown
        from .web.cache import check_cache, update_cache

        try:
            # Normalize URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # Check cache
            cached = self._get_cached(url)
            if cached:
                content = cached
            else:
                # Fetch URL
                response = fetch_url(url, follow_redirects=True)

                # Handle redirects to different host
                if response.get("redirected_to_different_host"):
                    return {
                        "success": True,
                        "redirect": True,
                        "redirect_url": response["final_url"],
                        "message": f"URL redirected to different host. "
                                   f"Fetch the redirect URL: {response['final_url']}"
                    }

                # Convert HTML to markdown
                html_content = response["content"]
                content = convert_html_to_markdown(
                    html_content,
                    include_links=include_links
                )

                # Truncate if too long
                if len(content) > self.max_content_length:
                    content = content[:self.max_content_length] + "\n\n[Content truncated...]"

                # Cache the result
                self._set_cached(url, content)

            # Process with prompt if provided
            if prompt:
                # Use a lightweight model to extract information
                extracted = self._process_with_prompt(content, prompt)
                return {
                    "success": True,
                    "url": url,
                    "extracted_content": extracted,
                    "prompt": prompt
                }

            return {
                "success": True,
                "url": url,
                "content": content,
                "content_length": len(content)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "execution",
                "retryable": True
            }

    def _get_cached(self, url: str) -> Optional[str]:
        """Get cached content"""
        if url in self._cache:
            content, timestamp = self._cache[url]
            age_minutes = (datetime.now() - timestamp).total_seconds() / 60
            if age_minutes < self.cache_ttl_minutes:
                return content
            else:
                del self._cache[url]
        return None

    def _set_cached(self, url: str, content: str) -> None:
        """Cache content"""
        self._cache[url] = (content, datetime.now())

    def _process_with_prompt(self, content: str, prompt: str) -> str:
        """Process content with the given prompt"""
        # Use parent agent's provider if available
        if hasattr(self, 'parent_agent') and self.parent_agent:
            response = self.parent_agent.provider.chat(
                model=self.parent_agent.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts "
                                   "information from web content. Be concise."
                    },
                    {
                        "role": "user",
                        "content": f"Based on the following web content, {prompt}\n\n"
                                   f"Content:\n{content[:10000]}"
                    }
                ],
                tools=[]
            )
            return response["message"]["content"]

        # Fallback: return raw content with prompt note
        return f"[Processing prompt: {prompt}]\n\n{content[:5000]}"
```

### URL Fetching and HTML Processing

```python
# cortex/tools/web/fetch.py

import requests
from typing import Dict, Any, Optional
from urllib.parse import urlparse


def fetch_url(
    url: str,
    timeout: int = 30,
    follow_redirects: bool = True,
    max_redirects: int = 5
) -> Dict[str, Any]:
    """
    Fetch content from a URL.

    Returns:
        Dict with 'content', 'status_code', 'content_type', and redirect info
    """
    headers = {
        "User-Agent": "Cortex/1.0 (AI Assistant)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    original_host = urlparse(url).netloc

    response = requests.get(
        url,
        headers=headers,
        timeout=timeout,
        allow_redirects=follow_redirects
    )

    final_host = urlparse(response.url).netloc

    result = {
        "content": response.text,
        "status_code": response.status_code,
        "content_type": response.headers.get("Content-Type", ""),
        "final_url": response.url,
        "redirected": response.url != url,
        "redirected_to_different_host": final_host != original_host
    }

    return result


def convert_html_to_markdown(
    html: str,
    include_links: bool = True,
    include_images: bool = False
) -> str:
    """
    Convert HTML to clean markdown.

    Uses html2text library for conversion.
    """
    try:
        import html2text

        converter = html2text.HTML2Text()
        converter.ignore_links = not include_links
        converter.ignore_images = not include_images
        converter.ignore_emphasis = False
        converter.body_width = 0  # No line wrapping
        converter.unicode_snob = True
        converter.skip_internal_links = True

        markdown = converter.handle(html)

        # Clean up excessive whitespace
        lines = markdown.split('\n')
        cleaned_lines = []
        blank_count = 0

        for line in lines:
            if line.strip():
                cleaned_lines.append(line)
                blank_count = 0
            else:
                blank_count += 1
                if blank_count <= 2:
                    cleaned_lines.append('')

        return '\n'.join(cleaned_lines).strip()

    except ImportError:
        # Fallback: basic HTML stripping
        from html.parser import HTMLParser

        class HTMLStripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []

            def handle_data(self, data):
                self.text.append(data)

        stripper = HTMLStripper()
        stripper.feed(html)
        return ' '.join(stripper.text)
```

---

## 4.2 Multimodal Support

### Purpose

Enable the agent to process images (screenshots, diagrams), PDFs, and Jupyter notebooks.

### Architecture

```
cortex/tools/
├── multimodal_tools.py   # Main multimodal tools
└── multimodal/
    ├── __init__.py
    ├── image.py          # Image processing
    ├── pdf.py            # PDF processing
    └── notebook.py       # Jupyter notebook processing
```

### Image Tool

```python
# cortex/tools/multimodal_tools.py

from typing import Dict, Any, Optional, List
from pathlib import Path
import base64
from .base import Tool


class ReadImageTool(Tool):
    """
    Read and analyze images.

    Supports:
    - PNG, JPG, GIF, WebP formats
    - Screenshots, diagrams, charts
    - Sending image to vision model for analysis
    """

    name = "read_image"
    description = "Read and analyze an image file"

    schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the image file"
            },
            "prompt": {
                "type": "string",
                "description": "What to analyze in the image",
                "default": "Describe this image in detail"
            }
        },
        "required": ["file_path"]
    }

    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
    MAX_IMAGE_SIZE_MB = 20

    def execute(
        self,
        file_path: str,
        prompt: str = "Describe this image in detail"
    ) -> Dict[str, Any]:
        """Read and analyze an image"""
        from .multimodal.image import load_image, encode_image_base64

        path = Path(file_path)

        # Validate file exists
        if not path.exists():
            return {
                "success": False,
                "error": f"Image file not found: {file_path}",
                "error_type": "not_found",
                "retryable": False
            }

        # Validate format
        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            return {
                "success": False,
                "error": f"Unsupported image format: {path.suffix}. "
                         f"Supported: {', '.join(self.SUPPORTED_FORMATS)}",
                "error_type": "validation",
                "retryable": False
            }

        # Check file size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.MAX_IMAGE_SIZE_MB:
            return {
                "success": False,
                "error": f"Image too large: {size_mb:.1f}MB (max {self.MAX_IMAGE_SIZE_MB}MB)",
                "error_type": "validation",
                "retryable": False
            }

        try:
            # Load and encode image
            image_data = load_image(path)
            base64_image = encode_image_base64(image_data, path.suffix)

            # Get image metadata
            metadata = self._get_image_metadata(path)

            # Send to vision model for analysis
            if hasattr(self, 'parent_agent') and self.parent_agent:
                analysis = self._analyze_with_vision(base64_image, prompt, path.suffix)
            else:
                analysis = "[Vision model not available for analysis]"

            return {
                "success": True,
                "file_path": str(path),
                "format": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
                "metadata": metadata,
                "analysis": analysis
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "execution",
                "retryable": False
            }

    def _get_image_metadata(self, path: Path) -> Dict[str, Any]:
        """Get image metadata"""
        try:
            from PIL import Image

            with Image.open(path) as img:
                return {
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "format": img.format
                }
        except ImportError:
            return {"note": "PIL not installed, metadata unavailable"}

    def _analyze_with_vision(
        self,
        base64_image: str,
        prompt: str,
        suffix: str
    ) -> str:
        """Analyze image using vision model"""
        # Map suffix to MIME type
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(suffix.lower(), 'image/png')

        # Construct vision API message
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": base64_image
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        # Use provider's vision capability
        response = self.parent_agent.provider.chat(
            model=self.parent_agent.model,
            messages=messages,
            tools=[]
        )

        return response["message"]["content"]
```

### PDF Tool

```python
# cortex/tools/multimodal_tools.py (continued)

class ReadPdfTool(Tool):
    """
    Read and analyze PDF documents.

    Features:
    - Text extraction
    - Page-by-page processing
    - Table extraction (if available)
    - Image extraction from PDF
    """

    name = "read_pdf"
    description = "Read and analyze a PDF document"

    schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the PDF file"
            },
            "pages": {
                "type": "string",
                "description": "Pages to read (e.g., '1-5', '1,3,5', 'all')",
                "default": "all"
            },
            "extract_images": {
                "type": "boolean",
                "default": False,
                "description": "Extract images from the PDF"
            }
        },
        "required": ["file_path"]
    }

    MAX_PAGES = 100

    def execute(
        self,
        file_path: str,
        pages: str = "all",
        extract_images: bool = False
    ) -> Dict[str, Any]:
        """Read and analyze a PDF"""
        from .multimodal.pdf import extract_text, extract_pages, parse_page_range

        path = Path(file_path)

        if not path.exists():
            return {
                "success": False,
                "error": f"PDF file not found: {file_path}",
                "error_type": "not_found"
            }

        if path.suffix.lower() != '.pdf':
            return {
                "success": False,
                "error": f"Not a PDF file: {path.suffix}",
                "error_type": "validation"
            }

        try:
            # Parse page range
            page_numbers = parse_page_range(pages, max_pages=self.MAX_PAGES)

            # Extract text
            extracted = extract_pages(path, page_numbers)

            # Format output
            content_parts = []
            for page_num, page_content in extracted.items():
                content_parts.append(f"--- Page {page_num} ---\n{page_content}")

            full_content = "\n\n".join(content_parts)

            result = {
                "success": True,
                "file_path": str(path),
                "total_pages": len(extracted),
                "pages_read": list(extracted.keys()),
                "content": full_content,
                "content_length": len(full_content)
            }

            # Extract images if requested
            if extract_images:
                from .multimodal.pdf import extract_images_from_pdf
                images = extract_images_from_pdf(path, page_numbers)
                result["images"] = [
                    {"page": img["page"], "size": img["size"]}
                    for img in images
                ]
                result["image_count"] = len(images)

            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "execution"
            }
```

### PDF Processing Module

```python
# cortex/tools/multimodal/pdf.py

from typing import Dict, List, Optional, Set
from pathlib import Path


def parse_page_range(pages: str, max_pages: int = 100) -> List[int]:
    """
    Parse page range string.

    Examples:
    - "all" -> all pages
    - "1-5" -> [1, 2, 3, 4, 5]
    - "1,3,5" -> [1, 3, 5]
    - "1-3,5,7-9" -> [1, 2, 3, 5, 7, 8, 9]
    """
    if pages.lower() == "all":
        return list(range(1, max_pages + 1))

    result: Set[int] = set()

    parts = pages.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = part.split('-', 1)
            start_num = int(start.strip())
            end_num = int(end.strip())
            result.update(range(start_num, min(end_num + 1, max_pages + 1)))
        else:
            page_num = int(part)
            if 1 <= page_num <= max_pages:
                result.add(page_num)

    return sorted(result)


def extract_pages(path: Path, page_numbers: List[int]) -> Dict[int, str]:
    """Extract text from specified pages"""
    try:
        import pymupdf  # PyMuPDF

        doc = pymupdf.open(path)
        result = {}

        for page_num in page_numbers:
            if 1 <= page_num <= len(doc):
                page = doc[page_num - 1]  # 0-indexed
                result[page_num] = page.get_text()

        doc.close()
        return result

    except ImportError:
        # Fallback to pdfplumber
        try:
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                result = {}
                for page_num in page_numbers:
                    if 1 <= page_num <= len(pdf.pages):
                        page = pdf.pages[page_num - 1]
                        result[page_num] = page.extract_text() or ""
                return result

        except ImportError:
            raise ImportError(
                "PDF processing requires PyMuPDF or pdfplumber. "
                "Install with: pip install pymupdf"
            )


def extract_images_from_pdf(
    path: Path,
    page_numbers: List[int]
) -> List[Dict[str, Any]]:
    """Extract images from PDF pages"""
    try:
        import pymupdf

        doc = pymupdf.open(path)
        images = []

        for page_num in page_numbers:
            if 1 <= page_num <= len(doc):
                page = doc[page_num - 1]
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)

                    images.append({
                        "page": page_num,
                        "index": img_index,
                        "size": len(base_image["image"]),
                        "format": base_image["ext"],
                        "width": base_image.get("width"),
                        "height": base_image.get("height")
                    })

        doc.close()
        return images

    except ImportError:
        return []
```

### Jupyter Notebook Tool

```python
# cortex/tools/multimodal_tools.py (continued)

class ReadNotebookTool(Tool):
    """
    Read and analyze Jupyter notebooks.

    Features:
    - Extract code cells and outputs
    - Extract markdown cells
    - View cell execution results
    - Extract embedded visualizations
    """

    name = "read_notebook"
    description = "Read and analyze a Jupyter notebook"

    schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the .ipynb file"
            },
            "include_outputs": {
                "type": "boolean",
                "default": True,
                "description": "Include cell outputs"
            },
            "cell_types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["code", "markdown", "raw"]
                },
                "default": ["code", "markdown"],
                "description": "Cell types to include"
            }
        },
        "required": ["file_path"]
    }

    def execute(
        self,
        file_path: str,
        include_outputs: bool = True,
        cell_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Read a Jupyter notebook"""
        import json

        path = Path(file_path)
        cell_types = cell_types or ["code", "markdown"]

        if not path.exists():
            return {
                "success": False,
                "error": f"Notebook not found: {file_path}",
                "error_type": "not_found"
            }

        if path.suffix.lower() != '.ipynb':
            return {
                "success": False,
                "error": f"Not a notebook file: {path.suffix}",
                "error_type": "validation"
            }

        try:
            with open(path, 'r', encoding='utf-8') as f:
                notebook = json.load(f)

            cells = notebook.get("cells", [])
            metadata = notebook.get("metadata", {})

            # Process cells
            processed_cells = []
            for idx, cell in enumerate(cells):
                cell_type = cell.get("cell_type", "")

                if cell_type not in cell_types:
                    continue

                source = "".join(cell.get("source", []))

                cell_data = {
                    "index": idx,
                    "type": cell_type,
                    "source": source
                }

                # Include outputs for code cells
                if include_outputs and cell_type == "code":
                    outputs = cell.get("outputs", [])
                    cell_data["outputs"] = self._process_outputs(outputs)
                    cell_data["execution_count"] = cell.get("execution_count")

                processed_cells.append(cell_data)

            # Format as readable text
            formatted = self._format_cells(processed_cells)

            return {
                "success": True,
                "file_path": str(path),
                "kernel": metadata.get("kernelspec", {}).get("display_name", "unknown"),
                "cell_count": len(cells),
                "processed_cells": len(processed_cells),
                "content": formatted,
                "cells": processed_cells
            }

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid notebook JSON: {e}",
                "error_type": "validation"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "execution"
            }

    def _process_outputs(self, outputs: List[Dict]) -> List[Dict]:
        """Process cell outputs"""
        processed = []

        for output in outputs:
            output_type = output.get("output_type", "")

            if output_type == "stream":
                processed.append({
                    "type": "text",
                    "name": output.get("name", "stdout"),
                    "text": "".join(output.get("text", []))
                })

            elif output_type == "execute_result":
                data = output.get("data", {})
                if "text/plain" in data:
                    processed.append({
                        "type": "result",
                        "text": "".join(data["text/plain"])
                    })

            elif output_type == "error":
                processed.append({
                    "type": "error",
                    "ename": output.get("ename", ""),
                    "evalue": output.get("evalue", ""),
                    "traceback": output.get("traceback", [])[:3]  # First 3 lines
                })

            elif output_type == "display_data":
                data = output.get("data", {})
                if "image/png" in data:
                    processed.append({
                        "type": "image",
                        "format": "png",
                        "note": "[Image output - base64 encoded]"
                    })
                elif "text/plain" in data:
                    processed.append({
                        "type": "display",
                        "text": "".join(data["text/plain"])
                    })

        return processed

    def _format_cells(self, cells: List[Dict]) -> str:
        """Format cells as readable text"""
        parts = []

        for cell in cells:
            cell_type = cell["type"]
            source = cell["source"]

            if cell_type == "markdown":
                parts.append(f"### Markdown Cell [{cell['index']}]\n{source}")

            elif cell_type == "code":
                exec_count = cell.get("execution_count", "?")
                parts.append(f"### Code Cell [{cell['index']}] (In [{exec_count}])")
                parts.append(f"```python\n{source}\n```")

                # Add outputs
                for output in cell.get("outputs", []):
                    if output["type"] == "text":
                        parts.append(f"Output ({output['name']}):\n{output['text']}")
                    elif output["type"] == "result":
                        parts.append(f"Result:\n{output['text']}")
                    elif output["type"] == "error":
                        parts.append(f"Error: {output['ename']}: {output['evalue']}")
                    elif output["type"] == "image":
                        parts.append("[Image output]")

        return "\n\n".join(parts)
```

---

## 4.3 Model Context Protocol (MCP)

### Purpose

Implement MCP to allow Cortex to connect with external tool servers and integrate with the broader AI tool ecosystem.

### What is MCP?

The Model Context Protocol (MCP) is a standardized protocol for:
- Connecting AI assistants to external tools
- Discovering available tools from servers
- Executing tools across process boundaries
- Sharing context between AI systems

### Architecture

```
cortex/mcp/
├── __init__.py
├── client.py           # MCP client implementation
├── server.py           # MCP server (expose Cortex as server)
├── transport.py        # Transport layer (stdio, http)
├── protocol.py         # Protocol message types
└── tools.py            # Tool wrapper for MCP tools
```

### MCP Client

```python
# cortex/mcp/client.py

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import json
import asyncio
import subprocess

from .protocol import (
    MCPRequest, MCPResponse, MCPError,
    InitializeRequest, ListToolsRequest, CallToolRequest
)


class TransportType(Enum):
    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


@dataclass
class MCPServer:
    """Configuration for an MCP server"""
    name: str
    command: List[str]  # Command to start server
    transport: TransportType = TransportType.STDIO
    env: Optional[Dict[str, str]] = None


@dataclass
class MCPTool:
    """A tool exposed by an MCP server"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str


class MCPClient:
    """
    Client for connecting to MCP servers.

    Features:
    - Connect to multiple MCP servers
    - Discover tools from servers
    - Execute tools via MCP protocol
    - Handle server lifecycle
    """

    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.connections: Dict[str, 'MCPConnection'] = {}
        self.tools: Dict[str, MCPTool] = {}

    async def add_server(self, server: MCPServer) -> None:
        """Add and connect to an MCP server"""
        self.servers[server.name] = server

        # Start connection
        connection = await self._connect(server)
        self.connections[server.name] = connection

        # Initialize
        await connection.initialize()

        # Discover tools
        tools = await connection.list_tools()
        for tool in tools:
            tool_key = f"{server.name}:{tool['name']}"
            self.tools[tool_key] = MCPTool(
                name=tool['name'],
                description=tool.get('description', ''),
                input_schema=tool.get('inputSchema', {}),
                server_name=server.name
            )

    async def _connect(self, server: MCPServer) -> 'MCPConnection':
        """Create connection to server"""
        if server.transport == TransportType.STDIO:
            return await StdioConnection.create(server)
        elif server.transport == TransportType.HTTP:
            return await HTTPConnection.create(server)
        else:
            raise ValueError(f"Unsupported transport: {server.transport}")

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on its MCP server"""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown MCP tool: {tool_name}")

        tool = self.tools[tool_name]
        connection = self.connections.get(tool.server_name)

        if not connection:
            raise ValueError(f"Not connected to server: {tool.server_name}")

        return await connection.call_tool(tool.name, arguments)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions in OpenAI format"""
        definitions = []

        for tool_key, tool in self.tools.items():
            definitions.append({
                "type": "function",
                "function": {
                    "name": tool_key.replace(':', '_'),  # Safe name
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            })

        return definitions

    async def disconnect_all(self) -> None:
        """Disconnect from all servers"""
        for name, connection in self.connections.items():
            await connection.close()

        self.connections.clear()
        self.tools.clear()


class MCPConnection:
    """Base class for MCP connections"""

    async def initialize(self) -> Dict[str, Any]:
        raise NotImplementedError

    async def list_tools(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class StdioConnection(MCPConnection):
    """MCP connection over stdio"""

    def __init__(self, process: asyncio.subprocess.Process):
        self.process = process
        self._request_id = 0

    @classmethod
    async def create(cls, server: MCPServer) -> 'StdioConnection':
        """Create stdio connection"""
        process = await asyncio.create_subprocess_exec(
            *server.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=server.env
        )
        return cls(process)

    async def _send_request(self, method: str, params: Dict = None) -> Dict:
        """Send request and wait for response"""
        self._request_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {}
        }

        # Send request
        request_bytes = (json.dumps(request) + '\n').encode()
        self.process.stdin.write(request_bytes)
        await self.process.stdin.drain()

        # Read response
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())

        if "error" in response:
            raise MCPError(
                response["error"].get("code", -1),
                response["error"].get("message", "Unknown error")
            )

        return response.get("result", {})

    async def initialize(self) -> Dict[str, Any]:
        """Initialize connection"""
        return await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "clientInfo": {
                "name": "Cortex",
                "version": "1.0.0"
            }
        })

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools"""
        result = await self._send_request("tools/list")
        return result.get("tools", [])

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool"""
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return result

    async def close(self) -> None:
        """Close connection"""
        self.process.terminate()
        await self.process.wait()
```

### MCP Tool Integration

```python
# cortex/mcp/tools.py

from typing import Dict, Any, Optional, List
from ..tools.base import Tool
from .client import MCPClient, MCPTool


class MCPToolWrapper(Tool):
    """
    Wrapper that exposes MCP tools as Cortex tools.

    This allows MCP tools to be used alongside native tools.
    """

    def __init__(
        self,
        mcp_tool: MCPTool,
        mcp_client: MCPClient,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.mcp_tool = mcp_tool
        self.mcp_client = mcp_client

        # Override tool attributes
        self.name = f"mcp_{mcp_tool.server_name}_{mcp_tool.name}"
        self.description = f"[MCP] {mcp_tool.description}"

    @property
    def schema(self) -> Dict[str, Any]:
        """Get schema from MCP tool"""
        return self.mcp_tool.input_schema

    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute via MCP client"""
        import asyncio

        try:
            # Run async call in sync context
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.mcp_client.call_tool(
                    f"{self.mcp_tool.server_name}:{self.mcp_tool.name}",
                    kwargs
                )
            )

            return {
                "success": True,
                "data": result
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "execution"
            }


def create_mcp_tools(mcp_client: MCPClient) -> List[Tool]:
    """Create Tool instances for all MCP tools"""
    tools = []

    for tool_key, mcp_tool in mcp_client.tools.items():
        wrapper = MCPToolWrapper(mcp_tool, mcp_client)
        tools.append(wrapper)

    return tools
```

### Configuration

```yaml
# config.yaml - MCP configuration

mcp:
  enabled: true
  servers:
    # File system server
    - name: filesystem
      command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
      transport: stdio

    # GitHub server
    - name: github
      command: ["npx", "-y", "@modelcontextprotocol/server-github"]
      transport: stdio
      env:
        GITHUB_TOKEN: "${GITHUB_TOKEN}"

    # Brave Search server
    - name: brave-search
      command: ["npx", "-y", "@modelcontextprotocol/server-brave-search"]
      transport: stdio
      env:
        BRAVE_API_KEY: "${BRAVE_API_KEY}"

    # Custom server
    - name: custom
      command: ["python", "-m", "my_mcp_server"]
      transport: stdio
```

### Integration with Agent

```python
# In cortex/agent.py

class Cortex:
    def __init__(self, ...):
        # ... existing init ...

        # Initialize MCP if enabled
        self.mcp_client = None
        if self.config.get("mcp", {}).get("enabled", False):
            self._init_mcp()

    def _init_mcp(self) -> None:
        """Initialize MCP client and connect to servers"""
        import asyncio
        from .mcp.client import MCPClient, MCPServer, TransportType
        from .mcp.tools import create_mcp_tools

        self.mcp_client = MCPClient()
        mcp_config = self.config.get("mcp", {})

        async def connect_servers():
            for server_config in mcp_config.get("servers", []):
                server = MCPServer(
                    name=server_config["name"],
                    command=server_config["command"],
                    transport=TransportType(
                        server_config.get("transport", "stdio")
                    ),
                    env=server_config.get("env")
                )

                try:
                    await self.mcp_client.add_server(server)
                    console.print(f"[dim]Connected to MCP server: {server.name}[/dim]")
                except Exception as e:
                    console.print(f"[yellow]Failed to connect to MCP server {server.name}: {e}[/yellow]")

        # Run async connection
        asyncio.get_event_loop().run_until_complete(connect_servers())

        # Add MCP tools to tool list
        mcp_tools = create_mcp_tools(self.mcp_client)
        self._register_mcp_tools(mcp_tools)

    def _register_mcp_tools(self, tools: List[Tool]) -> None:
        """Register MCP tools with the tool registry"""
        from .tools.registry import get_registry

        registry = get_registry()
        for tool in tools:
            registry.register(tool)
```

---

## Dependencies

### Phase 4 Required Packages

```
# requirements-phase4.txt

# Web Tools
duckduckgo-search>=3.0.0    # DuckDuckGo search (no API key)
html2text>=2020.1.16        # HTML to markdown
requests>=2.28.0            # HTTP requests

# Multimodal Tools
Pillow>=9.0.0               # Image processing
pymupdf>=1.23.0             # PDF processing (or pdfplumber)

# MCP Support
# MCP Python SDK (when available) or implement protocol

# Optional
pdfplumber>=0.9.0           # Alternative PDF processor
google-api-python-client    # Google Custom Search
```

---

## Summary

Phase 4 adds powerful extended capabilities:

1. **Web Search/Fetch**: Access up-to-date information from the web
2. **Multimodal**: Process images, PDFs, and Jupyter notebooks
3. **MCP Protocol**: Integrate with the broader AI tool ecosystem

These features are lower priority but significantly enhance Cortex's capabilities for real-world use cases.
