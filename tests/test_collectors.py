"""Tests for log collectors."""


class TestFileCollector:
    """Test file-based log collection."""

    def test_read_log_file_exists(self, sample_log_file):
        """Test reading an existing log file."""
        with open(sample_log_file) as f:
            lines = f.readlines()
        assert lines is not None
        assert len(lines) > 0

    def test_read_log_file_empty(self, temp_dir):
        """Test reading an empty log file."""
        empty_file = temp_dir / "empty.log"
        empty_file.write_text("")
        with open(empty_file) as f:
            lines = f.readlines()
        assert lines is not None
        assert len(lines) == 0
