"""A multi-file skill survives every path that reconstructs it (S23i).

A ``skill`` artifact is a folder: ``SKILL.md`` plus reference material, scripts and
assets beside it. Before S23i the canonical carried only the ``SKILL.md`` body, so
any path that rebuilt a skill from the store produced a folder holding just that
one file — and, because the executor then recorded the truncated folder's digest,
no later poll ever noticed. These tests pin the end-to-end guarantee across the
three paths that rebuild a folder: propagation to another tool, projection over a
truncated folder (the heal), and export→import onto another machine.

Regression for the field-reported ``references/`` data loss; see
``docs/amendment/021-skill-auxiliary-files-survive-projection.md``.
"""

from __future__ import annotations

from pathlib import Path

from agents_sync.canonical_store import list_canonical_ids, load_canonical
from agents_sync.domain_model.canonical_document import CanonicalDocument
from agents_sync.domain_model.sync_state import SyncState
from agents_sync.portable_library import export_library, import_library
from agents_sync.sync_once import sync_once
from agents_sync.tools.agentic_tools_registry import tool_definition

_TWO_TOOL_DEFINITIONS = (tool_definition("claude"), tool_definition("cursor"))

# Adoption, then projection: two polls suffice today. The bound is a runaway guard,
# not an expectation — a test that needs more polls than this has found a real loop.
_MAX_POLLS_TO_SETTLE = 5
AUXILIARY_RELATIVE_PATH = "references/detail.md"
AUXILIARY_CONTENT = "the single home of this skill's detail\n"
# A PNG header: bytes that are not valid UTF-8, so they must survive as base64.
BINARY_CONTENT = b"\x89PNG\r\n\x1a\n\x00\xff\xfe"


def _skill_workspace(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, Path]]:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    claude_skills = tmp_path / "claude" / "skills"
    cursor_skills = tmp_path / "cursor" / "skills"
    claude_skills.mkdir(parents=True)
    cursor_skills.mkdir(parents=True)
    resolved = {"claude_skills_dir": claude_skills, "cursor_skills_dir": cursor_skills}
    return state_dir, claude_skills, cursor_skills, resolved


def _plant_skill(root: Path, slug: str = "demo", body: str = "Body.\n") -> Path:
    folder = root / slug
    (folder / "references").mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\nname: {slug}\n---\n{body}", encoding="utf-8")
    (folder / AUXILIARY_RELATIVE_PATH).write_text(AUXILIARY_CONTENT, encoding="utf-8")
    return folder


def _plant_on_both(claude_skills: Path, cursor_skills: Path) -> tuple[Path, Path]:
    """The same skill on two tools.

    The rebuild reconciles these into ONE artifact recorded on both surfaces, which
    is the state every projection path starts from. (It does not yet create an
    artifact on a tool that has no copy — ``reconcile_known._absorb_change`` draws
    its targets from observed surfaces only — so a one-tool plant would never
    reach the other tool at all, for skills or agents alike.)
    """
    return _plant_skill(claude_skills), _plant_skill(cursor_skills)


def _sync(state_dir: Path, resolved: dict[str, Path], state: SyncState) -> SyncState:
    _result, _observations, new_state = sync_once(
        state_dir, resolved, state, {}, tool_definitions=_TWO_TOOL_DEFINITIONS
    )
    return new_state


def _sync_until_settled(state_dir: Path, resolved: dict[str, Path], state: SyncState) -> SyncState:
    """Poll until the daemon reaches steady state.

    Adoption mints and injects the id in one poll; projecting onto the other tools
    is the next poll's work — the project's own goal is propagation "within at most
    two polling intervals", so a settled outcome takes more than one call.
    """
    for _ in range(_MAX_POLLS_TO_SETTLE):
        result, _observations, state = sync_once(
            state_dir, resolved, state, {}, tool_definitions=_TWO_TOOL_DEFINITIONS
        )
        if result.changed == 0:
            return state
    raise AssertionError("the daemon never reached steady state")


def test_adoption_carries_auxiliary_files_into_the_canonical(tmp_path: Path) -> None:
    state_dir, claude_skills, _cursor, resolved = _skill_workspace(tmp_path)
    _plant_skill(claude_skills)

    _sync(state_dir, resolved, SyncState())

    [artifact_id] = list_canonical_ids(state_dir)
    stored = load_canonical(state_dir, artifact_id)
    assert isinstance(stored, CanonicalDocument)
    # The store holds the whole artifact, not just its front page (NFR-16).
    assert stored.auxiliary_files[AUXILIARY_RELATIVE_PATH].to_bytes() == (
        AUXILIARY_CONTENT.encode()
    )


def test_projection_repairs_a_truncated_folder(tmp_path: Path) -> None:
    """The field-reported defect: a folder holding the right SKILL.md but missing
    everything beside it must be repaired, not mistaken for up to date."""
    state_dir, claude_skills, cursor_skills, resolved = _skill_workspace(tmp_path)
    claude_folder, _cursor_folder = _plant_on_both(claude_skills, cursor_skills)
    state = _sync_until_settled(state_dir, resolved, SyncState())
    truncated = cursor_skills / "demo" / AUXILIARY_RELATIVE_PATH
    assert truncated.exists()

    # The truncation: SKILL.md stays correct, everything beside it disappears.
    truncated.unlink()
    truncated.parent.rmdir()
    # An edit on the other tool makes this artifact the poll's work, so the
    # truncated folder is a projection target (the heal's analogue in this tree).
    (claude_folder / "SKILL.md").write_text(
        "---\nname: demo\n---\nEdited body.\n", encoding="utf-8"
    )
    _sync_until_settled(state_dir, resolved, state)

    assert truncated.read_text() == AUXILIARY_CONTENT


