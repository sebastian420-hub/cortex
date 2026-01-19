# Contributing

We welcome contributions to Cortex! This document explains how to get started.

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/cortex.git
   cd cortex
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```

4. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   # or
   pip install -r requirements-dev.txt
   ```

## Making Changes

1. Create a branch:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make your changes

3. Run tests:
   ```bash
   pytest tests/ -v
   ```

4. Check code quality:
   ```bash
   black --check cortex tests
   flake8 cortex tests
   mypy cortex
   ```

5. Commit with a clear message:
   ```bash
   git commit -m "feat: add new feature"
   ```

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Maintenance tasks

## Pull Request Process

1. Push your branch:
   ```bash
   git push origin feature/my-feature
   ```

2. Open a Pull Request against `main`

3. Ensure CI passes

4. Request review

## Code Style

- Use Black for formatting (line length 100)
- Follow PEP 8 guidelines
- Add type hints for new code
- Write docstrings for public functions

## Testing

- Add tests for new features
- Ensure existing tests pass
- Aim for good coverage

## Questions?

Open an issue or discussion on GitHub.
