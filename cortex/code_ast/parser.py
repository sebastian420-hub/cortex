"""
AST Parser - Tree-sitter wrapper for parsing source code.

Handles language detection, parser initialization, and AST creation.
"""

import logging
from typing import Optional, Any, Dict, TYPE_CHECKING
from pathlib import Path

# Type hints for tree-sitter (only for type checking)
if TYPE_CHECKING:
    from tree_sitter import Parser, Language
else:
    Parser = Any
    Language = Any

try:
    from tree_sitter import Language, Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("tree-sitter not available. AST parsing will be disabled.")

from .languages import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


class ASTParser:
    """
    Tree-sitter based AST parser with multi-language support.

    Handles:
    - Language parser initialization
    - Source code parsing
    - Error handling and fallbacks
    """

    def __init__(self):
        """Initialize the AST parser."""
        if not TREE_SITTER_AVAILABLE:
            self.available = False
            self.parsers = {}
            self.languages = {}
            logger.error("tree-sitter not installed. Please install with: pip install tree-sitter")
            return

        self.available = True
        self.parsers: Dict[str, Parser] = {}
        self.languages: Dict[str, Language] = {}

        # Initialize parsers for supported languages
        self._initialize_parsers()

    def _initialize_parsers(self) -> None:
        """Initialize tree-sitter parsers for supported languages."""
        if not self.available:
            return

        try:
            # Try to load each language parser
            for lang_name, lang_config in SUPPORTED_LANGUAGES.items():
                try:
                    # Import the language module
                    module_name = f"tree_sitter_{lang_config['parser_module']}"
                    language_module = __import__(module_name)

                    # Get the PyCapsule and create a Language object from it
                    if lang_name == "typescript":
                        # For TypeScript, we have two language objects
                        # Use the one for TypeScript (not TSX) by default
                        lang_capsule = language_module.language_typescript()
                    elif lang_name == "php":
                        # PHP module has language_php and language_php_only
                        lang_capsule = language_module.language_php()
                    else:
                        # For other languages, call the language function
                        lang_capsule = language_module.language()

                    # Create a tree_sitter Language object from the capsule
                    language = Language(lang_capsule)
                    self.languages[lang_name] = language

                    # Create parser for this language and set the language
                    parser = Parser()
                    parser.language = language
                    self.parsers[lang_name] = parser

                    logger.debug(f"Loaded parser for {lang_name}")

                except ImportError as e:
                    logger.warning(
                        f"Failed to load parser for {lang_name}: {e}. "
                        f"Install with: pip install tree-sitter-{lang_config['parser_module']}"
                    )
                except Exception as e:
                    logger.warning(f"Error initializing parser for {lang_name}: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize AST parsers: {e}")
            self.available = False

    def parse(self, source_code: str, language: str) -> Optional[Any]:
        """
        Parse source code into an AST.

        Args:
            source_code: Source code as string
            language: Programming language name

        Returns:
            Tree-sitter Tree object or None if parsing fails
        """
        # Try native Rust parser first (Phase 2 hybrid)
        try:
            from ..core.feature_flags import FeatureFlag, FeatureManager

            fm = FeatureManager.get_instance()
            if fm.is_enabled(FeatureFlag.RUST_AST):
                from ..native import native_parse_code, NATIVE_AVAILABLE

                if NATIVE_AVAILABLE and native_parse_code is not None:
                    try:
                        result = native_parse_code(source_code, language)
                        return result
                    except Exception:
                        pass  # Fall through to Python parser
        except ImportError:
            pass

        if not self.available:
            logger.error("AST parsing not available (tree-sitter not installed)")
            return None

        if language not in self.parsers:
            logger.warning(f"No parser available for language: {language}")
            return None

        try:
            parser = self.parsers[language]
            tree = parser.parse(bytes(source_code, "utf-8"))

            # Check if parsing produced errors
            root_node = tree.root_node
            if root_node.has_error:
                # Tree-sitter is error-tolerant and minor parsing issues are common
                # Only log at debug level to avoid spam - tree-sitter recovers well
                logger.debug(f"Parsing recovered from errors in {language} code (tree-sitter error-tolerant)")
                # We still return the tree as tree-sitter handles errors gracefully

            return tree

        except Exception as e:
            logger.error(f"Failed to parse {language} code: {e}")
            return None

    def parse_file(self, file_path: Path, language: Optional[str] = None) -> Optional[Any]:
        """
        Parse a file into an AST.

        Args:
            file_path: Path to the file
            language: Programming language (auto-detected if None)

        Returns:
            Tree-sitter Tree object or None if parsing fails
        """
        if not self.available:
            return None

        try:
            # Read file content
            content = file_path.read_text(encoding="utf-8", errors="ignore")

            # Auto-detect language if not specified
            if language is None:
                # Try to detect from file extension
                for lang_name, lang_config in SUPPORTED_LANGUAGES.items():
                    if file_path.suffix.lower() in lang_config["extensions"]:
                        language = lang_name
                        break

            if language is None or language not in self.parsers:
                logger.warning(f"Cannot determine or unsupported language for {file_path}")
                return None

            return self.parse(content, language)

        except Exception as e:
            logger.error(f"Failed to parse file {file_path}: {e}")
            return None

    def is_language_supported(self, language: str) -> bool:
        """
        Check if a language is supported.

        Args:
            language: Programming language name

        Returns:
            True if language is supported, False otherwise
        """
        return language in self.parsers

    def get_supported_languages(self) -> list:
        """
        Get list of supported languages.

        Returns:
            List of language names
        """
        return list(self.parsers.keys())

    def get_parser(self, language: str) -> Optional[Parser]:
        """
        Get parser for a specific language.

        Args:
            language: Programming language name

        Returns:
            Parser object or None if not available
        """
        return self.parsers.get(language)

    def get_language(self, language: str) -> Optional[Language]:
        """
        Get Language object for a specific language.

        Args:
            language: Programming language name

        Returns:
            Language object or None if not available
        """
        return self.languages.get(language)

    def is_available(self) -> bool:
        """
        Check if AST parsing is available.

        Returns:
            True if tree-sitter is installed and parsers are loaded
        """
        return self.available and len(self.parsers) > 0
