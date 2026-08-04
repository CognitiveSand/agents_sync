# Amendment 023 — An artifact reaches a tool that has no copy of it

- status: applied (rebuild `src_new/`, 0.7.60)
- branch: fix/size-explosion-hardening
- date: 2026-08-04
- relates to: project description Goal 1 (propagation), FR-05…FR-09 (the matrices),
  US-03 (adoption), US-11 AC-3 (re-extend), NFR-02 (latency), NFR-05 (no churn);
  `docs/audits/cutover_loose_ends_register_2026_07_12.md` (AC parity sweep, G-gate-1/2).

## Motivation

The rebuild propagated edits **among** the tools that already held an artifact but
never **created** one on a tool that lacked it. `reconcile_known._absorb_change` drew
its projection targets from observed surfaces:

```python
targets = tuple(o.tool_surface for o in observations if o is not winner)
```

A tool with no copy produces no observation, so it was never a target. `adopt_candidates`
did not close the gap either: its `others` are the *already-present* duplicate surfaces
it reconciles into one identity at first boot. Reproduced on a two-tool workspace: an
artifact planted on one tool was adopted, its id injected, and the daemon then settled
at `changed == 0` with the second tool's root still empty, poll after poll — for every
kind, agents included.

This is the product's headline promise ("editing a customization on any one
agentic_tool propagates to every other participating agentic_tool"), so it also blocked
S24, which is defined as *proving behaviour against the rebuild*: `test_e2e_sync` and
`test_cross_adapter_adoption_matrix` cannot pass against a tree that does not do this.

## Principle / decision

**The planner decides where an artifact belongs, not merely where it was seen.** A
managed artifact has an *expected* set of surfaces — one per supporting tool whose root
exists — and an expected surface that no tool occupies is a projection target.

Deriving each location from `slugify_name(name)`, the same slug the reconciliation key
uses, is what makes minting safe without new guards: two artifacts that would land on
one path necessarily share a `(kind, slug)` key, so the planner's existing collision
rejection already refuses them. No minted write can silently displace another artifact.

Layering: `compute_sync_plan` stays pure and registry-free. `sync_once` already holds
both the surface specs and the stored canonicals (hence each artifact's name), so it
derives the expected surfaces and passes them in as **data**. No callable is injected
into the domain model, and `read_tool_surfaces` — which owns the spec types — owns the
minting.

Two invariants the rule must not break, both covered by tests:

- **A deliberate removal is never undone.** An extension rule that only asked "does this
  tool lack a copy?" would immediately restore a file the user just deleted, making
  deletion impossible. A recorded tool counts as occupied, and in any case a vanished
  recorded surface short-circuits to `RemoveArtifact` earlier in the pipeline.
- **An absent root is never created.** A missing root means the tool is not installed
  (US-11); syncing must not scatter files into directories the user never opted into.
  `projection_surfaces` yields nothing for a spec whose root does not exist.

Timing: adoption on one poll, extension on the next — within NFR-02's "twice the
configured polling interval", and it settles immediately after (verified).

## Proposed governance edits (require user validation)

### User stories
**None.** Goal 1, the FR-05…FR-09 matrices and US-03 already own this; the gap was a
failure to meet them.

### Requirements
**None.** No `shall`-language added.

## Implementation

1. `read_tool_surfaces.projection_surfaces(specs, kind, name)` — where an artifact
   belongs on every declared surface, skipping specs whose root is absent. Per layout:
   directory → `root/<slug><suffix>`; skill folder → `root/<slug>/SKILL.md`; whole-file
   rules → the highest-precedence declared filename (FR-10); keyed map → a slot keyed by
   the artifact's own name (wire data, not a filesystem basename).
2. `reconcile_known` gains `expected_surfaces` and a final rule: when nothing changed but
   a supporting tool holds no copy, `ProjectToTools` onto the unoccupied surfaces.
   `_absorb_change` adds them to its targets too, so an edit is how a new artifact first
   reaches its siblings rather than being stranded on its origin.
3. `compute_sync_plan` threads a per-artifact map through; defaulted empty, so every
   existing caller and test is unaffected and the rule is inert without it.
4. `sync_once` derives the map from the specs it already built and the stored canonicals
   it already loaded.

## Verification

`tests_new/test_cross_tool_creation.py` — a new artifact reaches a tool that never had
it; the projected copy carries the shared identity (not a lookalike that would be adopted
as a second artifact); extension settles and does not rewrite every poll (NFR-05); a
deliberate removal is not undone; an absent tool root is never created.

Two existing tests encoded the old behaviour and were corrected, not weakened: they
asserted that the poll after adoption was a no-op, which was only true because
propagation did not happen. They now assert adopt → extend → settle.

Parity probe: **Goal 1 now passes.** AC sweep: 13 of 14.

## Known limitation — US-11 AC-3 is blocked by a separate, older defect

The sweep's remaining failure is *re-extend onto a tool whose root returned*, and it is
**not** fixed here. A recorded tool whose root returns **empty** is read as a deletion:
`_has_vanished_surface` short-circuits to `RemoveArtifact` before the extension rule is
reached, and once the returning root lifts the two-tool guard the removal executes,
taking the artifact off every healthy tool. The bytes survive in the archive (NFR-01), so
this is disappearance rather than destruction, but the user is not told.

**The legacy tree behaves identically** — verified — so this is a long-standing defect
shared by both trees and live in the shipped daemon, not a rebuild regression. Resolving
it needs a US-11 availability decision (AC-4 says an unavailable tool's entry is
*preserved verbatim*, which is exactly what later reads as a deletion), so it is recorded
in the register rather than patched here. The test for AC-3 is kept as a **strict xfail**
naming the cause, so it fails loudly the moment the behaviour is fixed.
