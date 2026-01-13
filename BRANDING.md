# Yuplan Unified – Branding & UI System (Master Spec)

Detta dokument definierar den OFFICIELLA brandingen för Yuplan Unified.
Alla templates, CSS, JS och nya vyer ska följa dessa regler.

---

## 1. Logotyp

### 1.1 Fil och sökväg

**Enda giltiga logga:**

- Disk: `static/img/logo-proposal.svg`
- I templates:  
  ```jinja
  {{ url_for('static', filename='img/logo-proposal.svg') }}
  ```

**Inga andra loggor får användas eller skapas.**

### 1.2 Logotyp-användning

**Global header (alla huvudsidor):**

```html
<a href="{{ url_for('ui.cook_dashboard') }}" class="yp-header-brand" aria-label="Gå till startsidan för Yuplan Unified">
  <img src="{{ url_for('static', filename='img/logo-proposal.svg') }}" alt="Yuplan Unified" class="yp-logo">
  <span class="yp-brand-text">Yuplan Unified</span>
</a>
```

Om `ui.cook_dashboard` inte finns – använd den "home"-route som är definierad.

### 1.3 Logotyp-storlek

**Desktop / tablet:**

- `height: 28px`
- `max-height: 32px`
- `width: auto`
- Får ALDRIG bli större än 32px hög.

**Mobil (< 768px):**

- `height: 22px`
- `max-height: 24px`

Loggan får aldrig skalas i procent, endast i px.

**CSS (global):**

```css
.yp-global-header .yp-header-brand {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}

.yp-global-header .yp-logo {
    height: 28px;
    max-height: 32px;
    width: auto;
    object-fit: contain;
    flex-shrink: 0;
}

@media (max-width: 768px) {
    .yp-global-header .yp-logo {
        height: 22px;
        max-height: 24px;
    }
}

.yp-global-header .yp-brand-text {
    font-size: var(--yp-font-size-base, 1rem);
    font-weight: 600;
    white-space: nowrap;
}
```

---

## 2. Färgpalett (CSS-variabler)

Alla färger ska komma från `unified_ui.css` via dessa tokens:

```css
:root {
  /* Primary Colors - Blue theme */
  --yp-color-primary:        #2563eb;
  --yp-color-primary-hover:  #1d4ed8;
  --yp-color-primary-light:  #dbeafe;
  
  --yp-color-secondary:      #64748b;
  --yp-color-secondary-hover:#475569;
  --yp-color-secondary-light:#f1f5f9;
  
  --yp-color-accent:         #8b5cf6;
  --yp-color-accent-hover:   #7c3aed;
  --yp-color-accent-light:   #ede9fe;

  /* Background Colors */
  --yp-color-bg:             #ffffff;
  --yp-color-bg-alt:         #f8fafc;
  --yp-color-bg-elevated:    #ffffff;

  /* Text Colors */
  --yp-color-text:           #0f172a;
  --yp-color-text-muted:     #64748b;
  --yp-color-text-disabled:  #cbd5e1;

  /* Semantic Colors */
  --yp-color-success:        #16a34a;
  --yp-color-success-light:  #dcfce7;
  --yp-color-success-dark:   #15803d;
  
  --yp-color-warning:        #ea580c;
  --yp-color-warning-light:  #fed7aa;
  --yp-color-warning-dark:   #c2410c;
  
  --yp-color-danger:         #dc2626;
  --yp-color-danger-light:   #fee2e2;
  --yp-color-danger-dark:    #991b1b;
  
  --yp-color-info:           #0891b2;
  --yp-color-info-light:     #cffafe;

  /* Border & Divider */
  --yp-color-border:         #e2e8f0;
  --yp-color-border-dark:    #cbd5e1;
  --yp-color-divider:        #f1f5f9;

  /* Spacing */
  --yp-gap-xs:               0.25rem;  /* 4px */
  --yp-gap-sm:               0.5rem;   /* 8px */
  --yp-gap:                  1rem;     /* 16px */
  --yp-gap-lg:               1.5rem;   /* 24px */
  --yp-gap-xl:               2rem;     /* 32px */

  /* Border Radius */
  --yp-radius:               0.5rem;   /* 8px */
  --yp-radius-sm:            0.25rem;  /* 4px */
  --yp-radius-lg:            0.75rem;  /* 12px */
  --yp-radius-full:          9999px;

  /* Typography */
  --yp-font-size-xs:         0.75rem;  /* 12px */
  --yp-font-size-sm:         0.875rem; /* 14px */
  --yp-font-size-base:       1rem;     /* 16px */
  --yp-font-size-lg:         1.125rem; /* 18px */
  --yp-font-size-xl:         1.25rem;  /* 20px */
  --yp-font-size-2xl:        1.5rem;   /* 24px */

  /* Shadows */
  --yp-shadow-sm:            0 1px 2px 0 rgb(0 0 0 / 0.05);
  --yp-shadow:               0 1px 3px 0 rgb(0 0 0 / 0.1);
  --yp-shadow-md:            0 4px 6px -1px rgb(0 0 0 / 0.1);
  --yp-shadow-lg:            0 10px 15px -3px rgb(0 0 0 / 0.1);
  --yp-shadow-xl:            0 20px 25px -5px rgb(0 0 0 / 0.1);
}
```

