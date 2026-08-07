"""Codex CLI — tool definition (data only). Agents are whole-file TOML."""

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

# Codex's whole-file TOML agent spellings → canonical attributes (S20 increment 2).
_AGENT_FIELD_MAP = (
    ("model", "model"),
    ("model_reasoning_effort", "effort"),
)

# Codex spells HTTP auth across dedicated carriers, not a generic headers/auth block (S20
# increment 5): `http_headers` for literal headers, `env_http_headers` (header→env-name) and
# `bearer_token_env_var` (one env-name → Authorization bearer) for env-reference headers, and
# no generic auth field. The dialect folds all three onto the canonical `headers` map. Codex
# also carries no explicit transport field (inferred from command/url) and no inner name (the
# slot key is the name) — both suppressed (S20 increment 6).
_MCP_SPELLING = McpSpellingRecipe(
    transport_render_field=None,
    name_render_field=None,
    headers_render_field="http_headers",
    env_http_headers_field="env_http_headers",
    bearer_token_env_var_field="bearer_token_env_var",
    auth_render_field=None,
)

CODEX_TOOL = ToolDefinition(
    name="codex",
    surface_recipes=(
        SurfaceRecipe(
            "agent",
            "codex_agents_dir",
            structured_text_surface_format("toml", _AGENT_FIELD_MAP),
            default_location=DefaultLocation(_HOME, (".codex", "agents")),
            layout=Layout.DIRECTORY,
            filename_suffix=".toml",
        ),
        SurfaceRecipe(
            "slash_command",
            "codex_prompts_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".codex", "prompts")),
            layout=Layout.DIRECTORY,
            filename_suffix=".md",
        ),
        SurfaceRecipe(
            "rules",
            "codex_rules_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".codex",)),
            layout=Layout.RULES_FILE,
            candidate_filenames=("AGENTS.md",),
            default_artifact_name=GLOBAL_RULES_ARTIFACT_NAME,
        ),
        SurfaceRecipe(
            "mcp_server",
            "codex_config_file",
            mcp_surface_format(("mcp_servers",), "toml", _MCP_SPELLING),
            default_location=DefaultLocation(_HOME, (".codex", "config.toml")),
            layout=Layout.KEYED_MAP,
        ),
        SurfaceRecipe(
            "skill",
            "codex_skills_dir",
            markdown_surface_format(),
            default_location=DefaultLocation(_HOME, (".codex", "skills")),
            layout=Layout.SKILL_FOLDER,
        ),
    ),
)
