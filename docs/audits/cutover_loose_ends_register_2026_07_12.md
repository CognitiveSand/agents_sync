# Loose-Ends Register — Rebuild Cutover Readiness

- Date: 2026-07-12
- Branch: `fix/size-explosion-hardening`
- Purpose: identify **all** loose ends before revising the implementation plan's Phase G
  (cutover), so the revised plan carries every open item deliberately and nothing is
  dropped at the `src_new → src` flip.
- Method: five cross-checked investigations —
  1. Conformance-suite import-binding survey (73 `tests/` files).
  2. Independent Fable audit of the plan vs. `src_new`/`tests/` reality.
  3. Deferred-list reconciliation (plan "Deferred" list + inline `→ S2x` notes vs. code).
  4. Cutover coverage-parity sweep (what old-test coverage would be lost at retirement).
  5. Code + doc loose-end marker sweep (TODO/deferred markers, open governance, amendments).

Severity legend: **BLOCKING** (revised plan cannot be written correctly without resolving),
**HIGH**, **MEDIUM**, **LOW**, **ACCEPT** (deliberate deferral, record only).

---

## Category 1 — Phase G cutover: plan claims vs. mechanical reality (BLOCKING the current plan)

Confirmed independently by investigations 1 and 2.

| # | Loose end | Plan ref | Evidence | Severity |
|---|---|---|---|---|
| G1 | "Full conformance suite stays green against the new pipeline" is not a single incremental step | L256 | 59/73 `tests/` files import old-internal module names absent from `src_new`; one `agents_sync` on one path → all 59 `ImportError` on flip | BLOCKING |
| G2 | The `Syncer`-shaped test adapter — the largest cutover work item — is unscoped | (none) | `agents_sync.sync.Syncer` drives 40 tests via `tests/_helpers.py`; new API is functional (`sync_once(...)`). ~236 `.sync_once()` + ~256 `.tool_root()` + ~199 `.state_dir` call sites | BLOCKING |
| G3 | "Directory rename, no import rewritten" is false for the test tree | L173-176 | True for production code (package name stable); the conformance suite needs `sync`→`sync_once`, `canonical`→`canonical_store`, `state`→`sync_state_store`, `cli`→`command_line_interface`, `config`→`runtime_config` | BLOCKING |
| G4 | The "safety net" invariant list names old-internal unit tests as behavioural | L179-186 | `test_round_trip`→`claude_io`; per-tool `test_*_io`; `test_e2e_sync`→`adoption.*`/`state`/`archive`. These cannot "stay green across the cutover" — they retire with their modules | BLOCKING |
| G5 | Console-script entry point breaks at rename | `pyproject.toml:12-13` | `[project.scripts] agents-sync = "agents_sync.cli:main"`; new tree has no `cli.py` (it is `command_line_interface.py`). All three installers hard-fail on missing entrypoint | BLOCKING (trivial fix, unaccounted) |
| G6 | "Fold `tests_new/` into `tests/`" has an undisclosed collision + structural mismatch | L174 | `test_parser_bounds.py` exists in both dirs; `tests/` is a package (`__init__.py`, relative imports), `tests_new/` is not | MEDIUM |
| G7 | S24 gate enforcement is circular today | L256, L113-120 | `tests/test_size_explosion_regression.py` runs against **old** `src` — it exercises the old `parser_bounds`, not the `src_new` port. The port is only enforced by `tests_new/test_parser_bounds.py` until the harness is repointed | MEDIUM |
| G8 | Stated isolation mechanism does not exist | L168-171 | Claims `tests_new/` has a `conftest.py` that puts `src_new` first on `sys.path`; there is no `conftest.py` — isolation is `pytest_new.ini`'s `pythonpath = src_new` | STALE |
| G9 | "Phases D–G (S14–S25): not started" contradicts the progress block | L124 | Lines 24-120 show S14–S23 all ✓ and the S24 gate ✓; only Phase G remains | STALE |
| G10 | S25 "full suite green" + "never red at a step boundary" cannot both hold as written | L257, L272-274 | Deleting old modules reds the suite at collection unless the tests were already repointed (which is unplanned per G2) | BLOCKING |

