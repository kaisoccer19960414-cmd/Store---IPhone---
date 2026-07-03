import { SUPABASE_URL, SUPABASE_KEY } from './config.js';

export async function supabaseRequest(path, options = {}) {
  try {
    const response = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
      ...options,
      headers: {
        'apikey': SUPABASE_KEY,
        'Authorization': `Bearer ${SUPABASE_KEY}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    if (!response.ok) {
      // Supabase(PostgREST)が返す詳しいエラーJSONを読み取る
      const errorBody = await response.json().catch(() => null);
      const message = errorBody?.message || `HTTP ${response.status}`;
      return { data: null, error: message };
    }

    const data = options.method === 'GET' || !options.method
      ? await response.json()
      : true;
    return { data, error: null };

  } catch (err) {
    console.error('Supabase通信エラー:', err);
    return { data: null, error: err.message };
  }
}