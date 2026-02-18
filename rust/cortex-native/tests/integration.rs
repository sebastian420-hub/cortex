//! Integration tests for cortex-native.

#[cfg(test)]
mod search_tests {
    use tempfile::tempdir;
    use std::fs;

    #[test]
    fn test_search_basic() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("test.py"),
            "def hello():\n    return 'world'\n",
        ).unwrap();

        let result = cortex_native::search::search(
            "hello",
            dir.path().to_str().unwrap(),
            None, None, false, false, 0, 0,
            "files_with_matches", 100, 0,
        ).unwrap();

        assert_eq!(result.files_matched, 1);
        assert!(!result.matches.is_empty());
    }

    #[test]
    fn test_search_regex() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("test.py"),
            "def foo(a, b):\n    pass\ndef bar(x):\n    pass\n",
        ).unwrap();

        let result = cortex_native::search::search(
            r"def \w+\(",
            dir.path().to_str().unwrap(),
            None, None, false, false, 0, 0,
            "content", 100, 0,
        ).unwrap();

        assert!(result.total_matches >= 2);
    }

    #[test]
    fn test_search_glob_filter() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("test.py"), "hello\n").unwrap();
        fs::write(dir.path().join("test.js"), "hello\n").unwrap();

        let result = cortex_native::search::search(
            "hello",
            dir.path().to_str().unwrap(),
            Some("*.py"), None, false, false, 0, 0,
            "files_with_matches", 100, 0,
        ).unwrap();

        assert_eq!(result.files_matched, 1);
    }

    #[test]
    fn test_search_count_mode() {
        let dir = tempdir().unwrap();
        fs::write(
            dir.path().join("test.py"),
            "hello\nhello\nhello\nworld\n",
        ).unwrap();

        let result = cortex_native::search::search(
            "hello",
            dir.path().to_str().unwrap(),
            None, None, false, false, 0, 0,
            "count", 100, 0,
        ).unwrap();

        assert!(!result.matches.is_empty());
        assert_eq!(result.matches[0].count, Some(3));
    }
}

#[cfg(test)]
mod ast_tests {
    #[test]
    fn test_parse_python() {
        let code = "def hello():\n    return 'world'\n";
        let result = cortex_native::ast::parse_code(code, "python").unwrap();
        assert!(!result.has_errors);
        assert_eq!(result.language, "python");
        assert!(result.node_count > 0);
    }

    #[test]
    fn test_extract_functions_python() {
        let code = "def foo():\n    pass\ndef bar(x, y):\n    return x + y\n";
        let functions = cortex_native::ast::extract_functions(code, "python").unwrap();
        assert_eq!(functions.len(), 2);
        assert_eq!(functions[0].name, "foo");
        assert_eq!(functions[1].name, "bar");
    }

    #[test]
    fn test_extract_classes_python() {
        let code = "class Foo:\n    pass\nclass Bar(Foo):\n    pass\n";
        let classes = cortex_native::ast::extract_classes(code, "python").unwrap();
        assert_eq!(classes.len(), 2);
        assert_eq!(classes[0].name, "Foo");
        assert_eq!(classes[1].name, "Bar");
    }

    #[test]
    fn test_supported_languages() {
        let langs = cortex_native::ast::get_supported_languages();
        assert!(langs.contains(&"python".to_string()));
        assert!(langs.contains(&"javascript".to_string()));
        assert!(langs.contains(&"rust".to_string()));
    }

    #[test]
    fn test_unsupported_language() {
        let result = cortex_native::ast::parse_code("code", "brainfuck");
        assert!(result.is_err());
    }
}

#[cfg(test)]
mod tokenizer_tests {
    #[test]
    fn test_count_tokens_basic() {
        let count = cortex_native::tokenizer::count_tokens("Hello, world!", "gpt-4").unwrap();
        assert!(count > 0);
        assert!(count < 10);
    }

    #[test]
    fn test_count_tokens_empty() {
        let count = cortex_native::tokenizer::count_tokens("", "gpt-4").unwrap();
        assert_eq!(count, 0);
    }

    #[test]
    fn test_count_message_tokens() {
        let msg = r#"{"role": "user", "content": "Hello, world!"}"#;
        let count = cortex_native::tokenizer::count_message_tokens(msg, "gpt-4").unwrap();
        assert!(count > 0);
    }

    #[test]
    fn test_count_messages_batch() {
        let msgs = r#"[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]"#;
        let counts = cortex_native::tokenizer::count_messages_tokens(msgs, "gpt-4").unwrap();
        assert_eq!(counts.len(), 2);
        assert!(counts[0] > 0);
        assert!(counts[1] > 0);
    }
}
