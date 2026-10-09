Status: LOCKED
Last reviewed: 2026-10-09

# Yuplan Product Build Order & Future Plans

## Purpose

This is the canonical build-order view across Yuplan. It does not mean every item is committed scope. It separates:

- **NOW** — current closure work;
- **NEXT** — intended sequence after the current gate;
- **LATER** — platform/product expansion after pilot proof;
- **FUTURE LAB** — strategic ideas deliberately kept out of active delivery.

When this conflicts with older roadmap/checklist/issue documents, this file is the current planning authority.

## Ordering principle

Yuplan should grow outward from one proven operational chain.

**Finish real customer flow first -> prove pilot -> reuse shared platform -> open next vertical -> deepen shared food/production knowledge -> expand to new verticals/products.**

Do not trade a working A-Z customer flow for broad future architecture.

---

# PHASE 0 — NOW: Kommun identity/auth closure

Current stable auth checkpoint:
`5b301e8d4fdf184e340c449953b739fc1c8cafd9`

Order:

1. Finish credential revocation / `auth_version` implementation and checkpoint.
2. Product decision: first-login password change for pilot users.
3. If approved, implement smallest safe `must_change_password` flow.
4. Consolidate existing tenant user provisioning into **Admin -> Användare**:
   - Admin
   - Kök
   - Avdelning
5. Expose/reactivate only the account-lifecycle actions needed for pilot.
6. Real Firefox proof: create Department user -> login -> correct Department Portal scope.

Explicitly not part of this phase:
- SSO
- MFA
- invitation engine
- enterprise IAM
- multi-role users

---

# PHASE 1 — Kommun 1.1 clean-customer A-Z pilot closure

Goal: prove the complete real operator chain on a clean tenant/site.

Order:

1. Admin creates/configures customer, site and departments.
2. Registered needs/Kostbehov, variable counts and Serveringsanpassningar are configured.
3. Menu is imported or created in Builder-backed flow.
4. Dishes/components/recipes behind the menu remain canonical library data.
5. Menu is published.
6. Department user sees the published menu.
7. Department makes the default single-choice menu selection and submits.
8. Kitchen sees propagated Department choice/status.
9. Planera consumes published menu + demand context.
10. Produktionsunderlag shows exact normal/special production quantities with destination traceability.
11. Completion writes propagate to Kitchen Weekview; Admin Weekview remains read-only.
12. Reporting/persistence/relogin are proven.
13. Optional thin **Admin -> Menyval** overview/override only if it stays MVP-sized and does not become a new project.

Important parked Kommun expansion:
- generic custom multi-dish split-choice UX;
- dynamic choice groups beyond proven legacy/common Alt1/Alt2 semantics;
- broad Portal redesign.

---

# PHASE 2 — Shared responsive/tablet and pilot UX pass

Yuplan is operational software and tablet-first acceptance matters.

Order:

1. Global App Shell responsive breakpoints/tokens.
2. iPad/tablet acceptance across the real Kommun operator chain.
3. High-impact module-specific responsive fixes only after shell behavior is stable.
4. iPhone/mobile fallback/compact behavior.
5. Final UX consistency:
   - density
   - empty states
   - action placement
   - error/success feedback
   - shared modal behavior
6. Fix only pilot blockers/high-impact defects.

Do not reopen completed desktop information architecture during this pass.

---

# PHASE 3 — Kommun pilot candidate and first paying customers

1. Fresh-tenant operator smoke.
2. Full relevant regression suite.
3. Freeze/tag Kommun pilot candidate.
4. Pilot onboarding/runbook.
5. Real customer feedback.
6. Fix only observed pilot blockers before broadening scope.

This is the point where product evidence should outrank speculative feature expansion.

---

# PHASE 4 — Offshore 1.0

Resume existing Offshore work using Builder + Planera shared truth.

Core Offshore v1 surfaces, in practical order:

1. Installation/basic setup.
2. Periods and service events / rotation context.
3. Menu cycle mapping to Builder publication truth.
4. Periodplan with Lunch/Kväll operational view.
5. Operativ arbetsmeny for local service decisions.
6. Portion/default-demand handling.
7. Prep workflow.
8. Frysplock.
9. **Husk att bestill** / order reminders.
10. Handover.
11. Offshore dashboard/overview.
12. Final tablet/mobile operational acceptance.
13. Offshore 1.0 smoke/freeze.

Rules:
- no second menu library;
- no second Dish/Component truth;
- no duplicate production engine;
- reuse Planera 2.0;
- old Rigplan is product reference, not architecture.

Later Offshore:
- Crew Portal/shared portal foundation expansion;
- deeper production-needs/freezer intelligence;
- shared calendar/timeline consumption where useful.

---

# PHASE 5 — Recipe & food-knowledge layer deepening

Recipes already belong in Yuplan's core direction. The next work is to make them increasingly useful to production without destabilizing current verticals.

Recommended order:

1. Stabilize Recipe <-> Component ownership and canonical identity.
2. Recipe quantities + explicit units.
3. Yield/portion scaling.
4. Recipe version/snapshot semantics for historical production.
5. Recipe search/library UX.
6. Production integration through Components/Compositions.
7. Recipe import assistance.
8. Sharing scopes:
   - private
   - site
   - tenant/org
9. Later lightweight social capabilities:
   - favorites
   - comments
   - controlled public/curated sharing

Workflow first; social second.

### Nutrition

Nutrition remains library-owned metadata, not Kommun/Offshore duplicate truth.

Later steps:
1. stabilize nutrition ownership on Recipe/Component/Dish data;
2. define unit basis such as per 100 g / per portion;
3. support deterministic roll-up where recipe quantities/yield are sufficient;
4. expose dish/menu/week nutrition views only after source semantics are reliable.

