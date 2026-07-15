// --- 1. 設定値 ---
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

// ページを開いたときの初期処理
window.onload = async function() {
    const isLoggedIn = await checkAuth();
    if (!isLoggedIn) return; 

    const today = new Date();
    const jstOffset = 9 * 60 * 60 * 1000; 
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

    const token = await getValidToken();

    const response = await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes`, {
        method: 'POST',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${token}`,
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
        document.getElementById('input-content').value = ''; 
        
        if (dateValue === document.getElementById('search-date').value) {
            fetchLessonNotesByDate();
        }
    } else {
        alert('保存に失敗しました。');
    }
}

// 選ばれた日付のデータだけを取得する関数
async function fetchLessonNotesByDate() {
    const searchDate = document.getElementById('search-date').value;
    const title = document.getElementById('display-date-title');
    const list = document.getElementById('lesson-list');
    const summaryBox = document.getElementById('summary-content'); 

    if (!searchDate) return;

    title.innerText = `📅 ${searchDate} の授業メモ`;
    list.innerHTML = '<li class="status-msg">読み込み中...</li>';
    summaryBox.innerHTML = '<p class="status-msg">読み込み中...</p>'; 

    const token = await getValidToken();

    const response = await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes?lesson_date=eq.${searchDate}&order=id.asc`, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${token}`
        }
    });

    if (response.ok) {
        const data = await response.json();
        list.innerHTML = '';
        summaryBox.innerHTML = ''; 

        if (data.length > 0) {
            data.forEach(item => {
                const li = document.createElement('li');
                li.innerText = item.content;
                li.style.cursor = 'pointer';
                li.style.userSelect = 'none';

                let pressTimer;

                li.addEventListener('touchstart', (e) => {
                    pressTimer = setTimeout(() => {
                        handleLongPress(item.id, item.content);
                    }, 800);
                });
                li.addEventListener('touchend', () => clearTimeout(pressTimer));
                li.addEventListener('touchmove', () => clearTimeout(pressTimer));

                li.addEventListener('mousedown', (e) => {
                    pressTimer = setTimeout(() => {
                        handleLongPress(item.id, item.content);
                    }, 800);
                });
                li.addEventListener('mouseup', () => clearTimeout(pressTimer));
                li.addEventListener('mouseleave', () => clearTimeout(pressTimer));
                
                list.appendChild(li);
            });

            let foundSummary = null;
            for (let i = data.length - 1; i >= 0; i--) {
                if (data[i].summary && data[i].summary !== "REQUESTED") {
                    foundSummary = data[i].summary;
                    break;
                }
            }
            
            const hasRequested = data.some(item => item.summary === "REQUESTED");

            if (foundSummary) {
                summaryBox.innerText = foundSummary; 
            } else if (hasRequested) {
                summaryBox.innerHTML = '<p class="status-msg" style="color: #cca300;">⏳ 現在、PCのPythonが要約を作成中（REQUESTED）です...終わったら画面をリロードしてください。</p>';
            } else {
                summaryBox.innerHTML = '<p class="status-msg" style="color: #cca300;">⚠️ 要約がありません。「要約を生成する」ボタンを押して、PCでスクリプトを実行してください。</p>';
            }
        } else {
            list.innerHTML = '<li class="status-msg">この日のメモはまだ登録されていません。</li>';
            summaryBox.innerHTML = '<p class="status-msg">授業メモがないため、要約はありません。</p>';
        }
    } else {
        list.innerHTML = '<li class="status-msg" style="color:red;">データの取得に失敗しました。</li>';
        summaryBox.innerHTML = '<p class="status-msg" style="color:red;">要約の取得に失敗しました。</p>';
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
    const token = await getValidToken();

    const response = await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes?id=eq.${id}`, {
        method: 'DELETE',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${token}`,
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

// 要約リクエストをVercelのPython APIに直接送信する関数
async function generateSummaryNow() {
    const searchDate = document.getElementById('search-date').value;
    const summaryBox = document.getElementById('summary-content');
    const listItems = document.querySelectorAll('#lesson-list li');

    // 要約するメモがあるかチェック
    if (!searchDate || listItems.length === 0 || listItems[0].classList.contains('status-msg')) {
        alert('要約する授業メモがありません！');
        return;
    }

    summaryBox.innerHTML = '<p class="status-msg" style="color: #0066cc;">⏳ Geminiが要約を生成中...</p>';

    try {
        // 💡 Vercel上の自分自身のPython API（/api/summarize）を呼び出す
        // 相対パスで指定することで、本番環境でもそのまま動きます
        const response =await fetch('/api/page2/summarize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ target_date: searchDate })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '要約の生成に失敗しました。');
        }

        // 成功したら、画面の要約エリアを書き換える
        summaryBox.innerText = data.summary;
        alert('🎉 Geminiの要約が完了し、Supabaseへ保存されました！');

    } catch (error) {
        console.error(error);
        summaryBox.innerHTML = `<p class="status-msg" style="color:red;">❌ エラー: ${error.message}</p>`;
        alert('エラーが発生しました：' + error.message);
    }
}

// 補助関数: 生成した要約をSupabaseに格納する
async function saveSummaryToSupabase(dateStr, summaryText) {
    const token = await getValidToken();

    const getRes = await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes?lesson_date=eq.${dateStr}&order=id.desc&limit=1`, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${token}`
        }
    });

    if (getRes.ok) {
        const data = await getRes.json();
        if (data.length > 0) {
            const targetId = data[0].id;
            await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes?id=eq.${targetId}`, {
                method: 'PATCH', 
                headers: {
                    'apikey': SUPABASE_KEY,
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ summary: summaryText })
            });
            console.log("💾 Supabaseへ要約の同期が完了しました！");
        }
    }
}