import { fetchPrefectureStats } from './prefecturesApi.js';

let currentQuery = '';
let currentSort = 'value';
let currentOrder = 'desc';

function renderRows(data) {
  const tbody = document.getElementById('pref-table-body');
  tbody.innerHTML = '';

  data.forEach(item => {
    const row = document.createElement('tr');

    const nameTd = document.createElement('td');
    nameTd.textContent = item.prefectures?.name ?? '-';
    row.appendChild(nameTd);

    const regionTd = document.createElement('td');
    regionTd.textContent = item.prefectures?.region_block ?? '-';
    row.appendChild(regionTd);

    const valueTd = document.createElement('td');
    valueTd.textContent = item.value ?? '-';
    row.appendChild(valueTd);

    const yearTd = document.createElement('td');
    yearTd.textContent = item.year ?? '-';
    row.appendChild(yearTd);

    tbody.appendChild(row);
  });
}

export async function loadPrefectures() {
  const status = document.getElementById('pref-status');
  status.textContent = '読み込み中...';

  try {
    const data = await fetchPrefectureStats(currentQuery, currentSort, currentOrder);
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