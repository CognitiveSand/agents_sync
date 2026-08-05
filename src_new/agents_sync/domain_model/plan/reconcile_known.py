"""Reconcile a known artifact — a short pipeline of guards (§7.2, S6a–S6c).

One already-managed artifact's fate, in precedence order: **freeze** if any surface
won't parse (FR-11); **rebuild** if the stored canonical is corrupt (US-09 AC-4);
**remove** if a recorded tool's surface vanished (US-11, short-circuiting content);
the **content rule** — detect the changed surfaces by digest, absorb the freshest,
and either rename (the canonical's slug moved — US-04) or project onto the others;
else **reproject** if the stored canonical changed out of band (an import — US-09).
The two integrity guards (freeze, rebuild) come first: a broken artifact is fixed
before it is acted on. *Unchanged* is the empty case, *conflict* is just ≥2 changed
(losers projected) — so absorb-one, conflict-many, and propagation are one rule. The
cross-artifact downgrades (slug clash → reject_collision, glitch → reproject) live in
S8. A pure ``mv`` (a moved surface, same digest) needs no intent — its tool still has
an observation, so it is not a vanish. Pure: no I/O, no clock, no randomness.
"""

from __future__ import annotations

from collections.abc import Sequence

from agents_sync.domain_model.artifact_naming import slugify_name
from agents_sync.domain_model.canonical_document import CanonicalDocument, CorruptCanonical
from agents_sync.domain_model.observation import ParseFailure, SurfaceObservation
from agents_sync.domain_model.plan.winner_selection import freshest
from agents_sync.domain_model.sync_plan import (
    AbsorbToolEdit,
    FreezeArtifact,
    ProjectToTools,
    RebuildCorruptCanonical,
    RemoveArtifact,
    RenameArtifact,
    ReprojectCanonical,
    SyncIntent,
)
from agents_sync.domain_model.sync_state import ArtifactRecord
from agents_sync.domain_model.tool_surface import ToolSurface

StoredCanonical = CanonicalDocument | CorruptCanonical


def reconcile_known(
    artifact_id: str,
    observations: Sequence[SurfaceObservation],
    record: ArtifactRecord,
    stored_canonical: StoredCanonical | None = None,
    expected_surfaces: Sequence[ToolSurface] = (),
) -> tuple[SyncIntent, ...]:
    """Decide one already-managed artifact's fate — a short pipeline of guards.

    ``stored_canonical`` is the artifact's truth loaded by the read phase; it is
    ``None`` until S8 wires it, in which case the canonical-authority checks are
    skipped (the content/shape decisions still apply).

    ``expected_surfaces`` is where this artifact belongs on every supporting tool
    whose directory exists — including tools that hold no copy of it. It is what lets
    the artifact reach a tool it has never been on (Goal 1) and return to one whose
    directory came back (US-11 AC-3); with the default empty sequence the rule is
    inert and the pipeline behaves exactly as before.
    """
    if any(isinstance(observation.parsed, ParseFailure) for observation in observations):
        return (FreezeArtifact(artifact_id),)
    if isinstance(stored_canonical, CorruptCanonical):
        return (RebuildCorruptCanonical(artifact_id),)
    if _has_vanished_surface(observations, record, expected_surfaces):
        return (RemoveArtifact(artifact_id),)
    changed = [observation for observation in observations if _has_changed(observation, record)]
    if changed:
        return _absorb_change(artifact_id, observations, record, changed, expected_surfaces)
    if _canonical_moved_out_of_band(stored_canonical, record):
        return (ReprojectCanonical(artifact_id),)
    missing = _unoccupied_surfaces(observations, record, expected_surfaces)
    if missing:
        # Nothing changed, yet a supporting tool has no copy: extend onto it. This is
        # the steady-state half of propagation — a newly adopted artifact reaching the
        # other tools, and a tool whose directory returned being re-extended (US-11 AC-3).
        return (ProjectToTools(artifact_id, missing),)
    return ()


