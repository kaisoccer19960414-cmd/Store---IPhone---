// 設定値
const SUPABASE_URL = 'https://tekrwutayfleorpfbuhc.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRla3J3dXRheWZsZW9ycGZidWhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NzA1ODIsImV4cCI6MjA5ODE0NjU4Mn0.eG8ENxN1BxZn_yFdxrsytz2Qa9LCT95WgdRqLkEDs80';

// 1. クラウドDB（Supabase）へ保存する関数
async function saveToDB() {
    const textValue = document.getElementById('input-text').value;
    if (!textValue) {
        alert('文字を入力してください！');
        return;
    }

    const response = await fetch(`${SUPABASE_URL}/rest/v1/quiz_data`, {
        method: 'POST',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        },
        body: JSON.stringify({
            question: textValue,
            answer: 'O',
            explanation: 'テスト解説'
        })
    });

    if (response.ok) {
        alert('クラウドDBへの保存に成功しました！');
        document.getElementById('input-text').value = '';
        fetchAllFromDB(); // 保存したら一覧も自動更新
    } else {
        alert('保存に失敗しました。');
    }
}

// 2. クラウドDBから最新の文字を1件とり出す関数
async function readFromDB() {
    const outputArea = document.getElementById('output-area');
    outputArea.innerText = '通信中...';

    const response = await fetch(`${SUPABASE_URL}/rest/v1/quiz_data?order=id.desc&limit=1`, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`
        }
    });

    if (response.ok) {
        const data = await response.json();
        if (data.length > 0) {
            outputArea.innerText = data[0].question;
        } else {
            outputArea.innerText = 'まだデータが1件もありません。';
        }
    } else {
        outputArea.innerText = 'データの取得に失敗しました。';
    }
}

// 3. DBのデータを全件（最大20件）取得してテーブル表示する関数
async function fetchAllFromDB() {
    const table = document.getElementById('data-table');
    const tbody = document.getElementById('table-body');
    const status = document.getElementById('list-status');
    
    status.innerText = '読み込み中...';
    table.style.display = 'none';
    tbody.innerHTML = ''; // 古いデータをクリア

    const response = await fetch(`${SUPABASE_URL}/rest/v1/quiz_data?order=id.desc&limit=20`, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`
        }
    });

    if (response.ok) {
        const data = await response.json();
        status.innerText = `合計 ${data.length} 件のデータを表示しています。`;
        
        if (data.length > 0) {
            data.forEach(item => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${item.id || '-'}</td>
                    <td>${item.question || ''}</td>
                    <td>${item.answer || ''}</td>
                    <td>${item.explanation || ''}</td>
                `;
                tbody.appendChild(row);
            });
            table.style.display = 'table';
        } else {
            status.innerText = 'データが空っぽです。';
        }
    } else {
        status.innerText = 'データの取得に失敗しました。';
    }
}

// 📱 画面左端からの右スワイプで chat.html に遷移するロジック
// スワイプ処理の関数内
if (document.querySelector('#root').innerHTML === "") {
    alert("読み込み中です。あと数秒待ってからスワイプしてください！");
    return; // 処理を中断
}

let touchStartX = 0;
let touchStartY = 0;

// 1. 指が触れた瞬間
window.addEventListener('touchstart', (e) => {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
}, false);

// 2. 指が離れた瞬間
window.addEventListener('touchend', (e) => {
    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;
    
    const diffX = touchEndX - touchStartX; // 右への移動距離
    const diffY = Math.abs(touchEndY - touchStartY); // 上下のズレ

    // 💡 条件判定
    // ・画面の左端（50px以内）からスワイプが始まっていること
    // ・右に100px以上しっかり引っ張っていること
    // ・上下のブレが50px以内であること（誤作動防止）
    if (touchStartX < 50 && diffX > 100 && diffY < 50) {
        // 条件をクリアしたら chat.html へワープ
        window.location.href = './chat.html';
    }
}, false);