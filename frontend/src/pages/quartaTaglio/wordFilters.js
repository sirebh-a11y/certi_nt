// One selection for all three alternative list filters, including restored sessions.
export function normalizeWordFilters(state = {}) {
  const onlyAdditionalWords = state.onlyAdditionalWords === true;
  const onlyWordPending = !onlyAdditionalWords && state.onlyWordPending === true;
  return {
    onlyAdditionalWords,
    onlyWordPending,
    hideCertified: !onlyAdditionalWords && !onlyWordPending && state.hideCertified === true,
  };
}

export function toggleWordFilter(state, key) {
  const current = normalizeWordFilters(state);
  return normalizeWordFilters({ [key]: !current[key] });
}
