# Yuplan documentation — start here

**Reviewed: 2026-11-06.** Use this index to distinguish current delivery status from locked architecture and historical evidence.

## One current delivery status

**[Kommun 1.1 Live Acceptance](KOMMUN_1_1_LIVE_ACCEPTANCE.md)** is the **single authoritative operational ledger** for current Kommun 1.1 progress, accepted functionality, outstanding gates and the *next Copilot order*. Update its dated CURRENT section only at reviewed checkpoints. The [Roadmap](roadmap.md) shows phase sequence, not a competing status list.

**[Ground Truth](ground_truth/README.md)** owns *locked product and architecture decisions*. It is not a live task queue. Older status/HEAD paragraphs inside locks are historical snapshots; they do not overrule later accepted decisions in the live ledger.

## Where information belongs

| Kind of information | Location | Authority |
| --- | --- | --- |
| Current release status, next gate, pilot acceptance | [KOMMUN_1_1_LIVE_ACCEPTANCE.md](KOMMUN_1_1_LIVE_ACCEPTANCE.md) | Current operational truth |
| Phase ordering: Kommun → Offshore → Yuplan 1.0 | [roadmap.md](roadmap.md) | Sequence only |
| Shared Yuplan 1.0 release scope | [ground_truth/YUPLAN_1_0_FINISHLINE.md](ground_truth/YUPLAN_1_0_FINISHLINE.md) | Scope/architecture lock; old checkpoints historical |
| Kommun product requirements | [ground_truth/KOMMUN_1_0_MVP_LOCK.md](ground_truth/KOMMUN_1_0_MVP_LOCK.md) | Locked contract; historical filename retained |
| Builder / Planera / Portal / Offshore contracts | [ground_truth/README.md](ground_truth/README.md) | Locked architecture and decisions |
| UI / operational specs and deeper design | `docs/Platform/`, `docs/planera2/`, `docs/offshore2/`, `docs/builder/` | Supporting references |
| Legacy, audit, PR and historical notes | `docs/legacy_*.md`, `docs/pr/`, repository root `PR_BODY_*.md`, `CONTEXT.md` | Historical/reference only |
| Future ideas | `docs/future_lab/`, `new_ideas/`, future sections in Platform/Planera2 | Deferred unless explicitly activated |

## Documentation branch drift — discovered 2026-11-06

The active code branch `feat/planera-app-shell-2026-03-03` at `a75f754c` contained documentation whose last `docs/` commit was 2026-10-05, even though later updates were made on **separate documentation-only branches**.

Historical sources recovered:

- [October 30 status and October 31 MVP checklist (updated through November 2)](https://github.com/Henkemannn/YuplanUnified/tree/docs/kommun-status-review-2026-10-30/docs).
- [October 7–11 handoffs, documentation index, login/auth contracts and build order](https://github.com/Henkemannn/YuplanUnified/tree/handoff/kommun-1-1-2026-10-07/docs).
- [October 2 handoff](https://github.com/Henkemannn/YuplanUnified/tree/handoff/kommun-1-1-2026-10-02/docs/handoffs).

These branches are **historical sources, not alternate active masterplans**. Their dates, test results, pending orders and local HEADs are not live status. Relevant accepted facts were reconciled into the existing Live Acceptance ledger; preserve the branches as history rather than bulk-copying their outdated plans into new files.

## Maintenance rule

1. One Copilot order → one report → review → next order.
2. At a meaningful checkpoint, update **the existing Live Acceptance ledger** and, only if phase sequence actually changes, the Roadmap.
3. Change Ground Truth only when a *locked decision* changes; log that decision in `ground_truth/DECISION_LOG.md`.
4. Do not create new dated `MVP_MASTER`, `CURRENT_STATUS`, `FINISHLINE` or handoff master documents for routine updates.
5. Previously user-accepted functionality remains closed unless there is a reproduced regression. Automated-test gaps are not themselves a mandate to rebuild.
6. Copilot does not commit/push without approval; verify local branch/HEAD/dirty state and `git diff --check`, protect unrelated local changes.
