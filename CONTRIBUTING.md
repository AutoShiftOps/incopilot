# Contributing to firstsignal

Thank you for your interest in contributing to **firstsignal**! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check the issue list to see if the bug has already been reported.

**When filing a bug report, include:**
- A clear, descriptive title
- A detailed description of the observed behavior
- Expected behavior
- Steps to reproduce the issue
- Python version and OS
- Log output or error messages

### Suggesting Features

**Feature requests should include:**
- A clear, descriptive title
- Description of the suggested feature
- Use case and why it would be useful
- Possible implementation approach (optional)

### Pull Requests

1. **Fork the repository** and create a feature branch:
   ```bash
   git clone https://github.com/AutoShiftOps/firstsignal.git
   cd firstsignal
   git checkout -b feature/your-feature-name
   ```

2. **Set up development environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. **Make your changes** and write tests:
   ```bash
   pytest --cov
   ruff check .
   bandit -q -r firstsignal
   ```

4. **Commit with clear messages:**
   ```bash
   git commit -m "feat: add feature"
   git commit -m "fix: resolve issue"
   ```

5. **Push to your fork and create a Pull Request**

## Development Workflow

### Testing

- Write tests for all new features and bug fixes
- Tests should be in `tests/` directory
- Run tests with `pytest`
- Coverage must stay above 85% (CI enforces this)

```bash
pytest --cov
```

### Code Style

- **Linting and import order:** ruff (line length: 120)
- **Security:** bandit, plus ruff's `S` rules

### Design rules

- **Read-only.** Collectors only read. Suggested commands must not change state; a test enforces this.
- **No shell.** External tools run with an argument list, and user-supplied values are validated.
- **Redact before anything leaves the process.** Reports and AI prompts only ever see redacted text.
- **AI is optional.** Every feature must work with no key and no network.
- **New patterns need two tests:** a line that should match and a similar line that should not.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
