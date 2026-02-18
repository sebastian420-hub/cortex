//! Search engine module - ripgrep-based file search.
//!
//! Provides native search using the grep and ignore crates
//! (same core libraries as ripgrep) for 10x faster search
//! compared to subprocess calls.

mod engine;
mod filters;

pub use engine::{search, SearchMatch, SearchResult};
