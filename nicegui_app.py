# nicegui_app.py
# ============================================================
# 不登校・ひきこもり相談AIエージェント NiceGUI版
# Streamlit版からの移植版：OpenAI / Supabase / knowledge_base.json 対応
# デザイン調整版: 相談画面内見立てカード、ペカンの森ブランド表示、スマホ表示最適化、非同期応答、自然スクロール、JSON解析通知非表示
# ============================================================
#
# 必要ファイル:
#   nicegui_app.py
#   knowledge_base.json
#   static/icon-192.png
#   static/icon-512.png
#   static/manifest.json
#
# 起動:
#   pip install nicegui openai supabase python-dotenv
#   python nicegui_app.py
#
# 環境変数:
#   OPENAI_API_KEY
#   SUPABASE_URL
#   SUPABASE_KEY
#   NICEGUI_STORAGE_SECRET
#
# .env を使う場合:
#   OPENAI_API_KEY=sk-...
#   SUPABASE_URL=https://xxxx.supabase.co
#   SUPABASE_KEY=...
#   NICEGUI_STORAGE_SECRET=please-change-this-long-random-string
# ============================================================

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from nicegui import app, ui
from openai import OpenAI
from supabase import Client, create_client

# ============================================================
# 0. 基本設定
# ============================================================

load_dotenv()

ACCESS_PASS = os.getenv("ACCESS_PASS", "forest2025")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
NICEGUI_STORAGE_SECRET = os.getenv(
    "NICEGUI_STORAGE_SECRET",
    "change-this-secret-before-public-release-forest2025",
)

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY が未設定です。.env または環境変数に設定してください。")
if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL が未設定です。.env または環境変数に設定してください。")
if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY が未設定です。.env または環境変数に設定してください。")

client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

APP_TITLE = "不登校・ひきこもり相談AIエージェント"
APP_SUBTITLE = "安心して、なんでもご相談ください。"

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# --- ペカンの森：PWA/ホーム画面用アイコンを自動生成 ---
PECAN_FOREST_ICON_SVG = r'''
<svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="ペカンの森">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#F8FCF5"/>
      <stop offset="1" stop-color="#E7F3E4"/>
    </linearGradient>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#365C3E" flood-opacity="0.16"/>
    </filter>
  </defs>
  <rect x="0" y="0" width="512" height="512" rx="112" fill="url(#bg)"/>
  <circle cx="126" cy="105" r="54" fill="#FFFFFF" opacity="0.62"/>
  <circle cx="424" cy="130" r="68" fill="#FFF5DD" opacity="0.70"/>
  <g filter="url(#softShadow)">
    <path d="M256 414V222" stroke="#7A552B" stroke-width="34" stroke-linecap="round"/>
    <path d="M256 300C204 274 162 231 143 166" stroke="#8A6232" stroke-width="22" stroke-linecap="round"/>
    <path d="M256 280C316 250 360 205 388 142" stroke="#8A6232" stroke-width="22" stroke-linecap="round"/>
    <path d="M256 241C226 205 213 169 207 119" stroke="#8A6232" stroke-width="18" stroke-linecap="round"/>
    <ellipse cx="137" cy="158" rx="48" ry="61" fill="#7FB06B" transform="rotate(-35 137 158)"/>
    <ellipse cx="212" cy="103" rx="52" ry="65" fill="#5F9A55" transform="rotate(-16 212 103)"/>
    <ellipse cx="311" cy="108" rx="52" ry="65" fill="#6FA65D" transform="rotate(18 311 108)"/>
    <ellipse cx="397" cy="169" rx="48" ry="61" fill="#86B875" transform="rotate(35 397 169)"/>
    <ellipse cx="187" cy="232" rx="49" ry="57" fill="#8DBF7C" transform="rotate(-55 187 232)"/>
    <ellipse cx="331" cy="232" rx="49" ry="57" fill="#7CAF6B" transform="rotate(55 331 232)"/>
    <ellipse cx="187" cy="384" rx="28" ry="43" fill="#B47A33" transform="rotate(28 187 384)"/>
    <path d="M172 365C190 380 200 395 202 413" stroke="#7A552B" stroke-width="7" stroke-linecap="round" opacity="0.62"/>
    <ellipse cx="329" cy="384" rx="28" ry="43" fill="#B47A33" transform="rotate(-28 329 384)"/>
    <path d="M344 365C326 380 316 395 314 413" stroke="#7A552B" stroke-width="7" stroke-linecap="round" opacity="0.62"/>
    <path d="M154 441h205" stroke="#7FB06B" stroke-width="28" stroke-linecap="round" opacity="0.58"/>
  </g>
</svg>
'''

