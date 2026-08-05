# Amendment 024 — A removal signal requires a root we could read

- status: applied (rebuild `src_new/`, 0.7.61)
- branch: fix/size-explosion-hardening
- date: 2026-08-05
- relates to: US-11 AC-4 (only an `available` agentic_tool sources a removal), FR-04
  (trusted removal source), NFR-01 (data preservation), US-05 AC-2 (removal
  propagation); `docs/audits/cutover_loose_ends_register_2026_07_12.md` (G-gate-2).

## Motivation

Uninstalling one agentic_tool deleted the artifact from **every** tool.

`_has_vanished_surface` asked a single question — is a recorded surface missing this
poll? — which a deleted file and an unreachable root answer identically. The read
phase returns `[]` for a directory that does not exist and `[]` for one that is empty,
so the distinction US-11 rests on never reached the planner.

Verified before changing anything:

- With **three** tools and one artifact, removing a tool's root deleted the artifact
  from the other two on the next poll. The same is true with observations threaded as
  `make_periodic_poll` threads them, so this was the real runtime behaviour.
- The planner *always* emitted `RemoveArtifact`; only the two-tool destructive guard
  suppressed it (`available_tool_count=1` → `[]`, `=2` → `RemoveArtifact`). That guard
  is a blast-radius limiter for a different requirement (US-07 AC-5) and merely masked
  the defect in the degenerate two-tool case — which is why it first appeared to be a
  bug about a *returning* root.
- With two or more artifacts on the vanishing tool, AC-9's glitch rule caught it. The
  exposure was a tool holding exactly one managed artifact.
- **The legacy tree is not affected**: it gates participation on
  `tool_status.is_kind_available`. This was a regression against it.

## Principle / decision

**A missing file is evidence of deletion only if we looked where it should be.**

No new mechanism was needed. `expected_surfaces` — threaded into `reconcile_known` by
amendment 023 for cross-tool creation — is built by `projection_surfaces`, which skips
any surface whose root is absent. It therefore already lists exactly the surfaces we
could read. The vanish rule now consults it: a recorded tool missing from the expected
surfaces is unreachable and cannot source a removal.

This implements US-11 AC-4 as written; **no governance change**, no persisted state, no
extra parameter, no new concept.

### Reachability must be judged per kind, not per tool

An earlier draft proposed tool-level availability. Testing refuted it: removing only
cursor's *agents* root while its *skills* root survived left cursor tool-level
available, and the artifact was still deleted. `expected_surfaces` is per kind by
construction, so it does not have this flaw. The legacy tree documents the same trap:

> Gated on kind-level availability (`is_kind_available`), not tool-level: … (Tool-level
> `is_available` let such a cell through — e.g. copilot, available via its CLI surfaces
> but with no VS Code `rules` root — and crashed render on `Path(None)`.)

### What the rule must not become

"Never remove". A file missing from a root that *was* read is a deliberate deletion and
still propagates (US-05 AC-2), covered by test.

When an artifact has no stored canonical, no expected surfaces can be derived, so
reachability is unknown and the historic behaviour stands. That is a corner (a managed
artifact whose canonical is missing is already degraded) and it is explicit in the code
rather than implied.

## Proposed governance edits (require user validation)

**None.** AC-4 already states the rule normatively; this implements it.

## Implementation

`domain_model/plan/reconcile_known._has_vanished_surface` takes the artifact's expected
surfaces and treats a vanished recorded tool as a removal signal only when that tool is
among them. Four lines of logic; the data was already in the function.

## Verification

`tests_new/test_removal_requires_a_readable_root.py` — an uninstalled tool does not
delete the artifact elsewhere (three tools, so the two-tool guard cannot be mistaken for
the protection); reachability is judged per kind, not per tool; a deletion from a
readable root still propagates; plus two planner-level unit tests pinning both
directions.

Full local CI green: 585 conformance + 745 rebuild, 1 xfail.

## Residual — the returning root

Still open, and unchanged by this: when a root **returns empty**, it is genuinely
reachable again, so a recorded-but-absent surface is once more read as a deletion. A
tool holding exactly one artifact still loses it on reinstall (AC-9 covers two or more).

This residual is irreducible without history: at the moment of return, "the user deleted
the last artifact here" and "this root came back empty" are the same observation.
Distinguishing them needs the previous poll's availability, which is the temporal
qualifier proposed for AC-4 and **declined by the owner** — so the behaviour stands as
US-11 specifies it. The AC-3 test remains a strict xfail naming the cause.
