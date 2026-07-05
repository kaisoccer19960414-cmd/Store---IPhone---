import { saveToDB, readFromDB, toggleQuizList, renderAllQuizzes } from './quizUI.js';
import { initSwipeNavigation } from './swipeNav.js';
import { saveTokenFromUrlIfPresent, getPendingRequest, clearPendingRequest } from './authClient.js';
import { localApiRequest } from './localApiClient.js';

// ログイン画面から戻ってきた直後、中断されていたリクエストを自動で完了させる
async function resumePendingRequestIfAny() {
  const pending = getPendingRequest();
  if (!pending) return;

  clearPendingRequest(); // 二重実行を防ぐため、先に消しておく

  const { data, error } = await localApiRequest(pending.path, pending.options);

  if (error) {
    alert(`ログイン後の処理に失敗しました。\n理由: ${error}`);
    return;
  }

  alert(pending.successMessage || '処理が完了しました！');
  renderAllQuizzes(); // 一覧を最新の状態に更新
}

document.addEventListener('DOMContentLoaded', () => {
  saveTokenFromUrlIfPresent(); // ログインから戻ってきた時、URLのtokenを保存してURLをきれいにする
  resumePendingRequestIfAny();  // 保存しようとしていた内容があれば、自動で続きを実行する
  initSwipeNavigation();

  document.getElementById('save-btn').addEventListener('click', saveToDB);
  document.getElementById('read-btn').addEventListener('click', readFromDB);
  document.getElementById('fetch-all-btn').addEventListener('click', toggleQuizList);
});