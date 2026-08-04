"""A skill folder's auxiliary files survive a glitch heal (US-11 AC-9 + NFR-06).

A directory skill is a folder: ``SKILL.md`` plus whatever else the author put
beside it. The canonical document carries only the ``SKILL.md`` body, so a
projection that renders from the canonical *alone* produces a folder holding
just ``SKILL.md``. When that happens on a heal, ``update_state_n_way`` then
records the truncated tree as the tool's digest, so every later poll compares
truncated-to-truncated and no repair ever fires — the loss is silent and
permanent.

These tests pin the two halves of the guarantee:

- the heal sources auxiliary files from a tool copy that survived the glitch,
  so the folder comes back whole (the field-reported defect); and
- when no copy survives to source from, the daemon says so rather than
  quietly writing a half skill.

Regression for the ``references/``-subdirectory data loss; see
``docs/amendment/021-skill-auxiliary-files-survive-projection.md``.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

from agents_sync.canonical import empty_canonical, save_canonical, set_canonical_metadata
from agents_sync.state import CustomizationArtifactState, load_state, save_state
from agents_sync.sync import Syncer

from ._helpers import make_syncer, set_artifact_mtime, skill_md

# The glitch heuristic (US-11 AC-9) treats a tool as glitched only when >= 2 of
# its artifacts vanish in one poll; a lone disappearance is a deliberate
# deletion and propagates as a removal instead. Two skills is the minimum that
# reaches the heal path under test.
GLITCH_THRESHOLD_SKILL_COUNT = 2
AUXILIARY_RELATIVE_PATH = "references/detail.md"
AUXILIARY_CONTENT = "the single home of this skill's detail\n"


def _plant_skill_with_auxiliary_file(root: Path, name: str) -> Path:
    """Materialise a skill folder carrying one auxiliary file beside SKILL.md."""
    folder = root / name
    (folder / "references").mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(skill_md(name), encoding="utf-8")
    (folder / AUXILIARY_RELATIVE_PATH).write_text(AUXILIARY_CONTENT, encoding="utf-8")
    set_artifact_mtime(folder, 1_700_000_000.0)
    return folder


def _plant_and_propagate(tmp_path: Path) -> tuple[Syncer, Path, Path]:
    """Adopt two aux-carrying skills from claude and propagate them to codex."""
    syncer = make_syncer(tmp_path)
    claude_skills = syncer.tool_root("claude", "skill")
    codex_skills = syncer.tool_root("codex", "skill")
    for index in range(GLITCH_THRESHOLD_SKILL_COUNT):
        _plant_skill_with_auxiliary_file(claude_skills, f"demo{index}")
    syncer.sync_once()
    return syncer, claude_skills, codex_skills


def test_propagation_carries_auxiliary_files_to_a_new_tool(tmp_path: Path) -> None:
    # Baseline: the adoption path already copies the folder, aux files included.
    _syncer, _claude_skills, codex_skills = _plant_and_propagate(tmp_path)

    assert (codex_skills / "demo0" / AUXILIARY_RELATIVE_PATH).read_text() == AUXILIARY_CONTENT


def test_glitch_heal_restores_the_whole_folder_not_just_skill_md(tmp_path: Path) -> None:
    syncer, _claude_skills, codex_skills = _plant_and_propagate(tmp_path)

    # A whole tool's skills vanish at once: a glitch, so the pair is re-projected
    # from the canonical rather than treated as a deletion (US-11 AC-9).
    for index in range(GLITCH_THRESHOLD_SKILL_COUNT):
        shutil.rmtree(codex_skills / f"demo{index}")
    syncer.sync_once()

    restored = codex_skills / "demo0"
    assert (restored / "SKILL.md").exists()
    assert (restored / AUXILIARY_RELATIVE_PATH).read_text() == AUXILIARY_CONTENT


def test_healed_folder_is_recorded_whole_so_no_later_poll_diverges(tmp_path: Path) -> None:
    # NFR-05: the recorded digest must describe the restored tree, so the daemon
    # reaches steady state with the auxiliary file present rather than without it.
    syncer, _claude_skills, codex_skills = _plant_and_propagate(tmp_path)
    for index in range(GLITCH_THRESHOLD_SKILL_COUNT):
        shutil.rmtree(codex_skills / f"demo{index}")
    syncer.sync_once()

    assert syncer.sync_once().changed == 0
    assert (codex_skills / "demo0" / AUXILIARY_RELATIVE_PATH).exists()


def test_heal_without_a_surviving_copy_warns_instead_of_truncating_silently(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When every copy is gone the canonical cannot supply auxiliary files. The
    daemon still restores SKILL.md (a single-file skill must survive a glitch),
    but it must not do so silently — the truncated folder becomes the baseline."""
    syncer, _claude_skills, _codex_skills = _plant_and_propagate(tmp_path)

    # Every recorded copy disappears in one poll: nothing is left to source from.
    # The roots come from state so the test does not silently miss a tool as the
    # skill-capable set grows (it is five tools today, not the two planted from).
    recorded = load_state(syncer.state_dir)
    for artifact_state in recorded.values():
        for tool_state in artifact_state.agentic_tools.values():
            shutil.rmtree(tool_state.path, ignore_errors=True)
    with caplog.at_level(logging.WARNING):
        syncer.sync_once()

    assert "only SKILL.md can be restored" in caplog.text
    assert "demo0" in caplog.text


def test_zero_tool_import_stub_heals_without_a_spurious_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A freshly imported stub is recorded on zero tools and genuinely has no
    auxiliary files to lose, so the no-source warning must stay quiet there —
    otherwise every import would cry data loss. Guards the frozen stub-heal
    contract in ``test_heal_from_canonical.py``."""

    syncer = make_syncer(tmp_path)
    pair_id = "b3d1e2f4-0000-4000-8000-00000000abcd"
    canonical = empty_canonical("skill", pair_id)
    canonical["name"] = "imported"
    canonical["description"] = "d"
    canonical["body"] = "imported body"
    set_canonical_metadata(canonical, last_modified=1.0, generation=1)
    save_canonical(syncer.state_dir, pair_id, canonical)
    state = load_state(syncer.state_dir)
    state[pair_id] = CustomizationArtifactState(kind="skill", agentic_tools={})
    save_state(syncer.state_dir, state)

    with caplog.at_level(logging.WARNING):
        syncer.sync_once()

    assert (syncer.tool_root("claude", "skill") / "imported" / "SKILL.md").exists()
    assert "only SKILL.md can be restored" not in caplog.text
