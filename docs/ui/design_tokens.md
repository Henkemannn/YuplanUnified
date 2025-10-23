# Yuplan Design Tokens v0.1

Light/dark CSS variables for a calm, professional UI with high legibility and WCAG AA focus.

- Palette
  - Primary (teal): `--yu-color-primary: #1a9fb3` (safe teal), with 600/700 for hovers
  - Secondary (sand): `--yu-color-secondary: #e6dfd4` (warm, soft separators)
  - Accent: `--yu-color-accent: #93c47d` (positive highlights)
  - Text: `--yu-color-text: #0b1a22`, Muted: `--yu-color-text-muted: #3f5b66`
  - Border: `--yu-color-border: #d3dde4`
  - Error/Warning/Info: `--yu-color-error`, `--yu-color-warn`, `--yu-color-info`
- Radii: 8/12/16px; Pill for badges and segmented controls
- Spacing: 4px base (1,2,3,4,5,6,8,10 units)
- Typo: `--yu-font-sans` uses system fonts; sizes xs–xl
- Shadows: sm/md/lg tuned for subtle elevation
- Motion: base 220ms, `--yu-ease: cubic-bezier(.2,.8,.2,1)`; respects reduced motion

## Modes

- Light (default): `:root { ... }`
- Dark: `:root[data-theme="dark"] { ... }`
- Brand variants (proposals):
  - `data-brand="ocean"` for cooler blue
  - `data-brand="emerald"` for greener primary

## Buttons

- Solid (default primary), Outline (neutral border), Soft (tinted surface)

## Usage

- Include `/static/ui/tokens.css`
- Use container `.yu-container` and input `.yu-input` classes
- Toggle theme with `document.documentElement.setAttribute('data-theme','dark')`

## Semantic status tokens and alerts

- Status scales (AA in light/dark): `--yu-success-*`, `--yu-info-*`, `--yu-warn-*`, `--yu-error-*`
- Helper classes:
  - `.alert` base container
  - `.alert-error`, `.alert-warn`, `.alert-info`, `.alert-success`
- Example (Problem Details box):
  - `<div class="alert alert-error" role="alert" aria-live="assertive">...</div>`
- Focus ring: `--yu-focus-ring` applied via `:focus-visible` for inputs, buttons, links

## Theme & Brand i UI

HTML-attribut:
- `data-mode="light|dark"` – användarens ljus/mörk-läge (persist via localStorage key `yu_mode`)
- `data-brand="ocean|emerald|teal"` – tenantens brandtema (läses från serverns `tenant.theme`, persist i `yu_brand` för demo)

Exempel:
```html
<html data-mode="dark" data-brand="ocean">...</html>
```

Komponenter använder enbart CSS-variabler (tokens). Byt tema/brand utan att ändra markup.

