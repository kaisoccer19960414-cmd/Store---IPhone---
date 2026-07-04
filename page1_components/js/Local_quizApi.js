/*Local版　あとで消すかも... {localApiRequest}になっている。
使うときは、名前をquizApi.jsにする。

quizApi.js          ← 今実際に「使われている」本番のファイル
Local_quizApi.js     ← Flask版の中身を、コメントアウトして"待機"させてあるファイル



import { localApiRequest } from './localApiClient.js';

export function createQuiz(question) {
  return localApiRequest('quiz_data', {
    method: 'POST',
    body: JSON.stringify({ question })
  });
}

export function fetchLatestQuiz() {
  return localApiRequest('quiz_data?limit=1');
}

export function fetchAllQuizzes(limit = 20) {
  return localApiRequest(`quiz_data?limit=${limit}`);
}

export function deleteQuiz(id) {
  return localApiRequest(`quiz_data/${id}`, { method: 'DELETE' });
}

export function updateQuiz(id, question) {
  return localApiRequest(`quiz_data/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ question })
  });
}
  */