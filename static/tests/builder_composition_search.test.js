import { beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + '\n//# sourceURL=' + relativePath);
}

describe('builder composition search runtime', () => {
  beforeEach(() => {
    delete window.BuilderCompositionSearchRuntime;
  });

  it('matches canonical Builder dish name/id search semantics', () => {
    loadScript('../../static/js/builder_composition_search.js');

    const runtime = window.BuilderCompositionSearchRuntime;
    expect(runtime).toBeTruthy();

    const compositions = [
      { composition_id: 'plate_1', composition_name: 'Fish Plate', library_group: 'seafood' },
      { composition_id: 'plate_2', composition_name: 'Chicken Plate', library_group: 'poultry' },
      { composition_id: 'soup_1', composition_name: 'Tomato Soup', library_group: 'soup' },
    ];

    expect(runtime.normalizeSearchQuery('  FISH  ')).toBe('fish');
    expect(runtime.matchesCompositionSearch(compositions[0], 'fish')).toBe(true);
    expect(runtime.matchesCompositionSearch(compositions[0], 'plate_1')).toBe(true);
    expect(runtime.matchesCompositionSearch(compositions[0], 'soup')).toBe(false);
    expect(runtime.filterCompositionsBySearch(compositions, 'plate')).toEqual([
      compositions[0],
      compositions[1],
    ]);
    expect(runtime.filterCompositionsBySearch(compositions, 'fish')).toEqual([
      compositions[0],
    ]);
    expect(runtime.filterCompositionsBySearch(compositions, '')).toEqual(compositions);
  });

  it('stays separate from caller empty-query presentation', () => {
    loadScript('../../static/js/builder_composition_search.js');

    const runtime = window.BuilderCompositionSearchRuntime;
    const compositions = [{ composition_id: 'plate_1', composition_name: 'Fish Plate' }];

    expect(runtime.filterCompositionsBySearch(compositions, '')).toEqual(compositions);
    expect(runtime.filterCompositionsBySearch(compositions, '   ')).toEqual(compositions);
  });
});