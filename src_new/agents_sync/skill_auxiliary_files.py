"""The skill-folder ↔ auxiliary-file-map gateway (S23i).

A ``skill`` artifact is a folder: ``SKILL.md`` plus whatever the author put beside
it. This module is the only place that converts between the two representations —
the on-disk folder the read phase observes, and the ``auxiliary_files`` map the
canonical document carries — so the walk order, the exclusion rules and the size
bounds are defined once and cannot drift between reading and writing.

Excluded from the map, and therefore never propagated:

- ``SKILL.md`` itself, which is the artifact's parsed content, not an auxiliary;
- OS sidecar metadata (``.DS_Store``, AppleDouble ``._*``), which is per-machine
  Finder state that must not be copied onto another tool. The legacy tree
  excluded these too; keeping the rule preserves that behaviour across cutover.

Everything else is carried verbatim, at any nesting depth, and restored
byte-for-byte (NFR-06).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from agents_sync.domain_model.auxiliary_file import AuxiliaryFile
from agents_sync.parser_bounds import (
    MAX_SKILL_AUXILIARY_FILES,
    MAX_SKILL_FOLDER_BYTES,
    ParserBoundsExceeded,
    read_bytes_bounded,
)

SKILL_KIND = "skill"
SKILL_FILENAME = "SKILL.md"

_IGNORED_TREE_NAMES = frozenset({".DS_Store"})
_IGNORED_TREE_PREFIXES = ("._",)

_EXECUTE_BITS = 0o111  # user/group/other execute
_READ_BITS = 0o444  # user/group/other read; >> 2 maps each read bit to its execute bit


def is_ignored_tree_entry(name: str) -> bool:
    """OS sidecar metadata that is per-machine state, never artifact content."""
    return name in _IGNORED_TREE_NAMES or name.startswith(_IGNORED_TREE_PREFIXES)


def read_auxiliary_files(skill_dir: Path) -> dict[str, AuxiliaryFile]:
    """Every carried file under ``skill_dir`` except ``SKILL.md``, keyed by its
    POSIX-relative path within the folder (e.g. ``references/detail.md``).

    Raises :class:`ParserBoundsExceeded` when the folder exceeds the file-count or
    total-byte ceiling, so a mis-pointed directory is refused loudly instead of being
    adopted and copied onto every other tool.
    """
    auxiliary_files: dict[str, AuxiliaryFile] = {}
    total_bytes = 0
    for path in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
        relative = path.relative_to(skill_dir)
        if relative.as_posix() == SKILL_FILENAME:
            continue
        if any(is_ignored_tree_entry(part) for part in relative.parts):
            continue
        if len(auxiliary_files) >= MAX_SKILL_AUXILIARY_FILES:
            raise ParserBoundsExceeded(
                f"skill folder {skill_dir.name!r}: more than "
                f"{MAX_SKILL_AUXILIARY_FILES} auxiliary files"
            )
        raw = read_bytes_bounded(path, label=f"{skill_dir.name}/{relative.as_posix()}")
        total_bytes += len(raw)
        if total_bytes > MAX_SKILL_FOLDER_BYTES:
            raise ParserBoundsExceeded(
                f"skill folder {skill_dir.name!r}: auxiliary content exceeds "
                f"MAX_SKILL_FOLDER_BYTES ({MAX_SKILL_FOLDER_BYTES} bytes)"
            )
        auxiliary_files[relative.as_posix()] = AuxiliaryFile.from_bytes(
            raw, executable=bool(path.stat().st_mode & _EXECUTE_BITS)
        )
    return auxiliary_files


def populate_skill_folder(
    folder: Path,
    skill_md_text: str,
    auxiliary_files: dict[str, AuxiliaryFile],
) -> None:
    """Write a complete skill folder into ``folder`` (assumed fresh and empty).

    Passed as the ``populate`` callback of
    :func:`~agents_sync.atomic_file_writer.replace_directory_atomic`, so the folder
    becomes visible whole or not at all (NFR-03): a reader never sees a skill whose
    ``SKILL.md`` has landed but whose references have not.
    """
    folder.mkdir(parents=True, exist_ok=True)
    (folder / SKILL_FILENAME).write_text(skill_md_text, encoding="utf-8")
    for relative_path, auxiliary in auxiliary_files.items():
        destination = folder / Path(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(auxiliary.to_bytes())
        if auxiliary.executable:
            # US-01 AC-10: a skill's helper script must stay runnable where it lands.
            # Widen by the execute bits the file's read bits already allow, so the
            # target respects the receiving machine's umask rather than forcing 0o755.
            mode = destination.stat().st_mode
            destination.chmod(mode | ((mode & _READ_BITS) >> 2))


def auxiliary_files_digest(auxiliary_files: dict[str, AuxiliaryFile]) -> str:
    """A stable digest over the auxiliary map, path and bytes both.

    The read phase folds this into a skill surface's ``content_digest`` so that
    editing, adding or deleting a file beside ``SKILL.md`` registers as a change to
    the artifact. Without it the daemon would compare only ``SKILL.md`` and a
    reference edit would never propagate.
    """
    digest = hashlib.sha256()
    for relative_path in sorted(auxiliary_files):
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(auxiliary_files[relative_path].to_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
