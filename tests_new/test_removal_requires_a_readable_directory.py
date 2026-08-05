"""A missing file is only evidence of deletion if we looked where it should be.

US-11 AC-4: only an ``available`` agentic_tool can be the source of a removal signal.
An unreachable directory — the tool uninstalled, a drive unmounted — yields the same empty
result as a directory the user emptied, and treating the two alike propagated a removal to
every healthy tool. With three or more tools installed nothing suppressed it: the
two-tool destructive guard is a blast-radius limiter for a different requirement, and
it only masked the defect in the degenerate two-tool case.

The reachability signal is the artifact's expected surfaces, which
``projection_surfaces`` builds by testing each surface's own directory, per kind.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from agents_sync.domain_model.canonical_document import CanonicalDocument
from agents_sync.domain_model.observation import SurfaceObservation
from agents_sync.domain_model.plan.reconcile_known import reconcile_known
from agents_sync.domain_model.sync_plan import RemoveArtifact
from agents_sync.domain_model.sync_state import ArtifactRecord, RecordedSurface, SyncState
from agents_sync.domain_model.tool_surface import SurfaceFormat, ToolSurface
from agents_sync.sync_once import sync_once
from agents_sync.tools.agentic_tools_registry import tool_definition

# Three tools, so the two-tool destructive guard never fires and cannot be mistaken
# for the protection under test.
_THREE_TOOLS = ("claude", "cursor", "codex")
_DEFINITIONS = tuple(tool_definition(name) for name in _THREE_TOOLS)
_MAX_POLLS_TO_SETTLE = 8


def _workspace(tmp_path: Path) -> tuple[Path, dict[str, Path], dict[str, Path], dict[str, Path]]:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    resolved: dict[str, Path] = {}
    agent_directories: dict[str, Path] = {}
    skill_directories: dict[str, Path] = {}
    for name in _THREE_TOOLS:
        agents = tmp_path / name / "agents"
        skills = tmp_path / name / "skills"
        agents.mkdir(parents=True)
        skills.mkdir(parents=True)
        agent_directories[name] = agents
        skill_directories[name] = skills
        resolved[f"{name}_agents_dir"] = agents
        resolved[f"{name}_skills_dir"] = skills
    return state_dir, resolved, agent_directories, skill_directories


def _settle(
    state_dir: Path, resolved: dict[str, Path], state: SyncState, observations: dict
) -> tuple[SyncState, dict]:
    for _ in range(_MAX_POLLS_TO_SETTLE):
        result, observations, state = sync_once(
            state_dir, resolved, state, observations, tool_definitions=_DEFINITIONS
        )
        if result.changed == 0:
            return state, observations
    raise AssertionError("the daemon never reached steady state")


def _plant_and_settle(
    tmp_path: Path,
) -> tuple[Path, dict[str, Path], dict[str, Path], dict[str, Path], SyncState, dict]:
    state_dir, resolved, agent_directories, skill_directories = _workspace(tmp_path)
    (agent_directories["claude"] / "helper.md").write_text("---\nname: helper\n---\nBody.\n")
    state, observations = _settle(state_dir, resolved, SyncState(), {})
    return state_dir, resolved, agent_directories, skill_directories, state, observations


def test_an_uninstalled_tool_does_not_delete_the_artifact_elsewhere(tmp_path: Path) -> None:
    state_dir, resolved, agent_directories, _skills, state, observations = _plant_and_settle(
        tmp_path
    )
    assert (agent_directories["claude"] / "helper.md").exists()

    shutil.rmtree(agent_directories["cursor"])  # the tool is uninstalled
    _settle(state_dir, resolved, state, observations)

    assert (agent_directories["claude"] / "helper.md").exists()


def test_reachability_is_judged_per_kind_not_per_tool(tmp_path: Path) -> None:
    """A tool whose ``agent`` directory vanished while its ``skill`` directory survives is still
    reachable *as a tool*. Judging reachability at tool level would let its agents be
    deleted anyway — the granularity trap the legacy tree documented."""
    state_dir, resolved, agent_directories, skill_directories, state, observations = (
        _plant_and_settle(tmp_path)
    )

    shutil.rmtree(agent_directories["cursor"])  # only the agent directory goes
    assert skill_directories["cursor"].is_dir()  # the tool is still reachable overall
    _settle(state_dir, resolved, state, observations)

    assert (agent_directories["claude"] / "helper.md").exists()


def test_a_deletion_from_a_readable_directory_still_propagates(tmp_path: Path) -> None:
    # The rule must not become "never remove": a file missing from a directory we DID read
    # is a deliberate deletion and still propagates (US-05 AC-2).
    state_dir, resolved, agent_directories, _skills, state, observations = _plant_and_settle(
        tmp_path
    )
    assert (agent_directories["cursor"] / "helper.md").exists()

    (agent_directories["claude"] / "helper.md").unlink()
    _settle(state_dir, resolved, state, observations)

    assert not (agent_directories["cursor"] / "helper.md").exists()


def _surface(tool: str) -> ToolSurface:
    return ToolSurface(
        tool, "agent", Path(f"/{tool}/helper.md"), SurfaceFormat(dialect="markdown_frontmatter")
    )


def _record(*tools: str) -> ArtifactRecord:
    return ArtifactRecord(
        name="helper",
        surfaces={
            tool: RecordedSurface(location=Path(f"/{tool}/helper.md"), content_digest="d")
            for tool in tools
        },
    )


_ARTIFACT_ID = "11111111-1111-4111-8111-111111111111"
_PARSED = CanonicalDocument(artifact_id=_ARTIFACT_ID, kind="agent", name="helper")


def _observed(tool: str) -> SurfaceObservation:
    return SurfaceObservation(
        tool_surface=_surface(tool), content_digest="d", modified_time=1.0, parsed=_PARSED
    )


def test_planner_skips_removal_when_the_recorded_tool_is_unreachable() -> None:
    # claude still holds the artifact; cursor is recorded but absent from the expected
    # surfaces, which is how projection_surfaces reports a directory it could not read.
    intents = reconcile_known(
        _ARTIFACT_ID,
        [_observed("claude")],
        _record("claude", "cursor"),
        None,
        (_surface("claude"),),
    )

    assert not any(isinstance(intent, RemoveArtifact) for intent in intents)


def test_planner_still_removes_when_the_recorded_tool_is_reachable() -> None:
    # Same inputs, except cursor's directory WAS readable — so its missing file is a deletion.
    intents = reconcile_known(
        _ARTIFACT_ID,
        [_observed("claude")],
        _record("claude", "cursor"),
        None,
        (_surface("claude"), _surface("cursor")),
    )

    assert any(isinstance(intent, RemoveArtifact) for intent in intents)
