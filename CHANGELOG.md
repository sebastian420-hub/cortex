# Changelog

All notable changes to LocalAgent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-07

### Added
- Initial release of LocalAgent
- Core agent functionality with Ollama integration
- File I/O tools (read_file, write_file)
- Command execution tool
- File search and listing tools
- Git integration tools (status, diff, commit, log)
- Test execution tool (auto-detects pytest/unittest)
- Permission system (normal, auto-approve, plan modes)
- Session persistence (save/load conversations)
- Configuration system with YAML support
- Context window management with intelligent truncation
- Streaming responses (experimental)
- Security features (path traversal protection, dangerous command blocking)
- Rich terminal UI with syntax highlighting
- REPL interface with keyboard shortcuts
- Comprehensive test suite
- CI/CD pipeline
- Documentation

### Security
- Path traversal protection for all file operations
- Dangerous command detection and blocking
- Permission system to prevent unauthorized changes

### Performance
- Context window optimization
- Token counting and history truncation
- Retry logic with exponential backoff

