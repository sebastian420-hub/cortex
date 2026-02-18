//! Language detection and tree-sitter language configuration.

use std::path::Path;

/// Detect programming language from file extension.
pub fn detect_language(path: &Path) -> Option<&'static str> {
    let ext = path.extension()?.to_str()?;
    match ext.to_lowercase().as_str() {
        "py" | "pyi" | "pyx" => Some("python"),
        "js" | "jsx" | "mjs" | "cjs" => Some("javascript"),
        "ts" | "tsx" | "mts" | "cts" => Some("typescript"),
        "java" => Some("java"),
        "go" => Some("go"),
        "rs" => Some("rust"),
        "c" | "h" => Some("c"),
        "cpp" | "cc" | "cxx" | "hpp" | "hh" | "hxx" => Some("cpp"),
        _ => None,
    }
}

/// Get tree-sitter Language for a language name.
pub fn get_language(name: &str) -> Option<tree_sitter::Language> {
    match name.to_lowercase().as_str() {
        "python" => Some(tree_sitter_python::LANGUAGE.into()),
        "javascript" => Some(tree_sitter_javascript::LANGUAGE.into()),
        "typescript" => Some(tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into()),
        "tsx" => Some(tree_sitter_typescript::LANGUAGE_TSX.into()),
        "java" => Some(tree_sitter_java::LANGUAGE.into()),
        "go" => Some(tree_sitter_go::LANGUAGE.into()),
        "rust" => Some(tree_sitter_rust::LANGUAGE.into()),
        "c" => Some(tree_sitter_c::LANGUAGE.into()),
        "cpp" | "c++" => Some(tree_sitter_cpp::LANGUAGE.into()),
        _ => None,
    }
}

/// List all supported languages.
pub fn supported_languages() -> Vec<&'static str> {
    vec![
        "python",
        "javascript",
        "typescript",
        "tsx",
        "java",
        "go",
        "rust",
        "c",
        "cpp",
    ]
}
