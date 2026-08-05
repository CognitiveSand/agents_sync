# Amendment 024 — Uninstalling a tool must not delete customizations from the other tools

- status: applied (rebuild `src_new/`, 0.7.61)
- branch: fix/size-explosion-hardening
- date: 2026-08-05
- relates to: US-11 AC-4 (only an `available` agentic_tool can cause a removal), FR-04
  (trusted removal source), NFR-01 (data preservation), US-05 AC-2 (removal
  propagation); `docs/audits/cutover_loose_ends_register_2026_07_12.md` (G-gate-2).

## What went wrong

Uninstalling one agentic_tool deleted the customization from every other tool.

The daemon decides you have deleted a customization by noticing that a file it
recorded is no longer where it recorded it. But two different situations produce
exactly the same evidence — an empty result:

1. you deleted the file, and
2. the daemon could not read the directory the file was supposed to be in.

Uninstalling a tool deletes its directory, which is situation 2. The daemon read it as
situation 1 and propagated the deletion everywhere.

The cause sits one level lower than the decision. When the daemon lists a directory
that does not exist it returns an empty list, and when it lists a directory that exists
but is empty it also returns an empty list. The difference is discarded at that point,
so the code that decides never had it.

Verified before anything was changed:

- With **three** tools and one customization, deleting one tool's directory deleted the
  customization from the other two on the next poll. Also true when the polls carry
  their readings forward the way the running daemon does, so this was real behaviour
  and not an artefact of how it was tested.
- The deciding code *always* asked for the deletion. The only thing stopping it was the
  rule that suppresses destructive work when fewer than two tools are usable. That rule
  exists to limit damage generally (US-07 AC-5), not to handle missing directories, and
  it happened to hide this defect when exactly two tools were installed — which is why
  the problem first looked like it was about a directory *coming back*.
- With two or more customizations in the deleted directory, the existing rule for a
  sudden mass disappearance (US-11 AC-9) caught it. The exposure was a tool holding
  exactly one managed customization.
- **The released `src/` tree is not affected.** It checks whether a tool's directory for
  that kind of customization is reachable before letting it cause a removal. This was a
  regression against it.

## The rule

**A missing file is evidence of a deletion only if the directory it belongs in could be
read.**

No new machinery was needed to apply it. Amendment 023 had already passed the deciding
code a list of the places a customization belongs — one per tool, built by checking each
directory and skipping the ones that are not there. That list is therefore already a
record of which directories could be read. A tool missing from it is one the daemon
could not look at, so it cannot be the reason to delete anything.

This is what US-11 AC-4 already requires, so **no story or requirement changed**. Nothing
new is stored, no argument was added, no new idea was introduced.

### It must be judged per kind of customization, not per tool

An earlier draft proposed judging whether a *tool* was reachable. Testing refuted it:
deleting only cursor's `agent` directory while its `skill` directory survived left
cursor reachable as a tool, and the customization was still deleted. The list from
amendment 023 is per kind of customization, so it does not have this flaw. The released
tree records the same trap in its own code comment:

> Gated on kind-level availability (`is_kind_available`), not tool-level: … (Tool-level
> `is_available` let such a cell through — e.g. copilot, available via its CLI surfaces
> but with no VS Code `rules` root — and crashed render on `Path(None)`.)

### What the rule must not become

"Never delete anything." A file missing from a directory that *was* read is a deliberate
deletion and is still propagated to the other tools (US-05 AC-2). A test holds this.

One case is knowingly left as it was: when a customization has no stored canonical
document, the list of places it belongs cannot be built, so whether its directories were
readable is unknown and the old behaviour stands. Such a customization is already
damaged. This is written down rather than silently relied upon.

## Governance edits requiring validation

**None.** AC-4 already states the rule; this makes the code obey it.

## What changed in the code

`domain_model/plan/reconcile_known._has_vanished_surface` now receives the list of
places the customization belongs and treats a recorded file's absence as a deletion only
when its tool appears in that list. Four lines; the information was already being passed
in for another purpose.

## How it was checked

`tests_new/test_removal_requires_a_readable_root.py`:

- uninstalling a tool does not delete the customization from the others — set up with
  three tools, so the limit-the-damage rule cannot be mistaken for the protection;
- reachability is judged per kind of customization, not per tool;
- deleting a file from a directory that was readable still propagates;
- two tests on the deciding code alone, pinning both directions.

Full local checks green: 585 conformance tests + 745 rebuild tests, one expected
failure (below).

## What is still wrong

When a deleted directory is **recreated empty** — reinstalling a tool, restoring a
backup — it can be read again, so a file recorded there and now absent is once more read
as a deletion. A tool holding exactly one customization still loses it. Two or more are
caught by the mass-disappearance rule.

This cannot be fixed by looking at the present moment alone: when the directory comes
back, "you deleted the last customization here" and "this directory was recreated empty"
are the same observation. Telling them apart needs to know whether the tool was reachable
at the *previous* poll — the wording change proposed for AC-4 and **declined**, so the
behaviour stands as US-11 specifies. The test for it is kept, marked as an expected
failure naming this reason, so it will report loudly if the behaviour ever changes.
