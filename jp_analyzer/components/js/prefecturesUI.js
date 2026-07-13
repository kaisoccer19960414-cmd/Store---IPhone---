import { fetchPrefectureStats, fetchStatsMeta } from './prefecturesApi.js';

// 指標コード(DB上のindicator値)→表示用の日本語ラベル。
// 新しい指標を投入したときは、ここに1行足すだけで表示に反映される
// (登録し忘れてもコードがそのまま表示されるだけで壊れはしない)。
const INDICATOR_LABELS = {
  population: '人口',
  population_change_rate: '人口増減率',
};

function indicatorLabel(code) {
  return INDICATOR_LABELS[code] ?? code;
}

let currentQuery = '';
let currentSort = 'value';
let currentOrder = 'desc';
let currentIndicator = 'population';
let currentYear = null;
let statsMeta = [];

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

    const indicatorTd = document.createElement('td');
    indicatorTd.textContent = item.indicator ? indicatorLabel(item.indicator) : '-';
    row.appendChild(indicatorTd);

    const valueTd = document.createElement('td');
    const unit = item.unit ? ` ${item.unit}` : '';
    valueTd.textContent = item.value != null ? `${item.value}${unit}` : '-';
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
    const data = await fetchPrefectureStats(currentQuery, currentSort, currentOrder, currentIndicator, currentYear);
    renderRows(data);

    if (data.length === 0) {
      status.textContent = currentQuery
        ? `「${currentQuery}」の${indicatorLabel(currentIndicator)}データが見つかりませんでした。`
        : `${currentYear ?? ''}年のデータが見つかりませんでした。`;
    } else if (currentQuery) {
      status.textContent = `「${currentQuery}」の${indicatorLabel(currentIndicator)}データを ${data.length} 件表示中です(全年度)。`;
    } else {
      status.textContent = `${currentYear}年のデータを ${data.length} 件表示中です。`;
    }
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

export function changeYear(year) {
  currentYear = Number(year);
  loadPrefectures();
}

export function changeIndicator(indicator) {
  currentIndicator = indicator;
  populateYearOptions(indicator);
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

function populateYearOptions(indicator) {
  const yearSelect = document.getElementById('pref-year-select');
  const meta = statsMeta.find(m => m.indicator === indicator);
  const years = meta ? meta.years : [];

  yearSelect.innerHTML = '';
  years.forEach(y => {
    const opt = document.createElement('option');
    opt.value = y;
    opt.textContent = `${y}年`;
    yearSelect.appendChild(opt);
  });

  currentYear = years[0] ?? null;
  if (currentYear != null) {
    yearSelect.value = currentYear;
  }
}

// DBに実際に入っているindicator/yearをここで取得してセレクトを組み立てる。
// 新しいCSV(新しいindicator)を投入しても、ここは変更不要で自動的に反映される。
export async function initSelectors() {
  const indicatorSelect = document.getElementById('pref-indicator-select');
  const status = document.getElementById('pref-status');

  try {
    statsMeta = await fetchStatsMeta();
  } catch (err) {
    status.textContent = `指標一覧の取得に失敗しました。(${err.message})`;
    return;
  }

  indicatorSelect.innerHTML = '';
  statsMeta.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.indicator;
    opt.textContent = m.unit ? `${indicatorLabel(m.indicator)}(${m.unit})` : indicatorLabel(m.indicator);
    indicatorSelect.appendChild(opt);
  });

  const defaultMeta = statsMeta.find(m => m.indicator === currentIndicator) ?? statsMeta[0];
  if (defaultMeta) {
    currentIndicator = defaultMeta.indicator;
    indicatorSelect.value = currentIndicator;
    populateYearOptions(currentIndicator);
  }
}