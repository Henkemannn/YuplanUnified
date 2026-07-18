# Kommun UI Reference Audit

## Executive Summary
Kommun is the current visual reference for Yuplan's app shell, topbar, sidebar, page headers, cards, buttons, forms, tables, and responsive behavior. Offshore must later follow the same Yuplan feel without changing Kommun itself.

The current implementation is not a single unified shell in every route family. The strongest common pattern is the app-shell stack in [templates/ui/_layout/app_shell_base.html](../../templates/ui/_layout/app_shell_base.html), which powers the modern unified admin, weekview, and report pages. There is also an older global header/footer pattern in the cook dashboard include macros, and a legacy Kommun adapter under [core/legacy_kommun_ui.py](../../core/legacy_kommun_ui.py) that is explicitly separate and read-only oriented.

Recommended Offshore strategy: build a new Offshore app shell that reuses the same visual grammar, spacing, and token system, but do not require a refactor of Kommun as a prerequisite.

## 0. Audit Status

| Area | Status |
| --- | --- |
| Kommun UI entry points | COMPLETE |
| template hierarchy | COMPLETE |
| topbar | COMPLETE |
| sidebar/navigation | COMPLETE |
| page anatomy | COMPLETE |
| design inventory | COMPLETE |
| responsive behavior | COMPLETE |
| tenant/site/auth context | COMPLETE |
| theme readiness | COMPLETE |
| i18n readiness | COMPLETE |
| reuse strategy | COMPLETE |
| Offshore Foundation contract | COMPLETE |
| docs navigation | COMPLETE |
| scope verification | COMPLETE |
| test baseline | COMPLETE |

Status legend:
- COMPLETE: documented with concrete file-level evidence
- INCOMPLETE: not yet documented or not yet verified
- NOT APPLICABLE: intentionally out of scope for this audit

## 1. Actual Kommun UI Architecture

### Main entry points
- [core/ui_blueprint.py](../../core/ui_blueprint.py) registers the modern unified Kommun UI routes.
- [core/dashboard_ui.py](../../core/dashboard_ui.py) still exists as an older dashboard blueprint, but the actual modern dashboard surfaces in [core/ui_blueprint.py](../../core/ui_blueprint.py).
- [core/legacy_kommun_ui.py](../../core/legacy_kommun_ui.py) is a legacy Kommun adapter blueprint under `/kommun`, with placeholder routes and a separate template folder path.
- [core/app_factory.py](../../core/app_factory.py) registers the UI blueprint and the dashboard blueprint.

### Main modern Kommun route families
- `/ui/admin` -> admin dashboard
- `/ui/admin/departments` and related department CRUD pages
- `/ui/weekview` -> weekly operational grid
- `/ui/reports/weekly` -> weekly report
- `/ui/cook` and `/ui/cook/dashboard` -> cook-facing overview surfaces
- `/ui/planera/week` -> planning view
- `/ui/select-site` -> site selector and site context reset
- `/ui/account` -> user profile/account page
- `/ui/systemadmin/dashboard` -> system admin surface

### Legacy Kommun route family
- `/kommun/admin`
- `/kommun/admin/import`
- `/kommun/veckovy`
- `/kommun/rapport`
- `/kommun/redigera_boende`

These legacy routes are not the recommended Offshore starting point. They exist as compatibility and historical reference.

## 2. Template Hierarchy

### Primary shell
The real modern app shell is [templates/ui/_layout/app_shell_base.html](../../templates/ui/_layout/app_shell_base.html).

Structure:
- `html/body`
- `div.app-shell`
- `header.app-shell__topbar`
- `div.app-shell__body`
  - `aside.app-shell__sidebar`
  - `main.app-shell__main`

This shell is used by modern admin, weekview, and report templates such as:
- [templates/ui/unified_admin_base.html](../../templates/ui/unified_admin_base.html)
- [templates/ui/unified_weekview.html](../../templates/ui/unified_weekview.html)
- [templates/ui/unified_report_weekly.html](../../templates/ui/unified_report_weekly.html)
- [templates/ui/unified_admin_dashboard.html](../../templates/ui/unified_admin_dashboard.html)