def test_projection_writes_the_folder_even_when_skill_md_is_unchanged(tmp_path: Path) -> None:
    """The subtle half of the defect: a target whose SKILL.md already matches must
    still be rewritten when its auxiliary files do not. Comparing rendered text
    alone would skip it as up to date and leave the truncation in place."""
    state_dir, claude_skills, cursor_skills, resolved = _skill_workspace(tmp_path)
    claude_folder, _cursor_folder = _plant_on_both(claude_skills, cursor_skills)
    state = _sync_until_settled(state_dir, resolved, SyncState())

    (cursor_skills / "demo" / AUXILIARY_RELATIVE_PATH).unlink()
    # Touch only the auxiliary side on the winning tool: SKILL.md renders identically.
    (claude_folder / AUXILIARY_RELATIVE_PATH).write_text("edited detail\n", encoding="utf-8")
    _sync_until_settled(state_dir, resolved, state)

    assert (cursor_skills / "demo" / AUXILIARY_RELATIVE_PATH).read_text() == "edited detail\n"


def test_binary_auxiliary_files_survive_byte_for_byte(tmp_path: Path) -> None:
    # NFR-06: a PNG is not valid UTF-8, so it round-trips through base64 and must
    # come back identical rather than mangled by a text decode.
    state_dir, claude_skills, cursor_skills, resolved = _skill_workspace(tmp_path)
    claude_folder, _cursor_folder = _plant_on_both(claude_skills, cursor_skills)
    state = _sync_until_settled(state_dir, resolved, SyncState())

    (claude_folder / "logo.png").write_bytes(BINARY_CONTENT)
    _sync_until_settled(state_dir, resolved, state)

    assert (cursor_skills / "demo" / "logo.png").read_bytes() == BINARY_CONTENT


def test_a_multi_file_skill_survives_export_then_import(tmp_path: Path) -> None:
    """US-12: a library carried to another machine must restore whole skills.

    The export ships canonical documents, so before S23i it carried a skill's front
    page and nothing else — the same truncation as the heal, crossing a machine
    boundary instead of a tool boundary.
    """
    state_dir, claude_skills, _cursor, resolved = _skill_workspace(tmp_path)
    folder = _plant_skill(claude_skills)
    (folder / "logo.png").write_bytes(BINARY_CONTENT)
    _sync(state_dir, resolved, SyncState())
    [artifact_id] = list_canonical_ids(state_dir)

    export_path = tmp_path / "library.zip"
    export_library(state_dir, export_path)
    receiving_state_dir = tmp_path / "other-machine"
    receiving_state_dir.mkdir()
    import_library(receiving_state_dir, export_path)

    restored = load_canonical(receiving_state_dir, artifact_id)
    assert isinstance(restored, CanonicalDocument)
    assert restored.auxiliary_files[AUXILIARY_RELATIVE_PATH].to_bytes() == (
        AUXILIARY_CONTENT.encode()
    )
    assert restored.auxiliary_files["logo.png"].to_bytes() == BINARY_CONTENT


def test_an_executable_auxiliary_file_stays_executable(tmp_path: Path) -> None:
    """US-01 AC-10: a skill that ships a helper script is only useful if the script
    stays runnable where it lands, and mode is not recoverable from content."""
    state_dir, claude_skills, cursor_skills, resolved = _skill_workspace(tmp_path)
    claude_folder, _cursor_folder = _plant_on_both(claude_skills, cursor_skills)
    state = _sync_until_settled(state_dir, resolved, SyncState())

    script = claude_folder / "run.sh"
    script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    script.chmod(0o755)
    _sync_until_settled(state_dir, resolved, state)

    projected = cursor_skills / "demo" / "run.sh"
    assert projected.stat().st_mode & 0o111, "the propagated script lost its execute bit"


def test_a_non_executable_auxiliary_file_is_not_made_executable(tmp_path: Path) -> None:
    # The flag must travel per file, not be applied to the whole folder.
    state_dir, claude_skills, cursor_skills, resolved = _skill_workspace(tmp_path)
    _plant_on_both(claude_skills, cursor_skills)
    _sync_until_settled(state_dir, resolved, SyncState())

    projected = cursor_skills / "demo" / AUXILIARY_RELATIVE_PATH
    assert not projected.stat().st_mode & 0o111


def test_a_settled_multi_file_skill_produces_no_further_writes(tmp_path: Path) -> None:
    # NFR-05: the recorded digest describes the whole folder, so a second poll over
    # an unchanged multi-file skill is a no-op rather than an endless rewrite.
    state_dir, claude_skills, _cursor, resolved = _skill_workspace(tmp_path)
    _plant_skill(claude_skills)
    state = _sync_until_settled(state_dir, resolved, SyncState())

    result, _observations, _state = sync_once(
        state_dir, resolved, state, {}, tool_definitions=_TWO_TOOL_DEFINITIONS
    )

    assert result.changed == 0


def test_an_edit_to_an_auxiliary_file_propagates(tmp_path: Path) -> None:
    state_dir, claude_skills, cursor_skills, resolved = _skill_workspace(tmp_path)
    claude_folder, _cursor_folder = _plant_on_both(claude_skills, cursor_skills)
    state = _sync_until_settled(state_dir, resolved, SyncState())

    (claude_folder / AUXILIARY_RELATIVE_PATH).write_text("rewritten detail\n", encoding="utf-8")
    _sync_until_settled(state_dir, resolved, state)

    assert (cursor_skills / "demo" / AUXILIARY_RELATIVE_PATH).read_text() == "rewritten detail\n"
