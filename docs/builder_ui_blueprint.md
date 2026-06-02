# Yuplan Builder UI Blueprint

## Purpose
This blueprint defines the intended Builder UI structure and visual language for Builder Workspace v1.1.

## 1. Layout
- Page shell uses a fixed left sidebar and a main content area.
- Sidebar width: 240px (desktop), main area fills remaining width.
- Main content max width: 1200px.
- Main content horizontal padding: 24px desktop, 16px mobile.
- Section spacing:
  - 24px between major sections.
  - 12px between related cards within a section.
- Card grid rules:
  - Action cards: 2x2 on desktop, 1-column on narrow screens.
  - Overview cards: 4 columns desktop, 2 columns tablet, 1 column mobile.

## 2. Sidebar
### Items
- Home
- Components
- Dishes
- Menus
- Imports

### Style
- Sidebar uses rounded nav cards, not plain text links.
- Active item uses a clear selected state (background + border + stronger text).
- Imports item contains a small count badge.
- Sidebar remains visually integrated with the same card style and spacing as the main area.

## 3. Home Page Structure
Home includes three blocks.

### A. Hero/Header
- Title: Yuplan Builder
- Subtitle: Build components, dishes and menus from one calm workspace.

### B. Primary action cards (2x2)
Cards:
- Create dish
- Create component
- Create menu
- Import menu / recipes

Each action card includes:
- icon/emoji
- title
- one short sentence
- one clear styled button

### C. Library overview cards
Cards:
- Components count
- Dishes count
- Menus count
- Imports pending

Each overview card includes:
- label
- number
- direct action button (where relevant)

## 4. Component Library View
- Title: Components.
- Search input.
- Category chips:
  - All
  - Main
  - Side
  - Sauce
  - Dessert
  - Uncategorized
- Component card grid.
- Each component card includes:
  - name
  - category badge
  - needs recipe/recipe ready badge
  - Edit component action
  - Remove action

## 5. Dishes Library View
- Title: Dishes.
- Search input.
- Dish cards (no tables).
- Each dish card includes:
  - dish name
  - component chips/summary
  - Edit dish action
  - Remove action

## 6. Imports View
- Session list in card/list form.
- Pending badge count visible.
- Open session card/details panel.
- No table-based layout for the workspace surface.

## 7. Visual Rules
- No raw HTML button appearance.
- No full-width gray browser default buttons.
- No unstyled select/input controls on Home.
- All buttons must use builder-button-* classes.
- All major blocks must be card-based.
- Use rounded corners, soft shadows, and consistent spacing.
- Avoid admin/table look; preserve calm product-style hierarchy.

## 8. Interaction Rules
- Home is default surface.
- Components surface opens only when selecting Components or View components.
- Dishes surface opens only when selecting Dishes or View dishes.
- Browser back is not required for in-app navigation.
- Back to Home is always available from Components and Dishes surfaces.
