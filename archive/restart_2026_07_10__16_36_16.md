# Restart — 2026-07-01

> Last updated by Claude at 2026-07-01T14:23:30+0200. This file is a session-handoff
> snapshot. A fresh session reading this should be able to resume work without
> further explanation.

## 0. Git pin (do not edit by hand)

- `head_sha`: cc5c7b335659b5c3bf77dc5df6f58e3dfd5133b1
- `head_short`: cc5c7b3
- `branch`: fix/size-explosion-hardening
- `dirty`: false (tracked tree clean)
- `dirty_summary`: clean (tracked); 39 untracked — all `docs/audits/**` audit artifacts +
  `graphify-out/` (left untracked by project convention; NOT pending work)
- `remote_head`: cc5c7b3 (pushed; upstream = origin/fix/size-explosion-hardening — in sync)
- `saved_at`: 2026-07-01T14:23:30+0200

## 1. Read these first

- `~/.claude/AGENTS.md` — global engineering rules (POLA/KISS/YAGNI/DRY/SRP/SoC; functions
  ≤40 lines, modules ≤300; tools-as-data, NO tool-name branches; surgical; no bulk renames;
  Bash discipline). `~/.claude/CLAUDE.md` just @-includes it.
- `docs/architecture_implementation_plan.md` — **the spine.** The "Progress (current state)"
  block at the top is the live status (Phase F done through S22; **S23 COMPLETE**; S24–S25 next).
  The build-order table (rows S24/S25) + the "Deferred, tracked here so they are not lost" bullet
  are the carried-forward queue.
- `docs/architecture_simplification_proposal.md` (rev 4) — the design the plan builds.
- `docs/project_description.md` — glossary (defines `last_modified`/`generation` as store-owned
  canonical metadata; `last_modified` = user-content-mod time, NOT file mtime).
- `docs/project_requirements.md` — FR-*/NFR-*; **NFR-15 documents the secret-scan residual**
  (prose secrets belong in `env`/`headers`); NFR-16 = canonical authority/fidelity.
- `docs/stories/US-07-watch-mode.md` — AC-3 is the open governance clarification (see 3.6).
- `docs/audits/code_audit_remediation_2026_06_23__14_16.md` (untracked) — the just-finished
  remediation, per-finding disposition of all 40 audit findings.
- Auto-memory `MEMORY.md` (loaded each session) — esp. [[feedback_audit_cadence]],
  [[feedback_remediation_value_filter]], [[project_no_formal_backlog]], [[feedback_verify_before_designing]].

## 2. Working context (non-obvious deltas)

- **Greenfield-parallel REBUILD.** New code in `src_new/agents_sync/`, tests in `tests_new/`.
  Old `src/agents_sync/` is REFERENCE ONLY (never edit). Cutover (S24–S25) is a `src_new → src`
  rename. Rebuild suite: `uv run pytest -c pytest_new.ini`; default `pytest` runs the OLD
  conformance suite (`tests/`). Full gate = `bash scripts/ci.sh` (ruff + mypy src + mypy src_new +
  pytest tests/ + pytest -c pytest_new.ini); the pre-push hook runs it. Now **685 rebuild tests**.
- **Rebuild bumps are PATCH `feat(rebuild)` / `fix(rebuild)`**; a bump must run `uv lock` and stage
  `uv.lock`. NO git tag for rebuild steps. Stage ONLY intended source/test/doc/version files —
  `docs/audits/**` + `graphify-out/` stay untracked (never `git add -A`). Currently at **0.7.54**.
- **This session finished the end-of-S23 batched-audit remediation under a ponytail lens** —
  "verify all 40 resolver findings, apply only those that bring value." Key non-obvious catches
  (now in [[feedback_remediation_value_filter]]): a `read_export` duplicate-id guard was DEAD
  (`set(namelist())` collapses dupes first); an import embedded-id re-validate was REDUNDANT
  (filename id validated + equality enforced); the export secret-scan-vs-ship gap is NFR-15's
  DOCUMENTED RESIDUAL, not a hole. Don't auto-apply auditor/resolver recommendations.
- **This repo has NO CognitiveSDD backlog** (no `tools/backlog/`, no aggregate JSON). Track later
  work in the plan's "Deferred, tracked here so they are not lost" list — see [[project_no_formal_backlog]].
- **GOTCHA:** a `cd` inside one Bash call PERSISTS the shell working dir and can break a later
  `pytest -c pytest_new.ini` (config not found). Run git/pytest from the repo root.
- **Governance edits (description/objectives/stories/AC/requirements) need user approval of exact
  final text** — see [[feedback_governance_approval]]. The AC-3 item in 3.6 is exactly this.

## 3. Active task

### 3.1 Goal

Execute the thin-clean-architecture rebuild (`docs/architecture_implementation_plan.md`) one gated
increment at a time, until cutover replaces the old `src/` with `src_new/`.

### 3.2 Constraints specific to this task

- Hard: each plan step (and sub-increment) goes through the `incremental_step` gate (docs →
  red-first tests → `/audit-tests` → code → full CI → ship). Conformance suite (`tests/`) stays
  green at every step and across the cutover. Never edit `src/`. Governance edits need user
  approval of exact final text. `last_modified` is user-content-mod time NOT file mtime; import
  rule is the single `last_modified_wins` (amendment 009), ties favour local.
- Soft: rebuild bumps PATCH `feat(rebuild)`/`fix(rebuild)`; heavyweight two-auditor
  `/code_and_tests_quality_review` runs ONCE per plan-step NUMBER after all its sub-increments
  ([[feedback_audit_cadence]]).
- Out of scope now: nothing user-visible ships until cutover S24–S25.

