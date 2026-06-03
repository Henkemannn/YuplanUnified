# Custom Dietary Markers (Architecture Note)

Status: documentation note only (no runtime behavior change)

## Decision Summary
Yuplan keeps official EU14 allergens as a fixed, standards-based domain.
Tenant/site/customer-specific dietary adaptations are modeled separately as custom dietary markers.

## Domain Distinction

### 1) EU14 allergens
- Fixed list
- Stable keys
- Legal/menu/print oriented
- Used for official allergen declaration

Use Swedish wording in product surfaces such as:
- Allergener enligt EU14

### 2) Custom dietary markers
- Tenant/site/customer configurable
- Used for planning and operational adaptation, not as a legal allergen list
- Applicable in components, dishes, menus, and special-diet matching flows

Example markers:
- laktosfri
- mjölkfri
- citrus
- fläskfritt
- alkohol
- gelatin
- stark mat
- timbal
- flytande
- energi-/proteinberikad
- diabetesanpassad

Preferred Swedish wording for this domain:
- Egna kostmarkörer
- Kostmarkörer/anpassningar

Important: do not label non-EU14 items as allergens.

## Future Model Idea (Conceptual)

custom_dietary_markers:
- id
- tenant_id/site_id
- name
- slug/key
- display_code
- color
- description
- active
- sort_order

component_custom_dietary_markers:
- component_id
- marker_id

## Future Behavior Direction
- Components can be marked with custom dietary markers.
- Dishes can inherit markers from included components.
- Menus can show optional marker badges when enabled.
- Planera 2.0 can use markers when evaluating who cannot eat standard food.
- Print outputs can include a marker legend, separate from the official EU14 allergen legend.

## Guardrails
- EU14 keys remain the canonical source for official allergen handling.
- Custom dietary markers remain a separate metadata track.
- Keep legal allergen declaration and custom adaptation markers clearly separated in wording and UX.
