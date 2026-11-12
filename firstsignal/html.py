"""Self-contained HTML report: the report viewer with one report embedded."""

from __future__ import annotations

import json
from importlib import resources

_DATA_SLOT = '<script id="report-data" type="application/json">null</script>'
_SAMPLE_OPEN = '<script id="sample-data" type="application/json">'


def _safe_json(obj) -> str:
    """Serialize for embedding inside a <script> element: no markup-significant characters."""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    for ch, esc in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"), (" ", "\\u2029")):
        text = text.replace(ch, esc)
    return text


def render_html(report: dict) -> str:
    """Return the viewer page with `report` embedded and the bundled example removed."""
    page = resources.files("firstsignal").joinpath("viewer.html").read_text(encoding="utf-8")
    if _DATA_SLOT not in page or _SAMPLE_OPEN not in page:
        raise RuntimeError("viewer.html is missing its data slots")
    start = page.index(_SAMPLE_OPEN) + len(_SAMPLE_OPEN)
    end = page.index("</script>", start)
    page = page[:start] + "null" + page[end:]
    return page.replace(_DATA_SLOT, _DATA_SLOT.replace("null", _safe_json(report)), 1)
