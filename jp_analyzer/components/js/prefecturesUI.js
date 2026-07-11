import { fetchPrefectures } from './prefecturesApi.js';

let currentQuery = '';
let currentSort = 'id';
let currentOrder = 'asc';

function renderRows(data) {
  const tbody = document.getElementById('pref-table-body');
  tbody.innerHTML = '';

  data.forEach(item => {
    const row = document.createElement('tr');
    ['name', 'region_block', 'population', 'population_year'].forEach(key => {
      const td = document.createElement('td');
      td.textContent = item[key] ?? '-';
      row.appendChild(td);
    });
    tbody.appendChild(row);
  });
}

export async function loadPrefectures() {
  const status = document.getElementById('pref-status');
  status.textContent = '読み込み中...';

  try {
    const data = await fetchPrefectures(currentQuery, currentSort, currentOrder);
    renderRows(data);
    status.textContent = data.length === 0
      ? (currentQuery ? `「${currentQuery}」に一致するデータが見つかりませんでした。` : 'データが空です。')
      : `${data.length} 件を表示中です。`;
  } catch (err) {
    status.textContent = `データの取得に失敗しました。(${err.message})`;
  }
}

export function searchPrefectures() {
  const input = document.getElementById('pref-search-input');
  currentQuery = input.value.trim();
  loadPrefectures();
}

export function clearSearch() {
  const input = document.getElementById('pref-search-input');
  input.value = '';
  currentQuery = '';
  loadPrefectures();
}

// 見出しクリックで並び替え(同じ列を2回押すと昇順⇄降順)
export function sortBy(column) {
  if (currentSort === column) {
    currentOrder = currentOrder === 'asc' ? 'desc' : 'asc';
  } else {
    currentSort = column;
    currentOrder = 'asc';
  }
  updateSortIndicators();
  loadPrefectures();
}

function updateSortIndicators() {
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.classList.toggle('sorted', th.dataset.sort === currentSort);
  });
}