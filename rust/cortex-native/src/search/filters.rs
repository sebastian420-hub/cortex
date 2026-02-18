//! File filtering logic for search operations.

use std::path::Path;

/// Default directories to skip during search.
pub const SKIP_DIRS: &[&str] = &[
    ".git",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    "coverage",
    ".idea",
    ".vscode",
];

/// Binary file extensions to skip.
pub const BINARY_EXTENSIONS: &[&str] = &[
    "pyc", "pyo", "so", "dll", "dylib", "exe", "obj", "o", "a", "lib",
    "png", "jpg", "jpeg", "gif", "bmp", "ico", "svg", "webp",
    "mp3", "mp4", "avi", "mov", "wav", "flac",
    "zip", "tar", "gz", "bz2", "xz", "7z", "rar",
    "pdf", "doc", "docx", "xls", "xlsx",
    "woff", "woff2", "ttf", "eot",
    "db", "sqlite", "sqlite3",
];

/// Map file type names to extensions (matching ripgrep's type system).
pub fn get_type_extensions(file_type: &str) -> Vec<&'static str> {
    match file_type {
        "py" | "python" => vec!["py", "pyi", "pyx"],
        "js" | "javascript" => vec!["js", "jsx", "mjs", "cjs"],
        "ts" | "typescript" => vec!["ts", "tsx", "mts", "cts"],
        "java" => vec!["java"],
        "go" => vec!["go"],
        "rust" | "rs" => vec!["rs"],
        "c" => vec!["c", "h"],
        "cpp" | "c++" => vec!["cpp", "cc", "cxx", "hpp", "hh", "hxx", "h"],
        "ruby" | "rb" => vec!["rb", "rake", "gemspec"],
        "php" => vec!["php", "phtml"],
        "swift" => vec!["swift"],
        "kotlin" | "kt" => vec!["kt", "kts"],
        "scala" => vec!["scala", "sc"],
        "html" => vec!["html", "htm", "xhtml"],
        "css" => vec!["css", "scss", "sass", "less"],
        "json" => vec!["json", "jsonl", "jsonc"],
        "yaml" | "yml" => vec!["yaml", "yml"],
        "toml" => vec!["toml"],
        "xml" => vec!["xml", "xsd", "xsl"],
        "md" | "markdown" => vec!["md", "markdown", "mdx"],
        "sh" | "shell" | "bash" => vec!["sh", "bash", "zsh", "fish"],
        "sql" => vec!["sql"],
        "r" => vec!["r", "R", "Rmd"],
        "lua" => vec!["lua"],
        "perl" | "pl" => vec!["pl", "pm"],
        _ => vec![],
    }
}

/// Check if a file path should be skipped based on extension.
pub fn is_binary_file(path: &Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .map(|ext| BINARY_EXTENSIONS.contains(&ext))
        .unwrap_or(false)
}