def ensure_pecan_forest_static_assets() -> None:
    """Render公開時にも、ホーム画面アイコンとmanifestを必ず用意する。"""
    STATIC_DIR.mkdir(exist_ok=True)

    svg_path = STATIC_DIR / "pecan-forest-icon.svg"
    svg_path.write_text(PECAN_FOREST_ICON_SVG, encoding="utf-8")

    # Pillowがある場合はPNGも自動生成。なければSVGのみで動作継続。
    try:
        from PIL import Image, ImageDraw

        def make_png(path: Path, size: int) -> None:
            img = Image.new("RGBA", (size, size), (248, 252, 245, 255))
            draw = ImageDraw.Draw(img)
            s = size / 512
            def sc(v: float) -> int:
                return int(round(v * s))
            def ellipse(cx, cy, rx, ry, fill):
                draw.ellipse([sc(cx-rx), sc(cy-ry), sc(cx+rx), sc(cy+ry)], fill=fill)
            def line(points, fill, width):
                draw.line([(sc(x), sc(y)) for x, y in points], fill=fill, width=sc(width), joint="curve")

            # 背景と柔らかな光
            draw.rounded_rectangle([0, 0, size, size], radius=sc(112), fill=(248,252,245,255))
            ellipse(126, 105, 54, 54, (255,255,255,150))
            ellipse(424, 130, 68, 68, (255,245,221,178))

            # 幹と枝
            line([(256,414),(256,222)], (122,85,43,255), 34)
            line([(256,300),(204,274),(162,231),(143,166)], (138,98,50,255), 22)
            line([(256,280),(316,250),(360,205),(388,142)], (138,98,50,255), 22)
            line([(256,241),(226,205),(213,169),(207,119)], (138,98,50,255), 18)

            # 葉
            for cx, cy, rx, ry, color in [
                (137,158,48,61,(127,176,107,255)), (212,103,52,65,(95,154,85,255)),
                (311,108,52,65,(111,166,93,255)), (397,169,48,61,(134,184,117,255)),
                (187,232,49,57,(141,191,124,255)), (331,232,49,57,(124,175,107,255)),
            ]:
                ellipse(cx, cy, rx, ry, color)

            # ピーカンナッツ
            ellipse(187, 384, 28, 43, (180,122,51,255))
            line([(172,365),(190,380),(202,413)], (122,85,43,165), 7)
            ellipse(329, 384, 28, 43, (180,122,51,255))
            line([(344,365),(326,380),(314,413)], (122,85,43,165), 7)
            line([(154,441),(359,441)], (127,176,107,150), 28)
            img.save(path)

        make_png(STATIC_DIR / "icon-192.png", 192)
        make_png(STATIC_DIR / "icon-512.png", 512)
    except Exception:
        pass

    manifest = {
        "name": "ペカンの森 相談AI",
        "short_name": "ペカンの森",
        "description": "不登校やひきこもりに関する悩みに寄り添い、家庭での関わり方や次の一歩を一緒に考えるAI相談アプリです。",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#F8FCF5",
        "theme_color": "#6FA77A",
        "orientation": "portrait",
        "lang": "ja",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/pecan-forest-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}
        ]
    }
    (STATIC_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

ensure_pecan_forest_static_assets()

# static フォルダをWeb公開
if STATIC_DIR.exists():
    app.add_static_files("/static", str(STATIC_DIR))

# ============================================================
# 1. PWA / head設定
# ============================================================

ui.add_head_html("""
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#a5d6a7">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="相談AI">
<link rel="apple-touch-icon" href="/static/icon-192.png">
<link rel="icon" type="image/svg+xml" href="/static/pecan-forest-icon.svg">
""", shared=True)

# ============================================================
# 2. CSS
# ============================================================

ui.add_head_html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700;800&display=swap');

:root {
  --green-900: #183d25;
  --green-800: #28553a;
  --green-700: #356946;
  --green-600: #4f8a60;
  --green-500: #6fa77a;
  --green-100: #eaf5ea;
  --green-050: #f6fbf5;
  --cream-050: #fffaf1;
  --paper: rgba(255, 255, 255, 0.88);
  --paper-solid: #ffffff;
  --line: rgba(111, 167, 122, 0.22);
  --line-strong: rgba(79, 138, 96, 0.32);
  --text: #243128;
  --muted: #6b776f;
  --shadow-sm: 0 8px 22px rgba(54, 92, 62, 0.08);
  --shadow-md: 0 18px 55px rgba(54, 92, 62, 0.13);
  --radius-lg: 28px;
  --radius-md: 20px;
}

html, body, .nicegui-content {
  margin: 0;
  min-height: 100vh;
  color: var(--text);
  font-family: 'Noto Sans JP', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  background:
    radial-gradient(circle at 15% 10%, rgba(217, 239, 214, 0.55), transparent 34%),
    radial-gradient(circle at 90% 20%, rgba(255, 245, 221, 0.8), transparent 36%),
    linear-gradient(180deg, #fbfff9 0%, #f7fbf3 44%, #fffaf1 100%);
}

body.body--dark { background: #111; }

.page-wrap { width: min(1240px, 100%); margin: 0 auto; padding: 18px; }
.mobile-shell { width: min(1180px, 100%); margin: 0 auto; }

.app-card { background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius-lg); box-shadow: var(--shadow-md); backdrop-filter: blur(18px); }
.soft-card { background: rgba(255, 255, 255, 0.72); border: 1px solid var(--line); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); }

.top-bar { position: sticky; top: 0; z-index: 50; height: 76px; backdrop-filter: blur(20px); background: rgba(255, 255, 255, 0.82); border-bottom: 1px solid var(--line); }
.brand-logo { width: 48px; height: 48px; border-radius: 18px; display: grid; place-items: center; background: linear-gradient(135deg, #f1f8ee 0%, #ffffff 100%); border: 1px solid rgba(111, 167, 122, 0.25); box-shadow: var(--shadow-sm); color: var(--green-700); }
.brand-logo svg { width: 39px; height: 39px; }
.ai-avatar svg { width: 36px; height: 36px; }
.title-main { color: var(--green-900); font-weight: 800; letter-spacing: -0.02em; }
.subtitle { color: var(--muted); font-size: 13px; line-height: 1.6; }
.phase-chip { border-radius: 999px; padding: 7px 13px; background: var(--green-100); color: var(--green-800); font-weight: 800; font-size: 12px; }

.desktop-layout { display: grid; grid-template-columns: 190px minmax(0, 1fr); gap: 18px; align-items: start; }
.side-nav { position: sticky; top: 94px; min-height: calc(100vh - 116px); padding: 18px 12px; }
.nav-item { width: 100%; height: 46px; padding: 0 13px; display: flex; align-items: center; gap: 10px; border-radius: 16px; color: #2d4233; font-weight: 700; font-size: 14px; cursor: pointer; }
.nav-item-active { background: #eef8ec; color: var(--green-800); box-shadow: inset 4px 0 0 var(--green-600); }
.nav-note { margin-top: auto; padding: 16px; border-radius: 22px; background: linear-gradient(180deg, rgba(238, 248, 236, 0.95), rgba(255, 250, 241, 0.95)); color: var(--green-800); font-size: 12px; line-height: 1.9; border: 1px solid var(--line); }
.compact-history-list { max-height: 420px; overflow-y: auto; }
.history-row { border-radius: 16px; padding: 12px; border: 1px solid transparent; }
.history-row:hover { background: rgba(234, 245, 234, 0.65); }
.hero-card { padding: 22px; }

.current-phase-card { position: relative; overflow: hidden; border-radius: 26px; padding: 26px; background: linear-gradient(135deg, #ffffff 0%, #f7fbf3 100%); border: 1px solid var(--line); box-shadow: var(--shadow-md); }
.current-phase-title { color: var(--green-900); font-weight: 900; font-size: 34px; letter-spacing: -0.03em; }
.current-phase-subtitle { color: #3b493f; font-size: 15px; line-height: 2; }
.phase-track { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; align-items: center; margin: 20px 0 8px; }
.phase-dot { height: 10px; border-radius: 999px; background: #e5eee5; border: 1px solid rgba(111, 167, 122, 0.25); }
.phase-dot-active { background: var(--green-600); border-color: var(--green-600); box-shadow: 0 0 0 6px rgba(111, 167, 122, 0.16); }
.phase-list-item { border-radius: 17px; padding: 10px 12px; background: rgba(255,255,255,0.64); border: 1px solid rgba(111, 167, 122, 0.15); }
.phase-list-item-active { border-radius: 17px; padding: 10px 12px; background: linear-gradient(90deg, rgba(234,245,234,0.95), rgba(255,255,255,0.74)); border: 1px solid rgba(79,138,96,0.28); box-shadow: var(--shadow-sm); }
.phase-number { width: 27px; height: 27px; display: grid; place-items: center; border-radius: 999px; border: 1px solid rgba(36, 49, 40, 0.35); font-weight: 800; font-size: 12px; color: var(--text); }
.phase-number-active { background: var(--green-600); color: white; border-color: var(--green-600); }
.phase-name-active { color: var(--green-900); font-weight: 900; }

.chat-area { height: auto; min-height: 260px; overflow: visible; padding: 24px 18px 14px; scroll-behavior: smooth; background: linear-gradient(180deg, rgba(255,255,255,0.36), rgba(255,255,255,0.08)); }
.chat-bubble-user { background: linear-gradient(135deg, #e1f6d6, #d4f0c5); border-radius: 20px 20px 5px 20px; padding: 14px 16px; max-width: min(76%, 620px); margin-left: auto; margin-bottom: 14px; box-shadow: var(--shadow-sm); white-space: pre-wrap; line-height: 1.9; }
.chat-bubble-ai { background: #ffffff; border: 1px solid var(--line); border-radius: 20px 20px 20px 5px; padding: 16px 18px; max-width: min(84%, 680px); margin-right: auto; margin-bottom: 14px; box-shadow: var(--shadow-sm); white-space: pre-wrap; line-height: 1.95; }
.ai-avatar { width: 46px; height: 46px; border-radius: 50%; display: grid; place-items: center; margin-right: 10px; background: linear-gradient(135deg, #f1f8ee 0%, #ffffff 100%); color: var(--green-700); border: 1px solid rgba(111,167,122,0.28); box-shadow: var(--shadow-sm); flex: 0 0 auto; overflow: hidden; }
.user-avatar { width: 30px; height: 30px; border-radius: 999px; display: grid; place-items: center; margin-left: 8px; background: linear-gradient(135deg, #7fba87, #4f8a60); color: white; flex: 0 0 auto; }
.input-bar { position: static; z-index: 40; background: rgba(255,255,255,0.92); border-top: 1px solid var(--line); padding: 12px 14px 14px; backdrop-filter: blur(14px); border-radius: 0 0 var(--radius-lg) var(--radius-lg); }
.login-card { width: min(520px, calc(100vw - 28px)); margin: 44px auto; padding: 30px; }
.section-label { color: var(--green-900); font-weight: 900; font-size: 16px; }
.history-box { max-height: 55vh; overflow-y: auto; }
.small-muted { color: var(--muted); font-size: 12px; line-height: 1.7; }
.q-btn { border-radius: 999px !important; }
.q-field--outlined .q-field__control { border-radius: 22px !important; }
.q-textarea .q-field__control { min-height: 52px !important; }
.security-note { text-align: center; color: var(--muted); font-size: 12px; padding: 8px 0 14px; }
.mobile-bottom-nav { display: none; position: sticky; bottom: 0; z-index: 60; background: rgba(255,255,255,0.94); border-top: 1px solid var(--line); backdrop-filter: blur(16px); padding: 8px 8px 10px; }

@media (max-width: 980px) { .desktop-layout { grid-template-columns: 1fr; } .side-nav { display: none; } .page-wrap { padding: 10px; } .top-bar { height: 68px; } .brand-logo { width: 40px; height: 40px; border-radius: 15px; } .brand-logo svg { width: 33px; height: 33px; } .current-phase-card { padding: 20px; } .current-phase-title { font-size: 28px; } .chat-area { height: auto; min-height: 220px; overflow: visible; padding: 16px 10px; } .chat-bubble-user, .chat-bubble-ai { max-width: 88%; font-size: 14px; } .mobile-bottom-nav { display: grid; grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 600px) { .page-wrap { padding: 8px; } .login-card { margin-top: 20px; padding: 22px; } .title-main { font-size: 15px; } .subtitle { font-size: 12px; } .current-phase-card { border-radius: 22px; } .phase-list-item, .phase-list-item-active { padding: 9px 10px; } }

/* チャット欄を独立スクロールにせず、ページ全体で自然に上下移動する */
.chat-area::-webkit-scrollbar { display: none; }
.chat-area { -ms-overflow-style: none; scrollbar-width: none; }

/* ============================================================
   スマホUI微調整：中央寄せ・文字サイズ・余白・横ズレ対策
   ============================================================ */
* { box-sizing: border-box; }
html, body, .nicegui-content {
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
  -webkit-text-size-adjust: 100%;
}
.page-wrap {
  width: 100%;
  max-width: 1240px;
  padding: 18px clamp(12px, 3vw, 24px);
}
.mobile-shell {
  width: 100%;
  max-width: 1180px;
}
.login-card {
  width: 100%;
  max-width: 500px;
  margin: min(7vh, 52px) auto 24px;
  padding: clamp(24px, 4.8vw, 34px);
}
.login-card .q-field,
.login-card .q-btn {
  font-size: 16px;
}
.chat-bubble-user,
.chat-bubble-ai {
  font-size: 15px;
}
.app-card {
  overflow: hidden;
}
.q-field__native,
.q-field__input {
  font-size: 16px !important;
}
@media (max-width: 600px) {
  .page-wrap {
    width: 100%;
    max-width: 100%;
    padding: 12px;
    margin: 0 auto;
  }
  .login-card {
    width: 100%;
    max-width: calc(100vw - 24px);
    margin: 18px auto 20px;
    padding: 24px 20px;
    transform: none;
  }
  .login-card .title-main {
    font-size: 21px !important;
    line-height: 1.45;
  }
  .login-card .subtitle {
    font-size: 14px !important;
    line-height: 1.7;
  }
  .top-bar {
    height: 66px;
  }
  .top-bar .mobile-shell {
    padding-left: 10px;
    padding-right: 10px;
  }
  .brand-logo {
    width: 42px;
    height: 42px;
  }
  .brand-logo svg {
    width: 35px;
    height: 35px;
  }
  .chat-bubble-user,
  .chat-bubble-ai {
    max-width: 90%;
    font-size: 15px;
    line-height: 1.85;
    padding: 13px 15px;
  }
  .current-phase-title {
    font-size: 25px;
  }
  .current-phase-subtitle {
    font-size: 14px;
    line-height: 1.85;
  }
  .section-label {
    font-size: 15px;
  }
  .small-muted {
    font-size: 12.5px;
  }
  .input-bar {
    padding: 10px 12px 12px;
  }
  .mobile-bottom-nav {
    padding-bottom: max(10px, env(safe-area-inset-bottom));
  }
}

/* ============================================================
   ヘッダー・相談カード最終調整：ブランド名と見立てチップ
   ============================================================ */
.app-brand-title {
  color: var(--green-900);
  font-weight: 900;
  letter-spacing: -0.025em;
  font-size: 17px;
  line-height: 1.25;
}
.app-brand-subtitle {
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.45;
}
.consult-card-head {
  gap: 12px;
}
.consult-title-block {
  min-width: 0;
}
.consult-title {
  color: var(--green-900);
  font-weight: 900;
  letter-spacing: -0.025em;
  font-size: 28px;
  line-height: 1.25;
}
.phase-status-pill {
  min-width: 142px;
  max-width: 190px;
  padding: 9px 13px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(234,245,234,0.98), rgba(255,255,255,0.90));
  border: 1px solid rgba(79,138,96,0.28);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
}
.phase-status-icon {
  width: 31px;
  height: 31px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(79,138,96,0.12);
  color: var(--green-700);
  flex: 0 0 auto;
}
.phase-status-caption {
  color: var(--muted);
  font-size: 10.5px;
  line-height: 1.1;
  font-weight: 800;
  white-space: nowrap;
}
.phase-status-value {
  color: var(--green-900);
  font-size: 13px;
  line-height: 1.2;
  font-weight: 900;
  white-space: nowrap;
}
@media (max-width: 600px) {
  .app-brand-title {
    font-size: 14.5px;
    line-height: 1.25;
  }
  .app-brand-subtitle {
    font-size: 11.5px;
  }
  .consult-card-head {
    align-items: flex-start;
  }
  .consult-title {
    font-size: 22px;
  }
  .phase-status-pill {
    min-width: 124px;
    max-width: 142px;
    padding: 8px 10px;
  }
  .phase-status-icon {
    width: 28px;
    height: 28px;
  }
  .phase-status-caption {
    font-size: 9.5px;
  }
  .phase-status-value {
    font-size: 11.5px;
  }
}


/* ============================================================
   相談画面：見立てカードを主役にしたスマホ向けレイアウト
   ============================================================ */
.consult-intro {
  padding-bottom: 10px;
}
.consult-lead {
  color: var(--muted);
  font-size: 13.5px;
  line-height: 1.65;
  margin-top: 3px;
}
.consult-action-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.consult-action-button {
  min-width: 112px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(79,138,96,0.24);
  background: rgba(255,255,255,0.82);
  box-shadow: var(--shadow-sm);
  color: var(--green-800);
  font-weight: 900;
  cursor: pointer;
}
.consult-phase-summary {
  margin: 4px 16px 4px;
  padding: 22px 24px;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(247,251,243,0.92));
  border: 1px solid rgba(111,167,122,0.20);
  box-shadow: 0 12px 34px rgba(54, 92, 62, 0.08);
}
.consult-phase-topline {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.consult-phase-caption {
  color: var(--green-900);
  font-size: 18px;
  font-weight: 900;
  letter-spacing: -0.02em;
}
.consult-phase-chip {
  border-radius: 999px;
  padding: 8px 16px;
  background: rgba(234,245,234,0.96);
  color: var(--green-900);
  font-size: 14px;
  font-weight: 900;
  white-space: nowrap;
}
.consult-phase-title {
  color: var(--green-900);
  font-weight: 950;
  letter-spacing: -0.035em;
  font-size: 34px;
  line-height: 1.22;
  margin-bottom: 12px;
}
.consult-phase-description {
  color: #4d5c51;
  font-size: 16px;
  line-height: 1.95;
  margin-bottom: 20px;
}
.consult-phase-progress {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.consult-phase-bar {
  height: 13px;
  border-radius: 999px;
  background: rgba(221,235,221,0.82);
  border: 1px solid rgba(111,167,122,0.18);
  box-shadow: inset 0 1px 2px rgba(54,92,62,0.06);
}
.consult-phase-bar-active {
  background: var(--green-600);
  border-color: var(--green-600);
  box-shadow: 0 0 0 5px rgba(111,167,122,0.12);
}
.chat-date-separator {
  color: var(--muted);
  font-size: 12.5px;
  font-weight: 700;
  text-align: center;
  width: 100%;
  margin: 2px 0 10px;
}

@media (max-width: 600px) {
  .consult-intro { padding-bottom: 6px; }
  .consult-lead {
    font-size: 13px;
    margin-top: 4px;
  }
  .consult-action-row {
    gap: 8px;
    margin-top: 10px;
  }
  .consult-action-button {
    min-width: calc(50% - 4px);
    justify-content: center;
    padding: 10px 12px;
    font-size: 13px;
  }
  .consult-phase-summary {
    margin: 2px 12px 2px;
    padding: 18px 16px 17px;
    border-radius: 22px;
  }
  .consult-phase-caption {
    font-size: 16px;
  }
  .consult-phase-chip {
    font-size: 13px;
    padding: 7px 13px;
  }
  .consult-phase-title {
    font-size: 29px;
    margin-bottom: 10px;
  }
  .consult-phase-description {
    font-size: 15px;
    line-height: 1.85;
    margin-bottom: 18px;
  }
  .consult-phase-progress {
    gap: 10px;
  }
  .consult-phase-bar {
    height: 12px;
  }
  .chat-area {
    padding-top: 12px;
  }
}

</style>
""", shared=True)


ui.add_head_html("""
<style>

/* ============================================================
   ChatGPT風 最終UI調整：上部タブ / 入力固定 / 大型Phaseカード廃止
   ============================================================ */
body, html, .nicegui-content {
  background: #f7fbf3 !important;
  overflow-x: hidden !important;
}

.page-wrap.chatgpt-page {
  width: 100% !important;
  max-width: 920px !important;
  margin: 0 auto !important;
  padding: 0 12px !important;
}

.top-bar {
  height: 64px !important;
  background: rgba(255,255,255,0.94) !important;
  border-bottom: 1px solid rgba(111,167,122,0.18) !important;
  box-shadow: 0 3px 14px rgba(54,92,62,0.04) !important;
}

.header-inner {
  width: min(980px, 100%);
  margin: 0 auto;
  height: 64px;
  padding: 0 12px;
}

.header-logo .brand-logo {
  width: 38px !important;
  height: 38px !important;
  border-radius: 14px !important;
  box-shadow: none !important;
}

.header-logo .brand-logo svg {
  width: 31px !important;
  height: 31px !important;
}

.app-title-compact {
  color: var(--green-900);
  font-weight: 900;
  letter-spacing: -0.03em;
  font-size: 18px;
  line-height: 1.1;
  white-space: nowrap;
}

.phase-mini-chip {
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(234,245,234,0.95);
  color: var(--green-800);
  font-size: 12px;
  font-weight: 900;
  border: 1px solid rgba(79,138,96,0.22);
  white-space: nowrap;
}

.top-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
}

.top-tab {
  min-height: 34px !important;
  padding: 0 11px !important;
  border-radius: 999px !important;
  font-size: 13px !important;
  font-weight: 800 !important;
}

.top-tab-active {
  background: rgba(79,138,96,0.12) !important;
  color: var(--green-900) !important;
}

.chatgpt-main {
  min-height: calc(100vh - 64px);
  padding-top: 10px;
  padding-bottom: 0;
}

.chat-shell {
  height: calc(100vh - 78px);
  display: flex;
  flex-direction: column;
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(111,167,122,0.18);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 12px 38px rgba(54,92,62,0.08);
}

.chat-head-compact {
  padding: 14px 16px 10px;
  border-bottom: 1px solid rgba(111,167,122,0.14);
  background: rgba(255,255,255,0.80);
}

.chat-title-compact {
  color: var(--green-900);
  font-weight: 900;
  font-size: 18px;
  letter-spacing: -0.02em;
}

.phase-inline {
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.5;
}

.chat-scroll-area {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 16px 12px;
  background:
    radial-gradient(circle at 18% 8%, rgba(234,245,234,0.55), transparent 30%),
    linear-gradient(180deg, rgba(255,255,255,0.15), rgba(255,255,255,0.60));
}

.chat-scroll-area .chat-area {
  height: auto !important;
  min-height: 100% !important;
  overflow: visible !important;
  padding: 0 !important;
  background: transparent !important;
}

.chat-bubble-user {
  max-width: min(78%, 620px) !important;
  font-size: 15px !important;
  line-height: 1.85 !important;
}

.chat-bubble-ai {
  max-width: min(84%, 680px) !important;
  font-size: 15px !important;
  line-height: 1.9 !important;
}

.ai-avatar {
  width: 38px !important;
  height: 38px !important;
  margin-right: 9px !important;
}

.ai-avatar svg {
  width: 31px !important;
  height: 31px !important;
}

.chat-input-fixed {
  flex: 0 0 auto;
  padding: 10px 14px 12px;
  background: rgba(255,255,255,0.96);
  border-top: 1px solid rgba(111,167,122,0.16);
}

.chat-input-fixed .q-field--outlined .q-field__control {
  border-radius: 999px !important;
  background: white !important;
}

.security-note-compact {
  text-align: center;
  color: var(--muted);
  font-size: 11.5px;
  padding-top: 6px;
}

.mobile-bottom-nav,
.side-nav,
.consult-phase-summary,
.consult-intro {
  display: none !important;
}

.current-phase-card.compact-insight {
  padding: 18px !important;
  border-radius: 22px !important;
}

.current-phase-card.compact-insight .current-phase-title {
  font-size: 22px !important;
  letter-spacing: -0.02em !important;
}

.current-phase-card.compact-insight .current-phase-subtitle {
  font-size: 14px !important;
  line-height: 1.8 !important;
}

.current-phase-card.compact-insight .phase-track {
  margin: 12px 0 0 !important;
  gap: 8px !important;
}

.current-phase-card.compact-insight .phase-dot {
  height: 7px !important;
}

@media (max-width: 700px) {
  .header-inner {
    padding: 0 8px;
  }

  .header-logo .brand-logo {
    width: 34px !important;
    height: 34px !important;
  }

  .header-logo .brand-logo svg {
    width: 28px !important;
    height: 28px !important;
  }

  .app-title-compact {
    font-size: 15px;
  }

  .phase-mini-chip {
    font-size: 11px;
    padding: 5px 8px;
    max-width: 116px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .top-tabs {
    gap: 1px;
  }

  .top-tab {
    min-height: 31px !important;
    padding: 0 7px !important;
    font-size: 12px !important;
  }

  .top-tab .q-icon {
    display: none !important;
  }

  .page-wrap.chatgpt-page {
    padding: 0 !important;
  }

  .chatgpt-main {
    padding-top: 0;
  }

  .chat-shell {
    height: calc(100vh - 64px);
    border-left: none;
    border-right: none;
    border-bottom: none;
    border-radius: 0;
    box-shadow: none;
  }

  .chat-head-compact {
    padding: 10px 12px 8px;
  }

  .chat-title-compact {
    font-size: 16px;
  }

  .chat-scroll-area {
    padding: 14px 10px 10px;
  }

  .chat-bubble-user,
  .chat-bubble-ai {
    max-width: 88% !important;
    font-size: 14.5px !important;
  }

  .ai-avatar {
    width: 33px !important;
    height: 33px !important;
    margin-right: 7px !important;
  }

  .ai-avatar svg {
    width: 27px !important;
    height: 27px !important;
  }

  .chat-input-fixed {
    padding: 8px 10px max(10px, env(safe-area-inset-bottom));
  }
}



/* ============================================================
   ヘッダー微調整：正式タイトル表示＋ロゴ中央揃え
   ============================================================ */
.header-logo {
  min-width: 0 !important;
  flex: 1 1 auto !important;
  overflow: hidden !important;
}

.header-logo .brand-logo {
  flex: 0 0 auto !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 0 !important;
  transform: translateY(-1px);
}

.header-logo .brand-logo svg {
  display: block !important;
}

.app-title-compact {
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
  max-width: 360px;
  font-size: 15px !important;
  line-height: 1.16 !important;
}

@media (max-width: 700px) {
  .top-bar { height: 70px !important; }
  .header-inner { height: 70px !important; }
  .chat-shell { height: calc(100vh - 70px) !important; }
  .app-title-compact {
    max-width: 165px;
    font-size: 12.5px !important;
    line-height: 1.16 !important;
  }
  .phase-mini-chip {
    max-width: 86px !important;
    font-size: 10.5px !important;
    padding: 5px 7px !important;
  }
}

@media (max-width: 430px) {
  .app-title-compact {
    max-width: 145px;
    font-size: 11.8px !important;
  }
  .phase-mini-chip {
    display: none !important;
  }
}

</style>
""", shared=True)



# ============================================================
# 2.5. スマホ入力欄固定：ChatGPT風に常時画面下へ表示
# ============================================================
ui.add_head_html("""
<style>
/* ============================================================
   入力欄を常に画面内に残す最終調整
   - チャット本文だけをスクロール
   - 入力欄は下部に固定
   - iPhone/Androidのアドレスバー変動に強い 100dvh 対応
   ============================================================ */

:root {
  --app-header-height: 70px;
}

.chatgpt-main {
  min-height: calc(100dvh - var(--app-header-height)) !important;
  height: calc(100dvh - var(--app-header-height)) !important;
  overflow: hidden !important;
}

.chat-shell {
  height: calc(100dvh - var(--app-header-height)) !important;
  max-height: calc(100dvh - var(--app-header-height)) !important;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
}

.chat-scroll-area {
  flex: 1 1 auto !important;
  min-height: 0 !important;
  overflow-y: auto !important;
  -webkit-overflow-scrolling: touch !important;
  overscroll-behavior: contain !important;
  padding-bottom: 16px !important;
}

.chat-input-fixed {
  position: sticky !important;
  bottom: 0 !important;
  z-index: 120 !important;
  flex: 0 0 auto !important;
  background: rgba(255, 255, 255, 0.98) !important;
  border-top: 1px solid rgba(111, 167, 122, 0.18) !important;
  box-shadow: 0 -10px 28px rgba(54, 92, 62, 0.08) !important;
  padding: 10px 14px max(12px, env(safe-area-inset-bottom)) !important;
}

.chat-input-fixed .q-field__control {
  min-height: 46px !important;
}

.chat-input-fixed textarea {
  max-height: 132px !important;
  overflow-y: auto !important;
}

.security-note-compact {
  padding-top: 5px !important;
  padding-bottom: 0 !important;
}

@media (max-width: 700px) {
  :root {
    --app-header-height: 70px;
  }

  body, html, .nicegui-content {
    height: 100dvh !important;
    overflow: hidden !important;
  }

  .page-wrap.chatgpt-page {
    height: calc(100dvh - var(--app-header-height)) !important;
    overflow: hidden !important;
  }

  .chatgpt-main {
    height: calc(100dvh - var(--app-header-height)) !important;
    min-height: calc(100dvh - var(--app-header-height)) !important;
  }

  .chat-shell {
    height: calc(100dvh - var(--app-header-height)) !important;
    max-height: calc(100dvh - var(--app-header-height)) !important;
    border-radius: 0 !important;
  }

  .chat-head-compact {
    flex: 0 0 auto !important;
  }

  .chat-scroll-area {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    overflow-y: auto !important;
    padding: 12px 10px 14px !important;
  }

  .chat-input-fixed {
    padding: 8px 10px max(10px, env(safe-area-inset-bottom)) !important;
  }
}
</style>
""", shared=True)

# ============================================================
# 3. 知識ベースJSONの読み込み
# ============================================================

def load_knowledge_base(path: str = "knowledge_base.json") -> dict:
    p = BASE_DIR / path
    if not p.exists():
        raise FileNotFoundError(
            f"知識ベースJSONが見つかりません: {p}\n"
            "nicegui_app.py と同じフォルダに knowledge_base.json を置いてください。"
        )
    text = p.read_text(encoding="utf-8")
    return json.loads(text)


try:
    knowledge_base = load_knowledge_base("knowledge_base.json")
except Exception as exc:
    knowledge_base = {}
    KNOWLEDGE_BASE_LOAD_ERROR = str(exc)
else:
    KNOWLEDGE_BASE_LOAD_ERROR = ""

SLOT_SCHEMA = knowledge_base.get("slot_schema", {}) or {}


def default_slots_from_schema(schema: dict) -> dict:
    return {k: "不明" for k in schema.keys()}


PHASE_DISPLAY = [
    ("phase_1", "Phase 1：閉塞期（閉じこもり・虚無感を感じる時期）"),
    ("phase_2", "Phase 2：揺らぎ期（関係を求めたい気持ちと不安がある時期）"),
    ("phase_3", "Phase 3：希求・模索期（関わりや意味の模索している時期）"),
    ("phase_4", "Phase 4：転回期（価値観の転換と再出発に向けた時期）"),
]
PHASE_LABELS = {k: v for k, v in PHASE_DISPLAY}

PHASE_SHORT_LABELS = {
    "phase_1": "Phase 1：閉塞期",
    "phase_2": "Phase 2：揺らぎ期",
    "phase_3": "Phase 3：希求・模索期",
    "phase_4": "Phase 4：転回期",
}

PHASE_DESCRIPTIONS = {
    "phase_1": "閉じこもりや虚無感が強く、まず安心感と負担の軽減を優先したい時期です。",
    "phase_2": "関わりたい気持ちと不安が揺れ動き、無理のない接点づくりが大切な時期です。",
    "phase_3": "関わりや意味を少しずつ探し始め、小さな選択肢を広げやすい時期です。",
    "phase_4": "価値観の転換や再出発に向けて、本人のペースを尊重しながら次の行動を整える時期です。",
}


# ============================================================
# 4. 状態管理
# ============================================================

def user_store() -> Dict[str, Any]:
    """NiceGUIのユーザー別ストレージを初期化して返す。"""
    s = app.storage.user

    if "authenticated" not in s:
        s["authenticated"] = False
    if "user" not in s:
        s["user"] = None
    if "user_email" not in s:
        s["user_email"] = ""
    if "chat_history" not in s:
        s["chat_history"] = []
    if "current_phase" not in s:
        s["current_phase"] = None
    if "slots" not in s:
        s["slots"] = default_slots_from_schema(SLOT_SCHEMA)
    if "view_date" not in s:
        s["view_date"] = date.today().isoformat()
    if "active_view" not in s:
        s["active_view"] = "consult"
    if "app_date" not in s:
        s["app_date"] = date.today().isoformat()

    today_str = date.today().isoformat()
    if s["app_date"] != today_str:
        s["app_date"] = today_str
        s["chat_history"] = []
        s["current_phase"] = None
        s["slots"] = default_slots_from_schema(SLOT_SCHEMA)
        s["view_date"] = today_str
        s["active_view"] = "consult"

    return s


def get_current_user_id() -> Optional[str]:
    s = user_store()
    u = s.get("user")
    if not u:
        return None
    if isinstance(u, dict):
        return u.get("id")
    return getattr(u, "id", None)


def get_current_user_email() -> str:
    s = user_store()
    if s.get("user_email"):
        return s["user_email"]
    u = s.get("user")
    if isinstance(u, dict):
        return u.get("email", "")
    return getattr(u, "email", "") if u else ""


def reset_user_session() -> None:
    s = user_store()
    s["authenticated"] = False
    s["user"] = None
    s["user_email"] = ""
    s["chat_history"] = []
    s["current_phase"] = None
    s["slots"] = default_slots_from_schema(SLOT_SCHEMA)
    s["view_date"] = date.today().isoformat()
    s["active_view"] = "consult"
    s["app_date"] = date.today().isoformat()


# ============================================================
# 5. Supabase関連
# ============================================================

def load_today_history(user_id: str) -> None:
    s = user_store()
    today_str = date.today().isoformat()

    try:
        res = (
            supabase.table("user_chats")
            .select("*")
            .eq("user_id", user_id)
            .eq("chat_date", today_str)
            .order("message_time", desc=False)
            .execute()
        )
        data = res.data if hasattr(res, "data") else res.get("data", [])
    except Exception as exc:
        ui.notify(f"会話履歴の読み込み中にエラーが発生しました: {exc}", type="negative")
        data = []

    history: List[Dict[str, str]] = []
    current_phase = None
    for row in data:
        history.append(
            {
                "user": row.get("user_message", ""),
                "bot": row.get("bot_message", ""),
            }
        )
        if row.get("phase") and current_phase is None:
            current_phase = row.get("phase")

    s["chat_history"] = history
    s["current_phase"] = current_phase


def get_date_options(user_id: str) -> List[str]:
    today_str = date.today().isoformat()
    try:
        res_dates = (
            supabase.table("user_chats")
            .select("chat_date")
            .eq("user_id", user_id)
            .order("chat_date", desc=True)
            .execute()
        )
        data_dates = res_dates.data if hasattr(res_dates, "data") else res_dates.get("data", [])
        opts = sorted({row["chat_date"] for row in data_dates if row.get("chat_date")}, reverse=True)
        if today_str not in opts:
            opts = [today_str] + opts
        return opts
    except Exception as exc:
        ui.notify(f"過去の相談日リスト取得中にエラーが発生しました: {exc}", type="negative")
        return [today_str]


def get_hist_for_date(user_id: str, d: str) -> List[Dict[str, Any]]:
    try:
        res_hist = (
            supabase.table("user_chats")
            .select("*")
            .eq("user_id", user_id)
            .eq("chat_date", d)
            .order("message_time", desc=False)
            .execute()
        )
        return res_hist.data if hasattr(res_hist, "data") else res_hist.get("data", [])
    except Exception as exc:
        ui.notify(f"過去の相談履歴取得中にエラーが発生しました: {exc}", type="negative")
        return []


def get_phase_timeline(user_id: str) -> List[Dict[str, str]]:
    try:
        res = (
            supabase.table("user_chats")
            .select("chat_date,phase,message_time")
            .eq("user_id", user_id)
            .order("chat_date", desc=False)
            .order("message_time", desc=False)
            .execute()
        )
        rows = res.data if hasattr(res, "data") else res.get("data", [])
    except Exception as exc:
        ui.notify(f"フェーズ履歴の取得中にエラーが発生しました: {exc}", type="negative")
        return []

    first_phase_by_date: Dict[str, str] = {}
    for r in rows:
        d = r.get("chat_date")
        ph = r.get("phase")
        if d and ph and d not in first_phase_by_date:
            first_phase_by_date[d] = ph

    return [{"chat_date": d, "phase": first_phase_by_date[d]} for d in sorted(first_phase_by_date.keys())]


# ============================================================
# 6. GPT関連ユーティリティ
# ============================================================

def safe_json_load(s: str) -> dict:
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def clean_fallback_response(raw: str) -> str:
    """JSON解析に失敗した場合でも、利用者には自然な回答だけを返す。"""
    text = (raw or "").strip()
    # Markdownコードフェンスを除去
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    if not text:
        return "（すみません、うまく回答を生成できませんでした。もう一度、状況を短く教えてください。）"
    return text


def normalize_phase(p: str) -> str:
    if p in ["phase_1", "phase_2", "phase_3", "phase_4"]:
        return p
    return "phase_1"


def validate_slot_value(slot_key: str, value: str) -> str:
    meta = SLOT_SCHEMA.get(slot_key, {})
    allowed = meta.get("values", []) or []
    if value in allowed:
        return value
    return "不明"


def build_system_prompt(fixed_phase: Optional[str] = None, is_first_today: bool = False) -> str:
    s = user_store()
    prompt = ""
    prompt += "あなたは不登校・ひきこもり支援の専門家です。\n"
    prompt += "利用者に共感し、責めず、安全を優先し、現実的で具体的な一歩を提案してください。\n"
    prompt += "知識ベース（phases/compass_principles/key_scenes/slot_schema/action_cards）に基づいて応答してください。\n\n"
    prompt += "【重要ルール】\n"
    prompt += "- 出力は必ず「JSONのみ」。本文の外に説明や注釈、Markdown、コードブロックを書かない。\n"
    prompt += "- 推測でスロットを埋めない。根拠が弱い場合は「不明」のまま。\n"
    prompt += "- 回答の最後に、必ず1〜2個の具体的な確認質問を含める。\n"
    prompt += "- その質問は、次の支援分岐に直結する内容にする。\n"
    prompt += "- 質問は自然な会話文として response の中に書く（箇条書きにしない）。\n"
    prompt += "- action_cards は最大3枚まで選ぶ。\n"
    prompt += "- ただし、質問や支援カードの内容はUIに別表示しないため、必ず response の文章の中に自然に含める。\n"
    prompt += "- 緊急性が高い可能性があるときは、安全確保の確認を優先する。\n"
    prompt += "- 抽象的な理念だけで終わらせない。\n"
    prompt += "- 必ず具体的な声かけ例を最低2つ提示する。\n"
    prompt += "- 必ず段階的な小さな行動例（0か100かではない中間案）を2つ以上提示する。\n"
    prompt += "- 明日そのまま使える表現にする。\n"
    prompt += "- 命令口調や断定は避ける。\n"
    prompt += "- 実務性と安心感のバランスを取る。\n\n"
    prompt += "【出力構造強化ルール（具体性向上のための追加指示）】\n"
    prompt += "- 回答は次の順序で構成する。\n"
    prompt += "  ① 共感（2〜3文で簡潔に）\n"
    prompt += "  ② 具体的な支援策（本文の中心・最も分量を多くする）\n"
    prompt += "  ③ なぜその支援が適切かの短い説明\n"
    prompt += "  ④ 次の判断に必要な確認質問（1〜2個）\n"
    prompt += "- 具体的支援策は最低3つ提示する。\n"
    prompt += "- 行動例は『今日できること』と『今週試せること』の2段階で示す。\n"
    prompt += "- 必ず家庭内の実際の会話場面を想定した具体例を書く。\n"
    prompt += "- 抽象的助言（例：見守ることが大切、安心環境を整える等）だけで終わってはならない。\n\n"
    prompt += "【臨床具体性強化ルール（最終強化版）】\n"
    prompt += "- 初回回答では、相談者が“明日そのまま実行できる行動”を最低3つ提示する。\n"
    prompt += "- 行動は抽象語（見守る・寄り添う等）で表現してはならない。\n"
    prompt += "- 各提案は、家庭内の具体的場面を想定して描写する（例：夕食時、買い物後、就寝前など）。\n"
    prompt += "- 少なくとも2つは、親がそのまま使える会話文を『』で示す。\n"
    prompt += "- 会話文は評価・誘導・説得を含まない表現にする。\n"
    prompt += "- 登校を促す／促さないの判断基準を明示する（本人の自発性・感情の質・不安の強さなど）。\n"
    prompt += "- 0か100かではなく、“登校未満の接触”を必ず含める（例：校門まで散歩、HP閲覧、写真を見る等）。\n"
    prompt += "- 提案は必ず現在のフェーズと整合していることを前提にする。\n"
    prompt += "- 行動提案は自然な会話文の流れの中で、無理のない順序として示す。\n"
    prompt += "- 説明書のような区分（例：今日できること、今週試すこと等）は用いない。\n"
    prompt += "- 段階性は文章内に自然に含める。\n"
    prompt += "- 回答の中心は具体策とし、共感部分は簡潔にとどめる。\n"
    prompt += "- 一般論のみの回答は不十分とみなす。\n\n"

    if is_first_today:
        prompt += "今日はその日の最初の相談です。発言内容から phase_1〜phase_4 を一つだけ推定してください。\n"
    else:
        prompt += f"本日のフェーズは {fixed_phase} に固定です。再推定してはいけません。\n"

    prompt += "\n【あなたが返すJSON形式】\n"
    prompt += "{\n"
    prompt += '  "phase": "phase_1|phase_2|phase_3|phase_4",\n'
    prompt += '  "slots_update": { "SLOT_KEY": "VALUE", "...": "..." },\n'
    prompt += '  "questions": ["質問1","質問2"],\n'
    prompt += '  "selected_action_card_ids": ["AC_...","AC_..."],\n'
    prompt += '  "response": "相談者への回答（この文章の中に、確認質問も、具体支援も、次の一歩も全部含める）"\n'
    prompt += "}\n\n"

    prompt += "【現在のスロット（既知情報）】\n"
    prompt += json.dumps(s["slots"], ensure_ascii=False, indent=2) + "\n\n"

    prompt += "【知識ベース】\n"
    prompt += json.dumps(knowledge_base, ensure_ascii=False, indent=2)

    return prompt


def build_system_prompt_from_state(
    slots: Dict[str, str],
    fixed_phase: Optional[str] = None,
    is_first_today: bool = False,
) -> str:
    """別スレッドでも安全に使えるSystem Prompt生成。app.storageやuiを触らない。"""
    prompt = ""
    prompt += "あなたは不登校・ひきこもり支援の専門家です。\n"
    prompt += "利用者に共感し、責めず、安全を優先し、現実的で具体的な一歩を提案してください。\n"
    prompt += "知識ベース（phases/compass_principles/key_scenes/slot_schema/action_cards）に基づいて応答してください。\n\n"
    prompt += "【重要ルール】\n"
    prompt += "- 出力は必ず「JSONのみ」。本文の外に説明や注釈、Markdown、コードブロックを書かない。\n"
    prompt += "- 推測でスロットを埋めない。根拠が弱い場合は「不明」のまま。\n"
    prompt += "- 回答の最後に、必ず1〜2個の具体的な確認質問を含める。\n"
    prompt += "- その質問は、次の支援分岐に直結する内容にする。\n"
    prompt += "- 質問は自然な会話文として response の中に書く（箇条書きにしない）。\n"
    prompt += "- action_cards は最大3枚まで選ぶ。\n"
    prompt += "- ただし、質問や支援カードの内容はUIに別表示しないため、必ず response の文章の中に自然に含める。\n"
    prompt += "- 緊急性が高い可能性があるときは、安全確保の確認を優先する。\n"
    prompt += "- 抽象的な理念だけで終わらせない。\n"
    prompt += "- 必ず具体的な声かけ例を最低2つ提示する。\n"
    prompt += "- 必ず段階的な小さな行動例（0か100かではない中間案）を2つ以上提示する。\n"
    prompt += "- 明日そのまま使える表現にする。\n"
    prompt += "- 命令口調や断定は避ける。\n"
    prompt += "- 実務性と安心感のバランスを取る。\n\n"
    prompt += "【出力構造強化ルール（具体性向上のための追加指示）】\n"
    prompt += "- 回答は次の順序で構成する。\n"
    prompt += "  ① 共感（2〜3文で簡潔に）\n"
    prompt += "  ② 具体的な支援策（本文の中心・最も分量を多くする）\n"
    prompt += "  ③ なぜその支援が適切かの短い説明\n"
    prompt += "  ④ 次の判断に必要な確認質問（1〜2個）\n"
    prompt += "- 具体的支援策は最低3つ提示する。\n"
    prompt += "- 行動例は『今日できること』と『今週試せること』の2段階で示す。\n"
    prompt += "- 必ず家庭内の実際の会話場面を想定した具体例を書く。\n"
    prompt += "- 抽象的助言（例：見守ることが大切、安心環境を整える等）だけで終わってはならない。\n\n"
    prompt += "【臨床具体性強化ルール（最終強化版）】\n"
    prompt += "- 初回回答では、相談者が“明日そのまま実行できる行動”を最低3つ提示する。\n"
    prompt += "- 行動は抽象語（見守る・寄り添う等）で表現してはならない。\n"
    prompt += "- 各提案は、家庭内の具体的場面を想定して描写する（例：夕食時、買い物後、就寝前など）。\n"
    prompt += "- 少なくとも2つは、親がそのまま使える会話文を『』で示す。\n"
    prompt += "- 会話文は評価・誘導・説得を含まない表現にする。\n"
    prompt += "- 登校を促す／促さないの判断基準を明示する（本人の自発性・感情の質・不安の強さなど）。\n"
    prompt += "- 0か100かではなく、“登校未満の接触”を必ず含める（例：校門まで散歩、HP閲覧、写真を見る等）。\n"
    prompt += "- 提案は必ず現在のフェーズと整合していることを前提にする。\n"
    prompt += "- 行動提案は自然な会話文の流れの中で、無理のない順序として示す。\n"
    prompt += "- 説明書のような区分（例：今日できること、今週試すこと等）は用いない。\n"
    prompt += "- 段階性は文章内に自然に含める。\n"
    prompt += "- 回答の中心は具体策とし、共感部分は簡潔にとどめる。\n"
    prompt += "- 一般論のみの回答は不十分とみなす。\n\n"

    if is_first_today:
        prompt += "今日はその日の最初の相談です。発言内容から phase_1〜phase_4 を一つだけ推定してください。\n"
    else:
        prompt += f"本日のフェーズは {fixed_phase} に固定です。再推定してはいけません。\n"

    prompt += "\n【あなたが返すJSON形式】\n"
    prompt += "{\n"
    prompt += '  "phase": "phase_1|phase_2|phase_3|phase_4",\n'
    prompt += '  "slots_update": { "SLOT_KEY": "VALUE", "...": "..." },\n'
    prompt += '  "questions": ["質問1","質問2"],\n'
    prompt += '  "selected_action_card_ids": ["AC_...","AC_..."],\n'
    prompt += '  "response": "相談者への回答（この文章の中に、確認質問も、具体支援も、次の一歩も全部含める）"\n'
    prompt += "}\n\n"

    prompt += "【現在のスロット（既知情報）】\n"
    prompt += json.dumps(slots, ensure_ascii=False, indent=2) + "\n\n"

    prompt += "【知識ベース】\n"
    prompt += json.dumps(knowledge_base, ensure_ascii=False, indent=2)

    return prompt


def generate_response_background(
    user_input: str,
    user_id: str,
    chat_history: List[Dict[str, str]],
    current_phase: Optional[str],
    slots: Dict[str, str],
) -> Dict[str, Any]:
    """OpenAI/Supabase処理のみを行う別スレッド用関数。ui/app.storageは絶対に触らない。"""
    today_str = date.today().isoformat()
    warnings: List[str] = []

    is_first_today = len(chat_history) == 0 or current_phase is None
    fixed_phase = None if is_first_today else current_phase

    messages = [
        {
            "role": "system",
            "content": build_system_prompt_from_state(
                slots=slots,
                fixed_phase=fixed_phase,
                is_first_today=is_first_today,
            ),
        }
    ]

    for chat in chat_history:
        messages.append({"role": "user", "content": f"相談者の発言: {chat['user']}"})
        messages.append({"role": "assistant", "content": chat["bot"]})

    messages.append({"role": "user", "content": f"相談者の発言: {user_input}"})

    create_kwargs = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
        "messages": messages,
        "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
    }

    # JSON出力をできる限り強制する。未対応モデルの場合のみ通常呼び出しへフォールバック。
    try:
        resp = client.chat.completions.create(
            **create_kwargs,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        msg = str(exc).lower()
        if "response_format" in msg or "json_object" in msg or "unsupported" in msg:
            resp = client.chat.completions.create(**create_kwargs)
        else:
            raise

    raw = resp.choices[0].message.content.strip()

    phase_for_row = current_phase or "phase_1"
    new_phase = current_phase
    new_slots = dict(slots)

    try:
        obj = safe_json_load(raw)
    except Exception:
        # 利用者には内部エラーを見せず、自然な文章回答として扱う
        response_text = clean_fallback_response(raw)
    else:
        phase_out = normalize_phase(obj.get("phase", "phase_1"))
        if is_first_today:
            new_phase = phase_out
        phase_for_row = new_phase or phase_out

        slots_update = obj.get("slots_update", {}) or {}
        for k in new_slots.keys():
            if k in slots_update:
                v = slots_update.get(k)
                if isinstance(v, str):
                    v_norm = validate_slot_value(k, v)
                    if v_norm != "不明":
                        new_slots[k] = v_norm

        response_text = obj.get("response", "").strip()
        if not response_text:
            response_text = "（すみません、うまく回答を生成できませんでした。もう一度、状況を短く教えてください。）"

    try:
        supabase.table("user_chats").insert(
            {
                "user_id": user_id,
                "chat_date": today_str,
                "user_message": user_input,
                "bot_message": response_text,
                "phase": phase_for_row,
            }
        ).execute()
    except Exception as exc:
        warnings.append(f"会話の保存中にエラーが発生しました: {exc}")

    return {
        "response_text": response_text,
        "current_phase": new_phase,
        "slots": new_slots,
        "warnings": warnings,
    }


# ============================================================
# 7. UI補助
# ============================================================

def pecan_tree_svg_html(size_class: str = "") -> str:
    """ペカンの森をイメージした、柔らかい木のSVG。外部画像なしで表示できる。"""
    return f"""
    <div class="brand-logo {size_class}">
      <svg viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <!-- trunk -->
        <path d="M36 58V31" stroke="#7A552B" stroke-width="5" stroke-linecap="round"/>
        <path d="M36 42C29 38 22 32 19 23" stroke="#8A6232" stroke-width="3.2" stroke-linecap="round"/>
        <path d="M36 39C44 35 50 29 54 20" stroke="#8A6232" stroke-width="3.2" stroke-linecap="round"/>
        <path d="M36 34C32 29 30 24 29 17" stroke="#8A6232" stroke-width="2.8" stroke-linecap="round"/>
        <!-- leaves -->
        <ellipse cx="18" cy="21" rx="6.5" ry="8" fill="#7FB06B" transform="rotate(-35 18 21)"/>
        <ellipse cx="28" cy="13" rx="7" ry="8.5" fill="#5F9A55" transform="rotate(-16 28 13)"/>
        <ellipse cx="43" cy="14" rx="7" ry="8.5" fill="#6FA65D" transform="rotate(18 43 14)"/>
        <ellipse cx="55" cy="23" rx="6.5" ry="8" fill="#86B875" transform="rotate(35 55 23)"/>
        <ellipse cx="25" cy="31" rx="6.5" ry="7.5" fill="#8DBF7C" transform="rotate(-55 25 31)"/>
        <ellipse cx="47" cy="31" rx="6.5" ry="7.5" fill="#7CAF6B" transform="rotate(55 47 31)"/>
        <!-- pecan nuts -->
        <ellipse cx="24" cy="52" rx="4.3" ry="6.2" fill="#B47A33" transform="rotate(28 24 52)"/>
        <path d="M22 49.5C24.6 51.4 25.9 53.8 26.1 56" stroke="#7A552B" stroke-width="1.1" stroke-linecap="round" opacity="0.6"/>
        <ellipse cx="48" cy="52" rx="4.3" ry="6.2" fill="#B47A33" transform="rotate(-28 48 52)"/>
        <path d="M50 49.5C47.4 51.4 46.1 53.8 45.9 56" stroke="#7A552B" stroke-width="1.1" stroke-linecap="round" opacity="0.6"/>
        <!-- ground -->
        <path d="M21 62h30" stroke="#7FB06B" stroke-width="4" stroke-linecap="round" opacity="0.55"/>
      </svg>
    </div>
    """


def tree_logo(size_class: str = "") -> None:
    """タイトルやログイン画面で使う、ペカンの森ロゴ。"""
    ui.html(pecan_tree_svg_html(size_class))


def ai_avatar_logo() -> None:
    """チャット内の自然AIエージェント。ロボではなく、ペカンの木で表現する。"""
    ui.html(pecan_tree_svg_html("ai-avatar-logo"))


def render_phase_status_badge(current_phase: Optional[str], on_click: Optional[Any] = None) -> ui.label:
    """相談カード右上に表示する、現在の見立てチップ。戻り値はPhase表示ラベル。"""
    phase_text = PHASE_SHORT_LABELS.get(current_phase, "未推定")
    with ui.row().classes("phase-status-pill items-center gap-2").on("click", on_click or (lambda: None)):
        with ui.element("div").classes("phase-status-icon"):
            ui.icon("favorite_border").classes("text-lg")
        with ui.column().classes("gap-0"):
            ui.label("現在の見立て").classes("phase-status-caption")
            value_label = ui.label(phase_text).classes("phase-status-value")
    return value_label



def render_consult_phase_summary(container: ui.element, current_phase: Optional[str]) -> None:
    """相談画面では大きなカードを出さず、ヘッダー内チップで軽く表示する。"""
    container.clear()


def set_active_view(view: str) -> None:
    s = user_store()
    s["active_view"] = view
    ui.navigate.reload()


def app_header() -> None:
    s = user_store()
    active_view = s.get("active_view", "consult")
    phase = s.get("current_phase")
    phase_short = PHASE_SHORT_LABELS.get(phase, "見立て未推定")
    phase_name = phase_short.split("：", 1)[1] if "：" in phase_short else phase_short

    def tab_button(label: str, icon: str, view: str) -> None:
        active = active_view == view
        classes = "top-tab top-tab-active" if active else "top-tab"
        ui.button(label, icon=icon, on_click=lambda v=view: set_active_view(v)).props("flat dense no-caps").classes(classes)

    with ui.header().classes("top-bar"):
        with ui.row().classes("header-inner items-center justify-between w-full"):
            with ui.row().classes("header-logo items-center gap-2"):
                tree_logo()
                ui.label("不登校・ひきこもり相談AIエージェント").classes("app-title-compact")
                ui.label(phase_name).classes("phase-mini-chip")
            with ui.row().classes("top-tabs"):
                tab_button("相談", "chat_bubble_outline", "consult")
                tab_button("見立て", "favorite_border", "insight")
                tab_button("履歴", "history", "history")


def render_side_nav() -> None:
    """旧サイドナビは廃止。現在は上部タブで切り替える。"""
    return


def render_history_page() -> None:
    user_id = get_current_user_id()
    if not user_id:
        return

    timeline = get_phase_timeline(user_id)

    with ui.card().classes("app-card w-full p-0"):
        with ui.column().classes("w-full p-5 gap-2"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("履歴").classes("title-main text-2xl")
                ui.button(icon="chat_bubble_outline", on_click=lambda: set_active_view("consult")).props("flat round color=green")
            ui.label("これまでの相談と、その日の見立てを確認できます。").classes("small-muted")

        ui.separator()

        with ui.column().classes("w-full p-4 gap-3"):
            if not timeline:
                ui.label("まだ履歴がありません。まず今日の相談を始めてください。").classes("small-muted")
                return

            last_heading = None
            for item in timeline[::-1]:
                d = item.get("chat_date", "")
                phase = item.get("phase", "")
                heading = "今日" if d == date.today().isoformat() else d
                if heading != last_heading:
                    ui.label(heading).classes("section-label mt-2")
                    last_heading = heading

                rows = get_hist_for_date(user_id, d)
                first_text = "相談記録"
                time_text = ""
                if rows:
                    first_text = (rows[0].get("user_message") or "相談記録").replace("\n", " ")
                    if len(first_text) > 34:
                        first_text = first_text[:34] + "..."
                    time_text = str(rows[0].get("message_time") or "")[:5]

                def open_date(target_date=d) -> None:
                    s = user_store()
                    s["view_date"] = target_date
                    s["active_view"] = "consult"
                    ui.navigate.reload()

                with ui.row().classes("history-row w-full items-center justify-between").on("click", open_date):
                    with ui.column().classes("gap-0"):
                        ui.label(first_text).classes("font-bold text-sm")
                        ui.label(PHASE_SHORT_LABELS.get(phase, phase)).classes("small-muted")
                    with ui.row().classes("items-center gap-2"):
                        if time_text:
                            ui.label(time_text).classes("small-muted")
                        ui.icon("chevron_right").classes("text-gray-400")


def render_phase_panel(container: Optional[ui.element] = None) -> None:
    """見立てページ。相談画面では軽く、ここで詳細を見る。"""
    if container is not None:
        container.clear()
        with container:
            render_phase_panel()
        return

    s = user_store()
    current_phase = s.get("current_phase")
    active_index = {"phase_1": 0, "phase_2": 1, "phase_3": 2, "phase_4": 3}.get(current_phase, -1)

    with ui.card().classes("current-phase-card compact-insight w-full"):
        with ui.column().classes("gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label("現在の見立て").classes("section-label")
                ui.label(PHASE_SHORT_LABELS.get(current_phase, "未推定")).classes("phase-chip")

            if current_phase in PHASE_SHORT_LABELS:
                ui.label(PHASE_SHORT_LABELS[current_phase]).classes("current-phase-title")
                ui.label(PHASE_DESCRIPTIONS.get(current_phase, "")).classes("current-phase-subtitle")
            else:
                ui.label("まだ見立てはありません").classes("current-phase-title")
                ui.label("最初の相談内容を送信すると、その日の状態に合わせて見立てが表示されます。").classes("current-phase-subtitle")

            with ui.row().classes("phase-track w-full"):
                for i in range(4):
                    dot_class = "phase-dot phase-dot-active" if i == active_index else "phase-dot"
                    ui.html(f'<div class="{dot_class}"></div>')

        with ui.card().classes("soft-card w-full p-3 mt-3"):
            ui.label("フェーズの目安").classes("font-bold text-green-900")
            with ui.column().classes("w-full gap-2 mt-2"):
                for idx, (key, label) in enumerate(PHASE_DISPLAY, start=1):
                    active = current_phase == key
                    item_class = "phase-list-item-active w-full" if active else "phase-list-item w-full"
                    with ui.row().classes(f"{item_class} items-start gap-3"):
                        number_class = "phase-number phase-number-active" if active else "phase-number"
                        ui.label(str(idx)).classes(number_class)
                        with ui.column().classes("gap-0"):
                            ui.label(label).classes("phase-name-active text-sm" if active else "text-sm text-gray-700 font-medium")
                            ui.label(PHASE_DESCRIPTIONS.get(key, "")).classes("small-muted")


def render_chat_message(role: str, text: str) -> None:
    with ui.row().classes("w-full items-start" + (" justify-end" if role == "user" else " justify-start")):
        if role != "user":
            with ui.element("div").classes("ai-avatar"):
                ui.html("""
                <svg viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <path d="M36 58V31" stroke="#7A552B" stroke-width="5" stroke-linecap="round"/>
                  <path d="M36 42C29 38 22 32 19 23" stroke="#8A6232" stroke-width="3.2" stroke-linecap="round"/>
                  <path d="M36 39C44 35 50 29 54 20" stroke="#8A6232" stroke-width="3.2" stroke-linecap="round"/>
                  <path d="M36 34C32 29 30 24 29 17" stroke="#8A6232" stroke-width="2.8" stroke-linecap="round"/>
                  <ellipse cx="18" cy="21" rx="6.5" ry="8" fill="#7FB06B" transform="rotate(-35 18 21)"/>
                  <ellipse cx="28" cy="13" rx="7" ry="8.5" fill="#5F9A55" transform="rotate(-16 28 13)"/>
                  <ellipse cx="43" cy="14" rx="7" ry="8.5" fill="#6FA65D" transform="rotate(18 43 14)"/>
                  <ellipse cx="55" cy="23" rx="6.5" ry="8" fill="#86B875" transform="rotate(35 55 23)"/>
                  <ellipse cx="25" cy="31" rx="6.5" ry="7.5" fill="#8DBF7C" transform="rotate(-55 25 31)"/>
                  <ellipse cx="47" cy="31" rx="6.5" ry="7.5" fill="#7CAF6B" transform="rotate(55 47 31)"/>
                  <ellipse cx="24" cy="52" rx="4.3" ry="6.2" fill="#B47A33" transform="rotate(28 24 52)"/>
                  <ellipse cx="48" cy="52" rx="4.3" ry="6.2" fill="#B47A33" transform="rotate(-28 48 52)"/>
                  <path d="M21 62h30" stroke="#7FB06B" stroke-width="4" stroke-linecap="round" opacity="0.55"/>
                </svg>
                """)
            ui.label(text).classes("chat-bubble-ai")
        else:
            ui.label(text).classes("chat-bubble-user")
            with ui.element("div").classes("user-avatar"):
                ui.icon("person").classes("text-sm")


def render_chat_area(container: ui.element, display_history: List[Dict[str, str]]) -> None:
    container.clear()
    with container:
        if not display_history:
            with ui.column().classes("items-center justify-center w-full h-full gap-2"):
                ui.icon("forum").classes("text-5xl text-green-300")
                ui.label("まだ相談はありません。下の入力欄から、今の状況を短く教えてください。").classes("small-muted text-center")
        else:
            ui.label("今日").classes("chat-date-separator")
            for chat in display_history:
                render_chat_message("user", chat.get("user", ""))
                render_chat_message("assistant", chat.get("bot", ""))


# ============================================================
# 8. ページ：パスワード画面
# ============================================================

def show_access_gate() -> None:
    s = user_store()

    with ui.column().classes("page-wrap"):
        with ui.card().classes("login-card app-card"):
            with ui.column().classes("items-center gap-3 w-full"):
                tree_logo()
                ui.label(f"{APP_TITLE}へようこそ").classes("title-main text-2xl text-center w-full")
                ui.label("アクセスにはパスワードが必要です").classes("subtitle text-center w-full")

            password = ui.input(
                "アクセス用パスワード",
                password=True,
                password_toggle_button=True,
                placeholder="パスワードを入力",
            ).props("outlined").classes("w-full")

            def submit_password() -> None:
                if password.value == ACCESS_PASS:
                    s["authenticated"] = True
                    ui.notify("認証しました。", type="positive")
                    ui.navigate.reload()
                else:
                    ui.notify("パスワードが違います。", type="negative")

            password.on("keydown.enter", lambda _: submit_password())
            ui.button("はじめる", icon="arrow_forward", on_click=submit_password).props("color=green").classes("w-full")


# ============================================================
# 9. ページ：Supabaseログイン / 新規登録
# ============================================================

def show_login_page() -> None:
    s = user_store()

    with ui.column().classes("page-wrap"):
        with ui.card().classes("login-card app-card"):
            with ui.column().classes("items-center gap-2 w-full"):
                tree_logo()
                ui.label("ログイン / 新規登録").classes("title-main text-2xl text-center w-full")
                ui.label("登録済みのメールアドレスでログインしてください。").classes("subtitle text-center w-full")

            with ui.tabs().classes("w-full") as tabs:
                login_tab = ui.tab("ログイン")
                signup_tab = ui.tab("新規登録")

            with ui.tab_panels(tabs, value=login_tab).classes("w-full"):
                with ui.tab_panel(login_tab):
                    login_email = ui.input("メールアドレス").props("outlined").classes("w-full")
                    login_password = ui.input("パスワード", password=True, password_toggle_button=True).props("outlined").classes("w-full")

                    def login() -> None:
                        if not login_email.value or not login_password.value:
                            ui.notify("メールアドレスとパスワードを入力してください。", type="warning")
                            return
                        try:
                            res = supabase.auth.sign_in_with_password(
                                {"email": login_email.value, "password": login_password.value}
                            )
                            s["user"] = res.user
                            s["user_email"] = getattr(res.user, "email", login_email.value)
                            user_id = getattr(res.user, "id", None)
                            if user_id is None and isinstance(res.user, dict):
                                user_id = res.user.get("id")
                            if user_id:
                                load_today_history(user_id)
                            ui.notify("ログインしました。", type="positive")
                            ui.navigate.reload()
                        except Exception as exc:
                            ui.notify(f"ログインに失敗しました: {exc}", type="negative")

                    login_password.on("keydown.enter", lambda _: login())
                    ui.button("ログイン", icon="login", on_click=login).props("color=green").classes("w-full")

                with ui.tab_panel(signup_tab):
                    signup_email = ui.input("新規登録用メールアドレス").props("outlined").classes("w-full")
                    signup_password = ui.input(
                        "新規登録用パスワード（6文字以上推奨）",
                        password=True,
                        password_toggle_button=True,
                    ).props("outlined").classes("w-full")

                    def signup() -> None:
                        if not signup_email.value or not signup_password.value:
                            ui.notify("メールアドレスとパスワードを入力してください。", type="warning")
                            return
                        try:
                            supabase.auth.sign_up(
                                {"email": signup_email.value, "password": signup_password.value}
                            )
                            ui.notify("登録しました。確認メールが届いていれば、メール認証後にログインしてください。", type="positive")
                        except Exception as exc:
                            ui.notify(f"登録に失敗しました: {exc}", type="negative")

                    signup_password.on("keydown.enter", lambda _: signup())
                    ui.button("アカウント作成", icon="person_add", on_click=signup).props("color=green outline").classes("w-full")


# ============================================================
# 10. ページ：メインアプリ
# ============================================================

def show_main_page() -> None:
    s = user_store()
    user_id = get_current_user_id()
    if not user_id:
        ui.notify("ユーザーIDが取得できませんでした。Supabaseの認証設定を確認してください。", type="negative")
        reset_user_session()
        ui.navigate.reload()
        return

    if not s.get("chat_history") and s.get("view_date") == date.today().isoformat():
        load_today_history(user_id)

    app_header()

    today_str = date.today().isoformat()
    view_date = s.get("view_date", today_str)
    active_view = s.get("active_view", "consult")

    with ui.column().classes("page-wrap chatgpt-page"):
        with ui.column().classes("chatgpt-main w-full"):
            if active_view == "insight":
                with ui.column().classes("gap-3 w-full p-3"):
                    render_phase_panel()

            elif active_view == "history":
                with ui.column().classes("gap-3 w-full p-3"):
                    render_history_page()

            else:
                if view_date == today_str:
                    display_history = s["chat_history"]
                else:
                    rows = get_hist_for_date(user_id, view_date)
                    display_history = [
                        {"user": r.get("user_message", ""), "bot": r.get("bot_message", "")}
                        for r in rows
                    ]

                phase_for_view = None
                if view_date == today_str:
                    phase_for_view = s["current_phase"]
                else:
                    rows_view = get_hist_for_date(user_id, view_date)
                    for r in rows_view:
                        if r.get("phase"):
                            phase_for_view = r.get("phase")
                            break

                phase_label = PHASE_SHORT_LABELS.get(phase_for_view, "未推定")

                with ui.element("div").classes("chat-shell w-full"):
                    with ui.row().classes("chat-head-compact items-center justify-between w-full"):
                        with ui.column().classes("gap-0"):
                            ui.label("AIエージェントに相談する").classes("chat-title-compact")
                            ui.label(f"現在の見立て：{phase_label}").classes("phase-inline")
                        with ui.row().classes("items-center gap-1"):
                            ui.button("見立て", icon="favorite_border", on_click=lambda: set_active_view("insight")).props("flat dense color=green no-caps").classes("top-tab")
                            ui.button("履歴", icon="history", on_click=lambda: set_active_view("history")).props("flat dense color=green no-caps").classes("top-tab")

                    with ui.element("div").classes("chat-scroll-area w-full") as scroll_area:
                        chat_container = ui.column().classes("chat-area w-full")
                        render_chat_area(chat_container, display_history)

                    if view_date == today_str:
                        with ui.column().classes("chat-input-fixed w-full gap-0"):
                            with ui.row().classes("w-full items-end gap-2"):
                                message_input = ui.textarea(
                                    placeholder="どんなことでも大丈夫です。",
                                ).props("outlined autogrow rows=1").classes("flex-1")
                                send_button = ui.button(icon="send").props("round color=green size=lg")
                            ui.label("あなたの会話は安全に保護されています").classes("security-note-compact")

                        async def send_message() -> None:
                            user_text = (message_input.value or "").strip()
                            if not user_text:
                                return

                            message_input.value = ""
                            send_button.disable()

                            temp_history = s["chat_history"] + [{"user": user_text, "bot": "AIエージェントは考えています…"}]
                            render_chat_area(chat_container, temp_history)
                            ui.run_javascript("""
                                setTimeout(() => {
                                    const el = document.querySelector('.chat-scroll-area');
                                    if (el) el.scrollTo({top: el.scrollHeight, behavior: 'smooth'});
                                }, 50)
                            """)

                            try:
                                result = await asyncio.to_thread(
                                    generate_response_background,
                                    user_text,
                                    user_id,
                                    list(s["chat_history"]),
                                    s.get("current_phase"),
                                    dict(s["slots"]),
                                )
                                response_text = result["response_text"]
                                s["current_phase"] = result.get("current_phase")
                                s["slots"] = result.get("slots", s["slots"])
                                for warning in result.get("warnings", []):
                                    if "JSON" not in str(warning):
                                        ui.notify(warning, type="warning")
                            except Exception as exc:
                                response_text = f"エラー: {exc}"
                                ui.notify(f"エラー: {exc}", type="negative")

                            s["chat_history"].append({"user": user_text, "bot": response_text})

                            send_button.enable()
                            render_chat_area(chat_container, s["chat_history"])
                            ui.run_javascript("""
                                setTimeout(() => {
                                    const el = document.querySelector('.chat-scroll-area');
                                    if (el) el.scrollTo({top: el.scrollHeight, behavior: 'smooth'});
                                }, 50)
                            """)

                        send_button.on("click", send_message)
                        message_input.on("keydown.ctrl.enter", lambda _: send_message())
                    else:
                        ui.label("※ 過去の履歴を閲覧中です。入力するには『今日』を選択してください。").classes("small-muted p-4")


# ============================================================
# 11. ルーティング
# ============================================================

@ui.page("/")
def index() -> None:
    if KNOWLEDGE_BASE_LOAD_ERROR:
        with ui.column().classes("page-wrap"):
            with ui.card().classes("login-card app-card"):
                ui.label("知識ベースJSONの読み込みに失敗しました").classes("text-negative text-xl font-bold")
                ui.label(KNOWLEDGE_BASE_LOAD_ERROR).classes("small-muted")
        return

    s = user_store()

    if not s["authenticated"]:
        show_access_gate()
        return

    if not s["user"]:
        show_login_page()
        return

    show_main_page()


# ============================================================
# 12. 起動
# ============================================================

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title=APP_TITLE,
        favicon=str(STATIC_DIR / "pecan-forest-icon.svg") if (STATIC_DIR / "pecan-forest-icon.svg").exists() else (str(STATIC_DIR / "icon-192.png") if (STATIC_DIR / "icon-192.png").exists() else "🌳"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        reload=bool(os.getenv("NICEGUI_RELOAD", "")),
        storage_secret=NICEGUI_STORAGE_SECRET,
    )
