import { LOCAL_API_URL } from './config.js';

export async function localApiRequest(path, options = {}) {
  try {
    const response = await fetch(`${LOCAL_API_URL}/${path}`, {
      ...options,
      credentials: 'include', // ← ログイン時のCookie(認証の印)を一緒に送る
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    // ログインが必要なのにログインしていない場合、自動でログイン画面へ飛ばす
    if (response.status === 401) {
      const currentPageUrl = window.location.href;
      const loginUrl = `${LOCAL_API_URL}/login?next=${encodeURIComponent(currentPageUrl)}`;
      window.location.href = loginUrl; // ← ここでページ遷移が発生する
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