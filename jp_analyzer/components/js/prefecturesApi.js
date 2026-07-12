import { API_BASE_URL } from './config.js';

export async function fetchPrefectureStats(query = '', sort = 'value', order = 'desc', indicator = 'population', year = 2024) {
  const params = new URLSearchParams({ sort, order, indicator, year });
  if (query) params.set('q', query);

  const res = await fetch(`${API_BASE_URL}/prefecture-stats?${params.toString()}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error || `HTTP ${res.status}`);
  }
  return res.json();
}