### Secondary shell
The cook dashboard uses a separate global header/footer include pair:
- [templates/includes/yuplan_header.html](../../templates/includes/yuplan_header.html)
- [templates/includes/yuplan_footer.html](../../templates/includes/yuplan_footer.html)

That shell is visually simpler and not the same as the app-shell pattern.

### Legacy/local shell
The legacy Kommun adapter can render through `base.html`/legacy templates through [core/legacy_kommun_ui.py](../../core/legacy_kommun_ui.py), but this should be treated as historical compatibility, not the new Offshore shell.

## 3. Topbar

### App-shell topbar contents
From [templates/ui/_layout/app_shell_base.html](../../templates/ui/_layout/app_shell_base.html):
- Yuplan logo and brand text
- tenant badge: `Kund:`
- site badge: `Arbetsplats:`
- environment badge: `LOCAL`, `STAGING`, or `PROD`
- optional `Byt site` action for superuser/systemadmin or when site switching is allowed
- optional `← Admin` return link when a kitchen portal user is in a kitchen context
- theme toggle button
- user menu with account, support, and logout

### Classification
- GLOBAL PLATFORM: logo, environment badge, theme toggle, user menu, logout
- MODULE-SPECIFIC: `← Admin` when coming back from kitchen context
- COMMUN-SPECIFIC: tenant/site environment labels in the current Unified admin shell
- ROLE-SPECIFIC: `Byt site`, `← Admin`, and the user menu contents

### Cook dashboard header
The cook dashboard uses [templates/includes/yuplan_header.html](../../templates/includes/yuplan_header.html) and shows:
- brand link
- site
- week/year
- user name
- environment badge

That is visually lighter than the app shell and is best treated as an older header macro, not the preferred shell for Offshore Foundation.

## 4. Sidebar and Navigation

### App-shell sidebar
The sidebar in [templates/ui/_layout/app_shell_base.html](../../templates/ui/_layout/app_shell_base.html) is a persistent left sidebar on desktop with route groups generated from `nav_context` and `request.path`.

There are three active navigation modes:
- `systemadmin`
- `admin`
- `kitchen`
- fallback/default

### Admin nav items
From the app-shell template and `nav_context == 'admin'`:
- Översikt -> `/ui/admin`
- Veckovy -> `/ui/weekview`
- Avdelningar -> `/ui/admin/departments`
- Menyimport -> `/ui/admin/menu-import`
- Specialkost -> `/ui/admin/specialkost`
- Meddelanden / Påminnelser -> `/ui/admin/announcements`
- Rapport / Statistik -> `/ui/admin/report/week`
- Köksanvändare -> `/ui/admin/kitchen-users`

### Kitchen nav items
- Översikt -> `/ui/kitchen`
- Veckovy -> `/ui/kitchen/week`
- Planera -> `/ui/kitchen/planering`
- Menyöversikt -> `/ui/kitchen/menu`
- Produktionslistor -> `/ui/production-lists`

### Default nav items
- Veckovy -> `/ui/weekview`
- Planera -> `/ui/planera/week`
- Rapport -> `/ui/reports/weekly`
- Specialkost -> `/ui/admin/specialkost`
- Avdelningsportal -> `/ui/portal/week`

### Active state
Active links use `.app-shell__nav-item--active`, driven by the current path. The active marker is a left-side bar plus stronger background and text color.

### Collapse and small-screen behavior
- Desktop: sticky sidebar, fixed width, always visible.
- Tablet/mobile under 900px: body becomes one column, sidebar is no longer sticky, the nav becomes horizontal and scrollable.
- Under 640px: the topbar tightens, and brand text shrinks.

There is no dedicated hamburger drawer in this shell. On small screens the sidebar collapses into a horizontal nav strip rather than a slide-out drawer.

