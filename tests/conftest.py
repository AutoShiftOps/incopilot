"""Shared pytest fixtures for incopilot tests."""
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_log_file(temp_dir):
    """Create a sample log file for testing."""
    log_content = """2026-07-08T10:00:00.000Z ERROR [nginx] upstream connect error
2026-07-08T10:00:01.000Z ERROR [nginx] upstream connect error
2026-07-08T10:00:02.000Z WARN [nginx] upstream response time > 2s
2026-07-08T10:00:03.000Z ERROR [nginx] Connection reset by peer
2026-07-08T10:00:04.000Z INFO [nginx] 200 OK
"""
    log_file = temp_dir / "sample.log"
    log_file.write_text(log_content)
    return log_file


@pytest.fixture
def sample_journal_entry():
    """Provide sample journal entry data."""
    return {
        "timestamp": "2026-07-08T10:00:00Z",
        "unit": "nginx",
        "message": "upstream connect error",
        "level": "ERROR"
    }
