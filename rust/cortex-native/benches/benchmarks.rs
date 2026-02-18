//! Benchmarks for cortex-native Rust components.

use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn bench_search(c: &mut Criterion) {
    let mut group = c.benchmark_group("search");

    // Create a temp dir with some files for search benchmarks
    let dir = tempfile::tempdir().unwrap();
    for i in 0..100 {
        let content = format!(
            "def function_{}(arg1, arg2):\n    return arg1 + arg2 + {}\n\nclass Class_{}:\n    pass\n",
            i, i, i
        );
        std::fs::write(dir.path().join(format!("file_{}.py", i)), &content).unwrap();
    }

    let path = dir.path().to_str().unwrap();

    group.bench_function("simple_pattern_100_files", |b| {
        b.iter(|| {
            cortex_native::search::search(
                black_box("function"),
                black_box(path),
                None, None, false, false, 0, 0,
                "files_with_matches", 100, 0,
            )
        })
    });

    group.bench_function("regex_pattern_100_files", |b| {
        b.iter(|| {
            cortex_native::search::search(
                black_box(r"def \w+\("),
                black_box(path),
                None, None, false, false, 0, 0,
                "content", 50, 0,
            )
        })
    });

    group.finish();
}

fn bench_ast(c: &mut Criterion) {
    let mut group = c.benchmark_group("ast");

    let python_code = r#"
import os
import sys
from typing import List, Dict

class DataProcessor:
    def __init__(self, config):
        self.config = config

    def process(self, items: List[str]) -> List[Dict]:
        results = []
        for item in items:
            results.append(self.transform(item))
        return results

    def transform(self, item):
        return {"name": item, "length": len(item)}

def compute_stats(values):
    return {"min": min(values), "max": max(values)}
"#;

    group.bench_function("parse_python_small", |b| {
        b.iter(|| cortex_native::ast::parse_code(black_box(python_code), "python"))
    });

    let large_code = python_code.repeat(25);
    group.bench_function("parse_python_large", |b| {
        b.iter(|| cortex_native::ast::parse_code(black_box(&large_code), "python"))
    });

    group.bench_function("extract_functions", |b| {
        b.iter(|| cortex_native::ast::extract_functions(black_box(python_code), "python"))
    });

    group.bench_function("extract_classes", |b| {
        b.iter(|| cortex_native::ast::extract_classes(black_box(python_code), "python"))
    });

    group.finish();
}

fn bench_tokenizer(c: &mut Criterion) {
    let mut group = c.benchmark_group("tokenizer");

    let text_1k = "the quick brown fox jumps over the lazy dog ".repeat(25);
    let text_10k = text_1k.repeat(10);
    let text_100k = text_10k.repeat(10);

    group.bench_function("count_1k_chars", |b| {
        b.iter(|| cortex_native::tokenizer::count_tokens(black_box(&text_1k), "gpt-4"))
    });

    group.bench_function("count_10k_chars", |b| {
        b.iter(|| cortex_native::tokenizer::count_tokens(black_box(&text_10k), "gpt-4"))
    });

    group.bench_function("count_100k_chars", |b| {
        b.iter(|| cortex_native::tokenizer::count_tokens(black_box(&text_100k), "gpt-4"))
    });

    group.finish();
}

criterion_group!(benches, bench_search, bench_ast, bench_tokenizer);
criterion_main!(benches);
