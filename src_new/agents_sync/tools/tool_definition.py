"""Tool definitions — the recipe types tools-as-data instantiate (pure data, §13).

A ``ToolDefinition`` is one tool's complete integration: a tuple of per-kind
surface recipes, each pairing a config key (resolved to a real path by the
runtime config, S21) with its ``default_location``, the layout, and the
``SurfaceFormat`` the read phase and translation need. Carrying the default
location as data keeps the NFR-11 "matching configuration entry" in the tool's
own module. Adding a tool is one data module plus a registry entry; no
sync-mechanism change (NFR-11). Recipes carry no callables — behaviour lives in
the dialects, selected by the format's ``dialect`` field.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agents_sync.domain_model.tool_surface import SurfaceFormat


class PathAnchor(Enum):
    """The platform-neutral base a surface's default location is relative to.

    ``runtime_config`` (S21b) resolves each anchor to a real directory per OS:
    ``HOME`` is the user's home directory; ``CONFIG_ROOT`` is the per-OS config
    dir (``~/.config`` on POSIX, ``%APPDATA%`` on Windows)."""

    HOME = "home"
    CONFIG_ROOT = "config_root"


@dataclass(frozen=True)
class DefaultLocation:
    """A surface's built-in default path, as data: an anchor plus the parts
    joined under it. ``runtime_config`` resolves the anchor and joins the parts.
    A surface with no built-in default declares ``default_location=None``.

    ``relative_parts`` resolves to a directory for directory recipes and to a
    file for keyed-map / single-file recipes; the target kind is the consuming
    recipe's, not ``DefaultLocation``'s."""

    anchor: PathAnchor
    relative_parts: tuple[str, ...]


@dataclass(frozen=True)
class DirectorySurfaceRecipe:
    """Per-file artifacts in a configured directory (agents, commands, rule files)."""

    kind: str
    config_key: str
    filename_suffix: str
    surface_format: SurfaceFormat
    default_location: DefaultLocation | None


@dataclass(frozen=True)
class KeyedMapSurfaceRecipe:
    """Artifacts as slots of one configured shared keyed-map file (mcp servers)."""

    kind: str
    config_key: str
    surface_format: SurfaceFormat
    default_location: DefaultLocation | None


@dataclass(frozen=True)
class RulesFileSurfaceRecipe:
    """The whole-file global-rules family: an ordered filename precedence (FR-10).

    ``default_artifact_name`` is the name an artifact on this surface takes when the
    file declares none. A whole-file rules document is plain markdown — ``AGENTS.md``
    carries no front matter — so unlike every other surface its format supplies no
    name, and without a default it would fall through to ``slugify_name``'s
    placeholder slug. The name is what the artifact is reconciled and projected
    under, so it must be a real identity, and it belongs here as recipe data rather
    than as a constant inside the dialect (tools-as-data, NFR-11).
    """

    kind: str
    config_key: str
    candidate_filenames: tuple[str, ...]
    surface_format: SurfaceFormat
    default_location: DefaultLocation | None
    default_artifact_name: str = ""


@dataclass(frozen=True)
class SkillFolderSurfaceRecipe:
    """Skills: a folder per artifact, each holding a ``SKILL.md`` (FR-06, S23f).

    The artifact lives at ``<default_location>/<slug>/SKILL.md``; its identity is the
    ``pair_id`` embedded in the SKILL.md front-matter (the folder name is cosmetic),
    so the ``surface_format`` is the same markdown-frontmatter recipe an agent uses.
    Auxiliary files inside a skill folder are deferred to S23i — until then a folder
    carrying anything besides ``SKILL.md`` is frozen loudly, never truncated."""

    kind: str
    config_key: str
    surface_format: SurfaceFormat
    default_location: DefaultLocation | None


type SurfaceRecipe = (
    DirectorySurfaceRecipe
    | KeyedMapSurfaceRecipe
    | RulesFileSurfaceRecipe
    | SkillFolderSurfaceRecipe
)


@dataclass(frozen=True)
class ToolDefinition:
    """One tool's integration, as data: its name and its per-kind surface recipes.

    Kinds a tool supports but the rebuild's dialects do not yet (directory-tree
    skills) are absent from ``surface_recipes`` until their dialect lands."""

    name: str
    surface_recipes: tuple[SurfaceRecipe, ...] = ()
