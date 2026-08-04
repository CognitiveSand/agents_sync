# Amendment 021 — A skill's auxiliary files must survive a canonical projection

- status: applied — legacy `src/` heal path (0.7.57) and rebuild S23i (0.7.58)
- branch: fix/size-explosion-hardening
- date: 2026-08-04
- relates to: FR-06 (skill matrix), NFR-01 (no user content destroyed),
  NFR-05 (no churn), NFR-06 (round-trip byte preservation), NFR-16 (canonical
  authority), US-05 (data preservation), US-11 AC-8/AC-9 (glitch heal);
  amendment 020 (S23f/S23i scope split);
  `docs/audits/cutover_loose_ends_register_2026_07_12.md` (F3 skills-as-a-kind).

## Motivation

A field report of a running v0.7 daemon: a `skill` folder carrying a
`references/` subdirectory was restored by the daemon with its `SKILL.md` only.
The auxiliary file was not recreated, and nothing was logged. The restored skill
loaded normally and pointed at a file that no longer existed.

The report matters more than "an incomplete copy" because a skill may deliberately
make an auxiliary file the *single home* of a body of content, precisely so it is
not duplicated into `SKILL.md`. For such a skill this failure mode silently
deletes the majority of the artifact while leaving something that looks healthy.

Reproduced against `src/` before any change (now
`tests/test_skill_auxiliary_files_survive_heal.py`):

- adoption/propagation to a new tool carries the aux file (it copies the folder);
- a glitch heal restores `SKILL.md` alone;
- the following poll reports `changed == 0`.

## Root cause — two layers

**1. The heal renders with no source directory.** When ≥ 2 of a tool's artifacts
vanish in one poll, `Syncer._glitch_tools` classifies that tool as glitched
(US-11 AC-9) and `AdoptionEngine.process_pair` routes to
`project_from_canonical`, which called `_render_canonical_one` without
`source_dir`. `rendering._render_directory_skill` then takes its bare branch —
`mkdir` plus write `SKILL.md` — instead of `stage_skill_dir`, which copies the
whole tree. The sibling `_extend_to_new_tools` had always passed a `source_dir`
picked from a surviving tool copy, which is why propagation kept aux files and
only the heal lost them.

**2. The canonical document has no representation for auxiliary files.** A
directory skill's canonical carries the `SKILL.md` body and nothing else, so the
store — the declared authority under NFR-16 — cannot reconstruct a multi-file
skill from itself. A surviving on-disk copy is the *only* possible source.

Layer 2 is what makes the loss permanent rather than merely wrong.
`update_state_n_way` records the post-write digest, computed by
`sha256_skill_tree_snapshot` over the truncated tree; the next poll compares
truncated against truncated, finds no drift, and never repairs. NFR-05's
no-churn property and the missing canonical representation combine into silent,
self-confirming data loss.

Two consequences beyond the report, from the same layer 2:

- `portable_archive` has no skill-tree handling at all, so `export`/`import`
  (US-12) drops auxiliary files — a library restored on another machine yields
  truncated skills.
- A pair present on zero tools cannot be reconstituted whole by any means.

## Principle / decision

**A projection must never write a directory skill it cannot write whole, or —
where it must (a single-file skill has nothing more to write) — must not do so
silently.** The canonical is the authority (NFR-16); until it actually holds the
whole artifact, the daemon must prefer an on-disk source and say so out loud when
it has none.

Split, mirroring amendment 020's structure:

- **Legacy `src/` (this amendment, applied).** Thread a surviving on-disk copy
  into the heal path so the reported defect cannot recur, and make the
  unreconstructable case loud. This is the deployed tree; it is what users run
  today and cannot wait for the cutover.
- **Rebuild `src_new/` — S23i (promoted).** Put auxiliary files in the canonical,
  which is the only fix that also closes export/import and the zero-copy case.
  Amendment 020 deferred S23i with an explicit condition: *"must land before the
  flip if any skill-supporting tool needs a multi-file skill synced."* **That
  condition has now fired** — multi-file skills are in real use. S23i moves from
  deferred to required-before-S25.

### Scope boundary of the legacy fix

The legacy fix does **not** attempt to refuse the write when no source survives.
Refusing exactly when truncation would occur requires knowing whether the folder
ever held auxiliary files, which the state does not record; adding that field is
a state-schema change to a tree that S25 deletes, and guessing it wrong either
breaks the legitimate glitch recovery of a genuinely single-file skill (US-11
AC-9) or restores nothing at all. The legacy tree therefore restores `SKILL.md`
and logs a warning naming the pair and the affected tools. The guarantee — not
the diagnostic — is S23i's job.

## Proposed governance edits (require user validation)

### User stories
**None.** US-05 (data preservation) and US-11 AC-8/AC-9 (glitch heal) already own
this behaviour; the defect is a failure to meet them, not a gap in them. No
acceptance criterion changes.

### Requirements
**None.** FR-06 mandates skill sync and NFR-06 mandates byte-preserving
round-trip; a skill folder's auxiliary files are already inside both. This
amendment adds no `shall`-language.

**Raised for the owner, no change made:** the glitch heuristic (US-11 AC-9)
treats *any* bulk disappearance as transient, so a user deliberately removing
several skills from one tool has the removal undone. The field report's author
hit exactly this. Whether a deliberate bulk deletion should be distinguishable
from a glitch is a governance question, not an implementation detail, and is left
for the owner to decide.

