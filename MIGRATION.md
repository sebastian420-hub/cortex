# Migration Guide

## From Single-File to Package Structure

The codebase has been reorganized from a single `local-code.py` file into a proper Python package structure.

## What Changed

### File Structure

**Before:**
```
LocalTerminalAgent/
├── local-code.py
├── localagent-architecture.md
└── localagent-setup-guide.md
```

**After:**
```
LocalTerminalAgent/
├── localagent/          # Main package
│   ├── __init__.py
│   ├── agent.py
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── tools/
│   ├── core/
│   ├── ui/
│   ├── storage/
│   └── utils/
├── tests/
├── docs/
├── config/
├── pyproject.toml
├── requirements.txt
└── README.md
```

### Usage Changes

**Before:**
```bash
python local-code.py
```

**After:**
```bash
# After installation
localagent

# Or directly
python -m localagent.cli
```

### Installation

**Before:**
- Just run the script directly

**After:**
```bash
pip install -e .
# or
pip install -r requirements.txt
python -m localagent.cli
```

## Backward Compatibility

The old `local-code.py` file is still present but deprecated. For new installations, use the package structure.

## New Features

1. **Session Management**: Save and load conversations
2. **Configuration Files**: YAML-based configuration
3. **Git Tools**: Built-in git integration
4. **Test Tools**: Run tests directly
5. **Streaming**: Experimental streaming responses
6. **Better Security**: Path traversal protection
7. **Context Management**: Intelligent history truncation

## Migration Steps

1. Install the new package structure:
   ```bash
   pip install -e .
   ```

2. Update any scripts that import from `local-code.py`:
   ```python
   # Old
   from local_code import LocalAgent
   
   # New
   from localagent import LocalAgent
   ```

3. Use the new CLI:
   ```bash
   localagent --help
   ```

## Breaking Changes

- Import paths have changed
- CLI interface is now `localagent` instead of `python local-code.py`
- Some internal APIs have changed (but public API remains similar)

