# Kommun 1.1 — Live Acceptance & UX Race

## Status

TECHNICAL AUTOMATED GATE = GO

LIVE PILOT ACCEPTANCE = PENDING

## Baseline

- branch: feat/planera-app-shell-2026-03-03
- HEAD: 8aad73eb6afea8f9d11fa83df69b8dda4467c4a3
- 2342 passed
- 15 skipped
- 0 failed
- 3 warnings

## Section A — Clean Customer E2E

- [ ] New tenant/customer
- [ ] New site/kitchen
- [ ] New departments
- [ ] Resident/current quantities
- [ ] Requirement groups/needs
- [ ] Specialkost
- [ ] Serving adaptations
- [ ] Department login
- [ ] Builder menu import
- [ ] Resolve/build menu content
- [ ] Publish
- [ ] Kitchen Weekview
- [ ] Portal same menu
- [ ] Portal menu choices
- [ ] Explicit submit
- [ ] Portal→Kitchen propagation
- [ ] Planera lunch
- [ ] Planera kvällsmat
- [ ] Planera dessert
- [ ] Production underlag
- [ ] Completion propagation
- [ ] Report
- [ ] Persistence after reload/login

## Section B — Data Truth Assertions

Record these locks:

- Published Builder menu = canonical menu truth
- Department menu choice = canonical choice truth
- Registered needs/current quantities = business truth
- Portal = input/experience layer
- Planera 2.0 = production engine
- Weekview = operational projection
- No manual sync between Portal and Kitchen
- No second production/menu/choice truth

## Section C — UI/UX Race

For every major screen capture record:

- route/screen
- screenshot/reference
- task user is trying to complete
- friction
- severity: BLOCKER / HIGH / MEDIUM / LOW
- recommended action
- accepted/fixed/deferred

Initial screens to inspect:

1. Customer creation / onboarding
2. Site/kitchen setup
3. Departments list
4. Department create
5. Department detail
6. Department edit

Known concern:

Department edit is known to be visually and interaction-wise messy and requires serious UX review.

Then:

7. Needs / requirement-group administration
8. Builder import
9. Builder unresolved flow
10. Dish editor
11. Component editor
12. Publish flow
13. Kitchen Weekview
14. Planera entry/day overview
15. Planera review
16. Produktionsunderlag
17. Department Portal Home
18. Department Portal Week
19. Reports

UX principle:

Do not redesign everything blindly. First walk the real task, then screenshot, then identify friction, then challenge or redesign only where justified.

Tablet/iPad-first remains a core acceptance lens.

## Section D — Release Blockers

Only BLOCKER and HIGH issues can stop pilot unless the project lead decides otherwise.

| ID | Area | Finding | Severity | Owner | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |

## Section E — Release Exit Criteria

Kommun 1.1 may become final PILOT READY only when:

- clean-customer chain passes
- lunch/kvällsmat/dessert Planera requirement is verified or an explicit product decision is made
- Portal and Kitchen show the same canonical publication and choices
- tenant and department scoping is proven
- no blocker-level UX failure remains
- accepted UX fixes are regression-tested
- final automated suite is green after any product changes
- pilot candidate HEAD is frozen/tagged

## Notes

This document is the working ledger for the live acceptance phase and the UX race.