**Disposition:** resolved by the revised Phase G (see the plan-revision proposal). S24 becomes
"prove behaviour against `src_new` in a parallel stage, nothing deleted"; S25 becomes "flip +
retire", with the adapter (G2), entry point (G5), fold mechanics (G6), and doc fixes (G4/G8/G9)
made explicit.

---

## Category 2 — Functional gaps to resolve before / at cutover

These are not doc problems — they are real code gaps a clean cutover must not paper over.

### F1 — Framework egress-guard enforcement (US-15) is UNIMPLEMENTED. **HIGH / needs a user decision.**
The plan lists this as "→ read phase S17–S19" and marks Phase E complete, but the enforcement
never landed. Only the pure predicate exists — `dialects/global_rules.py:41 detect_framework_specific`
— with **zero callers** anywhere in `src_new/` outside its own test. `execute_sync_plan` renders
with no hold-back; the `rules_framework_specific_held_back` warning named in the docstring exists
nowhere. This is a whole US-15 acceptance-criteria family (AC-1/2/3/4/6/7) with no implementation
path. **Decision needed:** schedule an implementation step before cutover, or formally defer US-15
enforcement (a governance call — US-15 is a user story). US-15 itself already carries a "Known
limitation (deferred): the framework guard is whole-file … until US-16" note, and US-16 has
unresolved design questions (see GOV2), so US-15's full form is entangled with US-16.

### F2 — Rules-surface projection render leak. **HIGH / latent correctness bug.**
Read side stashes the pre-`@import` body in `per_tool_only[tool]["rules_source_body"]`
(`read_tool_surfaces.py:137-142`), but there is **no render-side consumer**:
`dialects/field_mapping.py:96-97 project_canonical_to_fields` copies every `per_tool_only` entry
back as a literal field, so projecting the canonical onto an `@import`-bearing origin rules file
would emit a `rules_source_body:` front-matter key instead of restoring the source body. Reachable
through today's rules recipes; silent wrong output; no `tests_new/` test projects onto a rules
surface. **Disposition:** fix (a bug), schedule before cutover.

### F3 — Skills / directory-tree dialect + antigravity recipes not landed. **HIGH if cutover precedes it.**
`tools/antigravity.py:13` registers antigravity with `surface_recipes=()` (inert);
`tool_definition.py:85-86` states directory-with-manifest kinds "are absent … until their dialect
lands." So the *skill* artifact kind has no functional home yet: old `test_antigravity_io` and the
skill-md halves of `test_codex_round_trip` have no new coverage. Agent/slash_command/rules/
mcp_server kinds are all wired. **Decision needed:** is "skills as an artifact kind" in-scope for
this cutover (schedule the dialect), or an accepted post-cutover follow-on?

### F4 — Cross-process file locking removed; the shared-file race it guarded is unmitigated. **HIGH / regression.**
Old `src/agents_sync/filesystem_lock.py` (fcntl/msvcrt) made keyed-map slot read-modify-write safe
against a concurrent writer in another process. No lock primitive exists anywhere in `src_new/`.
Amendment 008 fixed the `state.json` lost-update race (single-writer + atomic-write-wins), but the
**shared-file surface** race (a tool editing `~/.claude.json` `mcpServers` between the daemon's read
and its `os.replace`) has no new-tree mitigation and no test. **Decision needed:** accepted risk
(document it), or must-carry mitigation before cutover?

### F5 — v0.4 on-disk layout migration is gone; installers still call it. **HIGH / upgraders.**
`scripts/migrate_v0.4.py` does on-disk repair the new tree cannot replicate (moves stray
`<name>-skill/` duplicates aside with timestamped backups, relocates `~/.agents/skills`, strips
injected `pair_id:` front-matter). New-tree state migration is deliberate fail-fast
(`sync_state_store.py:56-62` quarantines `schema_version != 1` and rebuilds), which covers
`state.json` but **not** the v0.4 *layout* damage. `install.sh:132` and `install-macos.sh:150`
still execute the migrate script; `pyproject.toml` still packages `src/`. **Decision needed:** is
direct pre-0.4→post-cutover upgrade supported (carry the migrate path) or dropped (declare it, and
update the installers + their text tests)?

