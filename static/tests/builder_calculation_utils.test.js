import { beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + '\n//# sourceURL=' + relativePath);
}

describe('builder calculation utility', () => {
  beforeEach(() => {
    delete window.BuilderCalculationUtils;
  });

  it('preserves the current supported unit combinations and rounding behavior', () => {
    loadScript('../../static/js/builder_calculation_utils.js');

    const utils = window.BuilderCalculationUtils;
    expect(utils).toBeTruthy();

    expect(utils.calculateRowCost({ amount_value: '80', amount_unit: 'g', price_value: '11', price_unit: 'kr/kg' })).toBeCloseTo(0.88, 10);
    expect(utils.calculateRowCost({ amount_value: '2', amount_unit: 'kg', price_value: '11', price_unit: 'kr/kg' })).toBeCloseTo(22, 10);
    expect(utils.calculateRowCost({ amount_value: '60', amount_unit: 'ml', price_value: '21', price_unit: 'kr/l' })).toBeCloseTo(1.26, 10);
    expect(utils.calculateRowCost({ amount_value: '30', amount_unit: 'dl', price_value: '21', price_unit: 'kr/l' })).toBeCloseTo(63, 10);
    expect(utils.calculateRowCost({ amount_value: '1.5', amount_unit: 'l', price_value: '21', price_unit: 'kr/l' })).toBeCloseTo(31.5, 10);
    expect(utils.calculateRowCost({ amount_value: '3', amount_unit: 'st', price_value: '7.45', price_unit: 'kr/st' })).toBeCloseTo(22.35, 10);
    expect(utils.calculateRowCost({ amount_value: '80', amount_unit: 'g', price_value: '11', price_unit: 'kr/kg' })).toBe(0.88);
    expect(utils.formatCostValue(4.99)).toBe('4.99');
    expect(utils.formatCostValue(Number.NaN)).toBe('');
    expect(utils.calculateRowCost({ amount_value: '80', amount_unit: 'g', price_value: '', price_unit: 'kr/kg' })).toBeNull();
    expect(utils.calculateRowCost({ amount_value: '80', amount_unit: 'unknown', price_value: '11', price_unit: 'kr/kg' })).toBeNull();
  });
});
