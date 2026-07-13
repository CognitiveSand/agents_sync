"""Skill (SKILL.md-only) customization_type — round-trip, identity, fail-loud (S23f, FR-06).

A ``skill`` is a folder-per-artifact: ``<root>/<slug>/SKILL.md``. The SKILL.md body
reuses the ``markdown_frontmatter`` dialect (like an agent), so its ``pair_id`` carries
identity and the folder name is cosmetic. Auxiliary files inside a skill folder are
deferred to S23i; until then a folder carrying anything besides ``SKILL.md`` is frozen
loudly (a ``ParseFailure``), never silently truncated (amendment 020, §8 fail-loud).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents_sync.domain_model.canonical_document import CanonicalDocument
from agents_sync.domain_model.observation import ParseFailure
from agents_sync.domain_model.tool_surface import ToolSurface
from agents_sync.read_tool_surfaces import SkillFolderSurfaceSpec, read_tool_surfaces
from agents_sync.tools.agentic_tools_registry import (
    surface_specs_for,
    tool_definition,
)
from agents_sync.translation import canonical_to_file, extract_artifact_id, file_to_canonical

_ARTIFACT_ID = "11111111-1111-4111-8111-111111111111"
_AUX_ID = "22222222-2222-4222-8222-222222222222"

# Every tool whose supported_customization_types includes ``skill`` (project_description
# §problem-statement; copilot is deliberately absent).
_SKILL_TOOLS = ("claude", "codex", "cursor", "opencode", "gemini_cli", "antigravity")

# The tool → its resolved skills-root config key.
_SKILLS_DIR_KEY = {
    "claude": "claude_skills_dir",
    "codex": "codex_skills_dir",
    "cursor": "cursor_skills_dir",
    "opencode": "opencode_skills_dir",
    "gemini_cli": "gemini_cli_skills_dir",
    "antigravity": "antigravity_skills_dir",
}


def _skill_surface(tool_name: str, skill_md: Path) -> ToolSurface:
    """The tool's ``skill`` recipe as a ``ToolSurface`` at a ``SKILL.md`` path."""
    [recipe] = [r for r in tool_definition(tool_name).surface_recipes if r.kind == "skill"]
    return ToolSurface(tool_name, "skill", skill_md, recipe.surface_format)


def _skill_canonical(name: str = "formatter") -> CanonicalDocument:
    return CanonicalDocument(
        artifact_id=_ARTIFACT_ID,
        kind="skill",
        name=name,
        description="formats source files",
        body="Run the formatter, then report.\n",
    )


def _write_skill(root: Path, slug: str, artifact_id: str) -> Path:
    """Write ``<root>/<slug>/SKILL.md`` with an embedded id; return its folder."""
    skill_dir = root / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\npair_id: {artifact_id}\nname: {slug}\n---\nBody of {slug}.\n"
    )
    return skill_dir


# --- round-trip + cross-adapter (NFR-06 / FR-06) --------------------------------------


@pytest.mark.parametrize("tool_name", _SKILL_TOOLS)
def test_a_skill_round_trips_its_skill_md(tool_name: str, tmp_path: Path) -> None:
    # Every skill-supporting tool renders a SKILL.md and folds it back losslessly.
    surface = _skill_surface(tool_name, tmp_path / "SKILL.md")

    rendered = canonical_to_file(_skill_canonical(), surface, None)
    reparsed = file_to_canonical(rendered, surface, None)

    assert reparsed.name == "formatter", "skill name survives the round trip"
    assert reparsed.description == "formats source files"
    assert reparsed.body.strip() == "Run the formatter, then report."
    assert reparsed.artifact_id == _ARTIFACT_ID, "pair_id carries identity, never minted"


