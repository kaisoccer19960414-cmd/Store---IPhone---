import { createQuiz, fetchLatestQuiz, fetchAllQuizzes } from './quizApi.js';

export async function saveToDB() {
  const input = document.getElementById('input-text');
  const textValue = input.value.trim();
  if (!textValue) {
    alert('文字を入力してください！');
    return;
  }

  const { data, error } = await createQuiz(textValue);

  if (error) {
    alert(`保存に失敗しました。\n理由: ${error}`);
    return;
  }

  alert('クラウドDBへの保存に成功しました！');
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
    tbody.appendChild(row);
  });
  table.style.display = 'table';
}