(function () {
  'use strict';

  function normalizeCategoryThemeValue(value) {
    return String(value || '')
      .trim()
      .toLowerCase()
      .replace(/[åä]/g, 'a')
      .replace(/ö/g, 'o');
  }

  function resolveComponentCategoryThemeKey(component) {
    const explicitColor = String((component && component.category_color) || '').trim().toLowerCase();
    if (explicitColor) {
      return explicitColor;
    }

    const category = normalizeCategoryThemeValue(component && component.category);
    if (!category) {
      return 'neutral';
    }
    if (category === 'main' || category === 'kott' || category === 'protein') {
      return 'main';
    }
    if (category === 'fish' || category === 'fisk') {
      return 'fish';
    }
    if (category === 'side' || category === 'tillbehor' || category === 'vegetariskt') {
      return 'side';
    }
    if (category === 'sauce' || category === 'sas') {
      return 'sauce';
    }
    if (category === 'dessert') {
      return 'dessert';
    }
    return 'neutral';
  }

  globalThis.BuilderComponentTheme = Object.freeze({
    normalizeCategoryThemeValue,
    resolveComponentCategoryThemeKey,
  });
})();