Do not build a parallel nutrition truth inside a vertical.

---

# PHASE 6 — Production Needs, ingredients, costing and purchasing

Start with read-only value before inventory complexity.

### 6A. Production Needs V1
Published/effective menu + actual portions + recipe quantities -> required raw-material quantities.

Initial output:
- by service/day;
- by dish/component/ingredient;
- week aggregation.

No stock system required.

### 6B. Simple prep suggestions
Optional structured prep instruction + days-before-service can generate reminders.

### 6C. Ingredient/purchasing layer
Order:
1. structured ingredient lines;
2. quantity + unit;
3. optional direct price;
4. ingredient catalog;
5. purchasing references;
6. multiple supplier/product alternatives;
7. pack-size/waste/cost semantics;
8. recipe cost;
9. portion cost / food cost;
10. purchasing/order adapters.

Do not conflate ingredient need with supplier product selection.

Future order adapters may serve professional suppliers and later Home retail partners.

---

# PHASE 7 — Hotel / Bankett / EventCase

Build as a domain above shared Planera, not as another engine.

Order:
1. EventCase identity/status/date/customer/venue.
2. guest counts and segments.
3. Courses/items linked to canonical Components.
4. menu/composition integration.
5. production demand through Planera 2.0.
6. recipe/yield scaling.
7. ingredient requirements.
8. production lists.
9. purchasing/costing.
10. documents/images/run sheets.
11. margin/price support when cost data is trustworthy.

Target verticals:
- hotel
- banquet
- catering
- conference
- large event kitchens

---

# PHASE 8 — Shared platform services as proven by vertical demand

Build shared infrastructure only after at least one real domain needs it.

Candidates:

### Calendar/timeline
Existing read contract + Offshore adapter already provide a base.

Later:
- calendar/timeline UI;
- Kommun adapter where a concrete use case exists;
- Builder publication/date adapter where appropriate;
- reminders/tasks exposed through adapters.

### Messages / communication
Consolidate only semantics that are genuinely shared.

Candidates:
- kitchen -> Department one-way message;
- operational notices;
- reminders;
- portal communication;
- audience/visibility/time window.

Do not prematurely merge private notes, announcements, prep scratchpads and order reminders into one generic table.

### Portal Foundation
Continue sharing:
- scoped auth;
- shell;
- published menu presentation;
- status/progress;
- reminders/messages where semantics are stable.

Kommun Department and Offshore Crew remain domain adapters, not one forced data model.

---

# PHASE 9 — AI assistance

AI remains advisory over canonical structured data.

Suggested progression:

### AI 1 — assistant
- warnings;
- text help;
- simple production/prep suggestions;
- import assistance.

### AI 2 — analysis
- allergen/risk signals;
- overproduction patterns;
- waste/cost analysis;
- purchasing suggestions;
- historical pattern analysis.

### AI 3 — controlled automation
- draft purchasing lists;
- draft project/event plans;
- recommended menus/production adjustments.

Locked principle:
**deterministic engine = truth; AI = advisor.**

AI must not silently mutate production truth.

---

# PHASE 10 — Yuplan Home / Future Lab

Do not start before Professional/core proves the shared architecture.

Potential sequence:

### Home 0
- personal Dish/Recipe library;
- drag/drop weekly menu;
- household size;
- portion scaling;
- generated shopping list.

### Home 1
- deduplicated/categorized ingredients;
- package sizes;
- manual “already at home”.

### Home 2
- retailer adapters;
- ingredient -> retail product matching;
- basket / pickup / delivery handoff.

### Home 3
- waste intelligence / pantry lifecycle.

### Home 4
- sharing/community/forking.

### Home 5
- AI weekly planning and budget optimization.

Commercial possibilities:
- B2C subscription;
- affiliate/transaction revenue;
- retailer partnerships;
- B2B2C/white label;
- sponsored structured recipe/product blocks.

Home must reuse Yuplan Core rather than create a second recipe/menu/planning system.

---

# PARKED / NOT CURRENT BUILD ORDER

These remain deliberate future options, not active backlog:

- enterprise SSO/SAML/OIDC;
- MFA;
- invite-email platform;
- advanced device/session-management console;
- multi-role/multi-site enterprise IAM;
- full inventory/warehouse management;
- FIFO/shelf-life/stock reservation;
- advanced thawing engine;
- supplier EDI complexity before purchasing need is proven;
- generic social network;
- broad AI automation without human review;
- generic split-choice menu engine for every possible menu structure;
- premature shared abstractions with no second proven consumer.

---

# Small known follow-ups that should not derail pilot closure

Track, but schedule at natural seams:

- Builder parity: after “Create Dish”, open the shared Dish editor immediately.
- Builder parity: fix Component search in the shared Dish editor if still reproducible.
- Shared composition search: tag/# semantics only once in the canonical search runtime.
- Admin users: expose safe reactivation if needed for pilot operations.
- Forgot-password delivery: later unless real pilot operations require self-service recovery.
- Department Portal: kitchen message block only when there is real message data; no empty dead space.
- Menu dynamic custom choice semantics: parked beyond default single-choice 1.0.
- Nutrition aggregation: only after source/yield/unit semantics are stable.

---

# Product sequencing rule

When choosing between a new feature and closing a real operator journey, choose the operator journey.

Current macro order is:

**Kommun pilot -> paying-user proof -> Offshore 1.0 -> Recipe/Production Needs -> Purchasing/Cost -> Hotel/Bankett -> shared platform services -> AI expansion -> Home.**

This order can change deliberately through Ground Truth + Decision Log when customer evidence justifies it.