---

## Category 3 — Smaller deferred items (park in a named step; mostly non-blocking)

| # | Item | Status | Evidence | Disposition |
|---|---|---|---|---|
| D1 | `CanonicalDocument.from_dict` type-coercion hardening | STILL-OPEN | `canonical_document.py:94-128` silently coerces `tools:"abc"`→`('a','b','c')`, accepts `timeout:"x"`; raises only on absent required fields | Fix at next schema growth; add a bad-type test |
| D2 | gemini mcp `oauth` auth-field spelling | STILL-OPEN | `tools/gemini_cli.py:31-42` has no `auth_render_field`; renders under `auth` not `oauth` | Small S20-style knob |
| D3 | Reserved names (recipe data) | STILL-OPEN | No reserved-name data in `tools/` (distinct from the shipped Windows-slug guard) | Park |
| D4 | Extend-to-newly-available (project managed artifacts onto a tool that becomes available) | STILL-OPEN | No mechanism; projection targets always derive from own observations/recorded targets; grep "newly" = 0 hits | Confirm in-scope (US-?) or defer |
| D5 | Tied-mtime WARN | STILL-OPEN | `winner_selection.py` resolves ties silently (alphabetical); no warning emitted | Small logging add |
| D6 | Per-tool availability status transition logging (US-11) | REDUCED | New tree keeps only `count_available_tools`; old `tool_status.py` transition logging gone | Confirm intended reduction |
| D7 | Duplicate-render-file guard on siblings | PARTIAL | `reject_shared_write_file` covers project/adopt/rename; `remove_artifact` has no guard; guard itself untested | Add remove-arm guard + a guard test |
| D8 | JSONC support | ACCEPT (YAGNI) | Codec is json+toml only; no tool declares jsonc | Record only |
| D9 | New-tree boot over a real old-tree state+disk layout | UNTESTED | Quarantine + reconcile tested separately; no end-to-end upgrade-seam test (where old `test_migrate_v0_4_e2e` lived) | Add e2e if F5 says "supported" |
| D10 | `test_marker_discipline` successor | STALE-AT-CUTOVER | Meta-test enforcing the `make_syncer`/integration-marker convention has no `tests_new/` equivalent | Recreate the discipline for the folded suite or drop deliberately |

---

## Category 4 — Old-track amendments to close (superseded/realized by the rebuild)

Both are dated 2026-06-04 against the **old** tree and cite old modules; the greenfield rebuild
supersedes their mechanism. They are stale headers, **not** new open work. (No-rm policy: convert
to historical records with a superseded/realized note + landing links.)

| # | Amendment | Header status | Reality | Disposition |
|---|---|---|---|---|
| A015 | 015-rename-propagation (US-04 AC-2/3/5) | "in-progress (AC-1 applied; AC-2/AC-3/AC-5 pending)" | Substance **realized in rebuild**: reconcile_known S6b rename + executor `rename_artifact` (`identity_intents.py`) + S8b `RejectCollision` for the rename-created clash (plan L213). Cites old `adoption/engine.py`/`rendering` | Close as **realized-by-rebuild**; verify US-04 AC coverage in the behavioural conformance set |
| A016 | 016-simplify-full-code | "in-progress" | **Superseded**: it splits old god-modules (`portable_archive` 633, `engine` 631, `sync` 517, `config` 472); the rebuild replaces them wholesale with clean ≤300-line modules | Close as **superseded-by-rebuild** |
| A010 | 010-us12-dry-clean | "applied" but §`:87` header still "Design edits … pending" | Likely stale header | Verify the three design edits landed; update header |
| A011 | 011-single-identity-service | "applied (RC-1)"; RC-6 "deferred to P7" | RC-6/P7 is old-track (016) → moot post-rebuild | Note as moot when 016 closes |

---

## Category 5 — Governance decisions awaiting the user

