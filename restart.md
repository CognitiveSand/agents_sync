# Restart — 2026-07-11

> Last updated by Claude at 2026-07-11T16:45:00+0200. This file is a session-handoff
> snapshot. A fresh session reading this should be able to resume work without further
> explanation.

## 0. Git pin (do not edit by hand)

- `head_sha`: 5d770b1ffc34149cb7e70f81bba0823cb2534384
- `head_short`: 5d770b1
- `branch`: fix/size-explosion-hardening
- `dirty`: false (tracked tree clean)
- `dirty_summary`: clean (tracked); 4 untracked — all `docs/audits/**` artifacts +
  `agents_sync_library_export.zip` (left untracked by project convention; NOT pending work)
- `remote_head`: 5d770b1 (pushed; upstream = origin/fix/size-explosion-hardening — in sync)
- `saved_at`: 2026-07-11T16:45:00+0200

## 1. Read these first

- `~/.claude/AGENTS.md` — global engineering rules (POLA/KISS/YAGNI/DRY/SRP/SoC; functions
  ≤40 lines, modules ≤500/≤300; tools-as-data, NO tool-name branches; surgical; Bash
  discipline). `~/.claude/CLAUDE.md` just @-includes it. **§11 now documents the gh-token
  push pattern** (SSH keys are passphrase-protected here — see §2).
- `docs/architecture_implementation_plan.md` — **the spine.** The "Progress (current state)"
  block at the top is the live status (Phase F done through S22; **S23 COMPLETE**; **S24 gate
  `parser_bounds` COMPLETE 0.7.55**; **S24 cutover next**, then S25). The build-order table
  rows S24/S25 + the "Deferred, tracked here so they are not lost" bullet are the carried queue.
- `docs/architecture_simplification_proposal.md` (rev 4) — the design the plan builds (§9
  concurrency = atomic writes + recompute-from-disk; §10/§13 dialects + module map).
- `docs/project_description.md` — glossary (`last_modified`/`generation` = store-owned canonical
  metadata; `last_modified` = user-content-mod time, NOT file mtime).
- `docs/project_requirements.md` — FR-*/NFR-*; NFR-15 = export secret-scan residual; NFR-16 =
  canonical authority/fidelity; SEC-C-01/02 = the parser bounds just landed.
- `docs/stories/US-07-watch-mode.md` — AC-3 is the open governance clarification (see 3.6).
- Auto-memory `MEMORY.md` (loaded each session) — esp. [[feedback_audit_cadence]],
  [[feedback_remediation_value_filter]], [[project_no_formal_backlog]], [[feedback_code_change_workflow]].

## 2. Working context (non-obvious deltas)

- **Greenfield-parallel REBUILD.** New code in `src_new/agents_sync/`, tests in `tests_new/`.
  Old `src/agents_sync/` is REFERENCE ONLY (never edit). Cutover (S24–S25) is a `src_new → src`
  rename. Rebuild suite: `uv run pytest -c pytest_new.ini`; default `pytest` runs the OLD
  conformance suite (`tests/`). Full gate = `bash scripts/ci.sh` (ruff + mypy src + mypy src_new +
  pytest tests/ + pytest -c pytest_new.ini). Now **697 rebuild tests**.
- **Rebuild bumps are PATCH `feat(rebuild)` / `fix(rebuild)`**; a bump runs `uv lock` and stages
  `uv.lock`. NO git tag. Stage ONLY intended source/test/doc/version files — `docs/audits/**` +
  `graphify-out/` + `agents_sync_library_export.zip` stay untracked (never `git add -A`). At **0.7.55**.
- **Git network ops (pull/push/fetch) use the gh token over HTTPS** — the SSH keys for the
  `github-cs` host alias are passphrase-protected and the agent shell has no TTY/`SSH_AUTH_SOCK`,
  so plain `git pull`/`git push` fail with "Permission denied (publickey)". Pattern (now in
  AGENTS.md §11): `git -c credential.helper='!gh auth git-credential' push
  https://github.com/CognitiveSand/agents_sync.git fix/size-explosion-hardening`. Same for
  pull/fetch. A push via URL does NOT advance `origin/…`; a follow-up fetch into
  `refs/remotes/origin/…` keeps `git status` honest.
