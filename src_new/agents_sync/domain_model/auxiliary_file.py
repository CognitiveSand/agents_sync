"""``AuxiliaryFile`` — one file inside a skill folder other than its ``SKILL.md`` (S23i).

A ``skill`` artifact is a folder, not a file: ``SKILL.md`` plus whatever the author
put beside it — reference material, scripts, templates, assets. The canonical
document is JSON and JSON cannot hold raw bytes, so each auxiliary file records
its content together with the encoding used to represent it:

- ``text``   — the file decoded as UTF-8 and stored verbatim. The normal case, and
  what keeps a canonical store human-readable and its versions diffable.
- ``base64`` — anything that is not valid UTF-8 (images, PDFs, compiled assets),
  stored as standard base64.

The encoding is decided per file by *decoding*, never guessed from a suffix: a
``.md`` holding invalid UTF-8 is binary and a ``.png`` that happens to decode is
still restored byte-for-byte. Round-tripping is byte-exact in both directions
(NFR-06), which is why the bytes are never newline-normalised the way a document
``body`` is — an auxiliary file is opaque content, not prose the daemon owns.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Any

TEXT_ENCODING = "text"
BASE64_ENCODING = "base64"
_ENCODINGS = frozenset({TEXT_ENCODING, BASE64_ENCODING})


@dataclass(frozen=True)
class AuxiliaryFile:
    """One auxiliary file's bytes, encoded for canonical (JSON) storage.

    ``executable`` records whether the source file carried a POSIX execute bit. A
    skill that ships a helper script is only useful if the script stays runnable
    on the tools it is projected onto (US-01 AC-10), and mode is not recoverable
    from content.
    """

    content: str
    encoding: str = TEXT_ENCODING
    executable: bool = False

    def __post_init__(self) -> None:
        if self.encoding not in _ENCODINGS:
            raise ValueError(
                f"unknown auxiliary-file encoding {self.encoding!r}; "
                f"expected one of {sorted(_ENCODINGS)}"
            )

    @classmethod
    def from_bytes(cls, raw: bytes, *, executable: bool = False) -> AuxiliaryFile:
        """Encode ``raw`` for storage, preferring readable text over base64."""
        try:
            return cls(raw.decode("utf-8"), TEXT_ENCODING, executable)
        except UnicodeDecodeError:
            return cls(base64.b64encode(raw).decode("ascii"), BASE64_ENCODING, executable)

    def to_bytes(self) -> bytes:
        """The original bytes. Inverse of :meth:`from_bytes`."""
        if self.encoding == BASE64_ENCODING:
            try:
                return base64.b64decode(self.content.encode("ascii"), validate=True)
            except (binascii.Error, UnicodeEncodeError) as error:
                raise ValueError(
                    f"auxiliary file has undecodable base64 content: {error}"
                ) from error
        return self.content.encode("utf-8")

    @classmethod
    def from_dict(cls, data: Any) -> AuxiliaryFile:
        """Build from the stored JSON shape, failing loud on a malformed entry."""
        if not isinstance(data, dict):
            raise ValueError(f"auxiliary file entry must be an object, got {type(data).__name__}")
        content = data.get("content")
        if not isinstance(content, str):
            raise ValueError("auxiliary file entry missing string 'content'")
        return cls(
            content=content,
            encoding=str(data.get("encoding", TEXT_ENCODING)),
            executable=bool(data.get("executable", False)),
        )

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "content": self.content,
            "encoding": self.encoding,
            "executable": self.executable,
        }
