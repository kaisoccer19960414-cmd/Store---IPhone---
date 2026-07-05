import { USE_LOCAL_API } from './config.js';
import { localApiRequest } from './localApiClient.js';
import { supabaseRequest } from './supabaseClient.js';

const request = USE_LOCAL_API ? localApiRequest : supabaseRequest;

export function createQuiz(question) {
  return request('quiz_data', {
    method: 'POST',
    headers: { 'Prefer': 'return=representation' },
    body: JSON.stringify({ question })
  });
}

export function fetchLatestQuiz() {
  const path = USE_LOCAL_API
    ? 'quiz_data?limit=1'
    : 'quiz_data?order=id.desc&limit=1';
  return request(path);
}

export function fetchAllQuizzes(limit = 20) {
  const path = USE_LOCAL_API
    ? `quiz_data?limit=${limit}`
    : `quiz_data?order=id.desc&limit=${limit}`;
  return request(path);
}

export function deleteQuiz(id) {
  const path = USE_LOCAL_API
    ? `quiz_data/${id}`        // Flask版: URLのパスにIDを埋め込む
    : `quiz_data?id=eq.${id}`; // Supabase版: クエリパラメータでIDを指定
  return request(path, { method: 'DELETE' });
}

export function updateQuiz(id, question) {
  const path = USE_LOCAL_API
    ? `quiz_data/${id}`
    : `quiz_data?id=eq.${id}`;
  return request(path, {
    method: 'PATCH',
    headers: { 'Prefer': 'return=representation' },
    body: JSON.stringify({ question })
  });
}