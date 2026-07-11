import { loadPrefectures, searchPrefectures, clearSearch, sortBy } from './prefecturesUI.js';

document.addEventListener('DOMContentLoaded', () => {
  loadPrefectures();

  document.getElementById('pref-search-btn').addEventListener('click', searchPrefectures);
  document.getElementById('pref-search-clear-btn').addEventListener('click', clearSearch);
  document.getElementById('pref-search-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      searchPrefectures();
    }
  });

  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => sortBy(th.dataset.sort));
  });
});