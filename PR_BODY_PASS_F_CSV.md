Pass F: Admin – CSV import (client preview + mapping)

Adds CSV import UI to the Admin panel (client-side only):

- File input + drag-n-drop with focus states (A11y: keyboard Enter/Space)
- Parser: UTF-8 BOM handling, autodetect delimiter (';' or ','), quoting with doubled quotes ""
- Header normalization for auto-suggest mapping
- Mapping selects: Dag, Lunch, Kväll (auto-suggest from headers)
- Preview table: shows first 50 rows with a "Visa fler" button
- Summary per day (Lunch/Kväll), tolerant of Swedish/English day names and short forms
- Error banner for missing columns / parse issues
- No server writes in this pass
- Vitest unit tests for parser + mapping (åäö, BOM, delimiters)

Definition of Done
- I can pick a CSV → see a preview table → map columns → see a per-day summary (Lunch/Kväll)
- Handles ÅÄÖ and UTF-8 BOM
- No network POSTs/changes
- Tests pass (vitest green)

Notes
- This is UI-only; backend endpoint will come in a subsequent pass.
- Static assets/manifest improvements are handled in PRs #31/#32.