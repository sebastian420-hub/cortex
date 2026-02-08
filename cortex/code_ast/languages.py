"""
Language Management - Language detection and configuration for AST parsing.

Provides language detection from file extensions and content,
and configuration for tree-sitter parsers.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
import re

logger = logging.getLogger(__name__)

# Supported languages and their configurations
SUPPORTED_LANGUAGES = {
    "python": {
        "name": "Python",
        "extensions": [".py", ".pyw", ".pyi"],
        "parser_module": "python",
        "shebang_patterns": [r"^#!.*python"],
        "keywords": ["def", "class", "import", "from", "as"],
    },
    "javascript": {
        "name": "JavaScript",
        "extensions": [".js", ".jsx", ".mjs", ".cjs"],
        "parser_module": "javascript",
        "shebang_patterns": [r"^#!.*node"],
        "keywords": ["function", "const", "let", "var", "import", "export"],
    },
    "typescript": {
        "name": "TypeScript",
        "extensions": [".ts", ".tsx"],
        "parser_module": "typescript",
        "shebang_patterns": [],
        "keywords": ["interface", "type", "namespace", "declare"],
    },
    "java": {
        "name": "Java",
        "extensions": [".java"],
        "parser_module": "java",
        "shebang_patterns": [],
        "keywords": ["class", "interface", "enum", "public", "private"],
    },
    "go": {
        "name": "Go",
        "extensions": [".go"],
        "parser_module": "go",
        "shebang_patterns": [],
        "keywords": ["package", "import", "func", "struct", "interface"],
    },
    "rust": {
        "name": "Rust",
        "extensions": [".rs"],
        "parser_module": "rust",
        "shebang_patterns": [],
        "keywords": ["fn", "struct", "impl", "trait", "mod"],
    },
    "c": {
        "name": "C",
        "extensions": [".c", ".h"],
        "parser_module": "c",
        "shebang_patterns": [],
        "keywords": ["#include", "#define", "struct", "typedef"],
    },
    "cpp": {
        "name": "C++",
        "extensions": [".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"],
        "parser_module": "cpp",
        "shebang_patterns": [],
        "keywords": ["#include", "class", "namespace", "template"],
    },
    "ruby": {
        "name": "Ruby",
        "extensions": [".rb", ".rake", ".gemspec"],
        "parser_module": "ruby",
        "shebang_patterns": [r"^#!.*ruby"],
        "keywords": ["def", "class", "module", "require"],
    },
    "php": {
        "name": "PHP",
        "extensions": [".php", ".php3", ".php4", ".php5", ".phtml"],
        "parser_module": "php",
        "shebang_patterns": [r"^#!.*php"],
        "keywords": ["<?php", "function", "class", "namespace"],
    },
}

# File extension to language mapping (for quick lookup)
EXTENSION_TO_LANGUAGE: Dict[str, str] = {}
for lang_name, config in SUPPORTED_LANGUAGES.items():
    for ext in config["extensions"]:
        EXTENSION_TO_LANGUAGE[ext.lower()] = lang_name


def detect_language(file_path: Path, content: Optional[str] = None) -> Optional[str]:
    """
    Detect programming language from file path and optionally content.

    Args:
        file_path: Path to the file
        content: Optional file content for more accurate detection

    Returns:
        Language name or None if cannot detect
    """
    # First try by file extension
    extension = file_path.suffix.lower()
    if extension in EXTENSION_TO_LANGUAGE:
        return EXTENSION_TO_LANGUAGE[extension]

    # If content is provided, try to detect from content
    if content:
        return detect_language_from_content(content)

    # Try to detect from filename patterns
    filename = file_path.name.lower()

    # Common filename patterns
    filename_patterns = {
        "Makefile": "make",
        "Dockerfile": "dockerfile",
        "docker-compose.yml": "yaml",
        ".gitignore": "gitignore",
        "package.json": "json",
        "requirements.txt": "text",
        "README": "markdown",
        "LICENSE": "text",
    }

    for pattern, lang in filename_patterns.items():
        if pattern.lower() in filename:
            return lang

    return None


def detect_language_from_content(content: str) -> Optional[str]:
    """
    Detect programming language from file content.

    Args:
        content: File content as string

    Returns:
        Language name or None if cannot detect
    """
    # Check for shebang
    first_line = content.split("\n")[0] if content else ""
    if first_line.startswith("#!"):
        for lang_name, config in SUPPORTED_LANGUAGES.items():
            for pattern in config["shebang_patterns"]:
                if re.match(pattern, first_line, re.IGNORECASE):
                    return lang_name

    # Check for language-specific patterns
    lines = content.split("\n")[:10]  # Check first 10 lines

    # Python detection
    if any("import " in line or "from " in line or "def " in line for line in lines):
        return "python"

    # JavaScript detection
    if any("function " in line or "const " in line or "let " in line for line in lines):
        return "javascript"

    # TypeScript detection
    if any(": string" in line or ": number" in line or "interface " in line for line in lines):
        return "typescript"

    # Java detection
    if any("public class" in line or "import " in line and ".java" in line for line in lines):
        return "java"

    # Go detection
    if any("package " in line or "func " in line or 'import "' in line for line in lines):
        return "go"

    return None


def get_language_extension(language: str) -> List[str]:
    """
    Get file extensions for a language.

    Args:
        language: Language name

    Returns:
        List of file extensions
    """
    if language in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[language]["extensions"]
    return []


def get_language_name(language: str) -> str:
    """
    Get display name for a language.

    Args:
        language: Language identifier

    Returns:
        Display name
    """
    if language in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[language]["name"]
    return language


def is_language_supported(language: str) -> bool:
    """
    Check if a language is supported.

    Args:
        language: Language identifier

    Returns:
        True if language is supported
    """
    return language in SUPPORTED_LANGUAGES


def get_supported_extensions() -> List[str]:
    """
    Get all supported file extensions.

    Returns:
        List of file extensions
    """
    extensions = []
    for config in SUPPORTED_LANGUAGES.values():
        extensions.extend(config["extensions"])
    return sorted(set(extensions))


class LanguageManager:
    """
    Manages language configurations and detection.
    """

    def __init__(self):
        """Initialize language manager."""
        self.languages = SUPPORTED_LANGUAGES.copy()

    def detect(self, file_path: Path, content: Optional[str] = None) -> Optional[str]:
        """
        Detect language from file.

        Args:
            file_path: Path to the file
            content: Optional file content

        Returns:
            Language name or None
        """
        return detect_language(file_path, content)

    def get_config(self, language: str) -> Optional[Dict]:
        """
        Get configuration for a language.

        Args:
            language: Language identifier

        Returns:
            Language configuration or None
        """
        return self.languages.get(language)

    def get_extensions(self, language: str) -> List[str]:
        """
        Get file extensions for a language.

        Args:
            language: Language identifier

        Returns:
            List of file extensions
        """
        config = self.get_config(language)
        if config:
            return config["extensions"]
        return []

    def get_parser_module(self, language: str) -> Optional[str]:
        """
        Get parser module name for a language.

        Args:
            language: Language identifier

        Returns:
            Parser module name or None
        """
        config = self.get_config(language)
        if config:
            return config["parser_module"]
        return None

    def add_language(self, name: str, config: Dict) -> None:
        """
        Add a custom language configuration.

        Args:
            name: Language identifier
            config: Language configuration
        """
        self.languages[name] = config
        # Update extension mapping
        for ext in config.get("extensions", []):
            EXTENSION_TO_LANGUAGE[ext.lower()] = name

        logger.info(f"Added custom language: {name}")

    def remove_language(self, name: str) -> bool:
        """
        Remove a language configuration.

        Args:
            name: Language identifier

        Returns:
            True if language was removed
        """
        if name in self.languages:
            config = self.languages[name]
            # Remove from extension mapping
            for ext in config.get("extensions", []):
                if ext.lower() in EXTENSION_TO_LANGUAGE:
                    del EXTENSION_TO_LANGUAGE[ext.lower()]

            del self.languages[name]
            logger.info(f"Removed language: {name}")
            return True
        return False

    def list_languages(self) -> List[str]:
        """
        List all supported languages.

        Returns:
            List of language identifiers
        """
        return list(self.languages.keys())

    def is_supported(self, file_path: Path) -> bool:
        """
        Check if a file is supported based on extension.

        Args:
            file_path: Path to the file

        Returns:
            True if file extension is supported
        """
        extension = file_path.suffix.lower()
        return extension in EXTENSION_TO_LANGUAGE