| # | Item | State | Evidence |
|---|---|---|---|
| GOV1 | US-07 AC-3 wording clarification | Dispositioned (commit `cc5c7b3`), tracked plan L137-141, **no amendment record yet**, story text unchanged | AC-3 requires logging the `agentic_tool`; `SyncResult.failed` is a flat artifact-label tuple. Resolver judged AC-3 substantially met under NFR-13 "when applicable" and recommended clarifying the AC text, not code. Needs user approval of exact wording → new amendment 020 |
| GOV2 | US-16 global-rules-section-decomposition red-card questions | Pre-work, unresolved | `US-16:37-43`: marker mechanism, opt-in vs inferred, precedence vs US-15 `@import`, ordering/merge; "likely not estimable until a spike". Entangled with F1/US-15. Rebuild proposal declares US-16 out of scope (`proposal:518`) |

---

## Category 6 — Doc staleness (cheap fixes, fold into the plan revision)

| # | Item | Location |
|---|---|---|
| S1 | Referenced remediation report absent from disk | plan L112 → `docs/audits/code_audit_remediation_2026_06_23__14_16.md` (only in git history) |
| S2 | Stale forward-pointer: "One governance wording fix flagged (§17)" but §17 now says "resolved" | `architecture_simplification_proposal.md:518` vs `:560-575` |
| S3 | Stale architecture fact: daemon.py "37 lines" vs actual 108 (old-code audit) | `docs/audits/code_audit_V3.md:126,407` → check `docs/architecture.md` |
| S4 | "Phases D–G not started" | plan L124 (= G9) |
| S5 | `tests_new` conftest.py isolation claim | plan L168-171 (= G8) |

---

## Decisions (resolved 2026-07-12)

1. **US-15 framework egress enforcement (F1):** **DEFER post-cutover.** Add a governance note to
   US-15 that enforcement is deferred; drop the plan's false "done" claim. Entangled with US-16
   (GOV2), which needs a spike.
2. **Must-carry vs. drop (F3/F4/F5, D6):**
   - **F3 skills-as-a-kind → CARRY** (spec-required, FR-06) — new plan step **S23f**; the
     auxiliary-file half split out as **S23i**, deferred on the condition that it must land before
     the flip if a multi-file skill needs syncing. **Condition met 2026-08-04 → S23i is now
     REQUIRED before the flip** (see the update below).
   - **F4 cross-process file locking → KEEP** (mitigate the shared-file race) — new plan step **S23h**.
   - **F5 v0.4 upgrade migration → DEFER UNTIL NEEDED** — leave `migrate_v0.4.py` + installers
     untouched; revisit only if a direct-from-v0.4 upgrader need appears.
   - **D6 availability-status logging → DROP** (YAGNI) — document the reduced observability.
3. **Amendments 015/016 → CLOSE.** 015 realized-by-rebuild (verify US-04 AC coverage in the
   behavioural conformance set); 016 superseded-by-rebuild. Convert both to historical records.
4. **US-07 AC-3 (GOV1) → KEEP PARKED** past cutover (no amendment 020 drafted yet).
5. **Rules-surface projection leak (F2) → FIX before cutover** (it is a bug) — new plan step **S23g**.

**Plan applied 2026-07-12** to `docs/architecture_implementation_plan.md`: Phase G rewritten
(S24 = prove-behaviour-in-parallel-stage; S25 = flip + retire); new pre-cutover **Phase
F-completion** rows S23f/S23g/S23h; Safety-net section split behavioural vs old-internal-unit;
Build-location/cutover paragraph corrected (test-harness rewrite, entry point, fold); stale
"Phases D–G not started" and `tests_new` conftest.py claims fixed; a "Cutover readiness" block
recording these decisions.

Items scheduled without a decision: G-series (revised Phase G), D1–D5, D7, D9, D10, S1–S5.

---

## Update 2026-08-04 — F3/S23i: the conditional gate has fired

**S23i moves from deferred-conditional to REQUIRED before the flip.** Amendment 020 deferred the
auxiliary-file half of the skill kind on one stated condition: it "must land before the flip if any
skill-supporting tool needs a multi-file skill synced". A field report against the running v0.7
daemon establishes that multi-file skills — reference material in a subdirectory beside `SKILL.md` —
are in real use, so the condition is met.

