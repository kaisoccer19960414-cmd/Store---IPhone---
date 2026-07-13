import { loadPrefectures, searchPrefectures, clearSearch, sortBy, changeYear, changeIndicator, initSelectors } from './prefecturesUI.js';

document.addEventListener('DOMContentLoaded', async () => {
  await initSelectors();
  loadPrefectures();

  document.getElementById('pref-search-btn').addEventListener('click', searchPrefectures);
  document.getElementById('pref-search-clear-btn').addEventListener('click', clearSearch);
  document.getElementById('pref-search-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      searchPrefectures();
    }
  });
  document.getElementById('pref-year-select').addEventListener('change', (e) => {
    changeYear(e.target.value);
  });
  document.getElementById('pref-indicator-select').addEventListener('change', (e) => {
    changeIndicator(e.target.value);
  });

  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => sortBy(th.dataset.sort));
  });
});