### 3.3 Status — what is done

- Phases through **S22 COMPLETE**. **S23 (Portable library) COMPLETE**: S23a metadata block
  (0.7.49) · S23b export (0.7.50) · S23c import core (0.7.51) · S23d cross-identity merge +
  preview/`--force` (0.7.52) · S23e CLI export/import wiring (0.7.53).
- **End-of-S23 batched audit remediated → 0.7.54** (commit `435e372`): 40 findings verified under
  ponytail; ~22 applied (single-source `available_tool_count`, CLI `run_daemon`→`daemon_runner`
  shadow, `_apply` atomicity docstring, +13 test strengthenings, 2 red sync_once tests fixed), the
  rest skipped-with-reason / declined / escalated. Report:
  `docs/audits/code_audit_remediation_2026_06_23__14_16.md`.
- **Three escalations dispositioned** (commit `cc5c7b3`, current HEAD): `_import._apply`
  surviving-id guard → declined YAGNI; US-07 AC-3 → added to the plan's Deferred list (needs
  governance text, see 3.6); export secret-scan surface → documented as NFR-15's residual in
  `_export.py`'s docstring.
- Full `bash scripts/ci.sh` green at HEAD (conformance `tests/` + 685 rebuild tests).

### 3.4 Status — what is in progress

**Nothing mid-edit — clean shipped checkpoint at `cc5c7b3`.** Tracked tree clean; only untracked
`docs/audits/**` + `graphify-out/` artifacts. No background agents.

### 3.5 Next concrete step

Start **`parser_bounds` size-explosion hardening** via the `incremental_step` skill — the GATE for
the S24 cutover (it's what this branch is named for). Deferred from S9: a bounded YAML composer, a
front-matter scan window, and a text-size cap; the size-explosion regression tests already in the
conformance suite (`tests/`) enforce it. Must land before S24.

### 3.6 Open questions / decisions awaiting the user

- **US-07 AC-3 governance clarification** (from the S23 audit, poll_daemon 0001/0002 P0). The
  systemic/per-artifact failure logs carry no single `agentic_tool` dimension (`SyncResult.failed`
  is a flat artifact-id list). Resolver judged AC-3 substantially met under NFR-13's "when
  applicable" and recommended clarifying the AC text, NOT changing code. Needs user approval of
  exact governance wording (an `docs/amendment/…` record + the AC edit). Not blocking `parser_bounds`.

## 4. Other tasks queued behind the active one

- **S24 — cut the daemon over** (`poll_daemon`/`sync_once` = read→plan→execute as the active
  pipeline; point the full conformance suite at it, keep green). Blocked on `parser_bounds`. Large.
- **S25 — retire superseded modules** (delete old discovery/adoption/sync; `src_new → src` rename;
  measure LOC vs ~6–7k target; update `docs/architecture.md` + agentic_tool_integration_protocol.md).
  Blocked on S24. Large.
- **Deferred tail** (plan's "Deferred" list; some attached to already-passed S17–S20 — sweep to
  confirm still-open): mcp `@import` resolution + framework egress-guard enforcement; mcp secret
  policy; per-tool field-spelling overrides (opencode `enabled` inversion) + codex carriers (partly
  done); per-tool inline `env_reference_style` conversion; `CanonicalDocument.from_dict`
  type-coercion hardening; S19 audit watch-items (planner prunes vanished tool's surface after
  rename; same-file render targets); gemini mcp `oauth` auth-field spelling; **US-07 AC-3** (3.6).
  Each small–medium.
- **Trivia:** plan header (line ~17–18) still says Version 0.7.48 — stale, we're at 0.7.54; one-line fix.

## 5. Files touched this session (skim list)

- `src_new/agents_sync/canonical_store.py` [edited] — gen≥1 self-heal documented
- `src_new/agents_sync/command_line_interface.py` [edited] — `run_daemon`→`daemon_runner` rename; re-plan comment
- `src_new/agents_sync/sync_once.py` [edited] — derive `available_tool_count` internally; persistence comment
- `src_new/agents_sync/portable_library/_import.py` [edited] — `_apply` atomicity docstring
- `src_new/agents_sync/portable_library/_export.py` [edited] — NFR-15 residual pointer in docstring
- `tests_new/{test_canonical_metadata,test_command_line_interface,test_poll_daemon,test_portable_library,`
  `test_portable_library_import,test_portable_library_merge,test_sync_once}.py` [edited] — +13 strengthenings
- `docs/architecture_implementation_plan.md` [edited] — S23-complete note + Deferred-list AC-3 entry
- `pyproject.toml` + `uv.lock` [edited] — 0.7.53 → 0.7.54
- `docs/audits/code_audit_remediation_2026_06_23__14_16.md` [created, untracked] — remediation report
- READ: the 40-finding resolver `resolutions.json`; `_import_read.py`, `poll_daemon.py`,
  `secret_policy.py`, `execute_sync_plan/__init__.py`, US-07, NFR-15/16
- Memory [created]: `feedback_remediation_value_filter.md`, `project_no_formal_backlog.md` + `MEMORY.md` edits

## 6. Anything else the next session needs to know

- Commits this session: `435e372` (S23 remediation, 0.7.54) → `cc5c7b3` (escalation dispositions).
  Both pushed to `origin/fix/size-explosion-hardening`.
- The plan's top "Progress (current state)" block is the authoritative live status — trust it.
- Each rebuild step also writes a markdown audit/remediation report under `docs/audits/` (untracked).
- `2026-07-01`: `/restart` invoked with no argument after finishing the S23 audit remediation +
  escalation dispositions. Clean checkpoint at `cc5c7b3`. Next session begins `parser_bounds`.
