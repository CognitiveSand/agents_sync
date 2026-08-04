"""An artifact reaches a tool that has no copy of it (project description Goal 1).

The rebuild propagated edits *among* the tools already holding an artifact but never
created one on a tool that lacked it: projection targets came from observed surfaces,
and a tool with no copy produces no observation. That left the product's headline
promise — edit anywhere, appears everywhere — unimplemented for every kind, and it
also left US-11 AC-3 (re-extend onto a tool whose root returned) unreachable.

The fix derives, per artifact, where it *should* live on every supporting tool whose
root exists, and treats an unoccupied expected surface as a projection target. These
tests pin the promise and the two things it must not break: a deliberate removal must
never come back as an extension, and an absent root must never be created.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agents_sync.canonical_store import list_canonical_ids
from agents_sync.domain_model.sync_state import SyncState
from agents_sync.sync_once import sync_once
from agents_sync.tools.agentic_tools_registry import tool_definition

_TWO_TOOLS = (tool_definition("claude"), tool_definition("cursor"))
# Adoption, then extension: two polls today. The bound is a runaway guard, not an
# expectation — needing more than this means the poll never reaches steady state.
_MAX_POLLS_TO_SETTLE = 5


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, Path]]:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    claude = tmp_path / "claude" / "agents"
    cursor = tmp_path / "cursor" / "agents"
    claude.mkdir(parents=True)
    cursor.mkdir(parents=True)
    return (
        state_dir,
        claude,
        cursor,
        {
            "claude_agents_dir": claude,
            "cursor_agents_dir": cursor,
        },
    )


def _agent(name: str = "helper", body: str = "Help tersely.") -> str:
    return f"---\nname: {name}\n---\n{body}\n"


def _settle(state_dir: Path, resolved: dict[str, Path], state: SyncState) -> SyncState:
    for _ in range(_MAX_POLLS_TO_SETTLE):
        result, _observations, state = sync_once(
            state_dir, resolved, state, {}, tool_definitions=_TWO_TOOLS
        )
        if result.changed == 0:
            return state
    raise AssertionError("the daemon never reached steady state")


def test_a_new_artifact_reaches_a_tool_that_never_had_it(tmp_path: Path) -> None:
    state_dir, claude, cursor, resolved = _workspace(tmp_path)
    (claude / "helper.md").write_text(_agent())

    _settle(state_dir, resolved, SyncState())

    assert (cursor / "helper.md").exists()
    assert "Help tersely." in (cursor / "helper.md").read_text()
    assert len(list_canonical_ids(state_dir)) == 1  # one artifact, not one per tool


def test_the_projected_copy_carries_the_shared_identity(tmp_path: Path) -> None:
    # The created file is the same artifact, not a lookalike: its id must match, or the
    # next poll would adopt it as a second artifact and the two would fight.
    state_dir, claude, cursor, resolved = _workspace(tmp_path)
    (claude / "helper.md").write_text(_agent())

    _settle(state_dir, resolved, SyncState())

    [artifact_id] = list_canonical_ids(state_dir)
    assert artifact_id in (cursor / "helper.md").read_text()


def test_extension_settles_and_does_not_rewrite_every_poll(tmp_path: Path) -> None:
    # NFR-05: the extension is recorded, so the poll after it is a genuine no-op.
    state_dir, claude, _cursor, resolved = _workspace(tmp_path)
    (claude / "helper.md").write_text(_agent())
    state = _settle(state_dir, resolved, SyncState())

    result, _observations, _state = sync_once(
        state_dir, resolved, state, {}, tool_definitions=_TWO_TOOLS
    )

    assert result.changed == 0


def test_a_deliberate_removal_is_not_undone_by_extension(tmp_path: Path) -> None:
    """The dangerous interaction: removal empties a tool's surface, and an extension
    rule that only asked "is this tool missing a copy?" would immediately put it back,
    making deletion impossible. A recorded tool is occupied even when its surface is
    gone — that absence is a removal, decided earlier in the pipeline."""
    state_dir, claude, cursor, resolved = _workspace(tmp_path)
    (claude / "helper.md").write_text(_agent())
    state = _settle(state_dir, resolved, SyncState())
    assert (cursor / "helper.md").exists()

    (claude / "helper.md").unlink()  # the user deletes it on one tool
    state = _settle(state_dir, resolved, state)

    assert not (cursor / "helper.md").exists(), "removal was undone by re-extension"
    assert not (claude / "helper.md").exists(), "the deleted copy was recreated"


def test_an_absent_tool_root_is_never_created(tmp_path: Path) -> None:
    # US-11: a missing root means the tool is not installed. Syncing must not install
    # it — that would scatter files into directories the user never opted into.
    state_dir, claude, cursor, resolved = _workspace(tmp_path)
    (claude / "helper.md").write_text(_agent())
    shutil.rmtree(cursor)

    _settle(state_dir, resolved, SyncState())

    assert not cursor.exists()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Blocked by a separate, pre-existing defect shared with the legacy tree: a "
        "recorded tool whose root returns EMPTY is read as a deletion, so the artifact "
        "is removed from every healthy tool before the extension rule is reached "
        "(_has_vanished_surface short-circuits). Bytes survive in the archive (NFR-01) "
        "but the artifact disappears everywhere. Recorded in the cutover register; "
        "needs a US-11 availability decision, not a change here."
    ),
)
def test_an_artifact_re_extends_when_a_tool_root_returns(tmp_path: Path) -> None:
    """US-11 AC-3: a tool whose root vanished is not a removal source, and when the
    root comes back the artifact is projected onto it again."""
    state_dir, claude, cursor, resolved = _workspace(tmp_path)
    (claude / "helper.md").write_text(_agent())
    state = _settle(state_dir, resolved, SyncState())

    shutil.rmtree(cursor)  # the tool is uninstalled / its root unmounts
    state = _settle(state_dir, resolved, state)
    assert (claude / "helper.md").exists(), "an absent tool must not source a removal"

    cursor.mkdir(parents=True)  # the tool returns
    _settle(state_dir, resolved, state)

    assert (cursor / "helper.md").exists()
