# Session Logs

Lightweight log of important chat decisions and work steps. Use one file per working day to make later recovery easy.

Suggested filename: `YYYY-MM-DD.md`

Template:

```
# YYYY-MM-DD

## Context
- Branch: <branch>
- Area: <ui/auth/api>
- Goal: <one-liner>

## Decisions
- <What we decided and why>

## Changes
- Files:
  - <path>: <summary>

## Tests/Verification
- <what you ran or checked>

## Next
- <small TODO list>
```

Tips:
- Commit these logs (small) so the team can see context.
- When a big change lands, link to related ADRs.
