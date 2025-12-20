# fids_display.py — Pi-FIDS (Service Account ver.)
# - Google Sheets をサービスアカウントで読み込み（ブラウザ認証不要）
# - ETD(予定時刻)列 + 航空会社ロゴ表示
# - /       : 出発 (Departure)
# - /arrival: 到着 (Arrival)
# --------------------------------------------------

from datetime import datetime
from pathlib import Path
import re

from flask import Flask, render_template_string, abort, send_from_directory
import gspread

from config import SHEET_KEY, SHEET_NAME, UPDATE_INTERVAL
try:
    # 任意: config に SHEET_NAME_ARRIVAL が無ければ "Arrival" で代用
    from config import SHEET_NAME_ARRIVAL
except Exception:
    SHEET_NAME_ARRIVAL = "Arrival"

# --- Flask & Paths ---
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
LOGO_DIR = STATIC_DIR / "logos"

app = Flask(__name__, static_folder=str(STATIC_DIR))

# --- Helpers for logos ---
LOGO_BASE = "/static/logos"

def airline_code_from_flight(flight: str) -> str:
    """便名 'JL999' -> 'JL'（先頭の英字）"""
    if not flight:
        return ""
    m = re.match(r"([A-Za-z]+)", str(flight).strip())
    return (m.group(1).upper() if m else "")

def logo_img_html(flight: str) -> str:
    code = airline_code_from_flight(flight)
    if not code:
        return f'<img class="logo" src="{LOGO_BASE}/default.png" alt="-" />'
    # 見つからない時は onerror で default.png に切替
    return (f'<img class="logo" src="{LOGO_BASE}/{code}.png" alt="{code}" '
            f'onerror="this.onerror=null;this.src=\'{LOGO_BASE}/default.png\';" />')

# --- Service Account read ---
def _read_sheet_custom(sheet_name: str):
    sa_path = APP_DIR / "service_account.json"
    if not sa_path.exists():
        raise FileNotFoundError(f"Missing service_account.json at {sa_path}")
    gc = gspread.service_account(filename=str(sa_path))
    sh = gc.open_by_key(SHEET_KEY)
    ws = sh.worksheet(sheet_name)
    return ws.get_all_values()

