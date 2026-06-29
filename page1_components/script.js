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
        }
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

    // IDの降順（新しい順）で最大20件取得
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