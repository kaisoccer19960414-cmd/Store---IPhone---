import { localApiRequest } from './localApiClient.js';

export function createQuiz(question, authorId = null) {
  const body = { question };
  if (authorId) body.author_id = authorId;

  return localApiRequest('quiz_data', {
    method: 'POST',
    body: JSON.stringify(body)
  });
}

export function fetchLatestQuiz() {
  return localApiRequest('quiz_data?limit=1');
}

export function fetchAllQuizzes(limit = 20, offset = 0, silent = false) {
  return localApiRequest(`quiz_data?limit=${limit}&offset=${offset}`, { silent });
}

export function fetchAuthors() {
  return localApiRequest('authors');
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