(function () {
  'use strict';

  // Current Builder quantity/cost truth. Future ingredient-specific density profiles
  // should extend this seam rather than introduce screen-specific formulas.

  function parseFloatSafe(value) {
    const num = Number(String(value || '').replace(',', '.'));
    return Number.isFinite(num) ? num : null;
  }

  function calculateRowCost(row) {
    const amountValue = parseFloatSafe(row && row.amount_value);
    const priceValue = parseFloatSafe(row && row.price_value);
    const amountUnit = String((row && row.amount_unit) || '').trim().toLowerCase();
    const priceUnit = String((row && row.price_unit) || '').trim().toLowerCase();
    if (amountValue == null || priceValue == null) {
      return null;
    }
    if (priceUnit === 'kr/kg') {
      if (amountUnit === 'g') {
        return (amountValue / 1000) * priceValue;
      }
      if (amountUnit === 'kg') {
        return amountValue * priceValue;
      }
    }
    if (priceUnit === 'kr/l') {
      if (amountUnit === 'ml') {
        return (amountValue / 1000) * priceValue;
      }
      if (amountUnit === 'dl') {
        return (amountValue / 10) * priceValue;
      }
      if (amountUnit === 'l') {
        return amountValue * priceValue;
      }
      if (amountUnit === 'g') {
        return (amountValue / 1000) * priceValue;
      }
    }
    if (priceUnit === 'kr/st') {
      return amountValue * priceValue;
    }
    return null;
  }

  function formatCostValue(value) {
    if (!Number.isFinite(value)) {
      return '';
    }
    return value.toFixed(2);
  }

  globalThis.BuilderCalculationUtils = Object.freeze({
    parseFloatSafe,
    calculateRowCost,
    formatCostValue,
  });
})();