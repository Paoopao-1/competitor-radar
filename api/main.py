import os
import io
import csv
import json
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "competitors.json"
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(title="竞品侦察雷达")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

SHEETS_WEBAPP_URL = os.environ.get("SHEETS_WEBAPP_URL", "")
SHEETS_CSV_URL = os.environ.get("SHEETS_CSV_URL", "")


# ---------- 数据读取 ----------

def load_competitors() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取竞品数据失败: {e}")
        return {}


def generate_mock(name: str) -> dict:
    """当竞品不在内置数据库里时，生成一份合理的模拟报告。"""
    return {
        "赛道": "AI 视频生成",
        "官网": "",
        "关键词": [
            {"词": f"{name} 替代品", "趋势": "涨", "竞争度": "低", "建议": "可以抢，适合做对比页"},
            {"词": "AI 视频生成工具哪个好用", "趋势": "涨", "竞争度": "中", "建议": "值得抢，写一篇横评"},
            {"词": "免费 AI 视频工具", "趋势": "平", "竞争度": "高", "建议": "竞争激烈，建议用长尾词切入"},
        ],
        "广告": {
            "卖点": ["免费试用", "一键生成", "无需剪辑"],
            "渠道": ["抖音", "B 站", "Google Ads"],
            "切入建议": f"对比 {name}，强调你的差异化卖点，例如商用版权清晰、中文提示词更准。",
        },
        "定价变化": {
            "内容": "未发现明显变化",
            "时间": "2026-Q2",
            "判断": "暂不跟进",
            "建议": "继续观察",
        },
        "落地页变化": {
            "内容": "首屏未发现明显变化",
            "时间": "2026-Q2",
            "判断": "暂不跟进",
            "建议": "继续观察",
        },
        "产品发布": {
            "内容": "未发现新版本发布",
            "时间": "2026-Q2",
            "判断": "暂不跟进",
            "建议": "继续观察",
        },
        "内容渠道": {
            "内容": "未发现明显渠道变化",
            "时间": "2026-Q2",
            "判断": "暂不跟进",
            "建议": "继续观察",
        },
        "行动建议": [
            f"写一篇「{name} vs 你的产品」对比页",
            f"在抖音投一条「{name} 替代品」短视频",
            "把官网首屏改成「商用版权清晰」",
        ],
    }


def get_competitor(name: str):
    """返回 (竞品数据, 是否为模拟生成)"""
    data = load_competitors()
    if name in data:
        return data[name], False
    return generate_mock(name), True


# ---------- 页面路由 ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    data = load_competitors()
    examples = list(data.keys())
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"examples": examples},
    )


@app.get("/result", response_class=HTMLResponse)
async def result(request: Request, competitor: str = ""):
    competitor = competitor.strip()
    if not competitor:
        return RedirectResponse("/")
    info, is_mock = get_competitor(competitor)
    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "competitor": competitor,
            "info": info,
            "is_mock": is_mock,
        },
    )



@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="about.html",
        context={},
    )


@app.get("/thanks", response_class=HTMLResponse)
async def thanks(request: Request, type: str = "订阅", competitor: str = ""):
    return templates.TemplateResponse(
        request=request,
        name="thanks.html",
        context={"type": type, "competitor": competitor},
    )

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    rows = []
    error = ""
    if SHEETS_CSV_URL:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                r = await client.get(SHEETS_CSV_URL)
                r.raise_for_status()
                content = r.text
                reader = csv.reader(io.StringIO(content))
                for row in reader:
                    rows.append(row)
        except Exception as e:
            error = f"读取 Google Sheet 失败：{e}"
    else:
        error = "尚未配置 SHEETS_CSV_URL，暂无数据。请在环境变量中填入 Google Sheet 发布后的 CSV 链接。"

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"rows": rows, "error": error},
    )

# ---------- 订阅 / 注册接口 ----------

@app.post("/api/subscribe")
async def subscribe(
    email: str = Form(...),
    type: str = Form("订阅"),
    competitor: str = Form(""),
    source: str = Form("结果页"),
):
    email = email.strip()
    if not email or "@" not in email or "." not in email:
        return JSONResponse({"ok": False, "error": "邮箱格式不正确"}, status_code=400)

    payload = {
        "email": email,
        "type": type,
        "competitor": competitor,
        "source": source,
    }

    if SHEETS_WEBAPP_URL:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(SHEETS_WEBAPP_URL, json=payload)
        except Exception as e:
            print(f"写入 Google Sheet 失败: {e}")
            return JSONResponse({"ok": True, "mock": True})

    return JSONResponse({"ok": True})


# ---------- 健康检查 ----------

@app.get("/api/health")
async def health():
    return {"ok": True}