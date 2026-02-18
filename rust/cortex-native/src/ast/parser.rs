//! Core AST parsing using tree-sitter.

use std::path::Path;
use std::time::Instant;

use pyo3::prelude::*;
use tree_sitter::Parser;

use super::languages;

/// Result of parsing source code.
#[pyclass]
#[derive(Clone, Debug)]
pub struct ParseResult {
    /// Serialized AST as JSON string
    #[pyo3(get)]
    pub tree_sexp: String,
    /// Whether the AST contains syntax errors
    #[pyo3(get)]
    pub has_errors: bool,
    /// Detected or specified language
    #[pyo3(get)]
    pub language: String,
    /// Parsing time in milliseconds
    #[pyo3(get)]
    pub parse_time_ms: f64,
    /// Number of nodes in the AST
    #[pyo3(get)]
    pub node_count: usize,
    /// Root node kind
    #[pyo3(get)]
    pub root_kind: String,
}

#[pymethods]
impl ParseResult {
    fn __repr__(&self) -> String {
        format!(
            "ParseResult(language='{}', nodes={}, errors={}, time={:.2}ms)",
            self.language, self.node_count, self.has_errors, self.parse_time_ms
        )
    }
}

/// Count nodes in a tree-sitter tree.
fn count_nodes(node: tree_sitter::Node) -> usize {
    let mut count = 1;
    let mut cursor = node.walk();
    if cursor.goto_first_child() {
        loop {
            count += count_nodes(cursor.node());
            if !cursor.goto_next_sibling() {
                break;
            }
        }
    }
    count
}

/// Parse source code string with a specified language.
///
/// Args:
///     code: Source code to parse
///     language: Language name (e.g., "python", "javascript")
///
/// Returns:
///     ParseResult with AST information
#[pyfunction]
pub fn parse_code(code: &str, language: &str) -> PyResult<ParseResult> {
    let start = Instant::now();

    let lang = languages::get_language(language).ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!("Unsupported language: {}", language))
    })?;

    let mut parser = Parser::new();
    parser.set_language(&lang).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to set language: {}", e))
    })?;

    let tree = parser.parse(code.as_bytes(), None).ok_or_else(|| {
        pyo3::exceptions::PyRuntimeError::new_err("Failed to parse source code")
    })?;

    let root = tree.root_node();
    let duration = start.elapsed();

    Ok(ParseResult {
        tree_sexp: root.to_sexp(),
        has_errors: root.has_error(),
        language: language.to_string(),
        parse_time_ms: duration.as_secs_f64() * 1000.0,
        node_count: count_nodes(root),
        root_kind: root.kind().to_string(),
    })
}

/// Parse a file, auto-detecting language from extension.
///
/// Args:
///     path: File path to parse
///     language: Optional language override
///
/// Returns:
///     ParseResult with AST information
#[pyfunction]
#[pyo3(signature = (path, language = None))]
pub fn parse_file(path: &str, language: Option<&str>) -> PyResult<ParseResult> {
    let file_path = Path::new(path);

    if !file_path.exists() {
        return Err(pyo3::exceptions::PyFileNotFoundError::new_err(
            format!("File not found: {}", path),
        ));
    }

    let code = std::fs::read_to_string(file_path).map_err(|e| {
        pyo3::exceptions::PyIOError::new_err(format!("Failed to read file: {}", e))
    })?;

    let lang = if let Some(l) = language {
        l.to_string()
    } else {
        languages::detect_language(file_path)
            .ok_or_else(|| {
                pyo3::exceptions::PyValueError::new_err(format!(
                    "Cannot detect language for: {}",
                    path
                ))
            })?
            .to_string()
    };

    parse_code(&code, &lang)
}
