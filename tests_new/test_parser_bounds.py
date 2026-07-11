"""Regression tests for the rebuild's parser bounds (S24 gate; SEC-C-01 / SEC-C-02).

The long-running daemon must not be DoS'd by oversized or pathological input. The
bounds defend three seams:

- an oversized parser input (a 2 GB hostile mcp.json that OOMs the poll loop) — the
  structured-text codec and the file-read helpers cap input size;
- a YAML alias / anchor bomb (quadratic billion-laughs against ruamel's round-trip
  loader) — the front-matter loader threads a node-counting bounded composer;
- a multi-MB document body forcing the front-matter regex to walk the whole text —
  the scan is bounded to a leading window.

Every bound raises ``ParserBoundsExceeded``, a subclass of the dialect layer's
``MalformedSurfaceError``, so the read phase's existing ``except MalformedSurfaceError``
records a ``ParseFailure`` without any caller change.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents_sync.dialects import MalformedSurfaceError
from agents_sync.domain_model.tool_surface import SurfaceFormat, ToolSurface
from agents_sync.parser_bounds import (
    MAX_FRONTMATTER_BYTES,
    MAX_PARSE_BYTES,
    MAX_YAML_ALIAS_RESOLUTIONS,
    ParserBoundsExceeded,
    enforce_frontmatter_window,
    enforce_text_bound,
    read_text_bounded,
)
from agents_sync.translation import file_to_canonical

# --- the exception is a MalformedSurfaceError, so the read phase catches it uniformly ---


def test_parser_bounds_exceeded_is_a_malformed_surface_error() -> None:
    assert issubclass(ParserBoundsExceeded, MalformedSurfaceError)


# --- text-size cap (enforce_text_bound / read_text_bounded) ---


def test_enforce_text_bound_passes_within_limit() -> None:
    payload = "a" * 1024
    assert enforce_text_bound(payload, label="<test>") == payload


def test_enforce_text_bound_rejects_oversize() -> None:
    payload = "a" * (MAX_PARSE_BYTES + 1)
    with pytest.raises(ParserBoundsExceeded, match="MAX_PARSE_BYTES"):
        enforce_text_bound(payload, label="<test>")


def test_read_text_bounded_rejects_oversize_file_via_stat(tmp_path: Path) -> None:
    huge = tmp_path / "huge.json"
    huge.write_text("a" * (MAX_PARSE_BYTES + 1), encoding="utf-8")
    with pytest.raises(ParserBoundsExceeded, match="MAX_PARSE_BYTES"):
        read_text_bounded(huge)


def test_read_text_bounded_passes_small_file(tmp_path: Path) -> None:
    small = tmp_path / "small.json"
    small.write_text('{"k": "v"}', encoding="utf-8")
    assert read_text_bounded(small) == '{"k": "v"}'


# --- front-matter scan window (enforce_frontmatter_window) ---


def test_enforce_frontmatter_window_returns_full_text_when_small() -> None:
    text = "a" * (MAX_FRONTMATTER_BYTES - 1)
    assert enforce_frontmatter_window(text) is text


def test_enforce_frontmatter_window_truncates_to_the_leading_prefix() -> None:
    # A distinct head + homogeneous tail so the assertion distinguishes the leading
    # prefix (the contract — offsets must align with the original for body recovery)
    # from a same-length slice taken anywhere else.
    text = "HEAD" + "x" * (MAX_FRONTMATTER_BYTES * 3)
    windowed = enforce_frontmatter_window(text)
    assert windowed == text[:MAX_FRONTMATTER_BYTES]
    assert windowed.startswith("HEAD")


# --- the seams: structured-text codec caps input size ---

_JSON_SURFACE = SurfaceFormat(
    dialect="structured_text",
    id_field="pair_id",
    known_fields=(("name", "name"),),
    file_format="json",
)


def test_structured_text_deserialize_rejects_oversize_json() -> None:
    from agents_sync.dialects.structured_text import deserialize

    payload = '{"k": "' + ("a" * (MAX_PARSE_BYTES + 1)) + '"}'
    with pytest.raises(ParserBoundsExceeded, match="MAX_PARSE_BYTES"):
        deserialize(payload, "json")


def test_structured_text_deserialize_rejects_oversize_toml() -> None:
    from agents_sync.dialects.structured_text import deserialize

    payload = 'k = "' + ("a" * (MAX_PARSE_BYTES + 1)) + '"'
    with pytest.raises(ParserBoundsExceeded, match="MAX_PARSE_BYTES"):
        deserialize(payload, "toml")


# --- the seams: markdown front-matter loader (bounded composer + window) ---

_MARKDOWN_SURFACE = SurfaceFormat(
    dialect="markdown_frontmatter",
    id_field="pair_id",
    known_fields=(("name", "name"),),
)


def _markdown_surface() -> ToolSurface:
    return ToolSurface(
        tool="claude",
        kind="agent",
        location=Path("/u/.claude/agents/x.md"),
        surface_format=_MARKDOWN_SURFACE,
    )


def test_markdown_alias_bomb_rejected_by_bounded_composer() -> None:
    """SEC-C-01 — a front-matter mapping that composes past the node cap is rejected.

    A mapping of ~12 000 keys composes well over MAX_YAML_ALIAS_RESOLUTIONS nodes but
    stays under the 256 KB window, so the composer (not the window) is what fires.
    """
    keys = "".join(f"k{index}: 1\n" for index in range(MAX_YAML_ALIAS_RESOLUTIONS + 2_000))
    text = f"---\n{keys}---\nbody\n"
    with pytest.raises(ParserBoundsExceeded, match="MAX_YAML_ALIAS_RESOLUTIONS"):
        file_to_canonical(text, _markdown_surface(), None)


def test_markdown_huge_body_scans_only_the_window() -> None:
    """SEC-C-07 — a multi-MB body must not make the regex walk the whole document.

    The front-matter is at the top; the body is 1 MB. The scan is bounded to the head
    window, yet the full body is recovered from the original text (offset alignment).
    """
    huge_body = "x" * (MAX_FRONTMATTER_BYTES * 4)
    text = f"---\nname: huge\n---\n{huge_body}"
    canonical = file_to_canonical(text, _markdown_surface(), None)
    assert canonical.name == "huge"
    assert canonical.body == huge_body


def test_markdown_small_document_still_parses() -> None:
    """The bounds must not interfere with a legitimate small document."""
    text = "---\nname: ok\n---\nhello\n"
    canonical = file_to_canonical(text, _markdown_surface(), None)
    assert canonical.name == "ok"
    assert canonical.body == "hello"
