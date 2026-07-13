# Restart — 2026-07-12

> Last updated by Claude at 2026-07-12T00:00:00+0200. This file is a session-handoff
> snapshot. A fresh session reading this should be able to resume work without further
> explanation.

## 0. Git pin (do not edit by hand)

- `head_sha`: 1695783478d9322cf4f4e91dab4c9401a56c06ff
- `head_short`: 1695783
- `branch`: fix/size-explosion-hardening
- `dirty`: true
- `dirty_summary`: 1 modified (tracked), 5 untracked (audit artifacts + export zip)
- `remote_head`: 1695783 (upstream = origin/fix/size-explosion-hardening — in sync)
- `saved_at`: 2026-07-12T00:00:00+0200

Uncommitted paths (see 3.4): `M docs/architecture_implementation_plan.md` — the applied
Phase-G-feasibility revision, deliberately **left uncommitted pending user's wording review**.
Untracked (project convention — never stage): `agents_sync_library_export.zip`,
`docs/audits/.last_code_review.json`, `docs/audits/code_audit_2026_06_03__02_20.md`,
`docs/audits/cutover_loose_ends_register_2026_07_12.md` (THIS session's register),
`docs/audits/raw_audits_results/`.

## 1. Read these first

- `~/.claude/AGENTS.md` — global engineering rules (POLA/KISS/YAGNI/DRY/SRP/SoC; functions
  ≤40 lines, modules ≤500/≤300; surgical; Bash discipline; §11 gh-token push pattern).
  `~/.claude/CLAUDE.md` @-includes it.
- **`docs/audits/cutover_loose_ends_register_2026_07_12.md`** — THIS session's key output. The
  full loose-ends audit + every disposition decision. Read it before touching the plan.
- `docs/architecture_implementation_plan.md` — **the spine.** The top "Progress (current state)"
  block + the new "Cutover readiness" block + the rewritten Phase F-completion (S23f/g/h) and
  Phase G (S24/S25) tables are the live status. Trust the Progress + Cutover-readiness blocks.
- `docs/architecture_simplification_proposal.md` (rev 4) — the design (§9 concurrency = atomic
  writes + recompute, NO lock — this is exactly the F4 residual we're closing at S23h).
- `docs/project_requirements.md` — **FR-06** (skill matrix — the spec basis for S23f); NFR-15
  (export secret residual); NFR-16 (canonical authority).
- `docs/project_description.md` — glossary; the five `customization_type`s incl. `skill`.
- `docs/stories/US-07-watch-mode.md` (AC-3 open governance), `US-15-*` (egress enforcement,
  deferred), `US-16-*` (red-card design questions), `US-04-*` (rename — realized in rebuild).
- Auto-memory `MEMORY.md` — esp. [[feedback_code_change_workflow]], [[feedback_audit_cadence]],
  [[feedback_remediation_value_filter]], [[project_no_formal_backlog]], [[feedback_no_rm_policy]].

## 2. Working context (non-obvious deltas)

- **This session was an AUDIT + PLAN-REVISION session, not a coding session.** The trigger: the
  next queued step was "S24 cutover", but investigating it revealed the plan's Phase G was
  **mechanically infeasible** and the rebuild was **not feature-complete**. We audited, decided
  dispositions, and rewrote the plan. NO production code changed.
- **Greenfield-parallel REBUILD.** New code `src_new/agents_sync/`, tests `tests_new/`. Old
  `src/agents_sync/` is REFERENCE ONLY. Rebuild suite: `uv run pytest -c pytest_new.ini` (697
  tests); default `pytest` = OLD conformance suite `tests/` (against old src). Full gate =
  `bash scripts/ci.sh`. At **0.7.55**. Rebuild bumps = PATCH `feat(rebuild)`/`fix(rebuild)`.
- **Five investigations ran** (2 cutover audits via general-purpose+fable; 3 fable sweeps:
  deferred-list, coverage-parity, marker sweep). Findings consolidated into the register.
- **Key cutover facts:** 59/73 `tests/` files import old-tree module names absent from `src_new`
  (only `parser_bounds` survives the rename); 40 ride on `agents_sync.sync.Syncer` (no new-tree
  equivalent — new API is functional `sync_once(...)`). So S24 needs a `Syncer`-shaped ADAPTER,
  not an in-place repoint. The `tests/` suite splits: ~40 behavioural (repoint) vs ~27 old-internal
  units (retire at S25, coverage already in `tests_new/`).
- **Decisions locked this session:** US-15 egress enforcement → DEFER post-cutover; F2 rules-
  projection leak → FIX (S23g, a real bug); F3 skills-as-a-kind → CARRY (FR-06 required, S23f);
  F4 file-locking/shared-file race → KEEP (mitigate, S23h); F5 v0.4 migration → DEFER-UNTIL-NEEDED
  (leave script+installers untouched); D6 availability logging → DROP (YAGNI); amendments 015/016
  → CLOSE as realized/superseded.
- **Git push uses the gh token over HTTPS** (SSH keys passphrase-protected; AGENTS.md §11):
  `git -c credential.helper='!gh auth git-credential' push https://github.com/CognitiveSand/agents_sync.git fix/size-explosion-hardening`.
  A URL push doesn't advance `origin/…`; follow with a fetch into `refs/remotes/origin/…`.
- **GOTCHA (Bash hooks):** `&&`-chains and `sed` are BLOCKED by user hooks — one action per Bash
  call; use Read/Edit/Grep not sed.

## 3. Active task

### 3.1 Goal

Get the rebuild's implementation plan (`docs/architecture_implementation_plan.md`) back to a
**feasible, internally-consistent state**, then execute the revised Phase G (finish the rebuild,
prove behaviour against `src_new`, flip + retire the old tree) — nothing user-visible ships until
cutover.

### 3.2 Constraints specific to this task

- Hard: each plan step goes through the `incremental_step` gate (docs → red-first tests →
  `/audit-tests` → code → full CI → ship). OLD conformance suite `tests/` stays green at every
  step and across cutover. Never edit `src/`. Governance edits (US/reqs/AC/description/objectives)
  need user approval of exact final text. No-rm (convert obsolete docs to historical records).
- Soft: rebuild bumps PATCH `feat(rebuild)`/`fix(rebuild)`; apply only audit findings that bring
  value; the plan's Progress + Cutover-readiness blocks are the authoritative live status.
- Out of scope now: US-15 enforcement, v0.4 migration, D6 logging (all deferred post-cutover).

### 3.3 Status — what is done

- **Loose-ends audit COMPLETE** — 26 loose ends across 6 categories, all dispositioned. Saved to
  `docs/audits/cutover_loose_ends_register_2026_07_12.md` (untracked).
- **Plan revision APPLIED (uncommitted)** to `docs/architecture_implementation_plan.md` (+108/-21):
  fixed stale "Phases D–G not started"; corrected `@import`(done)/egress-enforcement(deferred);
  added "Cutover readiness" decisions block; fixed the `pytest_new.ini` isolation description;
  corrected the "directory rename / no import rewritten" paragraph; rewrote the Safety-net section
  (behavioural-invariant vs old-internal-unit); added Phase F-completion table (S23f skills/FR-06,
  S23g rules-projection fix, S23h shared-file mitigation) and rewrote Phase G (S24 = prove-behaviour-
  in-parallel-stage, S25 = flip + retire).
- **Register updated** with the resolved decisions + "plan applied" note.

### 3.4 Status — what is in progress

**One uncommitted tracked file: `docs/architecture_implementation_plan.md`** (the revision above),
left uncommitted on purpose — the user wanted to eyeball the applied wording before committing. The
register (`docs/audits/cutover_loose_ends_register_2026_07_12.md`) is written and stays untracked.
No background agents. No half-applied edits — the revision is complete and coherent.

### 3.5 Next concrete step

Ask the user whether to **commit the plan doc** (plan-only, message
`docs(rebuild): make Phase G feasible; add pre-cutover completion + loose-ends dispositions`) or
to review the wording first. Stage ONLY `docs/architecture_implementation_plan.md` (never the
untracked audit artifacts). Once committed, the first real work step is **S23f** (skill
directory-tree dialect + recipes, FR-06) via the `incremental_step` gate.

### 3.6 Open questions / decisions awaiting the user

- **Commit-now vs review-first** for the plan doc (see 3.5) — the only immediate blocker.
- **US-07 AC-3 wording clarification** (parked): `SyncResult.failed` is a flat artifact-id list
  with no `agentic_tool` dimension; resolver judged AC-3 met under NFR-13 "when applicable" and
  recommended clarifying the AC text (needs a `docs/amendment/020` + AC edit, user approval of
  exact text). Non-blocking; parked past cutover per this session's decision.

## 4. Other tasks queued behind the active one

- **S23f — Skill (directory-tree) dialect + skill recipes** (FR-06; Antigravity currently inert).
  First real work after the commit. Medium–large.
- **S23g — Rules-surface projection render restore** (fix the `rules_source_body` leak + test). Small–medium.
- **S23h — Shared-file concurrency mitigation** (re-read-verify-before-replace on keyed-map RMW + test). Medium.
- **S24 — Prove behaviour against `src_new`** (the `Syncer`-shaped adapter + repoint ~40 behavioural
  conformance tests to a `pythonpath=src_new` stage). Large — split into batches.
- **S25 — Flip + retire** (pyproject entry-point fix, `mv src_new→src`, delete old modules, retire
  27 old-internal unit tests, resolve `test_parser_bounds.py` collision, collapse pytest configs,
  measure LOC, update `architecture.md` + protocol). Large.
- **Close amendments 015/016** as historical records (realized / superseded). Small.
- **Deferred post-cutover** (tracked in register + plan Cutover-readiness): US-15 egress enforcement
  (+ US-16 spike), v0.4 migration, D6 availability logging, `from_dict` hardening, gemini `oauth`,
  reserved names, extend-to-newly-available, tied-mtime WARN, remove-arm render guard, JSONC (YAGNI),
  upgrade-seam e2e, marker-discipline successor, US-07 AC-3 (3.6).

## 5. Files touched this session (skim list)

- `docs/architecture_implementation_plan.md` [edited, UNCOMMITTED] — the Phase-G-feasibility revision
- `docs/audits/cutover_loose_ends_register_2026_07_12.md` [created, untracked] — the master register
- `docs/architecture_implementation_plan.md` [read, full]
- `docs/architecture_simplification_proposal.md` [read, concurrency/lock sections]
- `docs/project_requirements.md`, `docs/project_description.md` [read, grep — FR-06, skill kind]
- `docs/amendment/015-rename-propagation.md`, `016-simplify-full-code.md` [read]
- `src_new/agents_sync/sync_once.py`, `command_line_interface.py`, `__init__.py` [read]
- REFERENCE (never edit): `tests/conftest.py`, `tests/_helpers.py` context (via survey agents),
  `src/agents_sync/` vs `src_new/agents_sync/` module inventories

## 6. Anything else the next session needs to know

- **The plan's "Phase E/F complete" was overstated** — this session's central finding. Three gaps
  (skills/FR-06, rules-projection bug, shared-file race) were wrongly marked done; they are now the
  Phase F-completion steps S23f/g/h that MUST land before the S25 flip deletes the old tree.
- The register is the durable record of the whole audit — if the plan and register ever disagree,
  the register + git history win.
- Commits this session: `1695783` (archive consumed 2026-07-11 handoff — a Mode-B resume happened
  at the start of this session, then the work pivoted to the audit). The plan revision is NOT yet
  committed.
- 2026-07-12: `/restart save` invoked after applying the plan revision, with the plan doc still
  uncommitted pending user wording review. Next session: confirm commit, then begin S23f.
