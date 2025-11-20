Fix ADR lint failures by moving the template out of the ADR-*.md pattern.

Changes:
- Rename `adr/ADR-template.md` -> `adr/TEMPLATE.md`
- Update `adr/README.md` link to point to `TEMPLATE.md`

Rationale:
- `ADR-template.md` matched the linter glob `adr/ADR-*.md` and was flagged as invalid.
- Keeping the template in the folder but with a neutral filename preserves docs without tripping the linter.