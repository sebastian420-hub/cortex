"""Native Rust extension bindings for Cortex.

Provides high-performance implementations for:
- File search (ripgrep-based)
- AST parsing (tree-sitter)
- Token counting (tiktoken-rs)

Falls back gracefully if the native extension is not built.
"""

NATIVE_AVAILABLE = False

try:
    from cortex_native import (
        # Search
        search as native_search,
        SearchResult,
        SearchMatch,
        # AST
        parse_code as native_parse_code,
        parse_file as native_parse_file,
        extract_functions as native_extract_functions,
        extract_classes as native_extract_classes,
        extract_imports as native_extract_imports,
        get_supported_languages as native_supported_languages,
        # Tokenizer
        count_tokens as native_count_tokens,
        count_message_tokens as native_count_message_tokens,
        count_messages_tokens as native_count_messages_tokens,
        # Version
        __version__ as native_version,
    )

    NATIVE_AVAILABLE = True
except ImportError:
    native_search = None
    SearchResult = None
    SearchMatch = None
    native_parse_code = None
    native_parse_file = None
    native_extract_functions = None
    native_extract_classes = None
    native_extract_imports = None
    native_supported_languages = None
    native_count_tokens = None
    native_count_message_tokens = None
    native_count_messages_tokens = None
    native_version = None
