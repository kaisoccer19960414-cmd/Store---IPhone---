//ローカルサーバー(python)で試す版のJavascriptコード
import { LOCAL_API_URL } from './config.js';

export async function localApiRequest(path, options = {}) {
  try {
    const response = await fetch(`${LOCAL_API_URL}/${path}`, {
      ...options,
      headers: {
        //'Content-Type': 'application/json',
        //'X-App-Passcode': '1111',

         credentials: 'include', // ← ログイン時のCookie(認証の印)を一緒に送る
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