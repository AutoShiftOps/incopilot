"""Tests for log analysis."""


class TestAnalyzer:
    """Test log analysis functions."""

    def test_sample_log_parsing(self, sample_log_file):
        """Test that sample log file can be parsed."""
        with open(sample_log_file) as f:
            lines = f.readlines()
        assert len(lines) == 5
        assert "ERROR" in lines[0]

    def test_error_detection(self):
        """Test error pattern detection."""
        error_line = "ERROR [nginx] upstream connect error"
        assert "ERROR" in error_line
        assert "connect error" in error_line
