const SUPABASE_URL = 'https://tekrwutayfleorpfbuhc.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRla3J3dXRheWZsZW9ycGZidWhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NzA1ODIsImV4cCI6MjA5ODE0NjU4Mn0.eG8ENxN1BxZn_yFdxrsytz2Qa9LCT95WgdRqLkEDs80';

// 共通のSupabaseリクエスト関数（重複コードをここに集約）
async function supabaseRequest(path, options = {}) {
try {
const response = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
...options,
headers: {
'apikey': SUPABASE_KEY,
'Authorization': `Bearer ${SUPABASE_KEY}`,
'Content-Type': 'application/json',
...options.headers
}
});
if (!response.ok) throw new Error(`HTTP ${response.status}`);
return options.method === 'GET' || !options.method
? await response.json()
: true;
} catch (err) {
console.error('Supabase通信エラー:', err);
return null;
}
}

// 1. クラウドDBへ保存
async function saveToDB() {
const input = document.getElementById('input-text');
const textValue = input.value.trim();
if (!textValue) {
alert('文字を入力してください！');
return;
}

const result = await supabaseRequest('quiz_data', {
method: 'POST',
headers: { 'Prefer': 'return=representation' },
body: JSON.stringify({
question: textValue,
answer: 'O',
explanation: 'テスト解説'
})
});

if (result) {
alert('クラウドDBへの保存に成功しました！');
input.value = '';
fetchAllFromDB();
} else {
alert('保存に失敗しました。');
}
}

// 2. 最新の1件を取得
async function readFromDB() {
const outputArea = document.getElementById('output-area');
outputArea.innerText = '通信中...';

const data = await supabaseRequest('quiz_data?order=id.desc&limit=1');

if (data === null) {
outputArea.innerText = 'データの取得に失敗しました。';
} else if (data.length > 0) {
outputArea.innerText = data[0].question;
} else {
outputArea.innerText = 'まだデータが1件もありません。';
}
}

// 3. 全件取得してテーブル表示
async function fetchAllFromDB() {
const table = document.getElementById('data-table');
const tbody = document.getElementById('table-body');
const status = document.getElementById('list-status');

status.innerText = '読み込み中...';
table.style.display = 'none';
tbody.innerHTML = '';

const data = await supabaseRequest('quiz_data?order=id.desc&limit=20');

if (data === null) {
status.innerText = 'データの取得に失敗しました。';
return;
}

status.innerText = `合計 ${data.length} 件のデータを表示しています。`;

if (data.length === 0) {
status.innerText = 'データが空っぽです。';
return;
}

// innerHTML連結ではなくtextContentで安全にセット（XSS対策）
data.forEach(item => {
const row = document.createElement('tr');
['id', 'question', 'answer', 'explanation'].forEach(key => {
const td = document.createElement('td');
td.textContent = item[key] ?? (key === 'id' ? '-' : '');
row.appendChild(td);
});
tbody.appendChild(row);
});
table.style.display = 'table';
}

// スワイプでchat.htmlへ遷移
document.addEventListener('DOMContentLoaded', () => {
let touchStartX = 0;
let touchStartY = 0;

window.addEventListener('touchstart', (e) => {
touchStartX = e.touches[0].clientX;
touchStartY = e.touches[0].clientY;
}, { passive: true });

window.addEventListener('touchend', (e) => {
const diffX = e.changedTouches[0].clientX - touchStartX;
const diffY = Math.abs(e.changedTouches[0].clientY - touchStartY);

if (touchStartX < 50 && diffX > 100 && diffY < 50) {
window.location.href = './chat.html';
}
}, { passive: true });
});
