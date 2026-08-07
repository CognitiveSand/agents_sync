"""Cursor — tool definition (data only). Rules are a directory of ``.mdc`` files."""

from __future__ import annotations

from agents_sync.domain_model.tool_surface import McpSpellingRecipe
from agents_sync.tools._shared_formats import markdown_surface_format, mcp_surface_format
from agents_sync.tools.tool_definition import (
    DefaultLocation,
    Layout,
    PathAnchor,
    SurfaceRecipe,
    ToolDefinition,
)

_HOME = PathAnchor.HOME

# Cursor's agent front-matter spellings → canonical attributes (S20 increment 2).
_AGENT_FIELD_MAP = (
    ("model", "model"),
    ("tools", "tools"),
)

# Cursor's mcp wire spells the transport field `type` (S20 increment 4).
_MCP_SPELLING = McpSpellingRecipe(transport_render_field="type")

CURSOR_TOOL = ToolDefinition(
    name="cursor",
    surface_recipes=(
        SurfaceRecipe(
            "agent",
            "cursor_agents_dir",
            markdown_surface_format(_AGENT_FIELD_MAP),
            default_location=DefaultLocation(_HOME, (".cursor", "agents")),
            layout=Layout.DIRECTORY,
            filename_suffix=".md",
        ),
        SurfaceRecipe(
            "slash_command",
            "cursor_commands_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".cursor", "commands")),
            layout=Layout.DIRECTORY,
            filename_suffix=".md",
        ),
        SurfaceRecipe(
            "rules",
            "cursor_rules_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".cursor", "rules")),
            layout=Layout.DIRECTORY,
            filename_suffix=".mdc",
        ),
        SurfaceRecipe(
            "mcp_server",
            "cursor_mcp_servers_file",
            mcp_surface_format(("mcpServers",), "json", _MCP_SPELLING),
            default_location=DefaultLocation(_HOME, (".cursor", "mcp.json")),
            layout=Layout.KEYED_MAP,
        ),
        SurfaceRecipe(
            "skill",
            "cursor_skills_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".cursor", "skills")),
            layout=Layout.SKILL_FOLDER,
        ),
    ),
)
