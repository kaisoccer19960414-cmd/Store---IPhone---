// 設定値
const SUPABASE_URL = 'https://tekrwutayfleorpfbuhc.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRla3J3dXRheWZsZW9ycGZidWhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NzA1ODIsImV4cCI6MjA5ODE0NjU4Mn0.eG8ENxN1BxZn_yFdxrsytz2Qa9LCT95WgdRqLkEDs80';

// ページを開いたときの初期処理
window.onload = function() {
    // 保存用と検索用のカレンダー両方に「今日の日付」を初期値としてセット
    const today = new Date();
    const jstOffset = 9 * 60 * 60 * 1000; // 日本時間の時差（9時間）
    const jstDate = new Date(today.getTime() + jstOffset);
    
    // カレンダーに入力できる「YYYY-MM-DD」の形に変換
    const yyyy = jstDate.getUTCFullYear();
    const mm = String(jstDate.getUTCMonth() + 1).padStart(2, '0'); // 月は0から始まるので+1
    const dd = String(jstDate.getUTCDate()).padStart(2, '0');
    const formattedDate = `${yyyy}-${mm}-${dd}`;
    
    // 文字列になった日付をセット
    document.getElementById('lesson-date').value = formattedDate;
    document.getElementById('search-date').value = formattedDate;
    
    // 最初から今日の日付のデータを読み込む
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
        }
    });

    if (response.ok) {
        alert('クラウドDBへ保存しました！');
        document.getElementById('input-content').value = ''; // 入力欄をクリア
        
        // もし「保存した日付」と「今表示している日付」が同じなら、画面を自動更新
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

    // 画面のタイトルを選択された日付に書き換える
    title.innerText = `📅 ${searchDate} の授業メモ`;
    list.innerHTML = '<li class="status-msg">読み込み中...</li>';

    // SupabaseのAPIで条件指定して取得
    const response = await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes?lesson_date=eq.${searchDate}&order=id.asc`, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`
        }
    });

    if (response.ok) {
        const data = await response.json();
        list.innerHTML = ''; // クリア

        if (data.length > 0) {
            data.forEach(item => {
                const li = document.createElement('li');
                li.innerText = item.content;
                
                // 長押しできることをなんとなく伝えるスタイル調整
                li.style.cursor = 'pointer';
                li.style.userSelect = 'none'; // 長押し時に青い選択線を防ぐ

                // 長押し判定用の変数
                let pressTimer;

                // --- スマホ用（タッチ）イベント ---
                li.addEventListener('touchstart', (e) => {
                    pressTimer = setTimeout(() => {
                        handleLongPress(item.id, item.content);
                    }, 800); // 0.8秒長押しで発動
                });
                li.addEventListener('touchend', () => clearTimeout(pressTimer));
                li.addEventListener('touchmove', () => clearTimeout(pressTimer)); // スクロール時はキャンセル

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
        fetchLessonNotesByDate(); // 画面を自動更新
    } else {
        alert('削除に失敗しました。');
    }
}