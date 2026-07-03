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
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return options.method === 'GET' || !options.method
      ? await response.json()
      : true;
  } catch (err) {
    console.error('Supabase通信エラー:', err);
    return null;
  }
}