### Visual reuse assessment
Reusable for Offshore:
- sidebar placement and spacing
- nav item sizing and active marker
- header/footer spacing
- horizontal nav fallback on narrow screens

Kommun-specific labels that should not be copied verbatim:
- Veckovy
- Planera
- Rapport
- Specialkost
- Avdelningar
- Menyimport
- Köksanvändare

## 5. Page Anatomy

### Representative page 1: Admin dashboard
File: [templates/ui/unified_admin_dashboard.html](../../templates/ui/unified_admin_dashboard.html)

Structure:
- page header with title and subtitle
- cards for today, menu synchronization, announcements, and remember-to-order
- uses app-shell card/grid/list patterns
- primary action from the card area goes to the kitchen portal

This is the clearest example of the current Yuplan admin visual language.

### Representative page 2: Weekview
File: [templates/ui/unified_weekview.html](../../templates/ui/unified_weekview.html)

Structure:
- page header
- week navigation buttons
- department card
- week grid with meal sections
- badges, alerts, and menu icon cells
- print and no-print separation

This is the clearest operational grid pattern in Kommun and the best visual reference for Offshore's future period planner.

### Representative page 3: Admin department form
File: [templates/ui/unified_admin_departments_form.html](../../templates/ui/unified_admin_departments_form.html)

Structure:
- app-shell page header
- form cards
- form fields with labels, inputs, help text
- buttons and modal triggers
- table preview block for weekly values

This is the strongest form-layout reference.

### Representative page 4: Weekly report
File: [templates/ui/unified_report_weekly.html](../../templates/ui/unified_report_weekly.html)

Structure:
- page header and filter row
- cards for filter and result summary
- details elements for department rows
- day cards inside expandable sections
- print action

This is the best reference for cards, badges, and compact summary composition.

## 6. CSS / Design Inventory

### Token system
The global token system lives in [static/unified_ui.css](../../static/unified_ui.css).

Notable tokens:
- `--yp-color-primary`
- `--yp-color-secondary`
- `--yp-color-accent`
- `--yp-color-bg`
- `--yp-color-bg-alt`
- `--yp-color-bg-elevated`
- `--yp-color-text`
- `--yp-color-text-muted`
- `--yp-color-success`
- `--yp-color-warning`
- `--yp-color-danger`
- `--yp-color-info`
- `--yp-gap`
- `--yp-gap-sm`
- `--yp-gap-lg`
- `--yp-gap-xl`
- `--yp-radius`
- `--yp-shadow`
- `--yp-font-family`
- `--yp-font-size-*`

### App shell CSS
The shell visuals live in [static/css/app_shell.css](../../static/css/app_shell.css).

Important characteristics:
- custom property indirection for color, surface, and spacing
- light and dark modes already exist in the shell
- topbar uses a gradient and blur treatment
- sidebar is sticky and card-like on desktop
- main area uses grid and cards
- `.app-shell__nav-item--active` has a left accent bar
- `.yp-button` variants exist inside the shell styles
- a print block hides sidebar/topbar and keeps print output clean

### Admin CSS
[static/css/unified_admin.css](../../static/css/unified_admin.css) layers admin-specific colors and responsive behavior.

Important characteristics:
- it references unified tokens for most spacing, borders, and semantic colors
- it still contains hard-coded admin sidebar colors
- it explicitly hides some legacy duplicates
- mobile mode turns the sidebar into an overlay drawer below 768px

### Weekview CSS
[static/css/unified_weekview.css](../../static/css/unified_weekview.css) is the strongest tablet-first operational stylesheet.

Important characteristics:
- grid and meal sections are large enough for touch use
- yellow/amber Alt2 highlighting exists
- card, badge, and modal styling is token-based where possible
- tablet and mobile breakpoints collapse the grid to simpler forms

### Hard-coded and legacy-like items
- some sidebar colors in admin CSS are still hard-coded
- some purple secondary button colors remain ad hoc in weekview navigation
- several dark-mode overrides are still page-local rather than fully semantic

