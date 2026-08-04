"""Shared execution context + surface helpers for the executor package (pure plumbing)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from agents_sync.atomic_file_writer import replace_directory_atomic, write_text_atomic
from agents_sync.domain_model.auxiliary_file import AuxiliaryFile
from agents_sync.domain_model.observation import SurfaceObservation
from agents_sync.domain_model.sync_plan import SyncIntent
from agents_sync.domain_model.sync_state import ArtifactRecord, SurfaceLocation, SyncState
from agents_sync.domain_model.tool_surface import KeyedMapSlot, ToolSurface
from agents_sync.parser_bounds import ParserBoundsExceeded
from agents_sync.read_tool_surfaces import surface_content_digest
from agents_sync.skill_auxiliary_files import (
    SKILL_KIND,
    populate_skill_folder,
    read_auxiliary_files,
)


class IntentAbortError(RuntimeError):
    """A plan-vs-state inconsistency aborts this intent (not a real I/O failure;
    routed to ``failed`` and converging next poll — e.g. a canonical the planner
    expected was quarantined this poll, or an observation a race removed)."""


@dataclass
class ExecutionContext:
    """One poll's mutable execution context — accumulates outcomes and records."""

    observations_by_location: dict[SurfaceLocation, SurfaceObservation]
    records: dict[str, ArtifactRecord]
    state_dir: Path
    secret_policy_value: str
    changed: int = 0
    failed: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    frozen: list[str] = field(default_factory=list)
    diagnosed: list[str] = field(default_factory=list)


def intent_label(intent: SyncIntent) -> str:
    """The artifact id when the intent carries one, else its source location —
    the name a failure/refusal is reported under."""
    artifact_id = getattr(intent, "artifact_id", "")
    if isinstance(artifact_id, str) and artifact_id:
        return artifact_id
    source = getattr(intent, "source", None)
    assert isinstance(source, ToolSurface)  # every transactional intent has one or the other
    return str(source.location)


def target_file(target: ToolSurface) -> Path:
    """The file a render lands in — the slot's shared file for keyed-map surfaces."""
    location = target.location
    return location.file if isinstance(location, KeyedMapSlot) else location


def skill_folder(target: ToolSurface) -> Path | None:
    """The folder a ``skill`` surface owns, or ``None`` for any other kind.

    A skill's surface location is its ``SKILL.md``, but the *artifact* is the
    folder containing it: the auxiliary files beside it belong to the same
    artifact and are written, archived and removed with it (S23i).
    """
    if target.kind != SKILL_KIND:
        return None
    return target_file(target).parent


def auxiliary_files_already_on_disk(
    target: ToolSurface, auxiliary_files: Mapping[str, AuxiliaryFile]
) -> bool:
    """Whether a skill target's folder already holds exactly ``auxiliary_files``.

    Writers skip a target whose rendered text is identical (NFR-05). For a skill
    that test is not sufficient: a folder can hold the right ``SKILL.md`` and be
    missing every reference beside it — precisely the truncation this step exists
    to repair — so the skip must consider the whole folder. Always ``True`` for
    non-skill surfaces, which have no folder to differ.
    """
    folder = skill_folder(target)
    if folder is None:
        return True
    try:
        return read_auxiliary_files(folder) == dict(auxiliary_files)
    except (OSError, ParserBoundsExceeded):
        return False  # unreadable: rewrite rather than assume it is current


def write_surface_content(
    target: ToolSurface, text: str, auxiliary_files: Mapping[str, AuxiliaryFile]
) -> str:
    """Write one surface and return the digest the next poll will observe for it.

    Every write in the executor goes through here so the folder rule lives in one
    place: a skill is published as a whole directory — its ``SKILL.md`` plus the
    canonical's auxiliary files — swapped into place atomically, so a reader never
    sees a skill whose front page has landed but whose references have not
    (NFR-03). Every other surface is a single atomic text write.
    """
    folder = skill_folder(target)
    if folder is not None:
        replace_directory_atomic(
            folder,
            lambda staging: populate_skill_folder(staging, text, dict(auxiliary_files)),
        )
    else:
        write_text_atomic(target_file(target), text)
    return surface_content_digest(text, target, auxiliary_files)


def reject_shared_write_file(surfaces: tuple[ToolSurface, ...], artifact_id: str) -> None:
    """Abort the intent when two surfaces resolve to the same write file: a second
    atomic write would clobber the first surface's bytes. One clobber invariant for
    every multi-surface writer (project, adopt, rename), routed to ``failed`` and
    retried next poll rather than corrupting the file (US-06 AC-6; NFR-01/NFR-16)."""
    write_files = [target_file(surface) for surface in surfaces]
    if len(set(write_files)) != len(write_files):
        raise IntentAbortError(f"intent surfaces share a write file for {artifact_id}")


def recorded_targets(artifact_id: str, execution: ExecutionContext) -> tuple[ToolSurface, ...]:
    """The artifact's recorded surfaces, resolved to this poll's observed ToolSurfaces.

    A recorded location without an observation is skipped — a vanish is the
    planner's removal decision, not the executor's."""
    record = execution.records.get(artifact_id)
    if record is None:
        return ()
    targets: list[ToolSurface] = []
    for recorded in record.surfaces.values():
        observation = execution.observations_by_location.get(recorded.location)
        if observation is not None:
            targets.append(observation.tool_surface)
    return tuple(targets)


def sync_state_of(execution: ExecutionContext) -> SyncState:
    return SyncState(records=execution.records)
