# Branding Assets

This directory documents current Yuplan logo variants and usage guidelines.

## Files
- `static/logo/YuplanB&W.svg` – Black & White base (uses `currentColor` in original; here we keep monochrome).
- `static/logo/YuplanBlue.svg` – Primary brand blue (#0D6EFD).
- `static/logo/YuplanGreen.svg` – Secondary accent green (#16A34A).
- `static/logo/YuplanDuotone.svg` – Linear gradient blue→green.
- `static/logo/YuplanDuotoneDark.svg` – Duotone tuned for dark backgrounds.
- `static/logo/YuplanWhite.svg` – Solid white for dark headers.
- `static/logo/YuplanWordmark.svg` – Dev wordmark (symbol + text using system font).

## Usage (Flask templates)
```html
<img src="{{ url_for('static', filename='logo/YuplanBlue.svg') }}" alt="Yuplan" height="40" />
```
Swap filename for different variant.

## Usage (React / Vite)
```tsx
<img src="/static/logo/YuplanDuotone.svg" alt="Yuplan" height={32} />
```

## Theming via CSS color (for B&W/base)
If you want dynamic color, you can wrap the B&W version and apply `filter` or place SVG inline and change `fill`.

Example inline recolor:
```html
<span class="logo-blue">{% include 'logo/YuplanB&W.svg' %}</span>
```
With CSS:
```css
.logo-blue svg path { fill: #0D6EFD; }
```

## Favicon Suggestion
Modern browsers support SVG favicons; simplest option:
```html
<link rel="icon" href="{{ url_for('static', filename='logo/YuplanBlue.svg') }}" type="image/svg+xml" />
```
PNG fallback (optional, if you generate raster versions):
```html
<link rel="icon" href="{{ url_for('static', filename='logo/favicon-32.png') }}" sizes="32x32" />
<link rel="icon" href="{{ url_for('static', filename='logo/favicon-64.png') }}" sizes="64x64" />
```

## Suggested Guidelines
- Use Duotone for marketing / splash.
- Use Blue for navigation bars.
- Use B&W for dark-mode (invert via CSS) or print contexts.
- Keep aspect ratio; prefer height control.
 - For dark headers, prefer `YuplanWhite.svg` or `YuplanDuotoneDark.svg`.

## Next Steps
1. Add favicon PNGs.
2. Provide dark-mode duotone (adjust gradient stops).
3. Consider a wordmark variant for horizontal layouts.
