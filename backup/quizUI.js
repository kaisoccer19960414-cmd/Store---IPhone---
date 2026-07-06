import { createQuiz, fetchLatestQuiz, fetchAllQuizzes, deleteQuiz, updateQuiz } from './quizApi.js';
import { showAlert, showConfirm, showPrompt } from './modal.js';

export async function saveToDB() {
  const input = document.getElementById('input-text');
  const textValue = input.value.trim();
  if (!textValue) {
    await showAlert('文字を入力してください！');
    return;
  }

  const { data, error } = await createQuiz(textValue);

  if (error) {
    await showAlert(`保存に失敗しました。\n理由: ${error}`);
    return;
  }

  await showAlert('クラウドDBへの保存に成功しました！');
  input.value = '';
  renderAllQuizzes();
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
  renderAllQuizzes();
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
  renderAllQuizzes();
}

export async function toggleQuizList() {
  const table = document.getElementById('data-table');
  const status = document.getElementById('list-status');

  const isVisible = table.style.display === 'table';
  if (isVisible) {
    table.style.display = 'none';
    status.innerText = '';
    return;
  }

  await renderAllQuizzes();
}

export async function renderAllQuizzes() {
  const table = document.getElementById('data-table');
  const tbody = document.getElementById('table-body');
  const status = document.getElementById('list-status');

  status.innerText = '読み込み中...';
  table.style.display = 'none';
  tbody.innerHTML = '';

  const { data, error } = await fetchAllQuizzes();

  if (error) {
    status.innerText = `データの取得に失敗しました。(${error})`;
    return;
  }

  status.innerText = data.length === 0
    ? 'データが空っぽです。'
    : `合計 ${data.length} 件のデータを表示しています。`;

  data.forEach(item => {
    const row = document.createElement('tr');

    ['id', 'question'].forEach(key => {
      const td = document.createElement('td');
      td.textContent = item[key] ?? (key === 'id' ? '-' : '');
      row.appendChild(td);
    });

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

  table.style.display = 'table';
}