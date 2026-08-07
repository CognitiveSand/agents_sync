"""Gemini CLI — tool definition (data only). Rules are the fixed ``GEMINI.md``;
slash commands are whole-file TOML."""

from __future__ import annotations

from agents_sync.domain_model.tool_surface import McpSpellingRecipe
from agents_sync.tools._shared_formats import (
    GLOBAL_RULES_ARTIFACT_NAME,
    markdown_surface_format,
    mcp_surface_format,
    structured_text_surface_format,
)
from agents_sync.tools.tool_definition import (
    DefaultLocation,
    Layout,
    PathAnchor,
    SurfaceRecipe,
    ToolDefinition,
)

_HOME = PathAnchor.HOME

# Gemini CLI's agent front-matter spellings → canonical attributes (S20 increment 2).
# Only ``model`` folds; gemini's ``tools`` stay tool-private (per_tool_extra) until a
# later increment, matching the old codec.
_AGENT_FIELD_MAP = (("model", "model"),)

# Gemini carries no explicit transport field: the url-field SPELLING encodes it (S20
# increment 6) — ``httpUrl`` means http, ``url`` means sse — and the slot key is the server
# name, so no inner ``name`` is emitted. Env references use the ``${NAME}`` inline style (S20
# increment 7). ``oauth`` auth spelling is deferred to a later increment.
_MCP_SPELLING = McpSpellingRecipe(
    transport_render_field=None,
    name_render_field=None,
    transport_by_url_field=(("httpUrl", "http"), ("url", "sse")),
    url_field_by_transport=(
        ("http", "httpUrl"),
        ("streamable-http", "httpUrl"),
        ("sse", "url"),
    ),
    env_reference_style=("${", "}"),
)

GEMINI_CLI_TOOL = ToolDefinition(
    name="gemini_cli",
    surface_recipes=(
        SurfaceRecipe(
            "agent",
            "gemini_cli_agents_dir",
            markdown_surface_format(_AGENT_FIELD_MAP),
            default_location=DefaultLocation(_HOME, (".gemini", "agents")),
            layout=Layout.DIRECTORY,
            filename_suffix=".md",
        ),
        SurfaceRecipe(
            "slash_command",
            "gemini_cli_commands_dir",
            structured_text_surface_format("toml"),
            default_location=DefaultLocation(_HOME, (".gemini", "commands")),
            layout=Layout.DIRECTORY,
            filename_suffix=".toml",
        ),
        SurfaceRecipe(
            "rules",
            "gemini_cli_rules_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".gemini",)),
            layout=Layout.RULES_FILE,
            candidate_filenames=("GEMINI.md",),
            default_artifact_name=GLOBAL_RULES_ARTIFACT_NAME,
        ),
        SurfaceRecipe(
            "mcp_server",
            "gemini_cli_settings_file",
            mcp_surface_format(("mcpServers",), "json", _MCP_SPELLING),
            default_location=DefaultLocation(_HOME, (".gemini", "settings.json")),
            layout=Layout.KEYED_MAP,
        ),
        SurfaceRecipe(
            "skill",
            "gemini_cli_skills_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".gemini", "skills")),
            layout=Layout.SKILL_FOLDER,
        ),
    ),
)
