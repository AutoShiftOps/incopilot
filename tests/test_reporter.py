"""Tests for report generation."""
import json


class TestReporter:
    """Test report generation."""

    def test_json_serialization(self):
        """Test JSON report can be serialized."""
        findings = {
            "time_range": "last 30 min",
            "sources": ["nginx"],
            "signals": {}
        }
        report = json.dumps(findings)
        assert report is not None
        data = json.loads(report)
        assert "time_range" in data
        assert "sources" in data
