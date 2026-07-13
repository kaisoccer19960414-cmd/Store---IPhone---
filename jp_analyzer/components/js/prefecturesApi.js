import { API_BASE_URL } from './config.js';

export async function fetchPrefectureStats(query = '', sort = 'value', order = 'desc', indicator = '', year = null) {
  const params = new URLSearchParams({ sort, order });
  if (indicator) params.set('indicator', indicator);
  if (year) params.set('year', year);
  if (query) params.set('q', query);

  const res = await fetch(`${API_BASE_URL}/prefecture-stats?${params.toString()}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchStatsMeta() {
  const res = await fetch(`${API_BASE_URL}/stats-meta`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error || `HTTP ${res.status}`);
  }
  return res.json();
}