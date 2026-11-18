# Notices and attribution

The plugin layout follows Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack). Layout and installation wording were checked at upstream revision `6b0300214a09fd6029cfb7077043125758cd1fd2`.

The source repository's `NOTICE.md` records earlier adaptations from pstack at revision `ae5650f`: working principles, case framing, run review, red-team review, handoff, regression-skill templates and maintenance. Their generalized adaptations are retained here. The scope-audit concept also derives from that workflow. No pstack asset or full skill corpus is copied.

The coordination layer of release 0.123.0 adapts pstack 0.15.42: the orchestrate playbook of poteto-mode (one owner per unit, a fresh worker per task, a kickoff that names the evidence of done, reading artifacts rather than summaries, and starting with one unit before fanning out), swarm (a result that does not record what its brief asked for is sent back, then recorded as a gap), arena (the same brief to independent candidates, then a base picked and the others grafted by hand), and reflect and correct (a review after each batch, an enforcer at the highest level that works for an error seen twice, and a table pairing each rule with its enforcer). Arena's cross-judge from another model family is not adopted. The task brief template, the hand-back block and the five checks are new code.

Release 0.124.0 applies pstack's correct and encode-lessons-in-structure rules (an error seen twice becomes a check that refuses, registered with its enforcer), build-the-lever (a generator instead of hand-edited briefs), prove-it-works (each new check is tested on the failure it was written for) and make-operations-idempotent (regenerating a brief gives the same file) to failures recorded while the coordination layer was used. The brief generator, the domain brief templates and the new rules of the brief and hand-back checks are new code.

The following upstream notice applies to the adapted pstack portions. The package license is in `LICENSE`.


MIT License

Copyright (c) 2026 Lauren Tan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
