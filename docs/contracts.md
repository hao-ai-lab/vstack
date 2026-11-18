# Find contracts before freezing them

One card per contract family. Describe observable consequences, not the implementation that happens to exist.

## Three artifacts

A system and its properties are both temporal formulas, and correctness is implication (Lamport, *Specifying Systems*, Addison-Wesley, 2002). Keep three artifacts apart:

| Artifact | Frozen in | What it is | Place in a TLC configuration |
|---|---|---|---|
| Property clauses | S2 | Named state invariants, action invariants, liveness or relational formulas over observable state. SHA-256 pinned. | `INVARIANT` / `PROPERTY` |
| Ideal reference model | S2 | An operational specification without implementation detail, for example `Ideal.tla`. In a refinement check `ImplSpec ⇒ IdealSpec` it plays the property role; [`op_mirror.sh`](gates.md#copied-operator-mirror) compares operators copied from it. Pinned with the clauses. | `PROPERTY` (its specification) |
| Code-anchored model or descriptor | S3 | A transition system or computation descriptor built from `file:line@commit` at the pinned revision. | `SPECIFICATION` |

The ideal model is a state machine but sits on the property side; only the code-anchored model describes the implementation. Classify every property clause by [pillar and formal class](method-selection.md#property-classes-and-the-seven-pillars) before choosing its checker.

| Source | Required work |
|---|---|
| Top-level decomposition | Trace the contract to an approved system promise. Always required. |
| Historical bugs | Negate an evidenced bad state; record what the fix actually establishes at pinned buggy and fixed revisions. |
| Consumer requirements | At every handoff, work backward from unchecked consumer preconditions to the producer's Requires and Ensures. |
| One-step induction | On a small ledger or protocol model, classify each counterexample: a reachable predecessor indicates an operation defect; an unreachable one needs a strengthening fact. |

Top-level decomposition is mandatory, together with historical bugs or consumer requirements. Ledger and protocol contracts must complete one-step induction before freezing, including all three induction checks. Computation descriptors instead need differential checks against the actual functions.

## Consumer scan: seven categories

At every cross-component, cross-thread, device or stream boundary check:

- indices and offsets: who establishes bounds;
- value ranges: legal identifiers, positions and lengths;
- overwrite points: all writers and their ordering;
- execution context: producing and consuming streams or threads, event placement;
- lifetime: how long an asynchronously consumed allocation remains alive;
- aliases and views: whether retained data is a copy or a mutable view;
- initial values: whether anything can read a location before valid initialization.

## Two-sided calibration

For each contract, supply a violating execution, accepted reachability witnesses and legal edge behaviors, and the minimum scale exposing its failure. Explain why smaller bounds miss the failure. Run both the minimum and one increment. Add normal and fault-injected real traces when available.

Calibrate contracts in S2 before freezing them. Repeat calibration on the full model and add runtime alignment in S4; do not postpone all calibration to S4.

## Checks derived from a clause

A clause becomes a check on real code (a stateful test, a sweep, a differential test, a trace assertion) only with
the four parts below written into the check's brief; the clause sentence alone is not a check.

| Part | Requirement | Error it prevents |
|---|---|---|
| Input dimensions | List every input that can change the outcome at the checked site, beyond the arguments visible there: configuration switches, other items of the same request, parameters of another modality, same-named entities in different scopes, boundary values such as empty or whitespace-only text, and earlier turns of a conversation. Vary each one, or state why it is fixed. | The check runs at the right site and passes because the dimension that fails never varies there. |
| Second oracle | Judge each result by two independent methods: the clause's expected value and a relation that needs no expected value, such as a metamorphic relation (enabling an unrelated parser leaves this parser's output unchanged) or a reference implementation. Record every disagreement between them. | The side taken as the expected answer is itself wrong, and the check confirms it. |
| Refusal and silent success | Answer two questions for every operation sequence the check runs. First: does the documentation promise that this sequence, in this order, can be done? Second: was it refused (an error, an exception, a rejected request), or did it report success without taking effect (no state change, no output)? A promised sequence that is refused is a failure, and so is every operation that reports success without its effect. A refusal is a documented precondition only when the documentation forbids that same sequence: a precondition stated for another sequence does not cover it. When the documentation read says nothing, the refusal goes to triage, never to the safe side. Record both answers and the documentation read in the [refusal record](#refusal-record). | A check that counts "rejected with an error" as safe passes the very symptom of a defect; a precondition of one sequence (release without a pause) read as covering another (pause, then release) hides a documented sequence that is refused. |
| Triage before counting | Before reporting how many failures a check found, trace each to a root cause, drop those the check itself causes (harness, stub, wrong oracle) and count root causes, not rows. | Check defects inflate the count or hide real failures among them. |

These parts apply to the stateful real-code test of
[readout 1](model-adequacy.md#readout-1-trace-and-baseline-agreement), to exhaustive property sweeps and to every
check that S6 writes from a clause. The refusal part is checked by script, below; the other three are
documented-only.

### Refusal record

Every check derived from a clause that runs operations on real code writes one row per tested operation sequence
that was refused, had no effect or depends on what the documentation promises (print the header with
`python3 scripts/check_refusals.py --template`):

| Column | Content |
| :--- | :--- |
| `case_id` | The case. |
| `operation` | The calls in the order the check made them, separated by `;`. |
| `promised` | First question: `yes`, `no` (forbidden, or a precondition the case did not meet), `silent` or `unknown`. |
| `doc_read` | The documentation read, as `SOURCE[:LINE[-LINE]] ["quote"]` items separated by `;`; listed even when it is silent. A `yes` or `no` quotes the words, and the quotes name every call of the operation. |
| `outcome` | Second question: `refused`, `no_effect` or `done`. |
| `verdict` | Given by the answers: `pass` when done; `failure` when there was no effect, or when a promised sequence was refused; `documented_refusal` when a forbidden one was refused; `triage` when the documentation is silent; `await_facts` when the first question is open. |
| `note` | Free text. |

```sh
python3 scripts/check_refusals.py REFUSALS.tsv --docs DOC_ROOT
```

The checker refuses a verdict the answers do not give, a `yes` or `no` without a quote, a quote that does not name
every call of the sequence, and, with `--docs`, a quote that is not on the cited lines. It does not judge whether
the quoted text really promises or forbids the sequence; the reviewer reads the quotes. It counts only rows that
are written down; a refusal the check never recorded is not seen.

Before freezing, require cards for all in-scope models, consumer scans for every boundary, fully classified ledger and protocol induction counterexamples, recorded calibration and minimum bounds, and property-owner approval. The coordinator pins specs **and configurations**. Before deductive proof, pin the full inductive invariant and root statement too. Put parameter ranges and the proved configuration in explicit root `ASSUME … PROVE` premises and publish them verbatim; do not add module-level axioms. The card checklist is partly manual; the hash comparison is mechanical.

Discover strengthening before proof begins. A later invariant change requires new pins, Init and affected preservation checks in the same module tree, and renewed [proof acceptance](gates.md#deductive-proof-acceptance). Auxiliary definitions stay in the proof layer with proved bridges to the pinned model.
