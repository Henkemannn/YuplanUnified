Module 1 – Weekview planning

Scope to discuss/confirm:
- Data model (week, meal, department) in Unified format
- Endpoints: GET /weekview, PATCH /weekview/{id}, resolve API
- RBAC behavior: staff/admin
- UI layout: mobile-first
- Feature flag: ff.weekview.enabled

Acceptance
- Skinny first version with static/mock data behind ff.weekview.enabled
- Basic happy-path tests for GET, PATCH
- RBAC enforced via template + endpoint decorators (admin, staff)
