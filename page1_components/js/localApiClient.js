import { API_BASE_URL } from './config.js';
import { getToken, setToken } from './authClient.js';
import { showAlert, showPrompt, showLoading, hideLoading } from './modal.js';

let hasWarmedUp = false;

async function loginWithPrompt() {
  const passcode = await showPrompt('管理者パスコードを入力してください', '', 'password');
  if (passcode === null) return null;

  showLoading('ログイン中...');
  try {
    const res = await fetch(`${API_BASE_URL}/login`, {
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
  } finally {
    hideLoading();
  }
}

export async function localApiRequest(path, options = {}) {
  // silent: true にすると、ローディング表示を出さずに裏で静かに通信する
  const { silent = false, ...fetchOptions } = options;

  const shouldShowLoading = !silent && !hasWarmedUp;

  try {
    let token = getToken();

    if (shouldShowLoading) {
      showLoading('サーバーと通信中...\n(初回はRenderの起動に時間がかかることがあります)');
    }

    let response;
    try {
      response = await fetch(`${API_BASE_URL}/${path}`, {
        ...fetchOptions,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          ...fetchOptions.headers
        }
      });
    } finally {
      if (shouldShowLoading) hideLoading();
      hasWarmedUp = true;
    }

    if (response.status === 401) {
      const newToken = await loginWithPrompt();
      if (!newToken) {
        return { data: null, error: 'ログインがキャンセルされました' };
      }

      
        response = await fetch(`${API_BASE_URL}/${path}`, {
          ...fetchOptions,
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${newToken}`,
            ...fetchOptions.headers
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
    if (shouldShowLoading) hideLoading();
    console.error('ローカルAPI通信エラー:', err);
    return { data: null, error: err.message };
  }
}