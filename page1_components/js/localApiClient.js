import { LOCAL_API_URL } from './config.js';
import { getToken } from './authClient.js';

export async function localApiRequest(path, options = {}) {
  try {
    const token = getToken();

    const response = await fetch(`${LOCAL_API_URL}/${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers
      }
    });

    // ログインが必要なのにトークンが無い/無効な場合、自動でログイン画面へ飛ばす
    if (response.status === 401) {
      const currentPageUrl = window.location.href;
      const loginUrl = `${LOCAL_API_URL}/login?next=${encodeURIComponent(currentPageUrl)}`;
      window.location.href = loginUrl;
      return { data: null, error: 'ログインへ移動します' };
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      const message = errorBody?.error || `HTTP ${response.status}`;
      return { data: null, error: message };
    }

    const data = await response.json().catch(() => true);
    return { data, error: null };

  } catch (err) {
    console.error('ローカルAPI通信エラー:', err);
    return { data: null, error: err.message };
  }
}