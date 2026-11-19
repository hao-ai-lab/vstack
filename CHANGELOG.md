# Changelog

Releases of the vstack toolkit: skills, templates, documents and scripts. The version is the one carried by the
five manifests (`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`.cursor-plugin/plugin.json`, `pyproject.toml`).

## 0.126.0

The checks refuse what their documents say they refuse. Each claim of an outside review of 0.125.0 was run against
the released scripts first; every fix below comes with a self-test that failed on 0.125.0.

- `scripts/grade_findings.py`: the service-ending phrase list also reads a killed worker, an engine-dead error, new
  requests refused or failing without an auxiliary verb, and other requests failing, and ignores a negated phrase; a
  marker or class with no text after it (`availability: error:`, `error:`) is refused; a `test_only` record needs
  `entrypoint` `n/a`; an `unknown` grade is compared with listed ambiguous readings by the lowest grade its facts
  allow; a cell that starts with a quote but is not wholly quoted is read as written instead of refused.
- `scripts/check_hygiene.py`: file names are checked for `--deny` terms and bytes that are not UTF-8; personal paths
  without a trailing slash and Windows profiles with forward slashes are reported; decomposed Hangul jamo count as
  CJK; `--walk` scans a link to a directory as a link.
- `scripts/check_brief.py`: a stamp line with text after its comment is no stamp; patterns are tested against sample
  `FAIL` and `ERROR` lines; `**/` matches zero directories; `<name:value>` is a placeholder (only URL and e-mail
  autolinks in prose pass); ids are checked on `literal:` and `ref:` lines; blind paths are checked against every
  other line, with `:` ending a path and `..` resolved; an `except` glob under a writable glob is accepted;
  ``1 row of `FILE` `` is recounted.
- `scripts/make_brief.py`: a brief made with `--template` is checked against that template's sections; a slot name
  may be one letter.
- `scripts/parse_handback.py`: a changed file two sibling briefs may write is refused; a `--changed` line that reads
  both as a status line and as an existing path is refused as ambiguous; an invalid pattern in the brief is an error,
  not a crash; a relative `--ref` table resolves against `--root`.
- `scripts/refuse_inline_python.py` reads a command with the shell's quoting rules (quotes, comments, line
  continuations, descriptor numbers before redirections, here-documents with quoted or escaped delimiters, nested
  substitutions) and also refuses `python3 -- -`, a program read from a file descriptor, `env -S` in option
  clusters and with arguments after it, `uv` global options before `run`, `bash --rcfile FILE -c`, `eval --`,
  `flock FILE -c` and `coproc`. `python3 <<EOF script.py` and here-documents that no shell reads pass. What text
  reading cannot close is stated as a limit in its help and in [the inline Python hook](docs/gates.md#inline-python-hook).
- `scripts/gpu_pack.py`: a reversed CPU range and the run name `PACK.json` are refused; a `null` lock is no lock; runs
  that share a lock wait for each other instead of for the job's start; a run whose program cannot start fails alone
  and an unexpected error stops every run and still writes `PACK.json` and the done record; an existing output
  directory is refused before the claim is taken.
- `scripts/check_unit_table.py`: a one-column TSV plan is read as a plan and a short plan row is an error; a unit that
  is not key names one owner.
- `scripts/check_census_fixes.py`: a `missed_write` cannot have the right value `(removed)`; cited lines must lie in
  a file inside `--source`, the range running upwards.
- `scripts/scope_check.py --all` checks both paths of a rename; `scripts/check_names.py` keeps identifiers after a
  `//` inside a C-like string literal and leaves out docstrings of one word; `vstack gate tlc-verdict LOG RC` prints
  the label instead of running a file that only defines functions.
- New self-tests for `scope_check.py` and `vstack_cli.py`; `docs/danger-grading.md`, `docs/gates.md`,
  `docs/gpu-jobs.md` and `docs/rule-registry.md` follow.

## 0.125.0

Findings that end the service route to the private channel by rule.

- Finding records gain the `availability:` impact marker for a finding that ends the service for more than the
  request itself: the engine or server process exits, new requests are refused, or the other in-flight requests
  fail. As with `cross_request_data:`, the marker turns a reportable A or B route into `private_report`; C and D stay
  internal, and the grade does not change. The two markers may both lead `impact`, in either order, before an
  `error:`, `slow:` or `report:` class.
- `scripts/grade_findings.py` refuses a record whose `impact` states a process exit, refused new requests or a
  failure of other in-flight requests without the `availability:` marker, and names the marker in its message. The
  phrase list reads words, not causes, and errs toward the marker. A marker with no text after it is refused. Before
  this release such a finding reached `upstream_report` after review unless its route was overridden by hand.
- `docs/danger-grading.md` gains a [private routing](docs/danger-grading.md#private-routing) section;
  `docs/exposure-gate.md`, `docs/gates.md` and `docs/rule-registry.md` follow, and `templates/finding-record.tsv`
  has an example of a marked record.
- This changelog.

## 0.124.0

Coordination, pushing and grading hardened against failures seen while the coordination layer was used.

- Briefs are generated from templates by `scripts/make_brief.py`, which fills every slot from a fields file,
  refuses a field that fills no slot and stamps the result with hashes. `scripts/check_brief.py` refuses a brief
  edited after generation or derived from another brief, undeclared ids, and counts not computed from the files
  they name. Five domain brief templates (spec check, triage, reproduction, instance writing, comparison) move to the
  seven-section form.
- `scripts/parse_handback.py` checks that ids an output names exist in the table they refer to, and that a worker's
  changes stay inside its writable paths. Done evidence may give a regular expression for the expected last line.
- `scripts/check_unit_table.py` records which brief went to which worker and refuses undispatched briefs and
  reused workers.
- `scripts/check_hygiene.py --commits BASE..HEAD` scans every file version and commit message of a push range.
- New scripts: `refuse_inline_python.py` (a pre-command hook that refuses inline Python outside the project guard),
  `freeze_tools.py` (hashed read-only copies of the tools for running tasks), `gpu_pack.py` (packs single-GPU runs
  for a queue shared with another team), `check_names.py` (every code name in a sentence exists in the pinned
  source), `check_census_fixes.py` (census corrections are recorded and applied) and `check_refusals.py` (a
  refusal counts as safe only when the documentation forbids that same sequence).
- The danger grade counts a wrong, incomplete or missing output of the request itself as a serious consequence; a
  consequence recorded as not serious must say why, as an `error:`, `slow:` or `report:` class.
- `docs/gpu-jobs.md` is new; the rule registry gains a row for each new rule and its enforcer.

## 0.123.0

Finding records and danger grading, model and real-code agreement, and a coordination layer.

- Finding records (`templates/finding-record.tsv`) carry their facts as fields: entry point and kind, default and
  actual launch commands, preconditions, injected behaviour, natural hits and runs with their unit and kind, the
  three repair arms (stock, patched, reference), consequence and impact, duplicate search, review verdict, reviewer
  and ambiguous facts. `docs/danger-grading.md` defines the grade A to D and the route from who can trigger a
  finding and how easily; `scripts/grade_findings.py` validates a record and computes the settings difference,
  tier, grade and route. The grade comes from facts only: a narrow or partly holding verdict does not cap it, an
  unestablished launch is `unknown` rather than tier 0, free text in structured fields is refused, the verdicts
  `undetermined` and `spec_defect` are added, and an ambiguous fact must be recorded at its lower reading. The
  check is registered as `vstack gate grade-findings`.
- S6 adds a reference arm to the repair check; S5 and the coordinator record one review verdict per finding, by a
  reviewer other than the author.
- S4 owes an agreement record (`templates/agreement.tsv`) of the model's and the real code's verdicts for the
  pinned baseline and each calibration mutant. `scripts/check_agreement.py` counts agreement only when both sides
  violate the same clauses, refuses an undetected mutant unless its resolution says why, and counts a mutant only
  against a passing unmutated row at the same scale.
- `scripts/run_tlc_gate.py` classifies a finished TLC run and exits zero only for a complete pass; a time limit,
  errors, empty exploration and missing action coverage fail, and a bounded simulation without a violation is
  reported as a sample. It accepts TLC's advisory coverage terminator and a finished bounded simulation without a
  summary line.
- S3 keeps the anchor map on the hunt track and adds the reverse table of write sites (`templates/anchors.tsv`),
  checked by `scripts/check_anchors.py`. `docs/run-review.md` gains the run order and an exhaustive-search budget
  per unit.
- S0 and S1 take the per-resource table as the main census table, with an ownership rule for contested write sites
  and constructor counting by object lifetime; `docs/contracts.md` adds rules for checks derived from a clause.
- The coordination layer: briefs from `templates/task-brief.md` (`scripts/check_brief.py`), hand-back blocks
  parsed against their logs and brief (`scripts/parse_handback.py`), a unit table with one unit first per batch and
  no gaps against the plan (`scripts/check_unit_table.py`), key units written twice and merged through a
  comparison table (`scripts/check_writings.py`), and a review after each batch into `docs/rule-registry.md`. The
  method is adapted from pstack ([NOTICE.md](NOTICE.md)).
- `scripts/check_hygiene.py` scans the repository for non-English text, personal paths, chat links and case data
  outside `data/`.

## 0.122.0

Decomposition by plane, resource and edge kind.

- S0 labels each in-scope subsystem as control, data or both, fills a resource matrix (write, hold and read per
  subsystem, with sites and conditions), classifies each boundary as a state or a parameter edge, and runs the
  writer census twice with independent workers.
- S1 reads units off the resource matrix (one shared resource with the subsystems that write or hold it), records
  them in a unit table with their subsystem count, routes them by plane and formal class, and orders them by who can
  trigger them and under which deployment tier.
- vstack-mode describes sweeping many units in parallel: the unit table is the coverage matrix, with one worker and
  one output directory per unit and twin models for key units. Layer 0 adds separate output directories for
  parallel workers and the rule that a mistake seen twice becomes a check or a template field.
- Stage names, order and playbooks are unchanged.