- **incremental_step gate** (project workflow, NOT a registered skill): docs → red-first tests
  (proven red) → `/audit-tests` → code → full `bash scripts/ci.sh` → ship (commit + push). For
  changes that touch GOVERNANCE (project description/objectives/user stories/AC/requirements),
  use the `code_change` skill and get user approval of exact final text before editing US/reqs.
- **This repo has NO CognitiveSDD backlog** — track later work in the plan's "Deferred" list.
- **GOTCHA (formatter):** a PostToolUse ruff hook auto-strips a just-added import the instant it's
  unused. When wiring a new dependency, add the *usage* edits first (accept transient F821), then
  add the import last — it sticks once ≥1 usage exists.
- **GOTCHA (shell):** a `cd` inside one Bash call PERSISTS the shell working dir and can break a
  later `pytest -c pytest_new.ini` (config not found). Run git/pytest from the repo root.

## 3. Active task

### 3.1 Goal

Execute the thin-clean-architecture rebuild (`docs/architecture_implementation_plan.md`) one gated
increment at a time, until cutover replaces the old `src/` with `src_new/`.

### 3.2 Constraints specific to this task

- Hard: each plan step goes through the `incremental_step` gate (docs → red-first tests →
  `/audit-tests` → code → full CI → ship). The OLD conformance suite (`tests/`) stays green at
  every step and across the cutover. Never edit `src/`. Governance edits need user approval of
  exact final text. `last_modified` = user-content-mod time NOT file mtime.
- Soft: rebuild bumps PATCH `feat(rebuild)`/`fix(rebuild)`; heavyweight two-auditor
  `/code_and_tests_quality_review` runs ONCE per plan-step NUMBER after all its sub-increments
  ([[feedback_audit_cadence]]); apply only findings that bring value ([[feedback_remediation_value_filter]]).
- Out of scope now: nothing user-visible ships until cutover S24–S25.

### 3.3 Status — what is done

- Phases through **S22 COMPLETE**; **S23 (Portable library) COMPLETE**; end-of-S23 batched-audit
  remediation → 0.7.54.
- **S24 GATE COMPLETE — `parser_bounds` size-explosion hardening (0.7.55, commit `5d770b1`).**
  New `src_new/agents_sync/parser_bounds.py`: 16 MiB per-file text cap, 256 KiB front-matter scan
  window, 10 000-node bounded YAML composer. `ParserBoundsExceeded` subclasses the dialect layer's
  `MalformedSurfaceError`, so the read phase's existing `except MalformedSurfaceError → ParseFailure`
  absorbs every bound with no caller change. Wired at the minimal chokepoints: `dialects/
  structured_text.deserialize` (one seam covers JSON/TOML + keyed-map slots), `dialects/
  markdown_frontmatter` (`enforce_frontmatter_window` bounds the regex scan; body recovered from
  original text via `match.start(2)` offset alignment; `make_bounded_composer_class()` threaded into
  `_yaml()`), and five file-read seams via `read_text_bounded` (`read_tool_surfaces`,
  `canonical_store` [oversize→quarantine], `sync_state_store`, `runtime_config`,
  `rules_import_resolution`). `/audit-tests` PASS (2 minor weak-assertion fixes applied: prefix
  assertion on the window test + `match=` on 3 size-cap exception tests). Full CI green (conformance
  `tests/` + 697 rebuild tests). Pushed.

### 3.4 Status — what is in progress

**Nothing mid-edit — clean shipped checkpoint at `5d770b1`.** Tracked tree clean; only untracked
`docs/audits/**` + `agents_sync_library_export.zip` artifacts (convention: untracked, not pending).
No background agents.

### 3.5 Next concrete step

