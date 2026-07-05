const TOKEN_KEY = 'app_auth_token';

// ログインページから戻ってきた時、URLの ?token=... を検出して保存する
export function saveTokenFromUrlIfPresent() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');

  if (token) {
    localStorage.setItem(TOKEN_KEY, token);

    // URLからtokenを消す(ブラウザ履歴やブックマークにトークンが残らないようにする)
    params.delete('token');
    const newSearch = params.toString();
    const newUrl = window.location.pathname + (newSearch ? `?${newSearch}` : '') + window.location.hash;
    window.history.replaceState({}, '', newUrl);
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// --- ログイン待ちで中断されたリクエストを、一時的に保管する仕組み ---
const PENDING_KEY = 'app_pending_request';

// 「送ろうとしていた内容」+「成功した時に表示するメッセージ」をまとめて保存
export function savePendingRequest(path, options, successMessage) {
  localStorage.setItem(PENDING_KEY, JSON.stringify({ path, options, successMessage }));
}

export function getPendingRequest() {
  const raw = localStorage.getItem(PENDING_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function clearPendingRequest() {
  localStorage.removeItem(PENDING_KEY);
}