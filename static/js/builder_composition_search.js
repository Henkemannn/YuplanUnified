(function () {
  'use strict';

  function normalizeSearchQuery(query) {
    return String(query || '').trim().toLowerCase();
  }

  function matchesCompositionSearch(composition, searchQuery) {
    const needle = normalizeSearchQuery(searchQuery);
    if (!needle) {
      return true;
    }

    const compositionId = String((composition && composition.composition_id) || '').trim().toLowerCase();
    const compositionName = String((composition && composition.composition_name) || (composition && composition.composition_id) || '').trim().toLowerCase();

    return compositionId.includes(needle) || compositionName.includes(needle);
  }

  function filterCompositionsBySearch(compositions, searchQuery) {
    const list = Array.isArray(compositions) ? compositions : [];
    const needle = normalizeSearchQuery(searchQuery);
    if (!needle) {
      return list.slice();
    }
    return list.filter((composition) => matchesCompositionSearch(composition, needle));
  }

  globalThis.BuilderCompositionSearchRuntime = {
    filterCompositionsBySearch,
    matchesCompositionSearch,
    normalizeSearchQuery,
  };
}());