## Design edits (architecture — applied after)

`docs/architecture_implementation_plan.md`:
- Record the S23i gate as **fired**, moving it from the conditional-deferred list
  into Phase F-completion as required-before-cutover, with S23i's scope grown to
  cover portable export/import.

`docs/audits/cutover_loose_ends_register_2026_07_12.md`: same promotion, with the
field evidence.

No edit to `docs/architecture.md`: the legacy fix threads an existing parameter
through an existing call path and introduces no architectural principle.

## Implementation (legacy `src/`, applied)

1. `adoption/canonical_projection.py` — extract `surviving_skill_source(info)`,
   the first recorded tool copy of a directory skill still present on disk
   (previously inline in `_extend_to_new_tools`; now used by both callers, so
   extracted rather than duplicated).
2. `adoption/canonical_projection.py` — `project_from_canonical` accepts
   `source_dir` and passes it to `_render_canonical_one`. When the kind is
   `skill`, no source is supplied, and the pair has recorded tool copies (so it
   is not a fresh zero-tool import stub), it logs a warning naming the pair, the
   artifact and the target tools, and stating that auxiliary files are not held
   in the canonical and must be restored from a backup.
3. `adoption/engine.py` — the glitch-heal call site passes
   `surviving_skill_source(info)`. This is the site that fixes the report: at
   that point the artifact is still discovered on the tools that did not glitch.

The third caller, `removal_propagator.propagate_orphan_state`, has no surviving
copy by construction (the pair vanished from every available tool) and so
deliberately triggers the warning path.

## Verification

`tests/test_skill_auxiliary_files_survive_heal.py` — five tests:

| Test | Guarantee |
|---|---|
| `test_propagation_carries_auxiliary_files_to_a_new_tool` | baseline: adoption already copies the folder whole |
| `test_glitch_heal_restores_the_whole_folder_not_just_skill_md` | the reported defect |
| `test_healed_folder_is_recorded_whole_so_no_later_poll_diverges` | NFR-05: the restored tree is the recorded baseline |
| `test_heal_without_a_surviving_copy_warns_instead_of_truncating_silently` | the loss is never silent |
| `test_zero_tool_import_stub_heals_without_a_spurious_warning` | the frozen stub-heal contract still holds |

Full local CI green: ruff, `mypy --strict` over `src/` and `src_new/`, the
conformance suite, and the rebuild suite.

## S23i — the root fix (rebuild `src_new/`, applied 0.7.58)

Owner decisions taken before implementing (2026-08-04):

- **Auxiliary content encoding: text when UTF-8-decodable, base64 otherwise**, per
  file, with the encoding recorded alongside the content. Binary assets sync, and
  the ordinary case stays readable and diffable in the store. Chosen by decoding,
  never by file suffix.
- **Auxiliary content is body-like and is NOT secret-scanned.** `find_secret_literals`
  scans the wire-shaped carriers (`env`/`headers`/`auth`); `body` prose is NFR-15's
  documented residual. An auxiliary file is content of the same nature, so it
  inherits the same treatment rather than creating an aux-scanned/body-unscanned
  asymmetry. Residual risk accepted and recorded in the register.

What landed:

1. **`domain_model/auxiliary_file`** — the `AuxiliaryFile` codec.
2. **`skill_auxiliary_files`** — the folder↔map gateway: one home for the walk order,
   the exclusions (`SKILL.md`, OS sidecars) and the bounds, so reading and writing
   cannot drift apart.
3. **`CanonicalDocument.auxiliary_files`** — the store now holds the whole artifact,
   which is what makes NFR-16 true for skills.
4. **`read_tool_surfaces`** — the folder walk, with a composite digest so an edit to
   a reference file registers as a change to the artifact.
5. **`execute_sync_plan/_shared.write_surface_content`** — one folder-aware writer
   replacing four separate `write_text_atomic` + `surface_content_digest` pairs; a
   skill is published through `replace_directory_atomic` (NFR-03).
6. **`auxiliary_files_already_on_disk`** — the skip test now considers the whole
   folder. Without it a target whose `SKILL.md` matched would be skipped as current
   while its references stayed missing: the reported bug, reintroduced in the new
   tree by an optimisation that predates folders.
7. **`identity_intents`** — a renamed skill retires its whole old folder rather than
   unlinking its `SKILL.md` and orphaning the tree beside it.
8. **`parser_bounds`** — `read_bytes_bounded` plus file-count and folder-byte caps,
   so a mis-pointed root is refused rather than adopted and copied everywhere.

`portable_library` needed no change: it ships canonical documents, so auxiliary
files travel with them once the document carries them (US-12, verified by test).

`tests_new/test_skill_auxiliary_propagation.py` (7 tests) covers adoption into the
canonical, projection over a truncated folder, projection when only the auxiliary
side differs, binary byte-preservation, steady state, an auxiliary edit propagating,
and export→import. `tests_new/test_skill_surface.py`'s two S23f freeze tests are
replaced by the behaviour that supersedes them, plus digest and sidecar coverage.

## Unrelated blocker found while testing S23i

Writing the end-to-end tests surfaced that **the rebuild never creates an artifact on
a tool that does not already have one** — for any kind, agents included.
`reconcile_known._absorb_change` draws projection targets from observed surfaces, so a
tool with no copy is never a target. This is the product's headline behaviour and it
blocks S24. Recorded in full in the register and in the implementation plan as a
Phase G-gate; it needs an owner decision and is not addressed here.