**Evidence.** The report described a skill folder restored by the daemon with its `SKILL.md` alone
and no diagnostic. Reproduced against `src/` (now `tests/test_skill_auxiliary_files_survive_heal.py`):
propagation to a fresh tool copies the folder whole, but a glitch heal (US-11 AC-9) rendered from
the canonical writes only `SKILL.md`, and the post-write digest recorded by `update_state_n_way`
then describes the truncated tree — so the following poll reports `changed == 0` and no later poll
ever repairs it. The loss is silent and self-confirming.

**Root cause is layered, and only the first layer was a legacy-tree bug.** The heal path failed to
pass a `source_dir` that the sibling `_extend_to_new_tools` had always passed; that is fixed in
`src/` at 0.7.57 (amendment 021). The second layer is structural and belongs to the rebuild: the
canonical document has no representation for auxiliary files, so the store — the authority under
NFR-16 — cannot reconstruct a multi-file skill from itself. A surviving on-disk copy is the only
possible source, which is a mitigation, not a guarantee.

**Consequences that the legacy fix does not reach**, all requiring S23i:

- `portable_archive` (old) / `portable_library` (new) carry no skill-tree handling at all, so
  `export`→`import` (US-12) drops auxiliary files: a library restored on another machine yields
  truncated skills. This is the same defect crossing a machine boundary rather than a tool boundary.
- A pair present on zero tools (a fresh import stub) cannot be reconstituted whole by any means.

**Scope added to S23i** beyond amendment 020's description: the portable-library export/import path,
and `parser_bounds` size caps on auxiliary files (an unbounded folder is a size-explosion vector the
S24 gate otherwise closed).

**Correction to an earlier draft of this entry (owner decision 2026-08-04):** it proposed
secret-policy egress *scanning* of auxiliary content. That was inconsistent with the existing
design and is **not** implemented. `find_secret_literals` scans the wire-shaped credential carriers
(`env`/`headers`/`auth`); free-form prose in `body` is deliberately unscanned — NFR-15's documented
residual, on the reasoning that secrets belong in the structured fields. An auxiliary file is
content of the same nature as a body, so it inherits the same treatment. Scanning it would create an
asymmetry (aux scanned, body not) and produce false positives that freeze legitimate skills.
Residual risk, accepted and recorded: a skill folder containing a real credentials file propagates,
exactly as a body containing one does today.

### NEW FINDING 2026-08-04 — the rebuild never creates an artifact on a tool that lacks it. **BLOCKER for S24.**

Found while writing S23i's end-to-end tests, and **not caused by S23i** — it affects every
customization_type, agents included. The rebuild propagates edits *among* the tools that already
hold an artifact, but it never *creates* one on a tool that has no copy.

`reconcile_known._absorb_change` draws its projection targets from **observed surfaces**:

```python
targets = tuple(o.tool_surface for o in observations if o is not winner)
```

A tool with no copy of the artifact produces no observation, so it is never a target.
`adopt_candidates` does not close the gap either: its `others` are the *already-present* duplicate
surfaces it reconciles into one identity at first boot. Reproduced on a two-tool workspace: a skill
(and, identically, an agent) planted on one tool is adopted, its id injected, and the daemon then
settles at `changed == 0` with the second tool's root still empty, poll after poll.

This is the product's headline behaviour — project description Goal 1, "editing a customization on
any one agentic_tool propagates to every other participating agentic_tool" — so the old tree's
`test_cross_adapter_adoption_matrix` and `test_e2e_sync` would fail against `src_new` today. The
register's earlier "extend-to-newly-available projection" line, filed under *smaller carried items*,
understated this: that phrasing suggests a tool coming back online, but the missing behaviour is
first-time creation, which is the core loop.

**Disposition needed from the owner.** It is a new plan step before S24 (S24 is defined as *proving
behaviour against `src_new`*, and this behaviour does not exist to prove). Not scheduled here
because it is materially larger than a loose end: the planner must derive targets from the tool
registry — every tool whose `supported_customization_types` includes the kind, and whose root
resolves — rather than from observations, which also means minting target paths for tools with no
surface yet.

