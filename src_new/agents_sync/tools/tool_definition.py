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
from pathlib import Path

from agents_sync.domain_model.tool_surface import SurfaceFormat


class PathAnchor(Enum):
    """The platform-neutral base a surface's default location is relative to.

    ``runtime_config`` (S21b) resolves each anchor to a real directory per OS:
    ``HOME`` is the user's home directory; ``CONFIG_DIRECTORY`` is the per-OS
    configuration directory (``~/.config`` on POSIX, ``%APPDATA%`` on Windows)."""

    HOME = "home"
    CONFIG_DIRECTORY = "config_directory"


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


class Layout(Enum):
    """How a tool stores one kind of customization on disk.

    The four are irreducible — they come from the tools, not from us: a directory
    of files one per artifact; one file chosen from a precedence list; a folder per
    artifact; one entry inside a file shared with everything else of that kind.
    The read phase walks each differently, and this is what selects the walk.
    """

    DIRECTORY = "directory"
    RULES_FILE = "rules_file"
    SKILL_FOLDER = "skill_folder"
    KEYED_MAP = "keyed_map"


@dataclass(frozen=True)
class SurfaceRecipe:
    """How one tool stores one kind of customization: where to look, and how to read it.

    One shape for all four layouts. They previously had a class each, which meant the
    four fields every layout needs were declared four times — and two of those classes
    carried nothing else at all, existing only to be told apart by ``isinstance``.

    The trailing fields apply to some layouts and not others; each names the layout it
    belongs to. An unused one is inert, never consulted for a layout that has no use
    for it.
    """

    kind: str
    config_key: str
    surface_format: SurfaceFormat
    default_location: DefaultLocation | None
    layout: Layout

    #: ``DIRECTORY``: the suffix a file must carry to be one of this kind's artifacts.
    filename_suffix: str = ""
    #: ``RULES_FILE``: candidate filenames in precedence order; first present wins,
    #: and a file not on the list is never adopted (FR-10).
    candidate_filenames: tuple[str, ...] = ()
    #: ``RULES_FILE``: the name an artifact takes when its file declares none. A plain
    #: ``AGENTS.md`` has no front matter, so unlike every other surface its format
    #: supplies no name — and a nameless artifact would reconcile under
    #: ``slugify_name``'s placeholder. Recipe data, not a constant in the dialect
    #: (tools-as-data, NFR-11).
    default_artifact_name: str = ""


@dataclass(frozen=True)
class ResolvedRecipe:
    """One recipe with its config key resolved to a real path, for one tool.

    A recipe declares *where to look* symbolically — a config key, a filename
    suffix, a default location. This pairs it with what that key resolved to on
    this machine, which is the only thing the read phase needs that the recipe
    itself cannot know.

    ``path`` is whatever the config key names: a directory for the per-file,
    rules and skill layouts, the shared file itself for a keyed map. Which of
    those it is, is the recipe's business — this type deliberately does not
    restate it, because a wrapper per layout is what this replaces.
    """

    tool: str
    path: Path
    recipe: SurfaceRecipe


@dataclass(frozen=True)
class ToolDefinition:
    """One tool's integration, as data: its name and its per-kind surface recipes.

    Kinds a tool supports but the rebuild's dialects do not yet (directory-tree
    skills) are absent from ``surface_recipes`` until their dialect lands."""

    name: str
    surface_recipes: tuple[SurfaceRecipe, ...] = ()
