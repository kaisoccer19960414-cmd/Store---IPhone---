import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from google import genai

app = FastAPI()

# CORS設定（PWAの画面からの直接通信を許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Vercel上の環境変数から読み込み（.envは不要になります）
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

class SummaryRequest(BaseModel):
    target_date: str

@app.post("/api/page2/summarize")
async def summarize_lessons(request: SummaryRequest):
    target_date = request.target_date.strip()
    if not target_date:
        raise HTTPException(status_code=400, detail="日付が指定されていません。")

    # 1. 指定された日付の授業メモをすべて取得
    try:
        response = supabase.table("lesson_notes").select("*").eq("lesson_date", target_date).order("id", desc=False).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabaseエラー: {str(e)}")

    if not response.data:
        raise HTTPException(status_code=404, detail=f"{target_date} の授業メモは見つかりませんでした。")

    # 2. メモを1つに結合
    all_contents = [item["content"] for item in response.data if item.get("content")]
    if not all_contents:
        raise HTTPException(status_code=400, detail="要約するコンテンツが空です。")
    
    combined_note = "\n\n".join(all_contents)

    # 3. Gemini APIで要約生成
    prompt = f"""
以下の授業メモを要約してください。
以下のルールを絶対守ること：
1. 【タバコ休憩用の3行要約】を冒頭に置くこと。
2. 専門用語は最小限にし、ワイが友人に教えるような砕けたトーンで書くこと。
3. 最後に一言だけ、ワイをクスッとさせるようなユーモアかツッコミを入れること。

【授業メモ】
{combined_note}
"""
    try:
        ai_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        summary_text = ai_response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini APIエラー: {str(e)}")

    # 4. その日の最後のレコードの summary 列に書き込み
    last_record_id = response.data[-1]["id"]
    try:
        supabase.table("lesson_notes").update({"summary": summary_text}).eq("id", last_record_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"要約の保存に失敗しました: {str(e)}")

    return {
        "status": "success",
        "summary": summary_text
    }

from fastapi.responses import HTMLResponse
import re
import uuid

class GeneratePageRequest(BaseModel):
    prompt: str

@app.post("/api/page2/generate-page")
async def generate_page(request: GeneratePageRequest):
    user_prompt = request.prompt.strip()
    if not user_prompt:
        raise HTTPException(status_code=400, detail="プロンプトが空です。")

    system_instruction = """
あなたはHTML生成エンジンです。以下のルールを厳守してください：
1. 出力は完全な1つのHTMLドキュメント（<!DOCTYPE html>から</html>まで）のみ。
2. 説明文、前置き、Markdownのコードブロック記法（```html等）は絶対に含めない。
3. CSSは<style>タグ内にインラインで含め、外部ファイルへの依存は避ける。
"""
    try:
        ai_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_instruction}\n\n【ユーザーの要望】\n{user_prompt}"
        )
        raw_html = ai_response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini APIエラー: {str(e)}")

    # コードブロック記法の除去(念のため)
    cleaned_html = re.sub(r"^```html\s*|```\s*$", "", raw_html.strip(), flags=re.MULTILINE).strip()

    page_id = str(uuid.uuid4())
    try:
        supabase.table("generated_pages").insert({
            "id": page_id,
            "prompt": user_prompt,
            "html_content": cleaned_html
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存に失敗しました: {str(e)}")

    return {"status": "success", "page_id": page_id}


@app.get("/api/page2/render/{page_id}", response_class=HTMLResponse)
async def render_page(page_id: str):
    try:
        response = supabase.table("generated_pages").select("html_content").eq("id", page_id).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="ページが見つかりません。")

    return HTMLResponse(content=response.data["html_content"])
