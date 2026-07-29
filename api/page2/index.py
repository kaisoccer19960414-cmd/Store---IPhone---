import os
import re
import json
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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


# ============================================================
# 既存: 授業メモ要約機能
# ============================================================
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


# ============================================================
# AIページ生成機能（方式B: オンデマンド生成）
# ============================================================
class GeneratePageRequest(BaseModel):
    prompt: str


class GenerateSitePageRequest(BaseModel):
    site_id: str
    slug: str
    referrer_slug: str


def clean_json_output(raw_text: str) -> str:
    """Geminiの出力からMarkdownのコードブロック記法(```json ... ```)を除去する"""
    return re.sub(r"^```json\s*|```\s*$", "", raw_text.strip(), flags=re.MULTILINE).strip()


def build_click_interceptor_script(site_id: str, current_slug: str) -> str:
    """ページ内リンククリック時に、未生成ページなら確認ダイアログを出してオンデマンド生成するスクリプト"""
    return f"""
<script>
document.body.setAttribute('data-slug', '{current_slug}');

document.addEventListener('click', async function(e) {{
    const link = e.target.closest('a[href^="/api/page2/site/{site_id}/"]');
    if (!link) return;
    e.preventDefault();

    const targetUrl = link.getAttribute('href');
    const parts = targetUrl.split('/');
    const targetSlug = parts[parts.length - 1];

    try {{
        const existsRes = await fetch(`/api/page2/site/{site_id}/${{targetSlug}}/exists`);
        const existsData = await existsRes.json();

        if (existsData.exists) {{
            window.location.href = targetUrl;
            return;
        }}

        if (!confirm('このページはまだ存在しません。AIに新しく作成させますか？')) {{
            return;
        }}

        const genRes = await fetch('/api/page2/site/generate', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
                site_id: '{site_id}',
                slug: targetSlug,
                referrer_slug: '{current_slug}'
            }})
        }});
        const genData = await genRes.json();
        if (!genRes.ok) {{
            alert('生成に失敗しました: ' + (genData.detail || '不明なエラー'));
            return;
        }}

        window.location.href = `/api/page2/render/${{genData.page_id}}`;
    }} catch (err) {{
        alert('確認処理でエラーが発生しました: ' + err.message);
    }}
}});
</script>
"""


def inject_click_interceptor(html: str, site_id: str, slug: str) -> str:
    """生成HTMLの</body>直前にクリックインターセプタスクリプトを差し込む"""
    script_tag = build_click_interceptor_script(site_id, slug)
    if "</body>" in html:
        return html.replace("</body>", f"{script_tag}</body>")
    return html + script_tag


