# Amendment 020 — Skill customization_type lands in the rebuild (FR-06)

- status: proposed
- branch: fix/size-explosion-hardening
- date: 2026-07-13
- relates to: FR-06 (skill matrix), NFR-03 (atomic visibility, folders),
  NFR-06 (round-trip byte preservation), NFR-16 (canonical authority);
  `docs/architecture_implementation_plan.md` Phase F-completion (S23f);
  `docs/audits/cutover_loose_ends_register_2026_07_12.md` (F3 skills-as-a-kind).

## Motivation

FR-06 requires the daemon to sync user-level `skill` customization_artifacts
across every agentic_tool whose `supported_customization_types` includes `skill`.
The 2026-07-12 loose-ends audit found the `skill` kind **never landed in
`src_new`**: there is no skill dialect, no skill recipe, no read-spec, and
Antigravity — which participates *only* through skills — is registered inert
(`tools/antigravity.py`: `surface_recipes=()`). Shipping the cutover without the
skill kind would drop a spec-required artifact type and leave Antigravity
permanently unavailable. The governance already exists — FR-06 in
`docs/project_requirements.md` and the `skill` customization_type in
`docs/project_description.md` (a managed folder holding `SKILL.md` plus optional
auxiliary files) — so this is an *implementation* of governed intent, not a
governance change.

## Principle / decision

The `skill` kind is a folder-per-artifact: `<root>/<slug>/SKILL.md`. Its identity
is the folder name; its content is the `SKILL.md` body, which reuses the existing
`markdown_frontmatter` dialect. **This amendment implements the SKILL.md-only
scope.** Auxiliary files inside a skill folder are a required capability
(FR-06 + NFR-06 for real multi-file skills) but are deferred to a separately
named step (see below). Until that step lands, a skill folder containing anything
other than its `SKILL.md` is **rejected loudly**, never silently truncated —
there is no window in which aux files are dropped without an explicit error
(§8 Fail Fast, Fail Loud).

### Scope split (agreed with the user, 2026-07-13)

- **S23f (this amendment) — Skill (SKILL.md) sync.** SKILL.md round-trips across
  every skill-supporting tool; Antigravity becomes active. `CanonicalDocument` is
  untouched (surface location stays a `Path` to the SKILL.md). A fail-loud guard
  rejects folders carrying auxiliary files.
- **S23i — Directory-tree skill auxiliary-file propagation (deferred).** Adds an
  `auxiliary_files` representation to `CanonicalDocument`, a directory-tree
  surface location, and atomic folder writes that copy aux files verbatim
  (NFR-03). Deferred because no multi-file skills are in play today; it must land
  before the cutover if any skill-supporting tool needs a multi-file skill synced.
  Named `S23i` — not "S23f-2" — so the deferred function is identified by what it
  does, not by a placeholder ordinal.

## Proposed governance edits (require user validation)

### User stories
**None.** FR-06's behaviour is already owned by existing stories (US-06 family,
skill matrix). No acceptance criterion changes — the fail-loud rejection of aux
files is a mechanism, covered by the standing fail-closed posture (US-07 AC-7 /
NFR-13), not a new user-visible guarantee.

### Requirements
**None.** FR-06 already mandates the skill sync; the `skill` customization_type
and every tool's skill root are already defined in `docs/project_description.md`.
This amendment adds no `shall`-language. The S23i deferral is recorded here and in
the implementation plan, not as a requirement change.

## Design edits (architecture — applied after)

`docs/architecture_implementation_plan.md`:
- Narrow the Phase F-completion **S23f** row to the SKILL.md-only scope + the
  fail-loud aux-file guard.
- Add an **S23i** row (Directory-tree skill auxiliary-file propagation) and list
  it under "Cutover readiness" as a pre-cutover-conditional deferred item.

No edit to `docs/architecture.md` beyond the plan; the skill kind follows the
existing declarative read-spec + recipe-as-data + dialect pattern already
documented there (no new architectural principle).

## Implementation plan

Surgical, in `src_new/agents_sync/` only (never `src/`):

1. **New recipe** `SkillFolderSurfaceRecipe(kind, config_key, surface_format,
   default_location)` in `tools/tool_definition.py`; add to the `SurfaceRecipe`
   union. Artifact path is `<default_location>/<slug>/SKILL.md`.
2. **New read-spec + walker** in `read_tool_surfaces.py`: a
   `SkillFolderSurfaceSpec` that enumerates immediate child directories of the
   skill root, derives the artifact slug from the **folder name**, and locates
   `<slug>/SKILL.md`. If a `<slug>/` folder contains any entry other than
   `SKILL.md` (extra file or subdirectory), raise
   `SkillAuxiliaryFilesUnsupportedError` (fail loud) — do not read partially.
3. **Registry wiring** in `tools/agentic_tools_registry.py` `surface_specs_for`:
   add the `isinstance(recipe, SkillFolderSurfaceRecipe)` branch → spec.
4. **Dialect reuse**: the SKILL.md body uses the existing `markdown_frontmatter`
   dialect via `markdown_surface_format(...)`; no new dialect module unless a
   skill-specific field map is needed. `extract_id` for a skill surface returns
   the folder-name slug.
5. **Per-tool recipes**: add a skill `SkillFolderSurfaceRecipe` (with the correct
   `default_location`) to `tools/claude.py`, `tools/codex.py`, `tools/cursor.py`,
   `tools/opencode.py`, `tools/gemini_cli.py`, and replace `surface_recipes=()`
   in `tools/antigravity.py` with a live skill recipe. Verify each tool's
   `supported_customization_types` includes `skill` before wiring.
6. **New error type** `SkillAuxiliaryFilesUnsupportedError` beside the skill spec
   (or in the dialects error module), with a message naming the offending folder
   and pointing at S23i.

`runtime_config.py` derives config keys from `surface_recipes` automatically, so
the new recipe's `config_key`/`default_location` are picked up without an engine
edit; verify it handles the new recipe type.

## Test plan (tests_new/, red first)

One test per behaviour, failing before the code:

1. **Round-trip matrix** (`test_skill_round_trip.py`) — parametrized over every
   skill-supporting tool: render a canonical skill → SKILL.md on disk → reparse →
   assert SKILL.md body + frontmatter survive (NFR-06). Mirrors
   `tests_new/test_tool_field_maps.py` `_agent_surface` shape.
2. **Cross-adapter propagation** — render a skill for tool A, parse, render for
   tool B, parse; assert the SKILL.md content survives A→B (FR-06 core).
3. **Slug from folder name** — a skill read from `<root>/<slug>/SKILL.md` yields
   artifact id `<slug>`; `extract_id` recovers it in isolation (FR-11).
4. **Fail-loud aux guard** — a skill folder containing `SKILL.md` **and** an extra
   file (or subdirectory) raises `SkillAuxiliaryFilesUnsupportedError`; assert the
   message and that **nothing** is read/written for that folder.
5. **Antigravity active** — after wiring, the registry produces skill
   surface-specs for `antigravity` and it counts as available when its skill root
   exists (was zero before).

Then run `/audit-tests` on the new test module before writing production code.

## Verification

- Red-first: the five tests above fail against current `src_new` (no skill kind).
- Green: `uv run pytest -c pytest_new.ini` all pass after implementation.
- Full gate: `bash scripts/ci.sh` green (both scopes + `mypy --strict` over
  `src_new/`).
- The old conformance suite `tests/` stays green (never touched `src/`).
- Ship as PATCH `feat(rebuild)`; commit body links this amendment. Update status
  to `applied` with the landing commit.
