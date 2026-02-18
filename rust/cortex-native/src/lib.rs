//! Cortex Native - High-performance Rust extensions for Cortex AI assistant.
//!
//! Provides native implementations for performance-critical operations:
//! - File search (ripgrep-based)
//! - AST parsing (tree-sitter)
//! - Token counting (tiktoken-rs)

use pyo3::prelude::*;

mod search;
mod ast;
mod tokenizer;

/// Cortex Native Python module.
///
/// Exposes high-performance Rust implementations to Python via PyO3.
#[pymodule]
fn cortex_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Search functions
    m.add_function(wrap_pyfunction!(search::search, m)?)?;
    m.add_class::<search::SearchResult>()?;
    m.add_class::<search::SearchMatch>()?;

    // AST functions
    m.add_function(wrap_pyfunction!(ast::parse_code, m)?)?;
    m.add_function(wrap_pyfunction!(ast::parse_file, m)?)?;
    m.add_function(wrap_pyfunction!(ast::extract_functions, m)?)?;
    m.add_function(wrap_pyfunction!(ast::extract_classes, m)?)?;
    m.add_function(wrap_pyfunction!(ast::extract_imports, m)?)?;
    m.add_function(wrap_pyfunction!(ast::get_supported_languages, m)?)?;

    // Tokenizer functions
    m.add_function(wrap_pyfunction!(tokenizer::count_tokens, m)?)?;
    m.add_function(wrap_pyfunction!(tokenizer::count_message_tokens, m)?)?;
    m.add_function(wrap_pyfunction!(tokenizer::count_messages_tokens, m)?)?;

    // Version info
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;

    Ok(())
}
