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
  return request('quiz_data?order=id.desc&limit=1');
}

export function fetchAllQuizzes(limit = 20) {
  return request(`quiz_data?order=id.desc&limit=${limit}`);
}

export function deleteQuiz(id) {
  return request(`quiz_data?id=eq.${id}`, { method: 'DELETE' });
}

export function updateQuiz(id, question) {
  return request(`quiz_data?id=eq.${id}`, {
    method: 'PATCH',
    headers: { 'Prefer': 'return=representation' },
    body: JSON.stringify({ question })
  });
}