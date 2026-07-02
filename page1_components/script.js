// 設定値
const SUPABASE_URL = 'https://tekrwutayfleorpfbuhc.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRla3J3dXRheWZsZW9ycGZidWhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NzA1ODIsImV4cCI6MjA5ODE0NjU4Mn0.eG8ENxN1BxZn_yFdxrsytz2Qa9LCT95WgdRqLkEDs80';


// 🔑 Supabaseクライアントを初期化
const supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

// 🎟️ 有効なログインチケット（アクセストークン）を自動取得する関数
async function getValidToken() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    return session ? session.access_token : SUPABASE_KEY;
}

// 🔒 ログイン状態をチェックする関数（ポップアップ用）
async function checkAuth() {
    const { data: { session }, error } = await supabaseClient.auth.getSession();

    if (error || !session) {
        const email = prompt("登録したメールアドレスを入力してください：");
        const password = prompt("パスワードを入力してください：");

        if (!email || !password) {
            alert("ログインが必要やで！画面を再読み込みしてな。");
            return false;
        }

        const { error: loginError } = await supabaseClient.auth.signInWithPassword({
            email: email,
            password: password
        });

        if (loginError) {
            alert("ログインに失敗したわ： " + loginError.message);
            window.location.reload();
            return false;
        } else {
            alert("ログイン成功！");
            window.location.reload();
            return false;
        }
    }
    return true; 
}





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
        fetchAllFromDB(); 
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

// 3. DBのデータを全件取得してテーブル表示する関数
async function fetchAllFromDB() {
    const table = document.getElementById('data-table');
    const tbody = document.getElementById('table-body');
    const status = document.getElementById('list-status');
    
    status.innerText = '読み込み中...';
    table.style.display = 'none';
    tbody.innerHTML = ''; 

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

// ページ読み込み完了後にスワイプ処理を登録
document.addEventListener('DOMContentLoaded', () => {
    let touchStartX = 0;
    let touchStartY = 0;

    window.addEventListener('touchstart', (e) => {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, false);

    window.addEventListener('touchend', (e) => {
        const touchEndX = e.changedTouches[0].clientX;
        const touchEndY = e.changedTouches[0].clientY;
        
        const diffX = touchEndX - touchStartX;
        const diffY = Math.abs(touchEndY - touchStartY);

        // スワイプ判定
        if (touchStartX < 50 && diffX > 100 && diffY < 50) {
            // chat.htmlへ遷移
            window.location.href = './chat.html';
        }
    }, false);
});