import { saveToDB, readFromDB, toggleQuizList, initAuthorSelect, loadMoreQuizzes } from './quizUI.js';
import { API_BASE_URL } from './config.js';

// Renderの無料プランはアクセスが無いとスリープするため、ページを開いた直後に
// ウォームアップ用のpingを1回投げておく(ユーザーがボタンを押す頃には起きている状態を狙う)。
// 継続的なkeep-aliveではなく訪問時に1回だけなので、無料枠の消費はごくわずか。
// 失敗しても無視してよい(通常のリクエスト時に改めて起動を待てば良いだけ)。
fetch(`${API_BASE_URL}/ping`).catch(() => {});

document.addEventListener('DOMContentLoaded', () => {
  initAuthorSelect();

  document.getElementById('save-btn').addEventListener('click', saveToDB);
  document.getElementById('read-btn').addEventListener('click', readFromDB);
  document.getElementById('fetch-all-btn').addEventListener('click', toggleQuizList);
  document.getElementById('load-more-btn')?.addEventListener('click', loadMoreQuizzes);
});



async function loadPingStats() {
    try {
        const res = await fetch('https://store-iphone-1.onrender.com/ping-stats');
        const data = await res.json();
        const el = document.getElementById('ping-status');
        if (data.last_ping_at) {
            const date = new Date(data.last_ping_at);
            const formatted = date.toLocaleString('ja-JP');
            el.innerText = `🟢 最終ping: ${formatted}（累計${data.total_count}回）`;
        } else {
            el.innerText = 'まだpingが記録されていません';
        }
    } catch (e) {
        document.getElementById('ping-status').innerText = '取得失敗';
    }
}
window.addEventListener('load', loadPingStats);