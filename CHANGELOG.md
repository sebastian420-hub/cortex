# Changelog

All notable changes to Cortex will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-02-25

### Added
- **Bio-inspired Metacognitive Core**: New internal state tracking for confidence, urgency, and emotional tone.
- **Cognitive Gym**: Autonomous practice environment for agents to improve skills in sandboxed projects.
- **Metacognitive Reflection**: Capability for agents to generate 'Synthetic Experiences' and learn from past successes/failures.
- **Dynamic System Prompting**: Metacognitive state is now injected into the system prompt for better self-awareness.

### Fixed
- Fixed critical bug where the agent and state manager used inconsistent memory bank instances.
- Fixed system prompt refresh issue where internal state wasn't being sent to the LLM.
- Adjusted appraisal logic for more realistic emotional transitions (frustration, caution).
- Improved memory bank synchronization between session and global state.

## [2.0.0] - 2025-01-XX

### Changed
- **BREAKING**: Renamed project from LocalAgent to Cortex
- Renamed package directory: `localagent/` → `cortex/`
- Renamed main class: `LocalAgent` → `Cortex`
- Renamed CLI command: `localagent` → `cortex`
- Updated storage directory: `.localagent/` → `.cortex/`
- Updated all documentation and references
- Updated project description to reflect unified agent capabilities (coding, cybersecurity, personal assistance)

### Migration Notes
- Users will need to reinstall: `pip install -e .`
- Old CLI command `localagent` no longer works - use `cortex` instead
- Storage directory migration: `.localagent/` → `.cortex/` (may need manual migration for existing users)
- All imports in external code will need updating: `from localagent` → `from cortex`

## [1.0.0] - 2024-01-07

### Added
- Initial release of Cortex
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

