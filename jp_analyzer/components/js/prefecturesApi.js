import { API_BASE_URL } from './config.js';

export async function fetchPrefectures(query = '', sort = 'id', order = 'asc') {
  const params = new URLSearchParams({ sort, order });
  if (query) params.set('q', query);

  const res = await fetch(`${API_BASE_URL}/prefectures?${params.toString()}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error || `HTTP ${res.status}`);
  }
  return res.json();
}