import { createQuiz, fetchLatestQuiz, fetchAllQuizzes, deleteQuiz, updateQuiz, fetchAuthors } from './quizApi.js';
import { showAlert, showConfirm, showPrompt } from './modal.js';

// ページ読み込み時に一度だけ呼ぶ想定。投稿者一覧を取得してドロップダウンに入れる
export async function initAuthorSelect() {
  const select = document.getElementById('author-select');
  if (!select) return; // HTML側にまだ用意していなければ何もしない

  const { data, error } = await fetchAuthors();
  if (error || !data) return;

  // 「指定なし」の選択肢を先頭に用意しておく
  const noneOption = document.createElement('option');
  noneOption.value = '';
  noneOption.textContent = '(投稿者を選択)';
  select.appendChild(noneOption);

  data.forEach(author => {
    const option = document.createElement('option');
    option.value = author.id;
    option.textContent = author.name;
    select.appendChild(option);
  });
}

export async function saveToDB() {
  const input = document.getElementById('input-text');
  const textValue = input.value.trim();
  if (!textValue) {
    await showAlert('文字を入力してください！');
    return;
  }

  // ドロップダウンが存在すれば、選ばれているauthor_idを取得する
  const authorSelect = document.getElementById('author-select');
  const authorId = authorSelect?.value || null;

  const { data, error } = await createQuiz(textValue, authorId);

  if (error) {
    await showAlert(`保存に失敗しました。\n理由: ${error}`);
    return;
  }

  await showAlert('クラウドDBへの保存に成功しました！');
  input.value = '';
  renderAllQuizzes(true, true); // 一覧の裏側での再取得は、ローディング表示を出さず静かに、最初から表示し直す
}

export async function readFromDB() {
  const outputArea = document.getElementById('output-area');
  outputArea.innerText = '通信中...';

  const { data, error } = await fetchLatestQuiz();

  if (error) {
    outputArea.innerText = `データの取得に失敗しました。(${error})`;
    return;
  }
  outputArea.innerText = data.length > 0 ? data[0].question : 'まだデータが1件もありません。';
}

async function handleEdit(id, currentText) {
  const newText = await showPrompt('新しい内容を入力してください', currentText);
  if (newText === null || newText.trim() === '') {
    return;
  }

  const { error } = await updateQuiz(id, newText.trim());

  if (error) {
    await showAlert(`更新に失敗しました。\n理由: ${error}`);
    return;
  }

  await showAlert('更新しました！');
  renderAllQuizzes(true, true);
}

async function handleDelete(id) {
  const isConfirmed = await showConfirm('本当に削除しますか？');
  if (!isConfirmed) return;

  const { error } = await deleteQuiz(id);

  if (error) {
    await showAlert(`削除に失敗しました。\n理由: ${error}`);
    return;
  }

  await showAlert('削除しました！');
  renderAllQuizzes(true, true);
}

const PAGE_SIZE = 20;
let currentOffset = 0; // 「今、何件目まで表示しているか」を覚えておく

export async function toggleQuizList() {
  const table = document.getElementById('data-table');
  const status = document.getElementById('list-status');

  const isVisible = table.style.display === 'table';
  if (isVisible) {
    table.style.display = 'none';
    status.innerText = '';
    return;
  }

  await renderAllQuizzes(false, true); // 開く時は必ず最初(1件目)からやり直す
}

// reset=true: 最初からやり直す(offsetを0に戻し、既存の行を消す)
// reset=false: 続きから追加する(「もっと見る」ボタン用)
export async function renderAllQuizzes(silent = false, reset = true) {
  const table = document.getElementById('data-table');
  const tbody = document.getElementById('table-body');
  const status = document.getElementById('list-status');
  const loadMoreBtn = document.getElementById('load-more-btn');

  if (reset) {
    currentOffset = 0;
    tbody.innerHTML = '';
  }

  status.innerText = '読み込み中...';

  const { data, error } = await fetchAllQuizzes(PAGE_SIZE, currentOffset, silent);

  if (error) {
    status.innerText = `データの取得に失敗しました。(${error})`;
    return;
  }

  data.forEach(item => {
    const row = document.createElement('tr');

    ['id', 'question'].forEach(key => {
      const td = document.createElement('td');
      td.textContent = item[key] ?? (key === 'id' ? '-' : '');
      row.appendChild(td);
    });

    // authorsは { name: '...' } という入れ子のオブジェクトで返ってくる
    const authorTd = document.createElement('td');
    authorTd.textContent = item.authors?.name ?? '(未設定)';
    row.appendChild(authorTd);

    const actionTd = document.createElement('td');

    const editBtn = document.createElement('button');
    editBtn.textContent = '編集';
    editBtn.addEventListener('click', () => handleEdit(item.id, item.question));
    actionTd.appendChild(editBtn);

    const deleteBtn = document.createElement('button');
    deleteBtn.textContent = '削除';
    deleteBtn.addEventListener('click', () => handleDelete(item.id));
    actionTd.appendChild(deleteBtn);

    row.appendChild(actionTd);
    tbody.appendChild(row);
  });

  currentOffset += data.length; // 次回「もっと見る」を押した時のために、位置を進めておく

  const totalShown = tbody.querySelectorAll('tr').length;
  status.innerText = totalShown === 0
    ? 'データが空っぽです。'
    : `${totalShown} 件を表示中です。`;

  // 取れた件数がPAGE_SIZEちょうどなら、まだ続きがある可能性が高い→ボタンを出す
  // PAGE_SIZE未満なら、もうこれ以上データが無いということ→ボタンを隠す
  if (loadMoreBtn) {
    loadMoreBtn.style.display = data.length === PAGE_SIZE ? 'inline-block' : 'none';
  }

  table.style.display = 'table';
}

// 「もっと見る」ボタンから呼ばれる
export async function loadMoreQuizzes() {
  await renderAllQuizzes(false, false); // 続きから追加(消さずに継ぎ足す)
}