def test_a_skill_propagates_across_tools(tmp_path: Path) -> None:
    # FR-06: a skill edited on one tool surfaces on another that supports skills.
    claude_surface = _skill_surface("claude", tmp_path / "claude.md")
    antigravity_surface = _skill_surface("antigravity", tmp_path / "antigravity.md")

    claude_text = canonical_to_file(_skill_canonical(), claude_surface, None)
    via_claude = file_to_canonical(claude_text, claude_surface, None)
    antigravity_text = canonical_to_file(via_claude, antigravity_surface, None)
    via_antigravity = file_to_canonical(antigravity_text, antigravity_surface, None)

    assert via_antigravity.name == "formatter"
    assert via_antigravity.body.strip() == "Run the formatter, then report."
    assert via_antigravity.artifact_id == _ARTIFACT_ID


# --- identity through the read walker (FR-11) -----------------------------------------


def test_a_skill_is_observed_by_its_embedded_id(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill_dir = _write_skill(root, "formatter", _ARTIFACT_ID)
    specs = surface_specs_for(tool_definition("claude"), {"claude_skills_dir": root})

    observations = read_tool_surfaces(specs)

    [observation] = observations
    assert observation.tool_surface.kind == "skill"
    assert observation.tool_surface.location == skill_dir / "SKILL.md", (
        "the SKILL.md is the surface"
    )
    assert observation.embedded_id == _ARTIFACT_ID, "identity is the embedded pair_id"
    assert isinstance(observation.parsed, CanonicalDocument)
    assert observation.parsed.artifact_id == _ARTIFACT_ID
    # FR-11: the id is recoverable in isolation from the SKILL.md text alone.
    text = (skill_dir / "SKILL.md").read_text()
    assert extract_artifact_id(text, observation.tool_surface) == _ARTIFACT_ID


# --- fail-loud auxiliary-file guard (amendment 020, §8) -------------------------------


def test_a_skill_with_auxiliary_files_freezes_but_isolates(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    multi_dir = _write_skill(root, "multi", _AUX_ID)
    (multi_dir / "helper.py").write_text("print('hi')\n")  # an auxiliary file
    _write_skill(root, "solo", _ARTIFACT_ID)  # an aux-free sibling in the same root
    specs = surface_specs_for(tool_definition("claude"), {"claude_skills_dir": root})

    observations = read_tool_surfaces(specs)

    by_slug = {obs.tool_surface.location.parent.name: obs for obs in observations}
    # The aux-bearing skill is frozen loudly — named, never silently truncated.
    assert isinstance(by_slug["multi"].parsed, ParseFailure), "aux-bearing skill is frozen"
    assert "S23i" in by_slug["multi"].parsed.reason, "the freeze reason names the deferred step"
    assert "helper.py" in by_slug["multi"].parsed.reason, "the reason names the offending file"
    # Per-artifact isolation (FR-02, amendment 012): the sibling observes normally.
    assert isinstance(by_slug["solo"].parsed, CanonicalDocument), (
        "the aux-free sibling is unaffected"
    )
    assert by_slug["solo"].parsed.artifact_id == _ARTIFACT_ID


def test_a_subdirectory_inside_a_skill_folder_also_freezes(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill_dir = _write_skill(root, "nested", _ARTIFACT_ID)
    (skill_dir / "references").mkdir()  # a subdirectory is auxiliary content too
    specs = surface_specs_for(tool_definition("claude"), {"claude_skills_dir": root})

    observations = read_tool_surfaces(specs)

    [observation] = observations
    assert isinstance(observation.parsed, ParseFailure)
    assert "S23i" in observation.parsed.reason


# --- antigravity activation (was inert) -----------------------------------------------


@pytest.mark.parametrize("tool_name", _SKILL_TOOLS)
def test_every_skill_tool_resolves_a_skill_spec(tool_name: str, tmp_path: Path) -> None:
    # Each skill-supporting tool (incl. the once-inert antigravity) now produces a
    # SkillFolderSurfaceSpec from its skills root.
    specs = surface_specs_for(tool_definition(tool_name), {_SKILLS_DIR_KEY[tool_name]: tmp_path})

    skill_specs = [spec for spec in specs if spec.kind == "skill"]
    assert len(skill_specs) == 1, f"{tool_name} resolves exactly one skill spec"
    assert isinstance(skill_specs[0], SkillFolderSurfaceSpec)
    assert skill_specs[0].root == tmp_path
