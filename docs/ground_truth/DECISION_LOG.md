Status: LOCKED
Last reviewed: 2026-08-24

# Decision Log

## 2026-08-22
- Builder confirmed as canonical Knowledge Source of Truth.
- Planera 2.0 confirmed as generic Production Layer.
- Published Menu is immutable baseline.
- Effective Business Context sits between publication and production.
- Compatibility / Requirements becomes explicit application layer before Planera Core.
- Kommun selected as first full Planera 2.0 production integration.
- Planera 2.0 will enter Kommun through shadow and parity before cutover.
- Portal work will reuse and consolidate existing implementations instead of starting from zero.
- Main Yuplan 1.0 finishline prioritizes Kommun Ready for Pilot after the current Menu/Offshore seam closes.

## 2026-08-24
- Planning Slice confirmed as a non-canonical orchestration concept, not new source-of-truth persistence.
- Production Requirement must preserve traceable references to originating service, menu, Dish, and business context without Planera owning those objects.
- External menu-facing surfaces use effective_menu_name.
- Private Cook Work Menu or COW state is not portal or publication truth unless deliberately promoted or published.
- Planera 2.0 Architecture Lock marked complete; next launch path remains close Menu/Offshore seam -> Portal/Kommun integration -> Kommun Ready for Pilot.