### Component inventory
Reusable visual primitives already present:
- cards
- buttons
- badges/pills
- forms and inputs
- tables
- details/summary blocks
- flash alerts
- modal patterns
- week picker
- empty states

## 7. Theme Readiness

### Assessment
- The shell already has a theme toggle.
- `data-theme` support exists in the shell CSS.
- Many core colors already flow through CSS custom properties.
- Dark mode overrides are partial and somewhat page-local.

### Classification by area
- THEME-READY: topbar, cards, general shell spacing, many token-driven colors
- SMALL ADAPTATION: buttons, weekview cards, report cards, some badges
- REQUIRES REFACTOR: older hard-coded sidebar colors and some page-local dark overrides
- COMMUN-SPECIFIC, LEAVE AS-IS: legacy prototype-only styling and compatibility fragments

### Future platform contract
Recommended future contract for Offshore and later harmonization:
- `system`
- `light`
- `dark`

Offshore should be built against semantic CSS variables from the start and not wait for Kommun to fully migrate.

## 8. i18n Readiness

### Assessment
- UI text is overwhelmingly hard-coded in Swedish.
- There is no visible translation-key system in the current shell/templates.
- Date, weekday, and meal labels are rendered directly in templates or Python helpers.
- ARIA labels and tooltips are also mostly hard-coded strings.

### Classification
- I18N-READY: none of the major UI shell surfaces are fully key-driven yet
- EASY TO WRAP: some page headers and action labels in shell components
- SCATTERED STRINGS: forms, navigation labels, alerts, and template text
- REQUIRES LATER MIGRATION: the overall module

### Suggested future Offshore contract
- visible strings come from translation keys
- selected language comes from user profile or session
- fallback language is Swedish
- dates and weekdays are locale-aware
- keys are namespaced per module

## 9. Tenant, Site, and Auth Context

### What Kommun uses today
From [templates/ui/_layout/app_shell_base.html](../../templates/ui/_layout/app_shell_base.html) and [core/ui_blueprint.py](../../core/ui_blueprint.py):
- `session['tenant_id']`
- `session['site_id']`
- `session['role']`
- `session['full_name']`, `session['username']`, or `session['user_email']`
- `g.site_context_banner` and `g.host_mismatch_banner`
- `nav_context`
- `allow_site_switch`
- `has_role(...)`
- `get_active_context()` for strict site usage in multiple UI routes
- `select_site` route for site switching

### Offshore should reuse
- the existing auth and role checks
- the existing tenant/site context helpers
- the current site selector behavior
- the same session-scoped current user and role model

### Offshore should not copy
- hidden assumptions that `admin` and `kitchen` are the only important roles
- the legacy habit of falling back to arbitrary sites in contexts that should be locked
- template-level duplication of site resolution logic

## 10. Responsive Behavior

### Desktop
- persistent sidebar
- two-column app shell body
- grid/card layouts
- wider page header spacing

### Tablet / iPad
- app shell becomes one-column below 900px
- sidebar becomes horizontal scroll nav
- weekview cards and grids remain usable
- touch target sizing is already partially addressed in the global CSS

### Mobile
- topbar tightens at 640px
- admin sidebar drawer behavior exists in admin CSS below 768px
- weekview collapses to a single-column layout below 768px
- print styles hide shell navigation and topbar

### Offshore reference value
- the shell is already close to what Offshore needs on iPad and laptop
- the horizontal nav fallback is a useful pattern for narrow screens
- the current admin drawer overlay is more Kommun-specific and may not be ideal for Offshore

## 11. Reuse Matrix

### Common Yuplan ground
- app shell
- topbar placement
- sidebar structure
- logo
- user/profile area
- tenant/site context
- page header
- cards
- buttons
- forms
- alerts
- badges
- modals
- empty states
- responsive behavior
- typography
- spacing
- theme contract
- language contract readiness

### Kommun-specific
- Veckovy
- Planera
- Avdelningar
- Specialkost
- Menyimport
- Rapporter
- Köksanvändare
- specific weekview and report semantics