def _unoccupied_surfaces(
    observations: Sequence[SurfaceObservation],
    record: ArtifactRecord,
    expected_surfaces: Sequence[ToolSurface],
) -> tuple[ToolSurface, ...]:
    """Expected surfaces on tools that neither hold this artifact nor recorded it.

    A tool is occupied when it was observed carrying the artifact this poll or the
    record already places it there — the latter matters because a recorded tool whose
    surface merely vanished is a *removal*, decided earlier in the pipeline, and must
    never be silently re-created here.
    """
    occupied = {observation.tool_surface.tool for observation in observations}
    occupied |= set(record.surfaces)
    return tuple(surface for surface in expected_surfaces if surface.tool not in occupied)


def _absorb_change(
    artifact_id: str,
    observations: Sequence[SurfaceObservation],
    record: ArtifactRecord,
    changed: Sequence[SurfaceObservation],
    expected_surfaces: Sequence[ToolSurface] = (),
) -> tuple[SyncIntent, ...]:
    """Absorb the freshest changed surface, then rename or project onto the rest."""
    winner = freshest(changed)
    winner_canonical = winner.parsed
    assert isinstance(winner_canonical, CanonicalDocument)  # the freeze guard ruled out a failure
    intents: list[SyncIntent] = [AbsorbToolEdit(artifact_id, winner.tool_surface)]
    if slugify_name(winner_canonical.name) != slugify_name(record.name):
        # The name moved, so its slug did — rename relocates every projection (it
        # subsumes the projection step, which writes to the old-slug locations).
        intents.append(RenameArtifact(artifact_id, winner_canonical.name))
    else:
        # The edit goes to the tools that hold the artifact AND to any supporting tool
        # that does not yet — an edit is how a new artifact first reaches its siblings,
        # so restricting targets to observed surfaces would strand it on its origin.
        targets = tuple(o.tool_surface for o in observations if o is not winner)
        targets += _unoccupied_surfaces(observations, record, expected_surfaces)
        if targets:
            intents.append(ProjectToTools(artifact_id, targets))
    return tuple(intents)


def _canonical_moved_out_of_band(
    stored_canonical: StoredCanonical | None,
    record: ArtifactRecord,
) -> bool:
    """True iff the stored canonical's digest differs from the recorded one (an import)."""
    return (
        isinstance(stored_canonical, CanonicalDocument)
        and stored_canonical.content_digest() != record.canonical_digest
    )


def vanished_tools(
    observations: Sequence[SurfaceObservation],
    record: ArtifactRecord,
) -> set[str]:
    """The recorded tools with no observation this poll — where the artifact vanished (US-11).

    Keyed on tool presence, so a surface that merely moved location still counts as present
    (it has an observation) — that is the ``mv`` case, not a vanish. This is the one home for
    the vanish rule; the glitch guard (``compute_sync_plan``) reuses it so the removal it
    rewrites and the vanish it keys on can never drift apart.
    """
    observed_tools = {observation.tool_surface.tool for observation in observations}
    return {tool for tool in record.surfaces if tool not in observed_tools}


def _has_vanished_surface(
    observations: Sequence[SurfaceObservation],
    record: ArtifactRecord,
    expected_surfaces: Sequence[ToolSurface] = (),
) -> bool:
    """True iff a recorded surface is missing from a directory we could actually read.

    A missing file is only evidence of deletion if we looked where it should be. An
    unreadable directory — the tool uninstalled, the drive unmounted — produces the
    same empty result as a directory the user emptied, and treating the two alike
    deletes the artifact from every healthy tool (US-11 AC-4: only an ``available``
    agentic_tool can cause a removal).

    ``expected_surfaces`` already carries that distinction: it is built by
    ``projection_surfaces``, which skips any surface whose directory is absent, per
    kind — so a tool listed there is one we could look at. Judging it per tool would
    not do: a tool whose ``agent`` directory vanished while its ``skill`` directory
    survives is still reachable *as a tool*, and its agents would still be deleted.

    With no expected surfaces the artifact has no stored canonical to derive them
    from, so reachability is unknown and the historic behaviour stands.
    """
    vanished = vanished_tools(observations, record)
    if not expected_surfaces:
        return bool(vanished)
    reachable = {surface.tool for surface in expected_surfaces}
    return any(tool in reachable for tool in vanished)


def _has_changed(observation: SurfaceObservation, record: ArtifactRecord) -> bool:
    """True iff a recorded surface's content digest moved (digest is the detector)."""
    recorded = record.surfaces.get(observation.tool_surface.tool)
    return recorded is not None and observation.content_digest != recorded.content_digest
