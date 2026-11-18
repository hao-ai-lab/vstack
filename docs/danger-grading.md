# Danger grading

A finding can be true and still rarely trigger. Keep every finding in the
[finding record](../templates/finding-record.tsv); derive its danger grade and route from recorded facts.
This record supplements the public ledger without changing its columns. Grading does not replace any
[exposure gate](exposure-gate.md).

The grade answers how urgent a finding is: who can reach it, how easily and with what consequence. The review
verdict answers how sure we are that it holds as written. These are two separate quantities and neither adjusts the
other: a narrow or partly holding finding keeps the grade its facts give, and a high grade does not make a doubtful
finding more certain. Report both side by side.

## Who can trigger

Record `entry_kind` and the official server or CLI `entrypoint` by name:

| Entry kind | Reachability |
| :--- | :--- |
| `external_request` | Ordinary client traffic on the serving interface, including client cancel and disconnect. |
| `internal_control` | An administrative or control-plane call, such as pause, cache flush, weight update or adapter load. |
| `startup_config` | Only a launch flag or a model choice. |
| `test_only` | No official entry point reaches it; use `entrypoint = n/a` and record the harness commands. |
| `unknown` | Not yet established; the grade waits (see [grade and route](#grade-and-route)). |

Record in `preconditions` what must hold besides the launch settings, as `kind:condition` items separated by `;`,
or `none`. Kinds: `request` (a request parameter, such as `request:frequency_penalty>0` or a stop string),
`control` (an administrative call or its parameter, such as `control:pause in place`), `timing` (an ordering or
window, such as `timing:cancel while the block is being reclaimed`) and `unknown` (a precondition the author or
reviewer could not settle, named by what is open: `unknown:whether the retry frees the block first`). The whole field
is `unknown` when nobody has worked out the preconditions. A `control` precondition means ordinary client traffic
alone cannot trigger the finding, so its entry kind is not `external_request`; the grader enforces this.

## How easily it triggers

Record the documented `default_launch_cmd` and the actual `launch_cmd`.
[grade_findings.py](../scripts/grade_findings.py) computes `non_default_settings` as a semicolon-separated list
of settings present in the latter but absent from the former, compared by name and value. It recognizes leading
`NAME=value` assignments and long options `--name`, `--name=value` and `--name value`. A changed value counts;
identical repeated pairs count once. Different values for the same name count separately. Values containing spaces
or semicolons are shell-quoted in the list. Positional arguments and short options are ignored. Use resolved single
commands, not wrappers or shell pipelines; this is text comparison, not knowledge of option semantics. A non-option
token after a bare option is treated as its value. The reviewer checks the baseline and these parsing limits.

Both commands must name the same executable, so that the comparison compares like with like. Write `unknown` for
a command nobody established, for example a candidate never launched on a real engine. A placeholder (`n/a`,
`default`, `TBD`, `same`) is refused: read as a command it would have no settings and grade as `tier0`, which claims
the default configuration reaches the finding. When it is unclear whether the documented default includes a
setting, leave it out of `default_launch_cmd`, so it counts as non-default.

| Computed tier | Conditions |
| :--- | :--- |
| `tier0` | Zero non-default settings and nothing injected. |
| `tier1` | Exactly one non-default setting and nothing injected. |
| `common_combo` | Exactly two non-default settings and nothing injected. |
| `corner` | Three or more settings, anything injected into the target's source, or `single_model_only = yes`; these overrides take precedence. |
| `unknown` | A launch command is `unknown` and no override applies. |

Preconditions are not counted in the tier; they are recorded next to it and ordered within a grade (below).
`injected` is `none` or the source location and description of an injected delay or fault (`path:line what`).
A stand-in in the test counts as injected: a substituted tokenizer, model configuration or component, a recorder or
fake in place of a real component, a delay, or a process the test kills. Record each one, so that a finding reached
only with a stand-in is `corner`; it rises only when a run without the stand-in reaches it.

Record the natural `hits`/`runs`, `hit_unit` and `hit_kind` without injection as observed. `hit_kind` says how the
runs were chosen, and with it what the ratio means:

| `hit_kind` | Runs counted | The ratio means |
| :--- | :--- | :--- |
| `random` | Every run drawn without aiming at the trigger: random seeds, natural traffic. | A rate under that distribution. |
| `directed` | Constructed scenarios that reached the stated trigger condition; scenarios that never reached it are evidence, not runs. | How often the trigger condition fails the code. |
| `selected` | Runs chosen by hand or after the fact, such as one reproduction. | Existence only. |
| `none` | No natural observation: `0`/`0`. | Nothing; not a measured rate or passing evidence. |

Compare ratios only between records of the same `hit_kind` and `hit_unit`; never fold them into a tier. The grader
requires `none` exactly when `runs = 0`. Keep injected run counts and model counterexamples in the supporting
evidence, separately from natural observations. Provisional policy: an administrative interface routinely called
by the deployment's own training or operations loop is default use, not an additional non-default setting. The
property owner may change this policy.

## Grade and route

Apply the following rules, with D taking precedence, then C's trigger restrictions, then A and B:

| Grade | Facts | Route |
| :--- | :--- | :--- |
| A | `external_request`, `tier0` or `tier1`, and `serious_consequence = yes`. | `upstream_report`: report upstream first, subject to [private routing](#private-routing). |
| B | `internal_control` with `tier0` or `tier1`; or `external_request` with `common_combo`; or `external_request` with `tier0` or `tier1` and `serious_consequence = no`. | `upstream_report`, subject to [private routing](#private-routing). |
| C | `corner`, `startup_config`, or anything not covered above. | `keep_internal`: retain the grade; do not file upstream on its own. |
| D | `test_only`, or verdict `harness_only` or `false_positive`. | `not_a_product_defect`: retain in the graveyard list. |
| `unknown` | A fact the grade depends on is `unknown`. | `await_facts`: settle the fact, then grade again. |
| `n/a` | Verdict `spec_defect`: the property, not the engine, is wrong. | `property_owner`: a [rollback ticket](../templates/rollback.md) to S2. |

An `unknown` fact (`entry_kind`, `serious_consequence`, a launch command) leaves the grade `unknown` unless every
value it could take gives the same grade; for example `internal_control` at `tier0` is B whatever the consequence.
An `unknown` precondition can only lower the grade, since it may turn out to need a setting or a control call, so it
leaves the grade `unknown` unless the grade is D.

`serious_consequence` (`yes`, `no` or `unknown`) is `yes` when the consequence is any of:

- a wrong, incomplete or missing output of the request itself, such as a wrong value or tool-call argument, a
  dropped tool call, a schema that is silently not enforced, or a reply that never comes;
- silent corruption of another request's data or output;
- a deadlock or hang across ranks or workers;
- a leak of memory or slots on the main path.

A `no` says why the consequence is not serious: `impact` starts with one of the classes below, after the optional
markers (see [private routing](#private-routing)), and nothing outside them is `no`. The grader refuses a `no`
without a class and a `yes` with one. A consequence that fits no class is `yes`, or `unknown` while it is unsettled.

| Class | The consequence is only |
| :--- | :--- |
| `error:` | A visible failure within bounded time: an error reply, an exception, a refusal or a closed connection. No output is silently wrong. |
| `slow:` | Time or resources: latency, throughput, cache misses, memory held for a while and released. Every output is right. |
| `report:` | A log line or metric is wrong. Every reply is right. |

The first item was added by the property owner on 2026-11-18; before it, a request's own wrong output was recorded
as `no` with the other reading in `ambiguous_facts`. Records written that way are refused until they are regraded.
These boundaries are owned by the property owner. Explain the consequence in `impact`.

The verdict changes the route, never the grade, except that `harness_only` and `false_positive` are D and
`spec_defect` has none. `pending` (review not done) and `partial` (the record must be rewritten to what holds and
reviewed again) override every route with `hold_for_review`; `undetermined` routes to `await_facts`. A
`real_but_narrow` finding is graded from facts that already contain the narrowing: the grader refuses that verdict on
a record that still claims the plain default path (no setting, precondition, injection or model restriction, and
`external_request`). Within one grade, order `external_request` before `internal_control`, then fewer non-default
settings, then fewer preconditions. A route is a recommendation, not permission to publish. Keep all rows, including
D rows in the graveyard list, rather than deleting rejected findings.

### Private routing

Two kinds of finding go to the project's private security channel before any public text, because a public report
would hand others a way to harm a deployment. Each is recorded by a marker at the start of `impact`, followed by the
concrete impact:

| Marker | The finding |
| :--- | :--- |
| `cross_request_data:` | Lets one request read or change another request's data or output. |
| `availability:` | Ends the service for more than the request itself: the engine or server process exits, new requests are refused, or the other in-flight requests fail. |

A record may carry both markers, in either order, before any `error:`, `slow:` or `report:` class. A marker does not
change the grade; it changes a reportable A or B route to `private_report`. C and D stay internal; any later
disclosure of such a finding must also use the private channel first. A marker with no text after it is refused.

The grader cannot infer a missing `cross_request_data:` marker from prose; the independent reviewer must confirm it.
For `availability:` it refuses an unmarked record whose `impact` states a process exit (for example an engine or
server process that exits or dies, or an engine-dead error), refused new requests (new or later requests refused or
failing) or a failure of other in-flight requests (every or all requests failing, or a denial of service). The
phrase list in [grade_findings.py](../scripts/grade_findings.py) reads words, not causes, and errs toward the marker:
an impact that names such an effect, even one caused elsewhere and only met by the finding, carries the marker or is
rewritten to state the finding's own consequence. A service-ending effect told in other words is not caught; the
reviewer confirms the marker either way. Before this check, a service-ending finding reached `upstream_report` unless
someone overrode its route by hand.

## Who assigns

The author fills the facts, including duplicate-search queries and date in `dup_search` (`YYYY-MM-DD: query;
query`) and the checked upstream commit in `upstream_checked_at`. The script computes `non_default_settings`,
`tier`, `grade` and `route`. An independent reviewer, never the author, records one verdict per finding at Gate 2
and confirms the facts and computed fields at Gate 4. Use `pending` until review; it is a workflow state, not a
completed verdict.

| Review verdict | Meaning |
| :--- | :--- |
| `real` | Holds as stated. |
| `real_but_narrow` | Holds, but the write-up must add the preconditions and the grade must follow them. |
| `partial` | At least one sub-claim does not hold; rewrite to what holds. |
| `undetermined` | Review done, but a fact the claim depends on cannot be settled; record that fact as `unknown` (a field, or an `unknown:` precondition naming it). The grader refuses this verdict on a record with no `unknown` fact. |
| `spec_defect` | The engine behaves as its code and documentation define; the property clause or model contract states something else. The correction goes to the property owner; there is no danger grade. |
| `harness_only` | No sequence through an official entry point reaches it. |
| `false_positive` | The claimed defect does not hold. A refutation from code reading alone is a lead, not this verdict ([Gate 2](exposure-gate.md#gate-2-red-team)). |

Grades, tiers and routes come only from the grader. Nobody writes or adjusts them by hand, in the record or in any
summary, ledger or report built from it: copy them from a `--write` output that passed. A record the grader refuses
has no grade; it goes back to its author, and a summary lists it as refused, never with an estimated grade. Every
task that produces finding records runs the grader on its own output before handing back, and states the command
and its last line as done evidence.

When a fact allows two readings (is this interface ordinary client traffic or an administrative call? is the
consequence serious?), record the reading that gives the lower grade and list each other reading in
`ambiguous_facts` as `field=value` items separated by `;`, or write `none`. Fields that may be listed:
`entry_kind`, `serious_consequence`, `single_model_only`. The grader recomputes the grade under every combination of
listed readings and refuses the record when any of them gives a lower grade than the recorded facts. A human settles
the listed readings; until then the lower grade stands.

Use one header and one tab-separated row per finding; the template's `#` rows are examples, not findings.
All fact fields are required; `reviewer` may be empty while pending. `none`, `n/a` and `unknown` are values, not
blanks, and `unknown` is accepted only where this page names it. Identifier fields (`finding_id`, `unit`, `author`,
`reviewer`), `hit_unit`, `upstream_checked_at`, `dup_search`, `injected`, `preconditions` and `ambiguous_facts`
have fixed forms, and free text there is refused; prose belongs in `summary` and `impact`. Set all three arms and
`reference_kind` to `n/a` when no fix is claimed. Otherwise record all of `arm_stock`, `arm_patched` and
`arm_reference` as `hits/runs` with positive denominators, and set `reference_kind` to `reference_implementation` or
`deployment_variable_control`. The [S6 procedure](../skills/vstack-s6-hunt-fix/SKILL.md#2-procedure) governs the
reference run and expected value. Counts alone do not establish semantic agreement between the patched and reference
outcomes.

```sh
python3 scripts/grade_findings.py findings.tsv
python3 scripts/grade_findings.py findings.tsv --write graded-findings.tsv
```

This mechanical check validates record structure, enumerations, field forms, counts and their kind, arm
companions, reviewer identity, the class of a consequence that is not serious, the private-routing markers and the
service-ending phrases, verdict consistency
(`real_but_narrow`, `undetermined`), the lower reading of ambiguous facts, and stored computed tier/grade/route.
Blank computed fields are allowed; `--write` fills them and refreshes the settings list in a new output file,
preserving comments. It refuses existing outputs or its input as
output and writes nothing when validation fails. A header-only template fails until populated. Gate evidence,
preconditions, command semantics, reference agreement and the review itself remain partly manual; a structurally
valid pending row is still on hold.

## Use when choosing units

Use the same two axes before hunting in S1: who can reach a unit and how easily its conditions arise. Work first on
units ordinary client traffic can reach under the default configuration, then on units needing additional controls
or settings. The order guides coverage; it does not discard lower-priority findings.
