"""Antigravity — tool definition (data only).

Antigravity participates through directory-tree skills only (no per-agent file
format as of the v0.4 release). Its single surface is the ``skill`` kind, landed
in S23f (amendment 020): a folder per skill at ``~/.gemini/antigravity/skills/
<slug>/SKILL.md``. The SKILL.md body reuses the markdown-frontmatter dialect, so
no Antigravity-specific dialect is needed.
"""

from __future__ import annotations

from agents_sync.tools._shared_formats import markdown_surface_format
from agents_sync.tools.tool_definition import (
    DefaultLocation,
    Layout,
    PathAnchor,
    SurfaceRecipe,
    ToolDefinition,
)

_HOME = PathAnchor.HOME

ANTIGRAVITY_TOOL = ToolDefinition(
    name="antigravity",
    surface_recipes=(
        SurfaceRecipe(
            "skill",
            "antigravity_skills_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".gemini", "antigravity", "skills")),
            layout=Layout.SKILL_FOLDER,
        ),
    ),
)
