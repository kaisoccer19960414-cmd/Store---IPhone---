// 設定値
const SUPABASE_URL = 'https://tekrwutayfleorpfbuhc.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRla3J3dXRheWZsZW9ycGZidWhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NzA1ODIsImV4cCI6MjA5ODE0NjU4Mn0.eG8ENxN1BxZn_yFdxrsytz2Qa9LCT95WgdRqLkEDs80';

// ページを開いたときの初期処理
window.onload = function() {
    const today = new Date();
    const jstOffset = 9 * 60 * 60 * 1000; // 日本時間の時差（9時間）
    const jstDate = new Date(today.getTime() + jstOffset);
    
    const yyyy = jstDate.getUTCFullYear();
    const mm = String(jstDate.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(jstDate.getUTCDate()).padStart(2, '0');
    const formattedDate = `${yyyy}-${mm}-${dd}`;
    
    document.getElementById('lesson-date').value = formattedDate;
    document.getElementById('search-date').value = formattedDate;
    
    fetchLessonNotesByDate();
}

// データを保存する関数
async function saveToDB() {
    const dateValue = document.getElementById('lesson-date').value;
    const contentValue = document.getElementById('input-content').value;

    if (!contentValue) {
        alert('内容を入力してください！');
        return;
    }

    const response = await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes`, {
        method: 'POST',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        },
        body: JSON.stringify({
            lesson_date: dateValue,
            content: contentValue
        })
    });

    if (response.ok) {
        alert('クラウドDBへ保存しました！');
        document.getElementById('input-content').value = ''; // 入力欄をクリア
        
        if (dateValue === document.getElementById('search-date').value) {
            fetchLessonNotesByDate();
        }
    } else {
        alert('保存に失敗しました。');
    }
}

// 選ばれた日付のデータだけを狙い撃ちして取得する関数
async function fetchLessonNotesByDate() {
    const searchDate = document.getElementById('search-date').value;
    const title = document.getElementById('display-date-title');
    const list = document.getElementById('lesson-list');

    if (!searchDate) return;

    title.innerText = `📅 ${searchDate} の授業メモ`;
    list.innerHTML = '<li class="status-msg">読み込み中...</li>';

    const response = await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes?lesson_date=eq.${searchDate}&order=id.asc`, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`
        }
    });

    if (response.ok) {
        const data = await response.json();
        list.innerHTML = '';

        if (data.length > 0) {
            data.forEach(item => {
                const li = document.createElement('li');
                li.innerText = item.content;
                
                li.style.cursor = 'pointer';
                li.style.userSelect = 'none';

                let pressTimer;

                // --- スマホ用（タッチ）イベント ---
                li.addEventListener('touchstart', (e) => {
                    pressTimer = setTimeout(() => {
                        handleLongPress(item.id, item.content);
                    }, 800);
                });
                li.addEventListener('touchend', () => clearTimeout(pressTimer));
                li.addEventListener('touchmove', () => clearTimeout(pressTimer));

                // --- PC用（マウス）イベント ---
                li.addEventListener('mousedown', (e) => {
                    pressTimer = setTimeout(() => {
                        handleLongPress(item.id, item.content);
                    }, 800);
                });
                li.addEventListener('mouseup', () => clearTimeout(pressTimer));
                li.addEventListener('mouseleave', () => clearTimeout(pressTimer));
                
                list.appendChild(li);
            });
        } else {
            list.innerHTML = '<li class="status-msg">※この日の入力データはまだありません。</li>';
        }
    } else {
        list.innerHTML = '<li class="status-msg" style="color:red;">データの取得に失敗しました。</li>';
    }
}

// 長押しされたときの処理
function handleLongPress(id, content) {
    const shortContent = content.length > 20 ? content.substring(0, 20) + '...' : content;
    const confirmDelete = confirm(`❌ 以下の項目を削除しますか？\n\n「${shortContent}」`);
    
    if (confirmDelete) {
        deleteNote(id);
    }
}

// SupabaseのDBからデータを削除する関数
async function deleteNote(id) {
    const response = await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes?id=eq.${id}`, {
        method: 'DELETE',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`,
            'Prefer': 'return=representation'
        }
    });

    if (response.ok) {
        alert('削除しました！');
        fetchLessonNotesByDate();
    } else {
        alert('削除に失敗しました。');
    }
}