### Offshore-specific later
- own dashboard
- period plan
- menu cycle
- prep
- freezer picks
- Husk att bestill
- handover
- history and copy-forward

## 12. Recommended Strategy
Recommended approach: Strategy B, visual compatibility without a large Kommun refactor.

Why:
- the current shell already gives a usable shared visual grammar
- Offshore can adopt the same spacing and token language immediately
- the existing Kommun route families are too different to block Offshore on a large extraction
- a big Kommun refactor would be higher risk than value at this stage

Use Strategy A opportunistically where the shared shell and token system already exist. Reserve Strategy C for later harmonization only if needed.

## 13. Offshore Foundation Contract
The next Offshore foundation ticket should follow this visual and technical contract:

- new separate Offshore module
- `/offshore`
- feature flag
- existing Unified auth/RBAC
- existing tenant/site context
- Kommun-inspired app shell
- Kommun-inspired topbar
- Kommun-inspired sidebar structure
- Offshore-specific navigation labels and routes
- professional empty dashboard
- settings skeleton
- theme-ready CSS tokens
- i18n-ready visible strings
- no changes to Kommun

### Theme-ready means
- semantic CSS variables
- no unnecessary hard-coded light-only colors
- ability to support `system`, `light`, `dark` later
- no requirement to fully implement the theme switch on day one

### i18n-ready means
- Offshore strings can be collected via a minimal translation contract
- avoid scattered labels where practical
- support `sv`, `no`, `en` later
- no requirement to translate Kommun in this ticket

## 14. Explicit Non-Goals
- no Kommun refactor
- no template extraction
- no class renaming
- no route renaming
- no JavaScript rewrite
- no dark mode rollout in Kommun
- no language selector rollout in Kommun
- no Offshore implementation in this ticket
- no migration work

## 15. Notes on Readiness Gaps
- The shell CSS is already the strongest theme-ready surface.
- The admin drawer overlay is more of a page-family-specific solution than a platform-wide shell contract.
- The cook dashboard header/footer macros are reusable as concepts, but not the best technical basis for Offshore Foundation.
- The `dashboard_ui.py` blueprint is legacy and should not be treated as the source of truth for the modern shell.

## 16. Document Navigation
See [README.md](README.md) for the platform document index and authority notes.

## 17. Conclusion
Kommun already provides a solid visual base through the app-shell pattern, tokenized CSS, and responsive shell behavior. Offshore should match that language from the start, but the implementation should be done in a new module rather than by changing Kommun itself.

## 18. Scope Verification

Verified changed files for this audit:
- [docs/platform/commun_ui_reference_audit.md](commun_ui_reference_audit.md)
- [docs/platform/README.md](README.md)

No production code was modified for this audit.

Git status check:
- `git status --short` showed only the two audit docs as untracked files.
- `git diff --stat` and `git diff --name-status` were empty because the files are new and untracked.

## 19. Test Baseline

Relevant test files selected for this baseline:
- [tests/ui/test_unified_ui_phase1.py](../../tests/ui/test_unified_ui_phase1.py)
- [tests/admin/test_admin_ui_dashboard.py](../../tests/admin/test_admin_ui_dashboard.py)
- [tests/ui/test_unified_admin_phase1.py](../../tests/ui/test_unified_admin_phase1.py)
- [tests/ui/test_unified_weekview_phase1.py](../../tests/ui/test_unified_weekview_phase1.py)
- [tests/ui/test_weekview_site_overview_phase1.py](../../tests/ui/test_weekview_site_overview_phase1.py)
- [tests/ui/test_admin_weekview_menu_modal.py](../../tests/ui/test_admin_weekview_menu_modal.py)

Baseline command:
- `pytest -q`

Actual results:
- baseline subset: 46 passed
- full suite: 1524 passed, 15 skipped, 3 warnings

Warnings were deprecation warnings from `openapi_spec_validator.validate_spec`.

