# Mechanical gates: interfaces and limits

These adapted repository checks provide no solver, project model or end-to-end acceptance runner. Use the project's resource guard. The commands below define interfaces; they are not results from an installed project.

Requirements: Bash with associative arrays and `mapfile`, GNU grep at `/usr/bin/grep`, GNU coreutils with `sha256sum` and `readlink -f`; awk, sed and diff; Python 3 for the scope, document, agreement, anchor, TLC log, brief, hand-back, unit-table, writing-comparison, hygiene, name, census-correction and refusal checks, the tool freeze, the GPU job packer and the inline-Python hook; Git for the scope audit, the hygiene scan and the tool freeze; `nvidia-smi` on GPU hosts for the packer (Linux, for CPU pinning). Platform compatibility and solver integration have not been exercised for this package. See [acceptance limits](#legacy-tlc-label-parser).

## Pin check

```sh
bash scripts/check_spec_pins.sh PROJECT_ROOT SPEC_PINS
```

Resolve the sha256sum manifest `SPEC_PINS` relative to `PROJECT_ROOT` unless absolute. The coordinator supplies a trusted, nonempty manifest covering all intended specs, ideals, configurations, gold and checkers. `sha256sum --check --strict --quiet` compares listed bytes; it cannot detect missing coverage or approve specification changes. Never let workers update their reference manifest. Exit zero means listed hashes agree.

## Mapping assumptions

```sh
bash scripts/assumptions_check.sh MANIFEST.tsv
bash scripts/assumptions_check.sh --expect MODEL_DIR EXPECT.tsv KIND MODULE CFGDIR
```

Manifest rows are `model_dir<TAB>module<TAB>cfg`; the module name excludes `.tla`. Relative configuration paths are resolved under that row's model directory. Blank and `#` rows are skipped; an empty selection fails. `--expect` selects rows whose second field is `KIND`; it uses the first field as the config basename and defaults `CFGDIR` to `.`.

Within the first ten lines, the module must have exactly one header:

```text
\* ASSUMES: QuiescentBeforeReuse, OwnershipUnique
```

Use `\* ASSUMES: (none)` only when justified. Each name must be defined at column zero in the module or a same-directory transitive `EXTENDS` dependency, and checked under `INVARIANT(S)` or `PROPERTY/PROPERTIES` in every using config. The parser strips line and block comments but supports only the documented lexical layout; it is not a TLA+ semantic checker or a complete configuration parser. Exit zero means the selected pairs meet that syntax-level contract.

## Copied operator mirror

```sh
OP_MIRROR_HEADER='Op(m, o, s, t, hostOf) ==' \
OP_MIRROR_NORMALIZE=project-normalization.sed \
bash scripts/op_mirror.sh IDEAL.tla REFINE.tla WHITELIST.tsv
```

Supply the exact header for your project. The shown signature belongs to the inherited parser dialect; it does not constrain the target system. Normalization uses an optional sed file. Without it, no identifiers are renamed. Review and pin any supplied rules.

The parser expects a blank line to end definitions, a `CASE` of `o.k="lowercase"` branches, state record `m`, `[m EXCEPT !.field = expression]` updates, and explicit primed-field conjuncts in ideal actions. It has limited handling of comments and LET, ignores guards when comparing fields and does not establish semantic equivalence. It does not generalize to arbitrary TLA+ syntax. Port the parser under coordinator review for other layouts; do not rename real system behavior just to satisfy it.

Whitelist TSV fields: `kind`, `branch`, comma-separated `ideal actions`, `branch_sha16`, `ideal_sha16`, `reason`. `VERBATIM` compares extracted fields after normalization. Other reviewed rows use normalized hashes on both sides. Use the intended categories `COARSER` and `REWRITE`; the legacy script does not validate category names. Missing or stale branches fail. `--print IDEAL.tla REFINE.tla` prints branch hashes; supply `OP_MIRROR_ACTIONS` as a whitespace-separated action-list to print the corresponding ideal hashes. Printed hashes are proposals, never automatic approval.

## Legacy TLC label parser

```sh
source scripts/tlc_verdict.sh
tlc_verdict CHECKER_LOG CHECKER_EXIT_CODE
tlc_states CHECKER_LOG
```

These functions come from `rerun.sh`; they run no solver. Recognized invariant, action, temporal and deadlock violations take precedence over later success. Next come the timeout exit code, then the success marker; otherwise the parser emits an error label. `tlc_states` extracts the last matching distinct-state count.

**A printed `PASS` is not acceptance.** The function can accept nonzero exits, unknown or generic errors followed by success, empty exploration, and missing or zero required action coverage. Its shell return code is not the verdict. The source caller checked exact state counts only for selected rows. Require a project runner that enforces the full fail-closed sequence, final summaries and coverage. Use the [TLC run verdict](#tlc-run-verdict) as the acceptance check for finished TLC logs; the project still supplies execution and evidence identity checks.

## TLC run verdict

```sh
python3 scripts/run_tlc_gate.py --log LOG --exit-code N [--required-actions FILE] [--simulate] [--time-limit-hit]
vstack gate run-tlc --log LOG --exit-code N
```

This read-only classifier does not run TLC. It prints exactly one verdict line:

```text
VERDICT <kind> states=<distinct or NA> queue=<left on queue or NA>
```

| Kind | Meaning | Exit |
|---|---|---|
| `COMPLETE_PASS` | Success marker, final summary with positive distinct and generated counts, queue zero, exit zero, and nonzero coverage of every requested action. | 0 |
| `VIOLATION` | Invariant, action-property, temporal or deadlock violation; takes precedence over every other result, including later success. | 1 |
| `TIME_LIMIT` | Caller reports the limit, the final summary is absent, or the exhaustive queue is unfinished. | 1 |
| `ERROR` | Nonzero exit, a non-property error, or a completed exhaustive log without the success marker. | 1 |
| `EMPTY` | Zero distinct states or no generated states. | 1 |
| `COVERAGE_MISSING` | A requested action is absent or zero, or a required-actions file was supplied but no complete coverage report exists. | 1 |
| `SAMPLED_NO_VIOLATION` | A completed simulation without a violation; a sample, never an exhaustive pass. | 3 |

Bad usage or unreadable inputs exit 2 with `ERROR <where>: <reason>` diagnostics. With valid inputs, the order
after violations is explicit time limit, error/nonzero exit, missing summary, empty exploration, unfinished queue,
required coverage, then sampled or exhaustive success. Other than violations, an explicit limit takes priority
over errors; errors take priority over an absent summary.

Supply one complete English TLC console log and the real process exit status. The classifier trusts the
caller's time-limit flag; set `--simulate` for simulation (the standard simulation banner is also detected).
It reads final state summaries, not progress lines. Coverage parsing supports only the formats listed in
`--help`: action-location headers with a single count or a `distinct:total` pair inside the last complete
coverage block. Nested expression counts do not substitute for action coverage. The required-actions file
contains one action name per line, with blank and comment lines ignored; an empty list fails. Omitting it
does not establish required coverage: apply the [run-order coverage rule](run-review.md#run-order-and-budget).
The classifier cannot bind a log to source pins, validate witnesses, or accept a different output format by
inference. The project must supply those checks.

## Finding record and danger grade

```sh
python3 scripts/grade_findings.py findings.tsv [--write graded-findings.tsv]
vstack gate grade-findings findings.tsv
```

Read-only on its input. It validates the [finding record](../templates/finding-record.tsv) header, required
fields, enumerations, the fixed forms of structured fields (free text there is refused), counts and their kind,
preconditions, the three repair arms with their reference kind, the independent reviewer, the `real_but_narrow` and
`undetermined` verdicts and the lower reading of ambiguous facts, and rejects stored tier, grade or route values that
disagree with [danger grading](danger-grading.md). It compares literal long options and leading environment
assignments of the actual launch command against the documented default, which must name the same executable;
positional arguments and short options are ignored. An `unknown` launch or fact yields an `unknown` tier or grade
and the route `await_facts`, never `tier0`. `--write` fills the computed fields in a new output file, never the input. Exit zero establishes record consistency, not exposure-gate acceptance: evidence, command
semantics, the confirmation of the private-routing markers (`cross_request_data:`, `availability:`; an unmarked
service-ending impact is refused) and agreement with the reference arm remain manual, and a pending finding stays
on hold.

## Deductive proof acceptance

For TLAPS design-model proofs, require the five mathematical gates below before saying “machine proved.” No generic runner for these gates is bundled. Missing evidence is incomplete; one passing gate cannot offset another's failure.

| Gate | Required evidence |
|---|---|
| Statement and definitions | Byte-check the pinned root statement, `Spec`, `Init`, `Next`, `Safety`, full `IndInv` and their definition dependency closure. Import the pinned model without shadowing. The root concludes that model's `Spec ⇒ □Safety`; every auxiliary representation has a proved, root-reachable bridge to the pinned definitions. |
| Axioms and premises | Require zero new module-level `ASSUME` or `AXIOM` beyond the pinned model and zero hidden premises. Put approved parameter ranges and the proved configuration in the root's explicit `ASSUME … PROVE`; publish their full text. A proof-step premise is not a module axiom, but cannot assume the pending conclusion. |
| Dependency coverage | Derive every action and invariant-conjunct cell from pinned `Next` and the full invariant, including strengthening. Check actual proof references from the root to every cell, all Init goals, `Init ⇒ IndInv`, stuttering, `IndInv ⇒ Safety` and all delivered helpers and bridges. Check action parameters and domains. Prove explicitly when approved premises disable an action; never silently drop it. Reject circular dependencies and orphan proofs. Merely importing a module is not coverage. |
| No omissions | Require zero `OMITTED` in source and zero omissions in complete native prover logs throughout the closure. Missing or truncated logs cannot establish zero. |
| Complete strict results | Retain one complete strict result for every module in the root's full dependency closure. Require `rc = 0`, a final `proved` or `trivial` for every obligation and zero final failed, unknown, timeout or missing obligations. Reconcile results with native complete counts. Use a whole-module run or a slice certificate satisfying the conditions below. |

Keep S4 calibration, non-vacuity and S5 attacks as stage prerequisites; retain their evidence when the pinned model and configuration are unchanged. Report additional mutation diagnostics separately from proof completion. A timeout alone never proves a mutant false; pair proof non-discharge with a matching model-checker counterexample and identify whether it starts at Init or an arbitrary inductive state.

Record elapsed time, peak memory, budgets and repeat runs for diagnosis and reproducibility. Do not impose a half-budget finish, a per-module memory threshold or a second same-source run as a mathematical gate. Enforce resource protection through the [run policy](run-review.md#proof-runs); a killed or unfinished run supplies no complete result. Judge backend chains by each obligation's final status: an intermediate timeout or failure followed by a proof is valid fallback.

### Result identity and reuse

Bind each accepted result to the checked module bytes, its complete transitive `EXTENDS` and `INSTANCE` closure, external libraries and toolchain. Record resolved import paths, source and tool hashes, commands, settings, raw logs and cache provenance. Recompute identities against the assembled tree and verdicts from raw obligation events; do not trust a summary boolean alone. Results from different rounds may be combined when these identities match.

Lock passing results whose source and closure remain unchanged. If a dependency changes only its proof body, preserve downstream source and refresh its result with persistent fingerprints after its own changed dependencies pass. If exported definitions or statements change, review the affected proof contracts before rechecking; a refresh alone cannot establish compatibility. Recheck affected dependencies through the root, then repeat the static gates on the assembled tree.

Accept native fingerprint hits from strict runs under the same frozen toolchain and libraries. A fingerprint hashes the complete sequent, including premises, goal and proof directives; it is not just a source-file hash. Keep provenance for the successful cache entries. Do not require a cache-disabled rerun of an otherwise valid result.

### Slice certificates

Use parallel slices when a large module is limited by serial frontend processing and multiple cores are available. Keep small modules in whole-module runs. `--threads` parallelizes backends; fingerprint hits save backend work but leave serial frontend work. Do not expect slicing to reduce total CPU work; budget for higher aggregate memory during concurrent checks.

1. Freeze the module, full import closure and toolchain. Run `tlapm -N --toolbox 0 0 Module.tla` with the same import paths and proof settings to obtain the complete native obligation inventory. Use this inventory as the sole coverage reference; retain its raw log and `obligationsnumber` count. The `-N` run generates obligations without proving them.
2. Choose inclusive line ranges only between top-level theorems or lemmas, or between first-level `<1>` steps. Keep each selected step's subproof intact; never cut inside it. Include every split theorem's QED obligations in a slice. Read the complete unchanged module in every process; do not extract proof fragments or replace unselected proofs with assumptions.
3. Run each slice with `TLAPM_CACHE_DIR="$SLICE_CACHE" tlapm --strict --nofp --toolbox START END Module.tla`, replacing `START` and `END` with its line bounds. Assign each process a separate, new, empty cache directory; `--nofp` still writes fingerprints. Keep source, closure, libraries, toolchain and proof settings identical to the inventory run, apart from backend suppression and line selection. Start with one or two backend threads per slice and limit concurrency by aggregate memory.
4. Make reconciliation a hard acceptance gate. Require the multiset of source locations of all final `proved` or `trivial` obligations across slices to equal the native inventory's location multiset exactly, preserving multiplicities and full line/column spans. Count each obligation's final event once; do not compare only totals or assume process-local obligation IDs are globally unique. Require matching native counts, `rc = 0` for every slice, strict mode without `--lax`, zero native `OMITTED`, and zero final failed, unknown, timeout or missing obligations. Reject any missing, extra or duplicated coverage; an interrupted or incomplete run cannot pass.
5. Retain slice ranges, counts, source and closure hashes, toolchain identity, commands, cache provenance and complete raw logs in the certificate. Have an independent reviewer use a separate script to reconstruct the inventory and final slice results from raw logs and recheck all conditions; do not trust the certificate builder's summary. Supply this script in the project; no generic slice checker is bundled here.

Treat a complete certificate as equivalent to a whole-module strict check because it checks exactly the same obligation multiset from the same source, dependency closure, toolchain and full proof context. Require no additional whole-module proof run; a count-only run or an unreconciled line check remains insufficient.

See the [veriserve proof implementation and recorded results](https://github.com/hao-ai-lab/veriserve/tree/main/verification/pd-disagg/proofs) for a project example.

Only after all gates pass, report “the design model's `Spec ⇒ □Safety` is machine proved under the listed premises.” Describe implementation evidence as validation against the model, not as a proof of the code. Keep incomplete gates and bounded evidence explicit.

## Write-scope audit

```sh
VSTACK_PROJECT_ROOT=PROJECT_ROOT python3 scripts/scope_check.py ROLE path/to/output
VSTACK_PROJECT_ROOT=PROJECT_ROOT python3 scripts/scope_check.py --all
```

Role cards live in `PROJECT_ROOT/agents/<role>.md`, begin with YAML front matter, and declare unquoted globs in this restricted form:

```yaml
writable:
  - assigned/output/*
  - handoff/assigned-role.md
```

Supply canonical project-relative POSIX paths. Globs follow Python `fnmatch`; `*` can span slashes. `--all` reads Git's tracked and untracked status and checks whether a declared role may own each changed path. It cannot identify the writer. Optional `VSTACK_MAIN_GLOBS` names a coordinator-owned file with one additional pattern per line; no file means no implicit coordinator grants. The audit neither resolves symlinks or traversal nor polices live writes. It does not replace a sandbox. The inherited Git rename and path parser requires canonical simple paths. Exit zero means only that the supplied paths or changed-path union match declared patterns.

## Document check

```sh
python3 scripts/check_docs.py [--root DIR] [--links-only] [--expect-version X.Y.Z]
vstack gate check-docs
```

Read-only. Exit zero means zero errors in these checks:

| Check | Scope |
|---|---|
| Links | Every local link, image and `#anchor` in every `.md` file under the root resolves inside the root; anchors follow GitHub heading slugs or explicit HTML anchors. |
| Ledger | `bugs/verified-bugs.csv` has the expected header and unique `VS-NNN` ids; `violated_spec` is one of the seven pillars; `method` is one of the [method classes](exposure-gate.md#method-classes); no row citing a listed shell model is `model_check`; a row with a named `human_verifier` states a real-engine run in `evidence`. |
| Vocabularies | The pillar table in `bugs/README.md`, the sheet-sync styles and the method-class table list the same names as the check. |
| Versions | The five version manifests carry one `MAJOR.MINOR.PATCH` version. |

`--links-only` checks an installed tree such as `<base>/.claude`. The real-engine test is a keyword match on the evidence text and the shell-model list is kept by hand in the script; neither judges evidence.

## Coordination and hygiene checks

```sh
python3 scripts/make_brief.py FIELDS --out BRIEF.md [--template FILE] [--force]
python3 scripts/check_brief.py BRIEF.md [--template FILE] [--hand-written]
python3 scripts/parse_handback.py REPLY [--brief BRIEF.md] [--ref OUTPUT COLUMN TABLE ID] [--changed FILE --tree DIR --sibling BRIEF.md]
python3 scripts/check_unit_table.py UNITS.tsv (--plan PLAN | --no-plan) [--final] [--briefs DIR]
python3 scripts/check_writings.py COMPARE.tsv --a A.tsv --b B.tsv [--base a|b]
python3 scripts/check_hygiene.py [ROOT] [--deny FILE] [--untracked] [--commits BASE..HEAD]
```

The brief generator and read-only checks of the coordinator's task briefs, workers' hand-back blocks, the unit table,
the comparison of two writings of a key unit and the repository itself (`vstack gate make-brief`, `check-brief`,
`parse-handback`, `check-unit-table`, `check-writings`, `check-hygiene`). The generator writes only its `--out` file. Their rules, interfaces and limits are in the
[rule registry](rule-registry.md#coordination-and-hygiene-checks); each prints `--help`. They check form and
consistency with the named logs and files, not whether the work is right.

Before a push, run the hygiene check with `--commits` on the range the push publishes, for example
`--commits origin/main..HEAD`. A push carries every commit of the range, so a file cleaned in the working tree
still goes out in the older commit that holds it; the check scans every file version a commit of the range adds or
changes and every commit message, and fails on a range with no commits. Keep data and tool changes in separate
commits, so that one can be replaced without the other.

## Name check

```sh
python3 scripts/check_names.py SOURCE TABLE.tsv --column NAME [--column NAME] [--id-column NAME] [--allow FILE]
```

Read-only. At acceptance, a table whose sentences name code (property clauses, instance sentences, census rows)
is refused when a class, function or field it names does not exist in the source tree at the pinned revision. The
index holds identifiers of code only, not of comments, docstrings or documents, and names match whole, so an
abbreviated class name that is a prefix of a real one is missing. `--help` lists the word shapes taken as code
names. A CamelCase product or model name needs an entry in the `--allow` file (`name`, `reason`); every entry must
be used. The check does not verify that a named method belongs to the named class.

## Census corrections

```sh
python3 scripts/check_census_fixes.py FIXES.tsv --table NAME=PATH [--table NAME=PATH] [--source SOURCE]
python3 scripts/check_census_fixes.py --template
```

A correction of a census row, found by a second census, a second pass or a review, is recorded with who made it,
which row of which table (`row_key`), the field, the wrong and the right value, its kind (`missed_write`,
`not_shared`, `wrong_subsystem`, `wrong_access`, `wrong_site`, `wrong_condition`, `wrong_lifetime`), what found it
and `path:line` evidence. With `--table`, the table must now hold the right value (a recorded correction that was
never applied fails), a missed row must exist and a removed row must be gone; with `--source`, every cited line
must exist. See [S0](../skills/vstack-s0-decompose/SKILL.md#2-procedure) step 4.

## Refusal record

```sh
python3 scripts/check_refusals.py REFUSALS.tsv [--docs DOC_ROOT]
```

The two questions of the refusal rule for every refused or ineffective operation of a check on real code, with the
documentation read; see [checks derived from a clause](contracts.md#refusal-record).

## Frozen tool copies

```sh
python3 scripts/freeze_tools.py DEST --rev COMMIT [--path scripts --path templates]
python3 scripts/freeze_tools.py --verify DEST [--root REPO]
```

Tasks that run while the toolkit itself is being changed use a read-only copy of the scripts and templates of one
commit, never the live worktree: a template or grader changed under running tasks makes one task's output fail
the new check and another hand in two formats. The copy carries a SHA-256 manifest (`FREEZE.sha256`, the
`sha256sum` format that [the pin check](#pin-check) also reads) and the commit it came from (`FREEZE.txt`); it is
written next to `DEST` and renamed into place, and a second freeze of other content into the same `DEST` is
refused. Briefs name `DEST/scripts/...` and `DEST/templates/...`; a task moves to a new version only through a new
brief naming a new copy. `--verify` checks the hashes, that no file was added or removed, that nothing is
writable and, with `--root`, that the copy still equals its commit. The read-only mode is a marker, not a lock:
the manifest is what proves the copy unchanged.

## Shared GPU queue jobs

```sh
python3 scripts/gpu_pack.py check JOB.json --mine PREFIX
python3 scripts/gpu_pack.py run JOB.json --out DIR --claim DIR --mine PREFIX
python3 scripts/gpu_pack.py order QUEUE_DIR --mine PREFIX
```

One job packs up to four one-GPU runs, each with its own GPU and CPUs, a time cap, GPU memory back to idle and one
claim across the queues it was offered to; our job names sort after the other team's. Template and rules:
[GPU check jobs in a shared queue](gpu-jobs.md).

## Inline Python hook

Project rules forbid running Python code written inline in an agent's shell (`python3 -c ...`, `python3 -` with a
here-document or a pipe) outside the project's resource guard. A sentence in every brief did not stop it: three
agents each typed `python3 -` once in one evening. [`scripts/refuse_inline_python.py`](../scripts/refuse_inline_python.py)
refuses such a command before it runs. It finds the interpreter behind `env`, `nice`, `timeout`, `taskset`,
`sudo`, `xargs`, `uv run` and similar wrappers, after `;`, `&&`, `|` and newlines, and inside `bash -c`, `eval`,
`find -exec`, `$(...)` and backticks; a script file, `-m MODULE`, `--version` and everything run by the guard pass.

Install it for Claude Code as a `PreToolUse` hook on the Bash tool, in the project's `.claude/settings.json` or the
user's `~/.claude/settings.json`, with the absolute path of the installed script and the project's guard:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /ABSOLUTE/PATH/scripts/refuse_inline_python.py --guard compute/guard.sh --hint 'bash compute/guard.sh ROLE MEM /usr/bin/python3 -B FILE ARGS'"
          }
        ]
      }
    ]
  }
}
```

The hook reads the tool call as JSON on standard input; exit 2 refuses the call and shows the reason to the agent,
exit 0 lets it run, and unreadable input exits 1, which is reported and does not block. A harness with another
pre-command hook can call `refuse_inline_python.py --guard GUARD --command 'TEXT'` and refuse on exit 2. Try it
with `--command 'python3 -'` (exit 2) and `--command 'python3 tool.py'` (exit 0) after installing. It does not see
commands a shell reads from a pipe, scripts written first and run later, aliases or functions; it is a guard rail
for a habit, not a sandbox.

## Mutation gate

The original mutation runner builds specific PD models, applies anchored patches and checks named properties with paired controls. Those model and corpus dependencies are not included; no generic mutation runner is bundled. S2, S4 and S5 still require project-specific mutation and control evidence; absent evidence is a gap, not a pass.
