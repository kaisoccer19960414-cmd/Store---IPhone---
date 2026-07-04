import { supabaseRequest } from './localApiClient.js';     
 //from './supabaseClient.js';　←Supabase(クラウド版)

export function createQuiz(question) {
  return supabaseRequest('quiz_data', {
    method: 'POST',
    headers: { 'Prefer': 'return=representation' },
    body: JSON.stringify({ question })
  });
}

export function fetchLatestQuiz() {
  return supabaseRequest('quiz_data?order=id.desc&limit=1');
}

export function fetchAllQuizzes(limit = 20) {
  return supabaseRequest(`quiz_data?order=id.desc&limit=${limit}`);
}

export function deleteQuiz(id) {
  return supabaseRequest(`quiz_data?id=eq.${id}`, { method: 'DELETE' });
}

export function updateQuiz(id, question) {
  return supabaseRequest(`quiz_data?id=eq.${id}`, {
    method: 'PATCH',
    headers: { 'Prefer': 'return=representation' },
    body: JSON.stringify({ question })
  });
}