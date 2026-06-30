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
    const summaryBox = document.getElementById('summary-content'); // 💡 右側の要約エリアを取得

    if (!searchDate) return;

    title.innerText = `📅 ${searchDate} の授業メモ`;
    list.innerHTML = '<li class="status-msg">読み込み中...</li>';
    summaryBox.innerHTML = '<p class="status-msg">読み込み中...</p>'; // 💡 要約側も読み込み中に

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
        summaryBox.innerHTML = ''; // 要約エリアをクリア

        if (data.length > 0) {
            // --- 1. 左側：授業メモの表示処理 ---
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

            // --- 2. 右側：Gemini 要約の表示処理 💡 ---
            // その日のデータの「最後のレコード」に入っている要約、または最初に見つかった要約を代表して表示します
            const latestSummaryItem = data.reverse().find(item => item.summary);
            
            if (latestSummaryItem && latestSummaryItem.summary) {
                summaryBox.innerText = latestSummaryItem.summary; // 💡 要約テキストをガシャコン！
            } else {
                summaryBox.innerHTML = '<p class="status-msg" style="color: #cca300;">⚠️ この日の授業メモに対する要約スクリプトがまだ実行されていないか、生成中のようです。</p>';
            }
            
            // data.reverse() で配列が反転したのを元に戻しておく（念のため）
            data.reverse();

        } else {
            list.innerHTML = '<li class="status-msg">※この日の入力データはまだありません。</li>';
            summaryBox.innerHTML = '<p class="status-msg">授業メモが読み込まれると、ここに要約が表示されます。</p>';
        }
    } else {
        list.innerHTML = '<li class="status-msg" style="color:red;">データの取得に失敗しました。</li>';
        summaryBox.innerHTML = '<p class="status-msg" style="color:red;">要約データの取得に失敗しました。</p>';
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

//-----------------6/30--------------
// 「要約を生成する」ボタンが押された時の処理
// 💡 フロントエンドから直接Gemini APIを安全かつ単発で叩く関数
async function generateSummaryNow() {
    const searchDate = document.getElementById('search-date').value;
    const summaryBox = document.getElementById('summary-content');
    const listItems = document.querySelectorAll('#lesson-list li');

    if (!searchDate || listItems.length === 0 || listItems[0].classList.contains('status-msg')) {
        alert('要約する授業メモがありません！');
        return;
    }

    // 1. 画面上の授業メモのテキストをすべて合体させる
    let combinedNote = "";
    listItems.forEach(li => {
        combinedNote += li.innerText + "\n\n";
    });

    summaryBox.innerHTML = '<p class="status-msg" style="color: #0066cc;">🤖 ジェミタソがその場で要約を生成中...</p>';

    // ⚠️ 注意: フロントエンドにキーを直接置くため、GitHubなどのパブリック公開時は注意してください
    const GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"; // 👈 ここにお持ちのGemini APIキーをセットしてください
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_API_KEY}`;

    const prompt = `
以下のIT授業のメモを論理的に整理し、復習しやすいように要約してください。
重要なキーワードやコードの解説（Javaとの違いなどがあればそれも）を分かりやすく箇条書きでまとめてください。

【授業メモ】
${combinedNote}
`;

    try {
        // 2. ボタンを押したこの瞬間だけ、直接GeminiにFetchを飛ばす
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }]
            })
        });

        if (!response.ok) throw new Error('Gemini APIとの通信に失敗しました。');

        const result = await response.json();
        const summaryText = result.candidates[0].content.parts[0].text;

        // 3. 画面のグレーの枠に即時反映！
        summaryBox.innerText = summaryText;

        // 4. 次回以降も使い回せるよう、Supabaseのその日のデータに保存（UPDATE）をかける
        // 本日の日付のメモのうち、1件（最新のID）を狙ってsummaryを上書きします
        await saveSummaryToSupabase(searchDate, summaryText);

    } catch (error) {
        console.error(error);
        summaryBox.innerHTML = `<p class="status-msg" style="color:red;">❌ エラーが発生しました: ${error.message}</p>`;
    }
}

// 補助関数: 生成した要約をSupabaseに格納する
async function saveSummaryToSupabase(dateStr, summaryText) {
    // まずその日のデータから最新のIDを1件特定するためにGET
    const getRes = await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes?lesson_date=eq.${dateStr}&order=id.desc&limit=1`, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`
        }
    });

    if (getRes.ok) {
        const data = await getRes.json();
        if (data.length > 0) {
            const targetId = data[0].id;
            // 特定したIDのレコードにUPDATEをかける
            await fetch(`${SUPABASE_URL}/rest/v1/lesson_notes?id=eq.${targetId}`, {
                method: 'PATCH', // 部分更新
                headers: {
                    'apikey': SUPABASE_KEY,
                    'Authorization': `Bearer ${SUPABASE_KEY}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ summary: summaryText })
            });
            console.log("💾 Supabaseへ要約の同期が完了しました！");
        }
    }
}