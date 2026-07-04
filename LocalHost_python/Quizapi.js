import { localApiRequest } from './localApiClient.js';

// Flaskの/quiz_dataには question と id しか存在しないため、
// question のみを送信する
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

// 以下2つはFlask側にまだPUT/DELETEのルートが無いので、
// 今の時点では呼んでもエラーになります(次のステップで実装します)
export function deleteQuiz(id) {
  return localApiRequest(`quiz_data/${id}`, { method: 'DELETE' });
}

export function updateQuiz(id, question) {
  return localApiRequest(`quiz_data/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ question })
  });
}