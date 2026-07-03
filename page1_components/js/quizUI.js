import { createQuiz, fetchLatestQuiz, fetchAllQuizzes } from './quizApi.js';

export async function saveToDB() {
  const input = document.getElementById('input-text');
  const textValue = input.value.trim();
  if (!textValue) {
    alert('文字を入力してください！');
    return;
  }

  const result = await createQuiz(textValue);
  if (result) {
    alert('クラウドDBへの保存に成功しました！');
    input.value = '';
    renderAllQuizzes();
  } else {
    alert('保存に失敗しました。');
  }
}

export async function readFromDB() {
  const outputArea = document.getElementById('output-area');
  outputArea.innerText = '通信中...';

  const data = await fetchLatestQuiz();
  if (data === null) {
    outputArea.innerText = 'データの取得に失敗しました。';
  } else if (data.length > 0) {
    outputArea.innerText = data[0].question;
  } else {
    outputArea.innerText = 'まだデータが1件もありません。';
  }
}

export async function renderAllQuizzes() {
  const table = document.getElementById('data-table');
  const tbody = document.getElementById('table-body');
  const status = document.getElementById('list-status');

  status.innerText = '読み込み中...';
  table.style.display = 'none';
  tbody.innerHTML = '';

  const data = await fetchAllQuizzes();
  if (data === null) {
    status.innerText = 'データの取得に失敗しました。';
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
    tbody.appendChild(row);
  });
  table.style.display = 'table';
}