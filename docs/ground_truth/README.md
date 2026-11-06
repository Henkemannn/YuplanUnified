Status: LOCKED
Last reviewed: 2026-11-06 (documentation governance)

# Ground Truth

docs/ground_truth is Yuplan's canonical current project direction.

If an old document, legacy implementation, old PR body, or old ChatGPT discussion conflicts with Ground Truth, Ground Truth represents the current intended direction.

Existing ADRs and docs can still contain useful technical history and evidence.

A LOCKED decision may only be changed deliberately.

When a locked decision changes:
1. update the affected Ground Truth file,
2. add an entry to [DECISION_LOG.md](DECISION_LOG.md),
3. state what previous decision was superseded.

Ground Truth describes architecture and product intent, not implementation details that can be read from code.

Keep the files concise enough that a new project-lead conversation can read the whole directory quickly.

## Authority boundaries (2026-11-06)

- **Architecture/product contract:** the LOCKED files in this directory. A locked decision changes only by an explicit product decision and a DECISION_LOG entry.
- **Current implementation status / next Copilot gate / release acceptance:** [Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md), not an old "current" paragraph embedded in a September lock.
- **Phase ordering:** [Roadmap](../roadmap.md), not another MVP checklist.
- **Document map / historical documentation branches:** [Documentation index](../README.md).

September implementation checklists and HEADs within Ground Truth are evidence of their dates, not active development commands. K25–K27, current Planera and Builder Gates 19–21E must remain closed absent reproduced regression. The codebase and real acceptance evidence decide actual implementation state; Ground Truth decides intended behavior. Do not create competing status master files on handoff/documentation branches.

## Files

- [YUPLAN_1_0_FINISHLINE.md](YUPLAN_1_0_FINISHLINE.md)
- [KOMMUN_1_0_MVP_LOCK.md](KOMMUN_1_0_MVP_LOCK.md)
- [PLATFORM_ARCHITECTURE_LOCK.md](PLATFORM_ARCHITECTURE_LOCK.md)
- [BUILDER_MENU_LOCK.md](BUILDER_MENU_LOCK.md)
- [PLANERA_2_0_ARCHITECTURE_LOCK.md](PLANERA_2_0_ARCHITECTURE_LOCK.md)
- [PORTALS_ARCHITECTURE_LOCK.md](PORTALS_ARCHITECTURE_LOCK.md)
- [OFFSHORE_1_0_MVP_LOCK.md](OFFSHORE_1_0_MVP_LOCK.md)
- [DECISION_LOG.md](DECISION_LOG.md)

## Supporting Current Product References

These docs are not Ground Truth locks, but they capture detailed current design direction referenced by Ground Truth:

- [docs/planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md](../planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md)

## Historical References

These docs provide supporting history and evidence, but they do not override Ground Truth.

- [docs/portal_legacy_parity.md](../portal_legacy_parity.md)
- [docs/adr/ADR_department_portal_composite_and_etags.md](../adr/ADR_department_portal_composite_and_etags.md)
- [docs/planera_legacy_parity.md](../planera_legacy_parity.md)
- [docs/planera_module_functional_spec.md](../planera_module_functional_spec.md)