**Inga hårdkodade hex-färger direkt i nya komponenter – alltid via variablerna.**

---

## 3. Global Header & Footer

### 3.1 Header (App Shell)

**Höjd:**

- 56px mobil
- 64px desktop

**Bakgrund:** `var(--yp-color-primary)`

**Text:** `#FFFFFF`

**Struktur:**

```html
<header class="yp-global-header" role="banner">
  <div class="yp-global-header__container">
    <div class="yp-global-header__brand">
      <!-- Brand (se logotyp ovan) -->
    </div>
    <div class="yp-global-header__context">
      <!-- Kontextrubrik, site, vecka/år -->
    </div>
    <div class="yp-global-header__actions">
      <!-- Användare + ENV-badge -->
    </div>
  </div>
</header>
```

**ENV-badge använder:**

```html
<span class="yp-global-header__env-badge yp-global-header__env-badge--local">LOCAL</span>
<span class="yp-global-header__env-badge yp-global-header__env-badge--staging">STAGING</span>
<span class="yp-global-header__env-badge yp-global-header__env-badge--prod">PROD</span>
```

### 3.2 Footer

Likformig footer på alla huvudsidor:

```html
<footer class="yp-global-footer" role="contentinfo">
  <div class="yp-global-footer__container">
    <div class="yp-global-footer__copyright">
      <strong>Yuplan Unified</strong> · © 2025 · För pilotbruk
    </div>
    <div class="yp-global-footer__support">
      Support: kontakta systemansvarig eller Yuplan
    </div>
  </div>
</footer>
```

**Bakgrund:** `var(--yp-color-bg-alt)`  
**Text:** `var(--yp-color-text-muted)`

---

## 4. Standardkomponenter (klasser)

### 4.1 Kort (cards)

**Klasser:**

- `.yp-card`
- `.yp-card-header`
- `.yp-card-body`
- `.yp-card-footer`

All admin/veckovy/kockvy ska använda `yp-card` som bas.

### 4.2 Knappar

**Klasser:**

- `.yp-button` (primary)
- `.yp-button-secondary`
- `.yp-button-danger`
- `.yp-button-link`

Alla knappar ska använda dessa – inga ad hoc-knappar.

### 4.3 Badges

**Klasser:**

- `.yp-badge`
- `.yp-badge-success`
- `.yp-badge-warning`
- `.yp-badge-danger`
- `.yp-badge-muted`
- `.yp-badge-secondary`
- `.yp-badge-alt2`

**Används för:**

- Registrerad/Ej gjord
- Alt2
- Status (aktiv/inaktiv)
- Coverage i rapport

### 4.4 Tabeller

Alla tabeller i admin/rapporter:

```html
<table class="yp-table">
  <thead>
    <tr>
      <th>Kolumn 1</th>
      <th>Kolumn 2</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Data 1</td>
      <td>Data 2</td>
    </tr>
  </tbody>
</table>
```

Stripes, hovring och hörn via CSS.

### 4.5 Formulär

**Formkomponenter:**

```html
<form class="yp-form">
  <div class="yp-form-field">
    <label class="yp-label" for="name">Namn:</label>
    <input type="text" class="yp-input" id="name" name="name">
  </div>
  <div class="yp-form-field">
    <label class="yp-checkbox-label">
      <input type="checkbox" class="yp-checkbox">
      Godkänn villkor
    </label>
  </div>
  <button type="submit" class="yp-button">Skicka</button>
</form>
```

---

## 5. Tillgänglighet

- **Header:** `<header role="banner">`
- **Footer:** `<footer role="contentinfo">`
- **Landmarks:** `<main>`, `<nav>` där det är relevant
- **ARIA-label på:**
  - Logo-länken
  - Env-badge
  - Interaktiva ikoner utan text

---

## 6. Viktiga regler

1. **Skapa aldrig nya loggor.**  
   Endast `img/logo-proposal.svg`.

2. **Använd alltid CSS-variabler för färg, spacing och font-size.**

3. **Ny UI-kod ska återanvända:**
   - `.yp-card`
   - `.yp-table`
   - `.yp-button*`
   - `.yp-badge*`
   - `.yp-form`, `.yp-input`, `.yp-checkbox`

4. **Inga inline styles, inga inline onClick** – allt via CSS/JS-filer.

5. **Tablet-first:**
   - Minst 44px klickyta
   - 16px basfont

---

## 7. Referensfiler

- **CSS:** `static/unified_ui.css` - alla design tokens och komponenter
- **Header macro:** `templates/includes/yuplan_header.html`
- **Footer macro:** `templates/includes/yuplan_footer.html`
- **Logo:** `static/img/logo-proposal.svg`

---

**Senast uppdaterad:** 2025-12-01  
**Version:** 1.0
