//! Predefined AST queries for extracting code structures.

use pyo3::prelude::*;
use tree_sitter::{Parser, Query, QueryCursor};
use streaming_iterator::StreamingIterator;

use super::languages;

/// Information about a function/method.
#[pyclass]
#[derive(Clone, Debug)]
pub struct FunctionInfo {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub start_line: usize,
    #[pyo3(get)]
    pub end_line: usize,
    #[pyo3(get)]
    pub parameters: Vec<String>,
    #[pyo3(get)]
    pub is_method: bool,
}

#[pymethods]
impl FunctionInfo {
    fn __repr__(&self) -> String {
        format!(
            "FunctionInfo(name='{}', lines={}-{})",
            self.name, self.start_line, self.end_line
        )
    }
}

/// Information about a class.
#[pyclass]
#[derive(Clone, Debug)]
pub struct ClassInfo {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub start_line: usize,
    #[pyo3(get)]
    pub end_line: usize,
    #[pyo3(get)]
    pub methods: Vec<String>,
    #[pyo3(get)]
    pub bases: Vec<String>,
}

#[pymethods]
impl ClassInfo {
    fn __repr__(&self) -> String {
        format!(
            "ClassInfo(name='{}', methods={}, lines={}-{})",
            self.name,
            self.methods.len(),
            self.start_line,
            self.end_line
        )
    }
}

/// Information about an import statement.
#[pyclass]
#[derive(Clone, Debug)]
pub struct ImportInfo {
    #[pyo3(get)]
    pub module: String,
    #[pyo3(get)]
    pub names: Vec<String>,
    #[pyo3(get)]
    pub line: usize,
    #[pyo3(get)]
    pub is_from_import: bool,
}

#[pymethods]
impl ImportInfo {
    fn __repr__(&self) -> String {
        format!("ImportInfo(module='{}', line={})", self.module, self.line)
    }
}

/// Get the query pattern for function definitions by language.
fn get_function_query(language: &str) -> Option<&'static str> {
    match language {
        "python" => Some("(function_definition name: (identifier) @name) @func"),
        "javascript" | "typescript" | "tsx" => Some(
            "(function_declaration name: (identifier) @name) @func"
        ),
        "java" => Some("(method_declaration name: (identifier) @name) @func"),
        "go" => Some("(function_declaration name: (identifier) @name) @func"),
        "rust" => Some("(function_item name: (identifier) @name) @func"),
        "c" | "cpp" => Some("(function_definition declarator: (function_declarator declarator: (identifier) @name)) @func"),
        _ => None,
    }
}

/// Get the query pattern for class definitions by language.
fn get_class_query(language: &str) -> Option<&'static str> {
    match language {
        "python" => Some("(class_definition name: (identifier) @name) @class"),
        "javascript" | "typescript" | "tsx" => {
            Some("(class_declaration name: (identifier) @name) @class")
        }
        "java" => Some("(class_declaration name: (identifier) @name) @class"),
        "rust" => Some("(struct_item name: (type_identifier) @name) @class"),
        "go" => Some("(type_declaration (type_spec name: (type_identifier) @name)) @class"),
        "cpp" => Some("(class_specifier name: (type_identifier) @name) @class"),
        _ => None,
    }
}

/// Get the query pattern for import statements by language.
fn get_import_query(language: &str) -> Option<&'static str> {
    match language {
        "python" => Some(
            "[(import_statement) @import (import_from_statement) @import]"
        ),
        "javascript" | "typescript" | "tsx" => {
            Some("(import_statement) @import")
        }
        "java" => Some("(import_declaration) @import"),
        "go" => Some("(import_declaration) @import"),
        "rust" => Some("(use_declaration) @import"),
        _ => None,
    }
}

