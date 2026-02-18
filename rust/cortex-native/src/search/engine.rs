//! Core search engine implementation using grep and ignore crates.

use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Instant;

use grep_matcher::Matcher;
use grep_regex::RegexMatcherBuilder;
use grep_searcher::sinks::UTF8;
use grep_searcher::SearcherBuilder;
use ignore::WalkBuilder;
use pyo3::prelude::*;

use super::filters;

/// A single search match with file, line number, and content.
#[pyclass]
#[derive(Clone, Debug)]
pub struct SearchMatch {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub line_number: Option<usize>,
    #[pyo3(get)]
    pub content: Option<String>,
    #[pyo3(get)]
    pub count: Option<usize>,
}

#[pymethods]
impl SearchMatch {
    fn __repr__(&self) -> String {
        if let Some(line) = self.line_number {
            format!("SearchMatch(path='{}', line={})", self.path, line)
        } else {
            format!("SearchMatch(path='{}')", self.path)
        }
    }
}

/// Aggregated search results.
#[pyclass]
#[derive(Clone, Debug)]
pub struct SearchResult {
    #[pyo3(get)]
    pub matches: Vec<SearchMatch>,
    #[pyo3(get)]
    pub total_matches: usize,
    #[pyo3(get)]
    pub files_searched: usize,
    #[pyo3(get)]
    pub files_matched: usize,
    #[pyo3(get)]
    pub duration_ms: f64,
}

#[pymethods]
impl SearchResult {
    fn __repr__(&self) -> String {
        format!(
            "SearchResult(matches={}, files_searched={}, duration={:.1}ms)",
            self.total_matches, self.files_searched, self.duration_ms
        )
    }

    fn __len__(&self) -> usize {
        self.matches.len()
    }
}