# --- HTML Template (airport-ish style with logos & ETD) ---
TABLE_HTML = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="{{ refresh }}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pi-FIDS</title>
  <style>
    :root{
      --bg:#0a1726; --panel:#102a44; --line:rgba(255,255,255,.08);
      --txt:#eef5ff; --muted:#9bb3c9; --ok:#9BE28F; --delay:#FFD166; --cancel:#FF6B6B;
      --fs:20px; --lh:1.45; --padY:14px;
    }
    html, body { margin:0; padding:0; background:var(--bg); color:var(--txt);
      font-family: system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,"Noto Sans JP","Yu Gothic UI","Meiryo",sans-serif; }
    header { padding:12px 18px; background:var(--panel); display:flex; justify-content:space-between; align-items:center; }
    header .title { font-size:calc(var(--fs) + 4px); font-weight:800; letter-spacing:.4px; }
    header .time  { font-size:14px; color:var(--muted); }
    table { width:100%; border-collapse:collapse; table-layout:fixed; }
    th, td { padding:var(--padY) 16px; line-height:var(--lh); font-size:var(--fs);
      border-bottom:1px solid var(--line); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    th { background:var(--panel); font-weight:800; font-size:calc(var(--fs) - 2px); }
    tr:nth-child(even) td { background:rgba(255,255,255,.02); }
    .status { font-weight:800; text-align:right; }
    .ok { color:var(--ok); } .delay { color:var(--delay); } .cancel { color:var(--cancel); }
    .footer { padding:10px 16px; font-size:12px; color:var(--muted); }

    /* column widths */
    col.logo   { width: 9%; }
    col.flight { width: 16%; }
    col.dest   { width: 28%; }
    col.time   { width: 12%; }
    col.etd    { width: 12%; }
    col.gate   { width: 8%; }
    col.status { width: 15%; }

    .logo { height:26px; vertical-align:middle; }
    td.logo-cell, th.logo-cell { text-align:center; }
    td:nth-child(6), th:nth-child(6){ text-align:right; } /* Gate列を右寄せ（列順に合わせる） */

    .logo-title {
  display: flex;
  align-items: center;
  gap: 10px;
}
.title-logo {
  height: 28px;   /* ロゴの高さ（24〜32で調整可能） */
  width: auto;
  display: block;
}
  </style>
</head>
<body>
  <header>
    <div class="logo-title">
      <img src="/static/logos/MKM.png" onerror="this.src='/static/favicon.ico'" class="title-logo" alt="MKM Logo">
      <span class="title">Aeiron Pi-FIDS — {{ sheet_name }}</span>
    </div>
    <div class="time">{{ now }}</div>
  </header>

  <table>
    <colgroup>
      <col class="logo">      <!-- 9% -->
      <col class="flight">    <!-- 16% -->
      <col class="dest">      <!-- 28% -->
      <col class="time">      <!-- 12% -->
      <col class="etd">       <!-- 12% -->
      <col class="gate">      <!-- 8% -->
      <col class="status">    <!-- 15% -->
    </colgroup>
    <thead>
      <tr>
        {% for h in headers %}<th class="{{ 'logo-cell' if loop.index0==0 else '' }}">{{ h }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        {% for cell in row %}
          {% if loop.index0 == status_col and cell %}
            {% set low = (cell|string)|lower %}
            {% set cls = 'ok' if 'on time' in low or 'boarding' in low or 'departed' in low else ('delay' if 'delay' in low else ('cancel' if 'cancel' in low else '')) %}
            <td class="status {{ cls }}">{{ cell|safe }}</td>
          {% else %}
            <td class="{{ 'logo-cell' if loop.index0==0 else '' }}">{{ cell|safe }}</td>
          {% endif %}
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="footer">Auto-refresh: {{ refresh }}s • Updated at {{ now }}</div>

  <!-- 任意: 出発/到着を交互表示したい場合は下のJSを有効化（コメント解除）
  <script>
    (function(){
      const isArrival = location.pathname.replace(/\/+$/,'') === '/arrival';
      const next = isArrival ? '/' : '/arrival';
      const sec = {{ refresh|int }};
      setTimeout(() => { location.href = next; }, sec * 1000);
    })();
  </script>
  -->
</body>
</html>
"""

# ---- rendering helpers ----
def _find_col(headers, candidates):
    low = [str(h).strip().lower() for h in headers]
    for name in candidates:
        name = name.lower()
        if name in low:
            return low.index(name)
    return -1

def _parse_hhmm(s:str):
    try:
        s = str(s).strip()
        if not s: return None
        h, m = s.split(":")
        return int(h)*60 + int(m)
    except Exception:
        return None

def _classify_etd(std:str, etd:str):
    """STD/ETD を 'plain'|'delay'|'early' と表示テキストに分類"""
    t_std = _parse_hhmm(std)
    t_etd = _parse_hhmm(etd)
    if t_etd is None:
        return ("—", "etd-plain") if t_std is not None else ("", "etd-plain")
    if t_std is None:
        return (etd, "etd-plain")
    if t_etd == t_std:
        return ("—", "etd-plain")   # 同じ時刻ならダッシュを返す
    return (etd, "etd-delay" if t_etd > t_std else "etd-early")

def _rebuild_table(values):
    """ロゴ&ETDを含む 7列構成に並べ替え"""
    if not values:
        return [], [], -1

    headers = values[0]
    rows = values[1:] if len(values) > 1 else []

    idx_flight = _find_col(headers, ["flight", "便名", "便", "flt"])
    idx_time   = _find_col(headers, ["time", "sched", "std", "予定", "出発時刻"])
    idx_etd    = _find_col(headers, ["etd", "estimate", "estimated", "推定", "見込み"])
    idx_gate   = _find_col(headers, ["gate", "g", "ゲート"])
    idx_status = _find_col(headers, ["status", "remark", "remarks", "状態", "ステータス"])

    # Destinationは残りから選ぶ
    reserved = {i for i in [idx_flight, idx_time, idx_etd, idx_gate, idx_status] if i >= 0}
    idx_dest = -1
    for i, h in enumerate(headers):
        if i not in reserved and str(h).strip().lower() in ("destination", "to", "行先", "行き先", "dest"):
            idx_dest = i
            break
    if idx_dest < 0:
        for i in range(len(headers)):
            if i not in reserved:
                idx_dest = i
                break

    new_headers = ["", "Flight", "Destination", "Time", "ETD", "Gate", "Status"]
    new_rows = []

    for r in rows:
        flight = r[idx_flight] if idx_flight >= 0 and idx_flight < len(r) else ""
        time   = r[idx_time]   if idx_time   >= 0 and idx_time   < len(r) else ""
        etd_raw= r[idx_etd]    if idx_etd    >= 0 and idx_etd    < len(r) and r[idx_etd] else ""

        # ★ ETD 判定（Timeと同じなら「—」に）
        etd_text, etd_cls = _classify_etd(time, etd_raw or time)
        etd_html = f'<span class="{etd_cls}">{etd_text}</span>'

        dest   = r[idx_dest]   if idx_dest   >= 0 and idx_dest   < len(r) else ""
        gate   = r[idx_gate]   if idx_gate   >= 0 and idx_gate   < len(r) else ""
        status = r[idx_status] if idx_status >= 0 and idx_status < len(r) else ""

        logo_html = logo_img_html(flight)
        new_rows.append([logo_html, flight, dest, time, etd_html, gate, status])

    status_col = 6  # 0-based: Status列
    return new_headers, new_rows, status_col

def _render(values, sheet_name):
    if not values:
        abort(204)
    headers, rows, status_col = _rebuild_table(values)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(
        TABLE_HTML,
        headers=headers, rows=rows, now=now,
        refresh=int(UPDATE_INTERVAL), sheet_name=sheet_name, status_col=status_col
    )

# ---- Routes ----
@app.get("/")
def index():
    try:
        values = _read_sheet_custom(SHEET_NAME)
    except Exception as e:
        import traceback; traceback.print_exc()
        return f"<pre>Pi-FIDS error: {e}</pre>", 500
    return _render(values, SHEET_NAME)

@app.get("/arrival")
def arrival():
    try:
        values = _read_sheet_custom(SHEET_NAME_ARRIVAL)
    except Exception as e:
        import traceback; traceback.print_exc()
        return f"<pre>Pi-FIDS error: {e}</pre>", 500
    return _render(values, SHEET_NAME_ARRIVAL)

# 任意: favicon (static に favicon.ico があれば 404 が消える)
@app.get("/favicon.ico")
def favicon():
    return send_from_directory(STATIC_DIR, "favicon.ico")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
