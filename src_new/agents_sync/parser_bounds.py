"""Hard caps on parser input size and YAML alias expansion (S24 gate; SEC-C-01/02).

The long-running daemon must not be DoS'd by an oversized input file or a
pathological YAML alias graph. Deferred from S9 (the translation core kept the
dialects pure); this module is the one home for the size-explosion hardening the
S24 cutover gates on. It is wired at the minimal set of chokepoints:

- the structured-text codec (:mod:`agents_sync.dialects.structured_text`) caps the
  text handed to ``json`` / ``tomllib`` — covering the keyed-map-slot dialect too,
  which reads through the same codec;
- the markdown front-matter dialect threads :func:`make_bounded_composer_class`
  into its YAML loader and bounds the regex scan with :func:`enforce_frontmatter_window`;
- the file-read seams (read phase, canonical/state store, runtime config, ``@import``
  resolution) read through :func:`read_text_bounded`.

Every bound raises :class:`ParserBoundsExceeded`, a subclass of the dialect layer's
:class:`~agents_sync.dialects.MalformedSurfaceError`, so the read phase's existing
``except MalformedSurfaceError`` records a ``ParseFailure`` with no caller change.

The bounds are deliberately constants, not configuration. Legitimate inputs fit
comfortably within them (a tool's MCP config is a few KB; SKILL.md front-matter a
few hundred bytes). If a real input ever brushes a cap, raise the constant in a
follow-up; do not make it configurable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents_sync.dialects import MalformedSurfaceError

MAX_PARSE_BYTES: int = 16 * 1024 * 1024
"""Per-file parse-input ceiling (16 MiB), on the UTF-8 length of the parsed text."""

MAX_FRONTMATTER_BYTES: int = 256 * 1024
"""Markdown front-matter scan-window ceiling (256 KiB); the leading slice the
front-matter regex is allowed to examine."""

MAX_YAML_ALIAS_RESOLUTIONS: int = 10_000
"""Cap on node compositions per YAML document. Defeats quadratic billion-laughs
even though ruamel's round-trip loader resolves aliases by reference, not by
exponential expansion; legitimate front-matter has essentially no anchors."""


class ParserBoundsExceeded(MalformedSurfaceError):
    """A parser input exceeded one of the bounds in this module."""


def enforce_text_bound(text: str, *, label: str, limit: int = MAX_PARSE_BYTES) -> str:
    """Return ``text`` unchanged if within ``limit``; raise otherwise.

    ``label`` names the input (file path, ``<state.json>``, ``<mcp slot>``) so the
    operator can find the offending input from the error message.
    """
    size = len(text)
    if size > limit:
        raise ParserBoundsExceeded(
            f"{label}: input size {size} bytes exceeds MAX_PARSE_BYTES ({limit} bytes)"
        )
    return text


def read_text_bounded(
    path: Path,
    *,
    label: str | None = None,
    limit: int = MAX_PARSE_BYTES,
    encoding: str = "utf-8",
) -> str:
    """Read ``path`` as text, rejecting files larger than ``limit`` bytes.

    The ``stat().st_size`` check runs BEFORE the read, so a multi-GB hostile file
    never lands in memory. The on-disk byte size is a strict upper bound on the
    in-memory text length (UTF-8 is at most 4 bytes per code point), so the stat
    check is sufficient.
    """
    effective_label = label if label is not None else str(path)
    size = path.stat().st_size
    if size > limit:
        raise ParserBoundsExceeded(
            f"{effective_label}: file size {size} bytes exceeds MAX_PARSE_BYTES ({limit} bytes)"
        )
    return path.read_text(encoding=encoding)


def enforce_frontmatter_window(text: str) -> str:
    """Return the leading slice the front-matter scanner is allowed to examine.

    A document whose body exceeds the cap still parses — the scanner just does not
    see past the first :data:`MAX_FRONTMATTER_BYTES` characters, far more than any
    legitimate front-matter occupies. The window is a prefix of ``text``, so a match
    offset inside it aligns with the original text and the full body is recovered by
    slicing the original from that offset.
    """
    if len(text) <= MAX_FRONTMATTER_BYTES:
        return text
    return text[:MAX_FRONTMATTER_BYTES]


def make_bounded_composer_class() -> Any:
    """Return a ``BoundedComposer`` subclass of ruamel's round-trip composer.

    Constructed lazily so ``parser_bounds`` does not pay the ``ruamel.yaml`` import
    at module load time (callers that never touch YAML skip it entirely).
    """
    from ruamel.yaml.composer import Composer

    class BoundedComposer(Composer):
        """Counts node compositions; raises after the configured cap."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._composed_nodes = 0

        def compose_node(self, parent: Any, index: Any) -> Any:
            self._composed_nodes += 1
            if self._composed_nodes > MAX_YAML_ALIAS_RESOLUTIONS:
                raise ParserBoundsExceeded(
                    "YAML document exceeds MAX_YAML_ALIAS_RESOLUTIONS "
                    f"({MAX_YAML_ALIAS_RESOLUTIONS}) node compositions — "
                    "rejecting as potential alias/anchor bomb"
                )
            return super().compose_node(parent, index)

    return BoundedComposer


__all__ = [
    "MAX_FRONTMATTER_BYTES",
    "MAX_PARSE_BYTES",
    "MAX_YAML_ALIAS_RESOLUTIONS",
    "ParserBoundsExceeded",
    "enforce_frontmatter_window",
    "enforce_text_bound",
    "make_bounded_composer_class",
    "read_text_bounded",
]
