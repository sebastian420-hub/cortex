//! AST parsing module - tree-sitter based code analysis.
//!
//! Provides native AST parsing using Rust's tree-sitter bindings
//! for 50x faster parsing compared to Python tree-sitter.

mod parser;
mod queries;
mod languages;

pub use parser::{parse_code, parse_file, ParseResult};
pub use queries::{
    extract_functions, extract_classes, extract_imports,
    FunctionInfo, ClassInfo, ImportInfo,
    get_supported_languages,
};
