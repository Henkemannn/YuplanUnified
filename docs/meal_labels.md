# Weekview Meal Labels (Phase 1.1)

Unified backend models and APIs use neutral internal keys: `lunch` and `dinner` (e.g. `residents.lunch`, `residents.dinner`, `dinner_alt1`). This keeps persistence, service logic, and ETag semantics stable across deployments.

## UI Mapping
In Weekview UIs (`/ui/weekview` and `/ui/weekview_overview`) the visible meal names are provided via a view‑model helper `meal_labels`:

```json
{
  "meal_labels": {
    "lunch": "Lunch",
    "dinner": "Kvällsmat"
  }
}
```

Phase 1.1 introduces this mapping so templates no longer hardcode the second meal name (previously "Middag"). All headings, totals and popup sections use `meal_labels.dinner` instead.

## Scope
- No change to backend service or API field names.
- Pure UI/view‑model adaptation plus tests and templates.
- Default dinner label is **Kvällsmat** (Kommun style) for all sites.

## Future
`get_meal_labels_for_site(site_id)` will later inspect site configuration (e.g. municipal vs offshore) and return a context‑appropriate label:
- Kommun sites: `dinner = "Kvällsmat"`
- Offshore sites: `dinner = "Middag"`

This evolution does not alter internal data structures; only presentation changes. Templates will continue to rely solely on `meal_labels`.

## Migration Notes
Existing tests updated to assert the new label. If a deployment still expects "Middag" everywhere, Phase 2 will add per‑site configuration without reverting the unified model.