# --- ① 初回ページ生成（index） ---
@app.post("/api/page2/generate-page")
async def generate_page(request: GeneratePageRequest):
    user_prompt = request.prompt.strip()
    if not user_prompt:
        raise HTTPException(status_code=400, detail="プロンプトが空です。")

    site_id = str(uuid.uuid4())

    system_instruction = f"""
あなたはWebサイト生成エンジンです。以下のJSON形式で出力してください。

{{
  "html": "完全な1つのHTMLドキュメント(<!DOCTYPE html>から</html>まで)。内部リンクは href=\\"/api/page2/site/{site_id}/(スラッグ名)\\" の形式で書くこと(例: href=\\"/api/page2/site/{site_id}/careers\\")。CSSは<style>タグ内にインラインで含めること。",
  "design_spec": {{
    "color_palette": "使用した配色をコードで",
    "font": "見出し・本文のフォント方針",
    "tone": "サイト全体のトーン"
  }},
  "content_summary": "このページで扱っている内容の3行程度の要約"
}}

出力はこのJSONオブジェクトのみ。説明文やMarkdownのコードブロック記法は絶対に含めないこと。
"""

    try:
        ai_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_instruction}\n\n【ユーザーの要望】\n{user_prompt}"
        )
        raw_text = ai_response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini APIエラー: {str(e)}")

    cleaned_text = clean_json_output(raw_text)

    try:
        parsed = json.loads(cleaned_text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Geminiの出力をJSONとして解析できませんでした。")

    final_html = inject_click_interceptor(parsed["html"], site_id, "index")

    page_id = str(uuid.uuid4())
    try:
        supabase.table("generated_pages").insert({
            "id": page_id,
            "site_id": site_id,
            "slug": "index",
            "prompt": user_prompt,
            "html_content": final_html,
            "design_spec": parsed["design_spec"],
            "content_summary": parsed["content_summary"],
            "parent_slug": None
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存に失敗しました: {str(e)}")

    return {"status": "success", "site_id": site_id, "page_id": page_id}


# --- ③ オンデマンド生成（index以外の子ページ） ---
@app.post("/api/page2/site/generate")
async def generate_site_page(request: GenerateSitePageRequest):
    site_id = request.site_id
    slug = request.slug.strip()
    referrer_slug = request.referrer_slug.strip()

    if not site_id or not slug:
        raise HTTPException(status_code=400, detail="site_idまたはslugが不正です。")

    # 1. 既に存在しないか念のため確認(二重生成防止)
    existing = supabase.table("generated_pages") \
        .select("id") \
        .eq("site_id", site_id) \
        .eq("slug", slug) \
        .execute()
    if existing.data:
        return {"status": "success", "page_id": existing.data[0]["id"], "already_existed": True}

    # 2. indexページからdesign_specを取得
    index_page = supabase.table("generated_pages") \
        .select("design_spec, prompt") \
        .eq("site_id", site_id) \
        .eq("slug", "index") \
        .single().execute()
    if not index_page.data:
        raise HTTPException(status_code=404, detail="サイトの基準ページ(index)が見つかりません。")
    design_spec = index_page.data["design_spec"]

    # 3. リンク元(親)ページのcontent_summaryを取得
    parent_page = supabase.table("generated_pages") \
        .select("content_summary") \
        .eq("site_id", site_id) \
        .eq("slug", referrer_slug) \
        .single().execute()
    parent_summary = parent_page.data["content_summary"] if parent_page.data else "(情報なし)"

    # 4. 生成プロンプト組み立て
    system_instruction = f"""
あなたはWebサイト生成エンジンです。以下のJSON形式で出力してください。

{{
  "html": "完全な1つのHTMLドキュメント(<!DOCTYPE html>から</html>まで)。内部リンクは href=\\"/api/page2/site/{site_id}/(スラッグ名)\\" の形式で書くこと。CSSは<style>タグ内にインラインで含めること。",
  "content_summary": "このページで扱っている内容の3行程度の要約"
}}

【サイト全体のデザイン仕様(必ず踏襲すること)】
{json.dumps(design_spec, ensure_ascii=False)}

【リンク元ページ("{referrer_slug}")の文脈(このページはここから遷移してくる想定)】
{parent_summary}

【生成するページ】
スラッグ "{slug}" のページを、上記の文脈と自然につながる内容・トーンで作成してください。

出力はこのJSONオブジェクトのみ。説明文やMarkdownのコードブロック記法は絶対に含めないこと。
"""

    try:
        ai_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=system_instruction
        )
        raw_text = ai_response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini APIエラー: {str(e)}")

    cleaned_text = clean_json_output(raw_text)
    try:
        parsed = json.loads(cleaned_text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Geminiの出力をJSONとして解析できませんでした。")

    final_html = inject_click_interceptor(parsed["html"], site_id, slug)

    page_id = str(uuid.uuid4())
    try:
        supabase.table("generated_pages").insert({
            "id": page_id,
            "site_id": site_id,
            "slug": slug,
            "prompt": None,
            "html_content": final_html,
            "design_spec": design_spec,
            "content_summary": parsed["content_summary"],
            "parent_slug": referrer_slug
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存に失敗しました: {str(e)}")

    return {"status": "success", "page_id": page_id, "already_existed": False}


# --- ページ存在確認（クリック時のガード用） ---
@app.get("/api/page2/site/{site_id}/{slug}/exists")
async def check_page_exists(site_id: str, slug: str):
    response = supabase.table("generated_pages") \
        .select("id") \
        .eq("site_id", site_id) \
        .eq("slug", slug) \
        .execute()
    return {"exists": len(response.data) > 0}


# --- ページ表示（page_id指定） ---
@app.get("/api/page2/render/{page_id}", response_class=HTMLResponse)
async def render_page(page_id: str):
    try:
        response = supabase.table("generated_pages").select("html_content").eq("id", page_id).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="ページが見つかりません。")

    return HTMLResponse(content=response.data["html_content"])


# --- 生成履歴一覧 ---
@app.get("/api/page2/list-pages")
async def list_pages():
    try:
        response = supabase.table("generated_pages") \
            .select("id, prompt, created_at") \
            .order("created_at", desc=True) \
            .limit(50) \
            .execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取得に失敗しました: {str(e)}")

    return {"status": "success", "pages": response.data}