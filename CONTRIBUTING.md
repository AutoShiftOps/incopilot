# Contributing to incopilot

Thank you for your interest in contributing to **incopilot**! This document provides guidelines and instructions for contributing to the project.

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
   git clone https://github.com/AutoShiftOps/incopilot.git
   cd incopilot
   git checkout -b feature/your-feature-name
   ```

2. **Set up development environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Make your changes** and write tests:
   ```bash
   pytest
   black incopilot tests
   isort incopilot tests
   flake8 incopilot tests
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
- Aim for >80% code coverage

```bash
pytest --cov=incopilot tests/
```

### Code Style

- **Code formatting:** Black (line length: 88)
- **Import sorting:** isort
- **Linting:** flake8
- **Security:** bandit

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