/// Search files using ripgrep's core libraries.
///
/// Args:
///     pattern: Regex pattern to search for
///     path: Root directory to search in
///     glob_filter: Optional glob pattern to filter files (e.g., "*.py")
///     file_type: Optional file type filter (e.g., "py", "js")
///     case_insensitive: Whether to ignore case
///     multiline: Whether to enable multiline matching
///     context_before: Number of context lines before match
///     context_after: Number of context lines after match
///     output_mode: "files_with_matches", "content", or "count"
///     head_limit: Maximum number of results to return
///     offset: Number of results to skip
///
/// Returns:
///     SearchResult with matches and metadata
#[pyfunction]
#[pyo3(signature = (
    pattern,
    path = ".",
    glob_filter = None,
    file_type = None,
    case_insensitive = false,
    multiline = false,
    context_before = 0,
    context_after = 0,
    output_mode = "files_with_matches",
    head_limit = 100,
    offset = 0,
))]
pub fn search(
    pattern: &str,
    path: &str,
    glob_filter: Option<&str>,
    file_type: Option<&str>,
    case_insensitive: bool,
    multiline: bool,
    context_before: usize,
    context_after: usize,
    output_mode: &str,
    head_limit: usize,
    offset: usize,
) -> PyResult<SearchResult> {
    let start = Instant::now();
    let root = Path::new(path);

    if !root.exists() {
        return Err(pyo3::exceptions::PyFileNotFoundError::new_err(
            format!("Path does not exist: {}", path),
        ));
    }

    // Build the regex matcher
    let matcher = RegexMatcherBuilder::new()
        .case_insensitive(case_insensitive)
        .multi_line(multiline)
        .dot_matches_new_line(multiline)
        .build(pattern)
        .map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Invalid regex pattern: {}", e))
        })?;

    // Build file walker with ignore rules
    let mut walk_builder = WalkBuilder::new(root);
    walk_builder
        .hidden(true)        // Skip hidden files
        .git_ignore(true)    // Respect .gitignore
        .git_global(true)
        .git_exclude(true);

    // Apply file type filter via extension matching
    let type_extensions: Vec<String> = if let Some(ft) = file_type {
        filters::get_type_extensions(ft)
            .iter()
            .map(|s| s.to_string())
            .collect()
    } else {
        vec![]
    };

    // Collect matching results
    let matches: Arc<Mutex<Vec<SearchMatch>>> = Arc::new(Mutex::new(Vec::new()));
    let files_searched: Arc<Mutex<usize>> = Arc::new(Mutex::new(0));
    let files_matched: Arc<Mutex<usize>> = Arc::new(Mutex::new(0));

    let walker = walk_builder.build();

    for entry in walker {
        let entry = match entry {
            Ok(e) => e,
            Err(_) => continue,
        };

        let entry_path = entry.path();

        // Skip directories
        if entry_path.is_dir() {
            continue;
        }

        // Skip binary files
        if filters::is_binary_file(entry_path) {
            continue;
        }

        // Apply glob filter
        if let Some(glob) = glob_filter {
            if !matches_glob(entry_path, glob) {
                continue;
            }
        }

        // Apply type filter
        if !type_extensions.is_empty() {
            let ext = entry_path
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("");
            if !type_extensions.iter().any(|te| te == ext) {
                continue;
            }
        }

        *files_searched.lock().unwrap() += 1;

        // Search within the file
        let mut searcher = SearcherBuilder::new()
            .before_context(context_before)
            .after_context(context_after)
            .multi_line(multiline)
            .build();

        let path_str = entry_path.to_string_lossy().to_string();
        let rel_path = entry_path
            .strip_prefix(root)
            .unwrap_or(entry_path)
            .to_string_lossy()
            .to_string();

        let file_has_match = Arc::new(Mutex::new(false));
        let file_match_count = Arc::new(Mutex::new(0usize));
        let local_matches = Arc::clone(&matches);
        let local_file_has_match = Arc::clone(&file_has_match);
        let local_match_count = Arc::clone(&file_match_count);

        let search_result = searcher.search_path(
            &matcher,
            entry_path,
            UTF8(|line_num, line| {
                *local_file_has_match.lock().unwrap() = true;
                *local_match_count.lock().unwrap() += 1;

                match output_mode {
                    "content" => {
                        local_matches.lock().unwrap().push(SearchMatch {
                            path: rel_path.clone(),
                            line_number: Some(line_num as usize),
                            content: Some(line.trim_end().to_string()),
                            count: None,
                        });
                    }
                    "files_with_matches" => {
                        // Only add once per file
                        let mut m = local_matches.lock().unwrap();
                        if !m.iter().any(|sm| sm.path == rel_path) {
                            m.push(SearchMatch {
                                path: rel_path.clone(),
                                line_number: None,
                                content: None,
                                count: None,
                            });
                        }
                    }
                    "count" => {
                        // Will be handled after file is fully searched
                    }
                    _ => {}
                }

                Ok(true)
            }),
        );

        if search_result.is_ok() && *file_has_match.lock().unwrap() {
            *files_matched.lock().unwrap() += 1;

            if output_mode == "count" {
                let count = *file_match_count.lock().unwrap();
                matches.lock().unwrap().push(SearchMatch {
                    path: rel_path,
                    line_number: None,
                    content: None,
                    count: Some(count),
                });
            }
        }
    }

    let duration = start.elapsed();
    let mut all_matches = matches.lock().unwrap().clone();
    let total = all_matches.len();

    // Apply offset and limit
    if offset > 0 {
        if offset >= all_matches.len() {
            all_matches.clear();
        } else {
            all_matches = all_matches[offset..].to_vec();
        }
    }
    if head_limit > 0 && all_matches.len() > head_limit {
        all_matches.truncate(head_limit);
    }

    let final_files_searched = *files_searched.lock().unwrap();
    let final_files_matched = *files_matched.lock().unwrap();

    Ok(SearchResult {
        matches: all_matches,
        total_matches: total,
        files_searched: final_files_searched,
        files_matched: final_files_matched,
        duration_ms: duration.as_secs_f64() * 1000.0,
    })
}

/// Simple glob matching for file paths.
fn matches_glob(path: &Path, glob: &str) -> bool {
    let path_str = path.to_string_lossy();

    // Handle simple patterns
    if glob.starts_with("*.") {
        // Extension match
        let ext = &glob[2..];
        path.extension()
            .and_then(|e| e.to_str())
            .map(|e| e == ext)
            .unwrap_or(false)
    } else if glob.contains('*') {
        // Convert glob to simple regex-like matching
        let pattern = glob
            .replace('.', "\\.")
            .replace('*', ".*")
            .replace('?', ".");
        regex::Regex::new(&format!("^{}$", pattern))
            .map(|re| re.is_match(&path_str))
            .unwrap_or(false)
    } else {
        // Exact match
        path_str.contains(glob)
    }
}
