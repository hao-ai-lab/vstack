# Rollback Ticket: <one issue>

- Origin task, role and actual UTC timestamp: <...>.
- From stage / to stage / property: <...>.
- Frozen artifact and SHA256: <...>.
- Responsible upstream owner and failed exit check: <...>.

## Evidence

- Counterexample: <property, mechanism, command, evidence path>.
- Trace: <hash, first divergent event, mismatch class, reproduction command>.
- Source: <path:line@commit and short excerpt>.
- Confidence: <execution-supported or reproduced on real code; items without run evidence remain leads>.

## Proposed repair

- Minimal change and alternatives: <...>.
- Staging directory / regression command / before-and-after table: <...>.
- Affected downstream checks and pins: <...>.

## Approval and application

| Artifact | Decision owner | Application |
|---|---|---|
| Promise, ideal, frozen configuration | Property owner | Coordinator independently checks and re-pins |
| Gold expectations or verdict scripts | Coordinator | Assigned gate maintainer; attack regression |
| Model | Coordinator review | Worker creates a new version; full recalibration |
| Maps and historical anchors | Coordinator | Assigned investigator; evidence re-review |

Never edit the upstream frozen artifact from the downstream role. Never weaken a promise just to obtain a passing verdict.

## Resolution (coordinator)

- Accepted/rejected and recorded decision: <...>.
- Applied files/hashes, updated pins and independent rerun: <...>.
- Closed at actual UTC: <...>.