### AC PARITY SWEEP 2026-08-04 — 14 behaviours driven end-to-end through `sync_once`

Prompted by the cross-tool-creation discovery: two "complete" claims had already proved wrong, so
the remaining-work list was re-derived by exercising behaviours rather than reading the plan. Method:
drive the real entry point (`sync_once`) over a two-tool tmp workspace and assert the user-visible
outcome. The question asked is never "does the component work" — 728 unit tests answer that — but
**"is there a wired path from the daemon to this outcome"**. That distinction is what the earlier
completeness claims missed: unit coverage is exactly what said skills were done and Phase F complete.

**Result: 12 of 14 pass.** The core loop is sound — edit propagation, conflict resolution by
freshest mtime, rename relocation, removal propagation, first-boot reconciliation, archive-on-
overwrite, FR-10 rules filename precedence, FR-11 malformed-metadata freeze without a re-mint,
FR-14 out-of-band canonical re-projection, and the agent / skill / slash_command / mcp_server
matrices. Two failures, plus one regression found and fixed during the sweep.

**FAIL 1 — global-rules identity. ✓ FIXED 0.7.59 (amendment 022).** The whole-file rules recipes
declare `default_artifact_name = "global"` as tool data; the placeholder slug is gone and the value
matches what 0.7-synced installs already carry on disk. No cross-family reconciliation machinery was
written (owner decision) — a directory rules artifact names itself in its own front matter. Sweep
re-run: FR-07 passes, 13 of 14 overall. The investigation is retained below as the record.

**Investigated in depth 2026-08-04; the sweep's first reading was too broad and is corrected here.**

*Corrected finding.* Global rules **do** sync across the whole-file family in the rebuild:
claude ↔ codex ↔ opencode reconcile into one artifact and propagate normally (verified). The sweep
paired claude with **cursor**, and that specific pair is what fails. Two further corrections to the
sweep's first reading: rules are **not** a one-artifact-per-tool kind — cursor's rules surface is a
*directory* of `*.mdc` files and a user may hold many; and the rebuild is not uniformly a regression
— in one case it is strictly better than the legacy tree (below).

*Root cause.* The legacy tree forces a fixed canonical name on every whole-file global-rules surface
(`rules_io.GLOBAL_RULE_NAME = "global"`), because the format carries no name — plain `AGENTS.md` has
no front matter. The rebuild has no equivalent, so a whole-file rules surface parses to `name=''`,
which `slugify_name` turns into its **placeholder slug `"converted"`**. Consequences:

- Whole-file tools reconcile with each other only *by accident* — they share a key because they are
  equally unnamed, not because they share an identity.
- Any other artifact whose name also slugifies to the placeholder would collide with global rules.
- **Latent, user-visible:** once cross-tool creation lands (G-gate-1), projecting global rules onto
  cursor's directory surface will create `~/.cursor/rules/converted.mdc`.
- It cannot reconcile with a cursor rule named `global`, where legacy does.

*The legacy tree is not a model to copy.* Legacy joins claude's `AGENTS.md` with a cursor
`global.mdc` only because the forced name happens to match. Give cursor a differently-named rule
(`team.mdc`) and legacy adopts **nothing at all**: claude's `AGENTS.md` and cursor's `team.mdc` both
plan to write codex's fixed `AGENTS.md`, the collision blocker refuses both, and the daemon logs
`Target collision` on every poll forever. The rebuild handles the same input cleanly — two
artifacts, no errors, settling at `changed == 0`. So on the differently-named case the rebuild is an
**improvement**, and restoring legacy parity verbatim would import the deadlock.

*What is actually unresolved.* Many cursor `.mdc` rules cannot all become one `AGENTS.md`. Either
they compose into it (that is **US-16 section decomposition**, unimplemented in both trees) or only
one designated rules artifact crosses to whole-file tools. This is precisely why the register
already records US-15's egress enforcement as "entangled with US-16's unresolved marker/precedence
design (needs a spike)": the N-to-1 rules mapping is the unsolved core, and legacy "resolves" it by
deadlocking. **Needs an owner decision** — see the two options in the plan's G-gate-3.

