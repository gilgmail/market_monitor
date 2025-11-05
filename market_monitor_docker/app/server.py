\
# -*- coding: utf-8 -*-
import os, json, time, asyncio, datetime
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
import httpx
import feedparser
import yfinance as yf
from pytz import timezone
from urllib.parse import quote_plus

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
TEMPLATE_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

DATA_DIR.mkdir(exist_ok=True, parents=True)

UPDATE_INTERVAL_MIN = int(os.getenv("UPDATE_INTERVAL_MIN", "10"))
TICKERS = [t.strip() for t in os.getenv("TICKERS", "NVDA,SMCI,QQQ").split(",") if t.strip()]
NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "12"))
TZ = os.getenv("TZ", "Asia/Taipei")
UA = "Mozilla/5.0 (compatible; MarketMonitorBot/1.0)"
JSON_PATH = DATA_DIR / "dashboard.json"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(['html', 'xml'])
)

app = FastAPI(title="Market Monitor")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def now_ts():
    return int(time.time())

def now_iso_tz(tz=TZ):
    tzobj = timezone(tz)
    return datetime.datetime.now(tzobj).strftime("%Y-%m-%d %H:%M:%S %Z")

def fetch_price_summary(ticker: str) -> Dict[str, Any]:
    try:
        tk = yf.Ticker(ticker)
        info = tk.fast_info
        last = float(info['last_price']) if info and 'last_price' in info else None
        currency = info.get('currency', 'USD') if info else 'USD'
        return {
            "ticker": ticker,
            "price": last,
            "currency": currency,
            "exchange": info.get('exchange', None) if info else None,
        }
    except Exception as e:
        return {"ticker": ticker, "error": f"price_fetch_failed: {e}"}

async def fetch_rss(url: str) -> feedparser.FeedParserDict:
    headers = {"User-Agent": UA}
    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return feedparser.parse(r.content)

def google_news_rss_query(query: str, hl="zh-TW", gl="TW", ceid="TW:zh-Hant") -> str:
    q = quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"

async def collect_headlines_for(ticker: str) -> List[Dict[str, Any]]:
    queries = {
        "NVDA": ["NVIDIA NVDA", "NVIDIA earnings", "NVIDIA data center AI"],
        "SMCI": ["Super Micro Computer SMCI", "SMCI earnings", "SMCI server AI"],
        "QQQ":  ["Invesco QQQ Nasdaq-100", "QQQ ETF flows", "Nasdaq-100 AI megacap"],
    }
    seen = set()
    items: List[Dict[str, Any]] = []
    for q in queries.get(ticker, [ticker]):
        url = google_news_rss_query(q)
        try:
            feed = await fetch_rss(url)
        except Exception:
            continue
        for e in feed.entries:
            title = e.get("title", "").strip()
            link = e.get("link", "").strip()
            published = e.get("published", "") or e.get("updated", "")
            if not title or not link:
                continue
            key = (title, link)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "title": title,
                "link": link,
                "published": published,
                "source": e.get("source", {}).get("title") if isinstance(e.get("source", {}), dict) else None
            })
    return items[:NEWS_PER_TICKER]

async def build_json():
    data = {
        "generated_at_unix": now_ts(),
        "generated_at_local": now_iso_tz(),
        "tickers": {},
        "meta": {"interval_min": UPDATE_INTERVAL_MIN, "tz": TZ}
    }
    for t in TICKERS:
        data["tickers"][t] = {"price": fetch_price_summary(t), "news": await collect_headlines_for(t)}
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data

async def refresher_loop():
    if not JSON_PATH.exists():
        await build_json()
    while True:
        try:
            await build_json()
        except Exception as e:
            err = {"generated_at_unix": now_ts(),"generated_at_local": now_iso_tz(),"error": str(e)}
            JSON_PATH.write_text(json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8")
        await asyncio.sleep(UPDATE_INTERVAL_MIN * 60)

@app.on_event("startup")
async def on_start():
    asyncio.create_task(refresher_loop())

@app.get("/", response_class=HTMLResponse)
def index():
    tpl = env.get_template("dashboard.html")
    return tpl.render()

@app.get("/data/dashboard.json")
def data_json():
    if JSON_PATH.exists():
        return JSONResponse(content=json.loads(JSON_PATH.read_text(encoding="utf-8")))
    return JSONResponse(content={"status":"initializing"}, status_code=202)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8088, workers=1)
