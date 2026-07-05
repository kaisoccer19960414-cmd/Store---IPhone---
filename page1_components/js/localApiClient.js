import { LOCAL_API_URL } from './config.js';
import { getToken, savePendingRequest } from './authClient.js';

// successMessage: ログイン待ちで中断された場合に、戻ってきた後の自動再送信で使うメッセージ
export async function localApiRequest(path, options = {}, successMessage = null) {
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

    // ログインが必要なのにトークンが無い/無効な場合
    if (response.status === 401) {
      // 今送ろうとしていた内容を保存しておき、ログイン後に自動で再送信できるようにする
      savePendingRequest(path, options, successMessage);

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