"""Read phase — tool surfaces on disk to ``SurfaceObservation``s (FR-10/FR-11).

The one place the sync pipeline reads tool files: declarative surface specs
(directory, keyed-map, FR-10 rules-precedence — populated by tools-as-data at S20)
are turned into the observations the pure planner consumes. Each observation
carries the raw-text content digest, a fresh mtime, the id extracted in isolation
(never raises, FR-11), and a parse result — malformed content becomes a
``ParseFailure`` the planner routes to freeze; a recipe error stays a loud
``ValueError``. A surface whose digest matches its previous observation reuses the
prior parse (re-parse only changed; the daemon owns the cross-poll cache, S22).
A keyed-map file that no longer deserializes yields ``ParseFailure`` observations
for its previously-known slots — freeze, never removal propagation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from agents_sync.dialects import MalformedSurfaceError
from agents_sync.dialects.structured_text import deserialize
from agents_sync.domain_model.artifact_naming import slugify_name
from agents_sync.domain_model.auxiliary_file import AuxiliaryFile
from agents_sync.domain_model.canonical_document import CanonicalDocument
from agents_sync.domain_model.observation import ParseFailure, SurfaceObservation
from agents_sync.domain_model.sync_state import SurfaceLocation
from agents_sync.domain_model.tool_surface import KeyedMapSlot, SurfaceFormat, ToolSurface
from agents_sync.parser_bounds import ParserBoundsExceeded, read_text_bounded
from agents_sync.rules_import_resolution import RulesImportError, inline_rules_imports
from agents_sync.skill_auxiliary_files import (
    SKILL_FILENAME,
    auxiliary_files_digest,
    read_auxiliary_files,
)
from agents_sync.translation import extract_artifact_id, file_to_canonical


@dataclass(frozen=True)
class DirectorySurfaceSpec:
    """Per-file artifacts: every ``filename_suffix`` file in ``directory`` is a surface."""

    tool: str
    kind: str
    directory: Path
    filename_suffix: str
    surface_format: SurfaceFormat


@dataclass(frozen=True)
class KeyedMapSurfaceSpec:
    """A shared keyed-map file: every slot under its key path is one surface."""

    tool: str
    kind: str
    file: Path
    surface_format: SurfaceFormat


@dataclass(frozen=True)
class RulesFileSurfaceSpec:
    """FR-10: the highest-precedence present filename is THE rules surface;
    a filename not on the declared list is never observed.

    ``default_artifact_name`` names an artifact whose file declares no name — the
    normal case here, since a whole-file rules document is plain markdown."""

    tool: str
    kind: str
    directory: Path
    candidate_filenames: tuple[str, ...]
    surface_format: SurfaceFormat
    default_artifact_name: str = ""


@dataclass(frozen=True)
class SkillFolderSurfaceSpec:
    """Skills: every ``<slug>/SKILL.md`` under ``directory`` is one surface (FR-06, S23f).

    Identity is the SKILL.md's embedded ``pair_id`` (the folder name is cosmetic). A
    skill folder carrying anything besides its ``SKILL.md`` is frozen (deferred S23i)."""

    tool: str
    kind: str
    directory: Path
    surface_format: SurfaceFormat


type SurfaceSpec = (
    DirectorySurfaceSpec | KeyedMapSurfaceSpec | RulesFileSurfaceSpec | SkillFolderSurfaceSpec
)
type PreviousObservations = Mapping[SurfaceLocation, SurfaceObservation]

_NO_HISTORY: PreviousObservations = {}


def read_tool_surfaces(
    surface_specs: tuple[SurfaceSpec, ...],
    previous_observations: PreviousObservations = _NO_HISTORY,
) -> tuple[SurfaceObservation, ...]:
    """Observe every declared surface this poll (the only read-side disk walk)."""
    observations: list[SurfaceObservation] = []
    for spec in surface_specs:
        if isinstance(spec, DirectorySurfaceSpec):
            observations.extend(_observe_directory(spec, previous_observations))
        elif isinstance(spec, KeyedMapSurfaceSpec):
            observations.extend(_observe_keyed_map(spec, previous_observations))
        elif isinstance(spec, SkillFolderSurfaceSpec):
            observations.extend(_observe_skill_folder(spec, previous_observations))
        else:
            observations.extend(_observe_rules_file(spec, previous_observations))
    return tuple(observations)


# --- per-file surfaces ----------------------------------------------------------------


def _observe_directory(
    spec: DirectorySurfaceSpec, previous: PreviousObservations
) -> list[SurfaceObservation]:
    if not spec.directory.is_dir():
        return []
    return [
        _observe_file(ToolSurface(spec.tool, spec.kind, path, spec.surface_format), previous)
        for path in sorted(spec.directory.iterdir())
        if path.is_file() and path.name.endswith(spec.filename_suffix)
    ]


def _observe_skill_folder(
    spec: SkillFolderSurfaceSpec, previous: PreviousObservations
) -> list[SurfaceObservation]:
    """Every ``<slug>/SKILL.md`` under the skill directory is one surface (FR-06).

    The folder is the artifact, so the files beside ``SKILL.md`` are read as the
    document's ``auxiliary_files`` (S23i) and folded into the surface digest. A
    folder that breaches the size bounds is frozen rather than partly adopted:
    the error is caught per folder into a ``ParseFailure`` — loud but isolated
    (FR-02), exactly like ``_resolve_rules_imports_in``'s import failures."""
    if not spec.directory.is_dir():
        return []
    observations: list[SurfaceObservation] = []
    for skill_dir in sorted(spec.directory.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / SKILL_FILENAME
        surface = ToolSurface(spec.tool, spec.kind, skill_md, spec.surface_format)
        if not skill_md.is_file():
            continue
        observations.append(_attach_auxiliary_files(_observe_file(surface, previous), skill_dir))
    return observations


def _attach_auxiliary_files(observation: SurfaceObservation, skill_dir: Path) -> SurfaceObservation:
    """Fold the folder's non-``SKILL.md`` files into the parsed document and digest.

    The digest must cover them or an edit to a reference file would never surface
    as a change; the executor's ``surface_content_digest`` composes the same way,
    so a write records what the next poll will observe (NFR-05).
    """
    parsed = observation.parsed
    if isinstance(parsed, ParseFailure):
        return observation
    try:
        auxiliary_files = read_auxiliary_files(skill_dir)
    except (OSError, ParserBoundsExceeded) as error:
        return replace(observation, parsed=ParseFailure(f"unreadable skill folder: {error}"))
    if not auxiliary_files:
        return observation
    return replace(
        observation,
        content_digest=_compose_skill_digest(
            observation.content_digest, auxiliary_files_digest(auxiliary_files)
        ),
        parsed=replace(parsed, auxiliary_files=auxiliary_files),
    )


def _compose_skill_digest(skill_md_digest: str, auxiliary_digest: str) -> str:
    """One digest over the whole folder: its ``SKILL.md`` and its auxiliary files."""
    return _text_digest(f"{skill_md_digest}\0{auxiliary_digest}")


def _observe_rules_file(
    spec: RulesFileSurfaceSpec, previous: PreviousObservations
) -> list[SurfaceObservation]:
    for filename in spec.candidate_filenames:  # ordered: first present wins (FR-10)
        path = spec.directory / filename
        if path.is_file():
            surface = ToolSurface(spec.tool, spec.kind, path, spec.surface_format)
            # No reuse cache for rules: imports must re-resolve every poll (an edit
            # behind the pointer is content), and there is at most one rules file
            # per tool, so the saving would be nil anyway.
            observed = _name_unnamed_artifact(_observe_file(surface, _NO_HISTORY), spec)
            return [_resolve_rules_imports_in(observed, spec)]
    return []


def _name_unnamed_artifact(
    observation: SurfaceObservation, spec: RulesFileSurfaceSpec
) -> SurfaceObservation:
    """Give a nameless whole-file rules artifact the name its recipe declares.

    A plain ``AGENTS.md`` carries no front matter, so it parses with an empty name —
    and an empty name slugifies to a placeholder, which would be the slug the
    artifact reconciles and projects under. Naming it here, at the one seam that
    knows the recipe, keeps the dialect free of a rules-specific constant. A file
    that *does* declare a name keeps it; nothing overrides the user.
    """
    parsed = observation.parsed
    if isinstance(parsed, ParseFailure) or parsed.name or not spec.default_artifact_name:
        return observation
    return replace(observation, parsed=replace(parsed, name=spec.default_artifact_name))


def _resolve_rules_imports_in(
    observation: SurfaceObservation, spec: RulesFileSurfaceSpec
) -> SurfaceObservation:
    """Split the rules body into source and effective (US-15): ``@import`` directives
    inline into the effective body (what propagates); the user's directive-bearing
    source body is preserved for the origin tool under ``rules_source_body``.
    Imported content is content — it joins the digest, so an edit behind the
    pointer surfaces as a change. A bad import (escape/cycle/missing/too deep) is
    malformed content -> ``ParseFailure`` -> freeze."""
    parsed = observation.parsed
    if isinstance(parsed, ParseFailure):
        return observation
    try:
        effective_body, had_imports = inline_rules_imports(parsed.body, spec.directory)
    except RulesImportError as error:
        return replace(observation, parsed=ParseFailure(str(error)))
    if not had_imports:
        return observation
    tool_bags = {tool: dict(bag) for tool, bag in parsed.per_tool_only.items()}
    tool_bags.setdefault(spec.tool, {})["rules_source_body"] = parsed.body
    return replace(
        observation,
        content_digest=_text_digest(f"{observation.content_digest}\0{effective_body}"),
        parsed=replace(parsed, body=effective_body, per_tool_only=tool_bags),
    )


def _observe_file(tool_surface: ToolSurface, previous: PreviousObservations) -> SurfaceObservation:
    location = tool_surface.location
    assert isinstance(location, Path)
    modified_time = _modified_time(location)
    try:
        text = read_text_bounded(location)
    except (OSError, UnicodeDecodeError, MalformedSurfaceError) as error:
        return SurfaceObservation(
            tool_surface=tool_surface,
            modified_time=modified_time,
            parsed=ParseFailure(f"unreadable surface: {error}"),
        )
    content_digest = _text_digest(text)
    prior = previous.get(location)
    if prior is not None and prior.content_digest == content_digest:
        # unchanged content parses to the same result — reuse, re-stat only mtime.
        return replace(prior, modified_time=modified_time)
    return SurfaceObservation(
        tool_surface=tool_surface,
        embedded_id=extract_artifact_id(text, tool_surface),
        content_digest=content_digest,
        modified_time=modified_time,
        parsed=_parse_or_failure(text, tool_surface),
    )


# --- keyed-map surfaces ---------------------------------------------------------------


def _observe_keyed_map(
    spec: KeyedMapSurfaceSpec, previous: PreviousObservations
) -> list[SurfaceObservation]:
    if not spec.file.is_file():
        return []
    modified_time = _modified_time(spec.file)
    try:
        text = read_text_bounded(spec.file)
        slot_map = _navigate_slot_map(
            deserialize(text, spec.surface_format.file_format),
            spec.surface_format.map_key_path,
        )
    except (OSError, UnicodeDecodeError, MalformedSurfaceError) as error:
        return _freeze_known_slots(spec, previous, modified_time, str(error))

    observations: list[SurfaceObservation] = []
    for slot_key in sorted(slot_map):
        location = KeyedMapSlot(file=spec.file, slot=slot_key)
        tool_surface = ToolSurface(spec.tool, spec.kind, location, spec.surface_format)
        slot_value = slot_map[slot_key]
        content_digest = _slot_digest(slot_value)
        prior = previous.get(location)
        if prior is not None and prior.content_digest == content_digest:
            observations.append(replace(prior, modified_time=modified_time))
            continue
        observations.append(
            SurfaceObservation(
                tool_surface=tool_surface,
                embedded_id=extract_artifact_id(text, tool_surface),
                content_digest=content_digest,
                modified_time=modified_time,
                parsed=_parse_slot_or_failure(text, tool_surface, slot_value),
            )
        )
    return observations


def _parse_slot_or_failure(
    text: str, tool_surface: ToolSurface, slot_value: Any
) -> CanonicalDocument | ParseFailure:
    """Parse one slot, first refusing values the JSON-shaped pipeline cannot carry.

    A legal-but-foreign deserialized value (e.g. an unquoted TOML date) would
    survive parsing into the canonical and crash its JSON digest later — content
    the pipeline cannot represent is malformed content, frozen per slot."""
    try:
        json.dumps(slot_value, ensure_ascii=False)
    except TypeError:
        return ParseFailure("slot value is not JSON-representable (e.g. an unquoted TOML date)")
    return _parse_or_failure(text, tool_surface)


def _navigate_slot_map(root: dict[str, Any], map_key_path: tuple[str, ...]) -> dict[str, Any]:
    current: Any = root
    for key in map_key_path:
        current = current.get(key) if isinstance(current, dict) else None
    if not isinstance(current, dict):
        raise MalformedSurfaceError(f"keyed-map file has no slot map at {'.'.join(map_key_path)!r}")
    return current


def _freeze_known_slots(
    spec: KeyedMapSurfaceSpec,
    previous: PreviousObservations,
    modified_time: float,
    reason: str,
) -> list[SurfaceObservation]:
    """The file no longer deserializes: its previously-known slots surface as
    ``ParseFailure`` (the planner freezes them) rather than vanish (a removal)."""
    return [
        replace(
            prior,
            # A frozen observation must carry NO reusable digest: it pairs a
            # file-level failure with last-good content, and a stale digest would
            # make a restore-to-identical-bytes reuse the failure forever
            # (freeze-until-fixed, not freeze-until-changed).
            content_digest="",
            modified_time=modified_time,
            parsed=ParseFailure(f"keyed-map file no longer deserializes: {reason}"),
        )
        for location, prior in sorted(previous.items(), key=lambda item: str(item[0]))
        if isinstance(location, KeyedMapSlot) and location.file == spec.file
    ]


# --- shared mechanics -----------------------------------------------------------------


def projection_surfaces(
    surface_specs: tuple[SurfaceSpec, ...], kind: str, name: str
) -> tuple[ToolSurface, ...]:
    """Where an artifact of ``kind`` named ``name`` belongs on every declared surface.

    The read phase observes what *is* on disk; this derives what *should* be there —
    the surface an artifact would occupy on a tool that does not yet hold it. It is
    what lets the planner extend an artifact onto a tool with no copy (Goal 1) and
    re-extend onto one whose directory has returned (US-11 AC-3), neither of which can be
    expressed by observed surfaces alone.

    Deriving the location from ``slugify_name(name)`` — the same slug the
    reconciliation key uses — is what keeps minting safe: two artifacts that would
    land on one path necessarily share a key, so the planner's existing collision
    guard already refuses them and no minted write can silently displace another
    artifact. A spec whose directory does not exist yields nothing: an absent
    directory means the tool is not installed (US-11), and syncing must never
    create one.
    """
    slug = slugify_name(name)
    surfaces: list[ToolSurface] = []
    for spec in surface_specs:
        if spec.kind != kind:
            continue
        location = _projection_location(spec, slug, name)
        if location is not None:
            surfaces.append(ToolSurface(spec.tool, spec.kind, location, spec.surface_format))
    return tuple(surfaces)


def _projection_location(spec: SurfaceSpec, slug: str, name: str) -> Path | KeyedMapSlot | None:
    """The location ``spec`` would give an artifact, or ``None`` if its directory is absent."""
    if isinstance(spec, DirectorySurfaceSpec):
        if not spec.directory.is_dir():
            return None
        return spec.directory / f"{slug}{spec.filename_suffix}"
    if isinstance(spec, SkillFolderSurfaceSpec):
        if not spec.directory.is_dir():
            return None
        return spec.directory / slug / SKILL_FILENAME
    if isinstance(spec, RulesFileSurfaceSpec):
        if not spec.directory.is_dir():
            return None
        # FR-10: a rules file that does not exist yet is created under the
        # highest-precedence declared filename (``AGENTS.md`` where offered).
        return spec.directory / spec.candidate_filenames[0]
    if not spec.file.parent.is_dir():
        return None
    # A keyed-map slot is keyed by the artifact's own name, not its slug: the slot key
    # is wire data the tool reads back, not a filesystem basename.
    return KeyedMapSlot(spec.file, name)


def surface_content_digest(
    text: str,
    tool_surface: ToolSurface,
    auxiliary_files: Mapping[str, AuxiliaryFile] | None = None,
) -> str:
    """The digest this read phase would observe for ``text`` at ``tool_surface``.

    The executor records it after a write, so the next poll sees the written
    surface as unchanged (NFR-05). Keyed-map slots digest their slot VALUE (the
    canonical JSON form), per-file surfaces the raw text. Rules surfaces with
    imports use a composite recipe the executor does not yet write (S20).

    A skill surface digests the whole folder: ``auxiliary_files`` composes in
    exactly as ``_attach_auxiliary_files`` composes it on the read side, so a
    written folder and the next poll's observation of it agree."""
    if auxiliary_files:
        return _compose_skill_digest(
            _text_digest(text), auxiliary_files_digest(dict(auxiliary_files))
        )
    location = tool_surface.location
    if isinstance(location, KeyedMapSlot):
        slot_map = _navigate_slot_map(
            deserialize(text, tool_surface.surface_format.file_format),
            tool_surface.surface_format.map_key_path,
        )
        return _slot_digest(slot_map[location.slot])
    return _text_digest(text)


def _parse_or_failure(text: str, tool_surface: ToolSurface) -> CanonicalDocument | ParseFailure:
    try:
        return file_to_canonical(text, tool_surface, None)
    except MalformedSurfaceError as error:
        return ParseFailure(str(error))


def _text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slot_digest(slot_value: Any) -> str:
    """One slot's content digest: its canonical JSON serialization, key-order free.

    ``default=repr`` keeps the digest total over everything ``deserialize`` can
    emit (e.g. TOML dates) — change detection must never raise."""
    payload = json.dumps(slot_value, sort_keys=True, ensure_ascii=False, default=repr)
    return _text_digest(payload)


def _modified_time(path: Path) -> float:
    """The surface's mtime; ``0.0`` on a stat race (file vanished between checks).

    The epoch sentinel makes the racing surface lose any freshest-content tiebreak
    this poll — the conservative outcome; the next poll re-stats it."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
