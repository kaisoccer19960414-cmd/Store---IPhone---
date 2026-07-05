import { LOCAL_API_URL } from './config.js';
import { getToken, setToken } from './authClient.js';
import { showAlert, showPrompt } from './modal.js';

async function loginWithPrompt() {
  const passcode = await showPrompt('管理者パスコードを入力してください', '', 'password');
  if (passcode === null) return null;

  const res = await fetch(`${LOCAL_API_URL}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ passcode })
  });

  const body = await res.json().catch(() => null);

  if (!res.ok) {
    await showAlert(body?.error || 'ログインに失敗しました');
    return null;
  }

  setToken(body.token);
  return body.token;
}

export async function localApiRequest(path, options = {}) {
  try {
    let token = getToken();

    let response = await fetch(`${LOCAL_API_URL}/${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers
      }
    });

    if (response.status === 401) {
      const newToken = await loginWithPrompt();
      if (!newToken) {
        return { data: null, error: 'ログインがキャンセルされました' };
      }

      response = await fetch(`${LOCAL_API_URL}/${path}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${newToken}`,
          ...options.headers
        }
      });
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