# Changelog

All notable changes to Cortex will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Sphinx documentation infrastructure
- Plugin development guide
- Developer guide
- Release workflow for automated PyPI publishing
- Simple plugin example
- File size warnings for large files
- Configurable parallel worker count

### Changed
- Merged duplicate CI workflows into single comprehensive workflow
- Default parallel workers now auto-detected based on CPU count

### Fixed
- CI security checks are now blocking for high severity issues

## [0.1.0] - 2024-XX-XX

### Added
- Initial release
- Multi-model support (Claude, GPT, DeepSeek, Ollama)
- Tool system with 30+ built-in tools
- File operations (read, write, edit)
- Git integration
- AST-based code analysis
- Intelligent model routing
- Permission modes (normal, auto, plan)
- Plugin system for custom tools
