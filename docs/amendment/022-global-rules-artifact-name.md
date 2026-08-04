# Amendment 022 — A whole-file global-rules artifact carries a declared name

- status: applied (rebuild `src_new/`, 0.7.59)
- branch: fix/size-explosion-hardening
- date: 2026-08-04
- relates to: FR-07 (rules matrix), FR-10 (rules filename precedence), US-03
  (reconciliation), NFR-11 (extensibility / tools-as-data);
  `docs/audits/cutover_loose_ends_register_2026_07_12.md` (AC parity sweep, G-gate-3).

## Motivation

The 2026-08-04 AC parity sweep found that a whole-file global-rules surface has no
identity of its own. Every other surface takes its name from its own format; a
whole-file rules document does not, because `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`
are plain markdown with no front matter. So the artifact parsed with `name=""`, and
`slugify_name("")` returns its **placeholder slug `"converted"`**.

Consequences, all following from that one gap:

- Whole-file rules tools reconciled with each other **by accident** — they shared a
  key because they were equally unnamed, not because they shared an identity.
- Any other artifact whose name also slugified to the placeholder would have
  collided with the user's global rules.
- **Latent and user-visible:** once cross-tool creation lands (plan G-gate-1),
  projecting global rules onto a directory rules surface would have written
  `~/.cursor/rules/converted.mdc`.

## Principle / decision

**A surface whose format cannot carry a name declares one in its recipe.** The name
is what an artifact is reconciled and projected under, so it must be a real
identity, not a fallback. It belongs with the tool data (tools-as-data, NFR-11), not
as a constant inside the dialect: the dialect stays free of rules-specific
knowledge, and a future tool in the family supplies its own value.

The value is `"global"`, in one shared constant, for two reasons: every tool in the
family must agree or the single rules artifact a user keeps would reconcile as
several; and installs synced by the 0.7 daemon **already hold `name: global` on
disk** in their `AGENTS.md`, so the cutover neither renames the artifact nor
rewrites the field.

### Deliberately NOT done (owner instruction)

The legacy tree reaches the same name by a different route — a dialect constant
`rules_io.GLOBAL_RULE_NAME` — and thereby also makes a whole-file rules artifact
reconcile with a *directory* rules artifact (a cursor `.mdc`) that happens to share
the name. **No machinery for that case is implemented here**, by explicit owner
decision. None is needed: a cursor `.mdc` declares `name:` in its own front matter,
so it names itself through the ordinary path, and the generic `(kind, slug)` key
does whatever it does. There is no rules-specific cross-family code in the rebuild.

Copying legacy's behaviour wholesale would in any case have imported a defect: given
a *differently*-named directory rule, the legacy tree adopts **nothing at all** —
the two artifacts both plan to write a third tool's fixed `AGENTS.md`, the collision
blocker refuses both, and the daemon logs `Target collision` on every poll forever.
The rebuild settles cleanly at `changed == 0` on the same input, and keeps doing so.

### Still open, and not addressed here

Many directory rules cannot all become one whole-file `AGENTS.md`. Either they
compose into it — **US-16 section decomposition, unimplemented in both trees** — or
only one designated rules artifact crosses to whole-file tools. That is the design
debt behind this area and the same knot that has US-15's egress enforcement deferred
pending a spike. This amendment does not resolve it; it removes the placeholder slug
so the artifact has an identity to reason about.

## Proposed governance edits (require user validation)

### User stories
**None.** US-03's reconciliation and FR-07's matrix already own this behaviour; the
defect was a failure to meet them.

### Requirements
**None.** No `shall`-language added. FR-07 and FR-10 are unchanged.

## Implementation

1. `tools/tool_definition.RulesFileSurfaceRecipe` gains `default_artifact_name`
   (defaulted to `""`, so no other recipe kind is affected).
2. `tools/_shared_formats.GLOBAL_RULES_ARTIFACT_NAME = "global"` — one constant,
   shared by the family.
3. `tools/{claude,codex,gemini_cli,opencode}` declare it on their rules recipe.
4. `read_tool_surfaces.RulesFileSurfaceSpec` carries it through, and
   `_name_unnamed_artifact` applies it at the one seam that knows the recipe —
   only when the parsed name is empty, so a file that declares a name keeps it.

Rendering is unchanged: `name` was already a known field of the rules surface
format, so the projected file carries `name: global` exactly as installs synced by
the 0.7 daemon already do.

## Verification

- `tests_new/test_read_tool_surfaces.py` — a nameless rules file takes the recipe
  default; a file that declares a name keeps it; a recipe without a default leaves
  the name empty.
- `tests_new/test_tool_default_locations.py` — every whole-file rules recipe
  declares the *same* name (a drift guard: disagreement would split the artifact);
  and the name slugifies to itself rather than to the placeholder.
- AC parity sweep re-run: **13 of 14**, FR-07 now passing (one artifact, the edit
  crossing to a directory rules surface). The remaining failure is US-11 AC-3, which
  belongs to the cross-tool-creation gap (G-gate-1/2), not to this amendment.
- Full local CI green: ruff, `mypy --strict` over both trees, 585 conformance + 735
  rebuild tests.
