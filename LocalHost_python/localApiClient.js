import { LOCAL_API_URL } from './Config.js';

// Flask版は認証(apikey)が無く、URLも /rest/v1/ のような接頭辞が無いので
// supabaseClient.jsよりシンプルな形になる
export async function localApiRequest(path, options = {}) {
  try {
    const response = await fetch(`${LOCAL_API_URL}/${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

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