**FAIL 2 — US-11 AC-3 re-extend to a returning tool. STILL OPEN after cross-tool creation landed,
and it is a DIFFERENT and more serious defect than first assumed.**

The first reading said this shared a root cause with cross-tool creation and would be fixed by the
same change. It was not. With creation implemented (0.7.60, amendment 023) the extension rule is
never even reached here, because a recorded tool whose root returns **empty** is read as a deletion:
`_has_vanished_surface` short-circuits to `RemoveArtifact`, and once the returning root lifts the
two-tool guard the removal executes — **taking the artifact off every healthy tool**.

Traced end-to-end on a two-tool workspace: adopt → settle → remove the second tool's root → the
artifact correctly survives (the guard suppresses the removal) → recreate the empty root → the
artifact is deleted from *both* tools and the record emptied.

**The legacy tree does exactly the same** (verified with the same scenario through `Syncer`). So
this is a long-standing defect shared by both trees, **live in the shipped daemon**, not a rebuild
regression. Practical trigger: uninstalling and reinstalling a tool, or any root that is briefly
absent and returns empty — a re-created config directory, a remounted home, a restored backup.

Severity: the bytes are archived before the removal (NFR-01 holds — verified recoverable), so this
is *disappearance*, not destruction. But nothing tells the user, and the artifact is gone from every
tool at once, which reads exactly like the skill-truncation report that opened this investigation.

**Why it is not patched here.** It needs a US-11 semantics decision, not a code tweak. AC-4 requires
that an unavailable tool's state entry be *preserved verbatim* — and that preserved entry is
precisely what later reads as a deletion once the tool returns. Distinguishing "this tool was
unavailable and came back empty" from "the user deleted the artifact here" needs per-tool
availability history in the planner, which the rebuild deliberately does not carry (the old
`tool_status` transition tracking was dropped as YAGNI — see the deferred list). Options span from
recording an availability flag per surface, to dropping a recorded surface when its root goes away
so the artifact simply re-extends on return, to keeping AC-4 and accepting the behaviour. **Owner
decision required.**

The AC-3 test ships as a **strict xfail** naming this cause, so it fails loudly the moment the
behaviour changes rather than sitting silently green.

**FIXED DURING THE SWEEP — US-01 AC-10 executable bits (regression introduced by S23i earlier the
same day).** The legacy tree preserves mode on skill auxiliary files because `stage_skill_dir` uses
`shutil.copytree`, whose default `copy2` carries it. S23i's first implementation wrote auxiliary
content through `write_bytes`, losing the execute bit — a shipped skill's helper script arrived
non-runnable. `AuxiliaryFile` now records an `executable` flag, set from the source's mode and
re-applied on write by widening the file's existing read bits (so the receiving machine's umask is
respected rather than a hard 0o755). Two tests added. Sweep re-run: passes at mode 0o775.

**Not covered by this sweep**, and therefore still unknown: daemon/CLI exit codes end-to-end
(NFR-10 has unit coverage), portable-library merge against a live store, first-boot reconciliation
across more than two tools, secret-policy enforcement at each egress, NFR-08/09 resource behaviour,
and the Windows/macOS path surfaces. A second sweep pass should cover these before S24 is scoped.

**US-16 (global-rules section decomposition) is implemented in NEITHER tree.** Ten acceptance
criteria, zero implementation in `src/` or `src_new/`. This is unbuilt spec rather than a cutover
regression, so it does not block the flip — but it should not be carried as if it were done, and it
is entangled with the deferred US-15 egress enforcement (both concern global-rules content
boundaries, and the register already notes US-16 needs a spike).

**Raised for the owner, no change made — the glitch heuristic can undo a deliberate deletion.**
`Syncer._glitch_tools` flags a tool whose recorded artifacts vanish ≥ 2-at-once as glitched
(US-11 AC-9) and re-projects rather than propagating a removal. A user deliberately removing several
skills from one tool therefore has the removal undone; the field report's author hit exactly this
while trying to delete. Whether a deliberate bulk deletion should be distinguishable from a
filesystem glitch is a governance question (US-11 AC-9's wording), not an implementation detail.
