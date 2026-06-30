import os
from supabase import create_client, Client
from google import genai
from google.genai import types

# 接続設定
SUPABASE_URL = "https://tekrwutayfleorpfbuhc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRla3J3dXRheWZsZW9ycGZidWhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NzA1ODIsImV4cCI6MjA5ODE0NjU4Mn0.eG8ENxN1BxZn_yFdxrsytz2Qa9LCT95WgdRqLkEDs80"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key="YOUR_GEMINI_API_KEY") # ⚠️実際のキーを入れてね

def main():
    # 💡 ユーザーに入力させる（例: 2026-06-29）
    target_date = input("📅 要約したい授業の日付を入力してください (例: 2026-06-29): ").strip()
    if not target_date:
        print("❌ 日付が入力されませんでした。")
        return

    print(f"🔄 Supabaseから {target_date} の授業メモをすべて取得中...")
    
    # その日のメモをすべて取得
    response = supabase.table("lesson_notes").select("*").eq("lesson_date", target_date).order("id", desc=False).execute()
    
    if not response.data:
        print(f"❌ {target_date} の授業メモは見つかりませんでした。")
        return
    
    # すべてのメモの内容を1つの文章にガッチャンコする
    all_contents = []
    for item in response.data:
        all_contents.append(item["content"])
    
    combined_note = "\n\n".join(all_contents)
    
    print(f"📝 結合された授業メモ（全 {len(response.data)} 件）をGeminiに送信します...")

    # AIへの要約プロンプト
    prompt = f"""
以下のIT授業のメモを論理的に整理し、復習しやすいように要約してください。
重要なキーワードやコードの解説（Javaとの違いなどがあればそれも）を分かりやすく箇条書きでまとめてください。

【授業メモ】
{combined_note}
"""

    print("🤖 ジェミタソが要約を生成中...")
    ai_response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    
    summary_text = ai_response.text
    print("\n✨ 生成された要約:\n", summary_text)
    
    # その日の「最後のレコード」の summary 列に書き込む
    last_record_id = response.data[-1]["id"]
    print(f"💾 SupabaseのレコードID: {last_record_id} へ要約を保存中...")
    
    try:
        supabase.table("lesson_notes").update({"summary": summary_text}).eq("id", last_record_id).execute()
        print("🎉 要約の保存が完全に完了しました！アプリ画面をリロードしてください。")
    except Exception as e:
        print(f"❌ 保存エラー: {e}")

if __name__ == "__main__":
    main()