Start **S24 — cut the daemon over** via the `incremental_step` gate. The gate (`parser_bounds`) is
now satisfied. First action: read the plan's S24 build-order row + `architecture_simplification_
proposal.md`'s cutover/pipeline sections, and map how the OLD conformance suite (`tests/`) currently
binds to `src/` vs what "point the full conformance suite at the new pipeline (`poll_daemon`/
`sync_once` = read → plan → execute)" concretely requires — to scope the cutover before writing
red-first tests. Keep `tests/` green throughout. Large step; expect to split it.

### 3.6 Open questions / decisions awaiting the user

- **US-07 AC-3 governance clarification** (from the S23 audit, poll_daemon 0001/0002 P0). The
  systemic/per-artifact failure logs carry no single `agentic_tool` dimension (`SyncResult.failed`
  is a flat artifact-id list). Resolver judged AC-3 substantially met under NFR-13's "when
  applicable" and recommended clarifying the AC text, NOT changing code. Needs user approval of
  exact governance wording (a `docs/amendment/…` record + the AC edit). Not blocking S24.

## 4. Other tasks queued behind the active one

- **S25 — retire superseded modules** (delete old discovery/adoption/sync; `src_new → src` rename;
  measure LOC vs ~6–7k target; update `docs/architecture.md` + `agentic_tool_integration_protocol.md`).
  Blocked on S24. Large.
- **Deferred tail** (plan's "Deferred" list; some attached to already-passed S17–S20 — sweep to
  confirm still-open): mcp `@import` resolution + framework egress-guard enforcement; mcp secret
  policy; per-tool field-spelling overrides (opencode `enabled` inversion) + codex carriers (partly
  done); per-tool inline `env_reference_style` conversion; `CanonicalDocument.from_dict`
  type-coercion hardening; S19 audit watch-items (planner prunes vanished tool's surface after
  rename; same-file render targets); gemini mcp `oauth` auth-field spelling; **US-07 AC-3** (3.6).
  Each small–medium.

## 5. Files touched this session (skim list)

- `src_new/agents_sync/parser_bounds.py` [created] — the bounds module
- `tests_new/test_parser_bounds.py` [created] — 12 regression tests (mock-free)
- `src_new/agents_sync/dialects/structured_text.py` [edited] — `enforce_text_bound` at deserialize
- `src_new/agents_sync/dialects/markdown_frontmatter.py` [edited] — window + bounded composer
- `src_new/agents_sync/read_tool_surfaces.py` [edited] — `read_text_bounded` at both read seams
- `src_new/agents_sync/canonical_store.py` [edited] — oversize→quarantine + bounded store read
- `src_new/agents_sync/sync_state_store.py` [edited] — bounded state.json read
- `src_new/agents_sync/runtime_config.py` [edited] — bounded config TOML read
- `src_new/agents_sync/rules_import_resolution.py` [edited] — bounded `@import` target read
- `docs/architecture_implementation_plan.md` [edited] — S24-gate progress bullet; deferred entry
  struck; version header 0.7.48 → 0.7.55
- `pyproject.toml` + `uv.lock` [edited] — 0.7.54 → 0.7.55
- REFERENCE READs (old tree, never edit): `src/agents_sync/parser_bounds.py`,
  `tests/test_parser_bounds.py`, `src/agents_sync/markdown_yaml_metadata_block.py`

## 6. Anything else the next session needs to know

- Commits this session: `bc9a0d2` (archive consumed 2026-07-01 handoff) → `5d770b1`
  (parser_bounds feat, 0.7.55). Both pushed to `origin/fix/size-explosion-hardening`.
- Early this session a stale `.gitignore` "clean-up" chore that gitignored the audit artifacts was
  made then DROPPED via `git reset --hard` — it violated the untracked-audits convention. Audit
  artifacts + the export zip stay untracked, never gitignored, never staged.
- The plan's top "Progress (current state)" block is the authoritative live status — trust it.
- Each rebuild step also writes a markdown audit/remediation report under `docs/audits/` (untracked).
- 2026-07-11: `/restart save` invoked after shipping the parser_bounds S24 gate, to `/clear` and
  begin S24 in a fresh context. Clean checkpoint at `5d770b1`. Next session begins the S24 cutover.