/// Extract function definitions from source code.
#[pyfunction]
pub fn extract_functions(code: &str, language: &str) -> PyResult<Vec<FunctionInfo>> {
    let lang = languages::get_language(language).ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!("Unsupported language: {}", language))
    })?;

    let query_str = get_function_query(language).ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "No function query for language: {}",
            language
        ))
    })?;

    let mut parser = Parser::new();
    parser.set_language(&lang).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to set language: {}", e))
    })?;

    let tree = parser.parse(code.as_bytes(), None).ok_or_else(|| {
        pyo3::exceptions::PyRuntimeError::new_err("Failed to parse code")
    })?;

    let query = Query::new(&lang, query_str).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Invalid query: {}", e))
    })?;

    let mut cursor = QueryCursor::new();
    let mut matches = cursor.matches(&query, tree.root_node(), code.as_bytes());

    let name_idx = query
        .capture_index_for_name("name")
        .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("No 'name' capture in query"))?;

    let func_idx = query
        .capture_index_for_name("func")
        .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("No 'func' capture in query"))?;

    let mut functions = Vec::new();

    while let Some(m) = matches.next() {
        let mut name = String::new();
        let mut start_line = 0;
        let mut end_line = 0;

        for capture in m.captures {
            if capture.index == name_idx {
                name = capture
                    .node
                    .utf8_text(code.as_bytes())
                    .unwrap_or("")
                    .to_string();
            }
            if capture.index == func_idx {
                start_line = capture.node.start_position().row + 1;
                end_line = capture.node.end_position().row + 1;
            }
        }

        if !name.is_empty() {
            functions.push(FunctionInfo {
                name,
                start_line,
                end_line,
                parameters: Vec::new(),
                is_method: false,
            });
        }
    }

    Ok(functions)
}

/// Extract class definitions from source code.
#[pyfunction]
pub fn extract_classes(code: &str, language: &str) -> PyResult<Vec<ClassInfo>> {
    let lang = languages::get_language(language).ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!("Unsupported language: {}", language))
    })?;

    let query_str = get_class_query(language).ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "No class query for language: {}",
            language
        ))
    })?;

    let mut parser = Parser::new();
    parser.set_language(&lang).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to set language: {}", e))
    })?;

    let tree = parser.parse(code.as_bytes(), None).ok_or_else(|| {
        pyo3::exceptions::PyRuntimeError::new_err("Failed to parse code")
    })?;

    let query = Query::new(&lang, query_str).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Invalid query: {}", e))
    })?;

    let mut cursor = QueryCursor::new();
    let mut matches = cursor.matches(&query, tree.root_node(), code.as_bytes());

    let name_idx = query.capture_index_for_name("name");
    let class_idx = query.capture_index_for_name("class");

    let mut classes = Vec::new();

    while let Some(m) = matches.next() {
        let mut name = String::new();
        let mut start_line = 0;
        let mut end_line = 0;

        for capture in m.captures {
            if Some(capture.index) == name_idx {
                name = capture
                    .node
                    .utf8_text(code.as_bytes())
                    .unwrap_or("")
                    .to_string();
            }
            if Some(capture.index) == class_idx {
                start_line = capture.node.start_position().row + 1;
                end_line = capture.node.end_position().row + 1;
            }
        }

        if !name.is_empty() {
            classes.push(ClassInfo {
                name,
                start_line,
                end_line,
                methods: Vec::new(),
                bases: Vec::new(),
            });
        }
    }

    Ok(classes)
}

/// Extract import statements from source code.
#[pyfunction]
pub fn extract_imports(code: &str, language: &str) -> PyResult<Vec<ImportInfo>> {
    let lang = languages::get_language(language).ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!("Unsupported language: {}", language))
    })?;

    let query_str = get_import_query(language).ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "No import query for language: {}",
            language
        ))
    })?;

    let mut parser = Parser::new();
    parser.set_language(&lang).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to set language: {}", e))
    })?;

    let tree = parser.parse(code.as_bytes(), None).ok_or_else(|| {
        pyo3::exceptions::PyRuntimeError::new_err("Failed to parse code")
    })?;

    let query = Query::new(&lang, query_str).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Invalid query: {}", e))
    })?;

    let mut cursor = QueryCursor::new();
    let mut matches = cursor.matches(&query, tree.root_node(), code.as_bytes());

    let mut imports = Vec::new();

    while let Some(m) = matches.next() {
        for capture in m.captures {
            let node = capture.node;
            let text = node
                .utf8_text(code.as_bytes())
                .unwrap_or("")
                .to_string();
            let line = node.start_position().row + 1;

            let is_from = text.starts_with("from ");
            let module = if is_from {
                text.split_whitespace()
                    .nth(1)
                    .unwrap_or("")
                    .to_string()
            } else {
                text.split_whitespace()
                    .nth(1)
                    .unwrap_or("")
                    .to_string()
            };

            imports.push(ImportInfo {
                module,
                names: Vec::new(),
                line,
                is_from_import: is_from,
            });
        }
    }

    Ok(imports)
}

/// Get list of supported languages for AST parsing.
#[pyfunction]
pub fn get_supported_languages() -> Vec<String> {
    languages::supported_languages()
        .iter()
        .map(|s| s.to_string())
        .collect()
}
