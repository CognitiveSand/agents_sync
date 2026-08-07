"""Claude Code — tool definition (data only)."""

from __future__ import annotations

from agents_sync.domain_model.tool_surface import McpSpellingRecipe
from agents_sync.tools._shared_formats import (
    GLOBAL_RULES_ARTIFACT_NAME,
    markdown_surface_format,
    mcp_surface_format,
)
from agents_sync.tools.tool_definition import (
    DefaultLocation,
    Layout,
    PathAnchor,
    SurfaceRecipe,
    ToolDefinition,
)

_HOME = PathAnchor.HOME

# Claude's agent front-matter spellings → canonical attributes (S20 increment 2).
_AGENT_FIELD_MAP = (
    ("model", "model"),
    ("effort", "effort"),
    ("tools", "tools"),
    ("disallowedTools", "disallowed_tools"),
    ("permissionMode", "permission_mode"),
)

# Claude's mcp wire: transport under `type`, auth under `oauth` (S20 increment 4); env
# references in the `${NAME}` inline style (S20 increment 7).
_MCP_SPELLING = McpSpellingRecipe(
    transport_render_field="type",
    auth_render_field="oauth",
    env_reference_style=("${", "}"),
)

CLAUDE_TOOL = ToolDefinition(
    name="claude",
    surface_recipes=(
        SurfaceRecipe(
            "agent",
            "claude_agents_dir",
            markdown_surface_format(_AGENT_FIELD_MAP),
            default_location=DefaultLocation(_HOME, (".claude", "agents")),
            layout=Layout.DIRECTORY,
            filename_suffix=".md",
        ),
        SurfaceRecipe(
            "slash_command",
            "claude_commands_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".claude", "commands")),
            layout=Layout.DIRECTORY,
            filename_suffix=".md",
        ),
        SurfaceRecipe(
            "rules",
            "claude_rules_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".claude",)),
            layout=Layout.RULES_FILE,
            candidate_filenames=("AGENTS.md", "CLAUDE.md"),
            default_artifact_name=GLOBAL_RULES_ARTIFACT_NAME,
        ),
        SurfaceRecipe(
            "mcp_server",
            "claude_mcp_servers_file",
            mcp_surface_format(("mcpServers",), "json", _MCP_SPELLING),
            default_location=DefaultLocation(_HOME, (".claude.json",)),
            layout=Layout.KEYED_MAP,
        ),
        SurfaceRecipe(
            "skill",
            "claude_skills_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".claude", "skills")),
            layout=Layout.SKILL_FOLDER,
        ),
    ),
)
