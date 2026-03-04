"""Built-in UI: JSON endpoints + HTML dashboard (Sanic).

- /metrics.json -> StatsStore snapshot
- /errors.json -> recent error ring (last N)
- / -> HTML dashboard with KPIs + sparkline, theme toggle, recent errors table
- Supports bearer token auth (optional), saves token from `?token` to localStorage
- Configurable ui_prefix (mounted via Sanic Blueprint)
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import Any

from sanic import Blueprint
from sanic.request import Request
from sanic.response import HTTPResponse, text
from sanic.response import json as sanic_json

from profilis.core.stats import StatsStore


# ---------------- Error ring (in-memory) ----------------
@dataclass
class ErrorItem:
    ts_ns: int
    route: str
    status: int
    exception_type: str | None
    exception_value: str
    traceback: str


class _ErrorRing:
    def __init__(self, maxlen: int = 200) -> None:
        self._buf: deque[ErrorItem] = deque(maxlen=maxlen)

    def record(self, item: ErrorItem) -> None:
        self._buf.append(item)

    def dump(self) -> list[dict[str, str | int | None]]:
        return [asdict(x) for x in list(self._buf)][-50:]


# Singleton-ish registry (simple module-level reference)
_ERROR_RING: _ErrorRing | None = _ErrorRing(maxlen=500)


def get_error_ring() -> _ErrorRing | None:
    return _ERROR_RING


def record_error(item: ErrorItem) -> None:
    ring = get_error_ring()
    if ring:
        ring.record(item)


# ---------------- UI Blueprint ----------------
_HTML = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Profilis Metrics</title>
  <style>
    :root { --bg:#0b1220; --card:#121a2b; --muted:#789; --fg:#eaf1ff; --accent:#6aa1ff; --bad:#ff6b6b; --ok:#4cd964; }
    :root.light { --bg:#f7f9ff; --card:#ffffff; --muted:#50607a; --fg:#0b1220; --accent:#2a66ff; --bad:#d94141; --ok:#198754; }
    html,body{margin:0;padding:0;background:var(--bg);color:var(--fg);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,\"Helvetica Neue\",Arial,\"Apple Color Emoji\",\"Segoe UI Emoji\"}
    .wrap{max-width:1100px;margin:32px auto;padding:0 16px}
    .report-section{display:flex;align-items:center;gap:12px;margin-bottom:16px; justify-content: flex-end;}
    header{display:flex;align-items:center;gap:12px;margin-bottom:16px}
    header h1{font-size:20px;margin:0}
    .kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:12px 0}
    .card{background:var(--card);border-radius:14px;padding:14px;box-shadow:0 1px 0 rgba(255,255,255,.04) inset}
    .label{font-size:12px;color:var(--muted);margin-bottom:6px}
    .value{font-size:28px;font-weight:700}
    .muted{color:var(--muted)}
    .row{display:grid;grid-template-columns:1.5fr .7fr;gap:12px;margin-top:12px}
    canvas{width:100%;height:260px}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th,td{padding:8px;border-bottom:1px solid rgba(255,255,255,.08)}
    th{color:var(--muted);text-align:left}
    .err{color:var(--bad);font-weight:600}
    .ok{color:var(--ok);font-weight:600}
    .btn{margin-left:auto;background:transparent;border:1px solid var(--accent);color:var(--accent);padding:6px 10px;border-radius:10px;cursor:pointer;display:flex;align-items:center;gap:6px;justify-content:center}
    .feedback-links{margin-right:auto;display:flex;gap:8px}
    .feedback-link{color:var(--muted);text-decoration:none;font-size:16px;opacity:0.6;transition:opacity 0.2s ease}
    .feedback-link:hover{opacity:1}
    @media (max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.row{grid-template-columns:1fr}}
  </style>
  <script src=\"https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js\"></script>
  <script>
    // Theme handling
    function setTheme(t){ document.documentElement.classList.toggle('light', t==='light'); localStorage.setItem('profilis_theme', t); }
    function toggleTheme(){ const t = localStorage.getItem('profilis_theme')==='light' ? 'dark' : 'light'; setTheme(t); }
    (function(){ setTheme(localStorage.getItem('profilis_theme') || (window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark')); })();

    // Auth token helper
    const tokenKey='profilis_token';
    (function persistToken(){const u=new URL(window.location.href);const t=u.searchParams.get('token');if(t){localStorage.setItem(tokenKey,t)}})();
    function authHeaders(){ const t=localStorage.getItem(tokenKey); return t? {Authorization:'Bearer '+t}: {}; }

    const fmt = (n)=> n==null? '—' : (Number.isInteger(n)? n.toString() : n.toFixed(2));
    // Ensure JSON endpoints are resolved relative to the dashboard path,
    // so both `/profilis` and `/profilis/`-style mounts work as expected.
    const basePath = (()=>{
      const p = window.location.pathname;
      return p.endsWith('/') ? p : (p + '/');
    })();
    let chart;
    let countdown=4;
    async function fetchJSON(path){ const r = await fetch(path,{headers:authHeaders(),cache:'no-cache'}); if(!r.ok) throw new Error('HTTP '+r.status); return await r.json(); }
    function relTime(ms){
      const diff = Date.now() - ms;
      if(diff<1000) return diff+' ms ago';
      if(diff<60000) return Math.floor(diff/1000)+'s ago';
      return Math.floor(diff/60000)+'m ago';
    }
    async function refresh(){
      try{
        const m = await fetchJSON(basePath + 'metrics.json');
        // KPIs
        document.getElementById('rps').textContent = fmt(m.rps);
        document.getElementById('err').textContent = fmt(m.error_pct)+'%';
        document.getElementById('p50').textContent = (m.p50==null?'—':fmt(m.p50)+' ms');
        document.getElementById('p95').textContent = (m.p95==null?'—':fmt(m.p95)+' ms');
        // Sparkline
        const labels = Array.from({length:60},(_,i)=> i-59).map(x=> x%10===0? x+'s':'');
        const data = (m.spark||[]).map(Number);
        if(!chart){
          const ctx = document.getElementById('spark').getContext('2d');
          chart = new Chart(
            ctx, {
            type:'line',
            data:{
            labels,
            datasets:[
            { data, tension:.25, borderWidth:2, pointRadius:0 }
            ]},
            options:{
            responsive:true, maintainAspectRatio:false,
            plugins:{legend:{display:false}},
            scales:{
                x:{grid:{display:false},ticks:{color:'#8ba0c9',maxTicksLimit:8}},
                y:{
                    grid:{
                        color:'rgba(255,255,255,.07)'
                    },
                    ticks:{
                        color:'#8ba0c9',
                        precision:0
                    }
                }
            }
        }});
        } else { chart.data.datasets[0].data = data; chart.update('none'); }
        document.getElementById('status').textContent='Live';
        document.getElementById('status').className='ok';
        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        countdown=4;
      } catch(e){ document.getElementById('status').textContent='401/Offline'; document.getElementById('status').className='err'; }

      // Errors table
      try{
        const errs = await fetchJSON(basePath + 'errors.json');
        console.log(`Errors:`, errs);
        const tbody = document.getElementById('errs');
        tbody.innerHTML = errs.errors.map(e=>`<tr><td>${e.route}</td><td>${e.status}</td><td>${e.exception_type||''}</td><td>${relTime(e.ts_ns/1e6)}</td></tr>`).join('');
      } catch(_){ /* ignore */ }
    }
    setInterval(refresh, 4000);
    setInterval(()=>{ if(countdown>0) countdown--; document.getElementById('countdown').textContent = countdown; },1000);
    window.addEventListener('load', refresh);

    function download(path){
      fetchJSON(path).then(data=>{
        const blob = new Blob([JSON.stringify(data,null,2)],{type:"application/json"});
        const a=document.createElement("a");
        a.href=URL.createObjectURL(blob);
        a.download=path;
        a.click();
      });
    }

    function createIssue(type){
      // Get current dashboard state for context
      const currentUrl = window.location.href;
      const currentTime = new Date().toISOString();
      const userAgent = navigator.userAgent;

      let title, body, labels;

      if(type === 'bug') {
        title = "Bug Report from Profilis Dashboard";
        labels = "bug";
        body = `## Bug Report

**Dashboard URL:** ${currentUrl}
**Reported at:** ${currentTime}
**User Agent:** ${userAgent}

## Description
Please describe the bug you encountered:

## Steps to Reproduce
1.
2.
3.

## Expected Behavior
What should have happened?

## Actual Behavior
What actually happened?

## Additional Context
Any other information that might be helpful:

---
*This report was generated automatically from the Profilis dashboard.*`;
      } else {
        title = "Feature Request from Profilis Dashboard";
        labels = "enhancement";
        body = `## Feature Request

**Dashboard URL:** ${currentUrl}
**Requested at:** ${currentTime}
**User Agent:** ${userAgent}

## Description
Please describe the feature you would like to see:

## Use Case
How would this feature help you?

## Proposed Solution
Any ideas on how this could be implemented?

## Additional Context
Any other information that might be helpful:

---
*This request was generated automatically from the Profilis dashboard.*`;
      }

      // Encode for GitHub
      const encodedTitle = encodeURIComponent(title);
      const encodedBody = encodeURIComponent(body);
      const encodedLabels = encodeURIComponent(labels);

      // Open GitHub issues page with pre-filled content and labels
      const githubUrl = `https://github.com/ankan97dutta/profilis/issues/new?title=${encodedTitle}&body=${encodedBody}&labels=${encodedLabels}`;
      window.open(githubUrl, '_blank');
    }
  </script>
</head>
<body>
  <div class=\"wrap\">
    <!-- position the report bug link to the right of the screen -->
    <div class="report-section">
      <a href="#"
      style="color:var(--muted);text-decoration:none;font-size:12px;opacity:0.6;transition:opacity 0.2s ease;cursor:pointer"
      onclick="createIssue('bug')"> Report Bug </a>

      <span style="color:var(--muted);font-size:12px;opacity:0.6;transition:opacity 0.2s ease">|</span>

      <a href="#"
      style="color:var(--muted);text-decoration:none;font-size:12px;opacity:0.6;transition:opacity 0.2s ease;cursor:pointer"
      onclick="createIssue('enhancement')"> Request Feature </a>
    </div>
    <header>

      <svg width="32" height="32" viewBox="0 0 512 512"
            xmlns="http://www.w3.org/2000/svg">
        <!-- Profilis: Cool Tech Palette -->

        <!-- Outer ring -->
        <circle cx="256" cy="256" r="180" stroke="#2E3440" stroke-width="28" fill="none"/>

        <!-- Inner ring -->
        <circle cx="256" cy="256" r="108" stroke="#ECEFF4" stroke-width="20" fill="none"/>

        <!-- Flow curve -->
        <path d="M140 300 C200 180, 312 332, 372 212"
                stroke="#5E81AC" stroke-width="24" fill="none"
                stroke-linecap="round" stroke-linejoin="round"/>

        <!-- Handle -->
        <rect x="356" y="356" width="120" height="28" rx="14"
                transform="rotate(45 356 356)" fill="#2E3440"/>
        </svg>

      <h1>Profilis</h1>
      <span class=\"muted\" style=\"margin-left:auto\">Status: <strong id=\"status\">—</strong></span>
      <span class="timestamp">Last update: <span id="lastUpdate">—</span> | Refresh in <span id="countdown">4</span>s</span>
      <div style="display:flex;gap:6px;margin-left:auto">
        <button class="btn" onclick="download('metrics.json')" title="Download metrics">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Metrics
        </button>
        <button class="btn" onclick="download('errors.json')" title="Download errors">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Errors
        </button>

      <button class=\"btn\" onclick=\"toggleTheme()\" title=\"Toggle theme\">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      </div>

    </header>

    <section class=\"kpis\">
      <div class=\"card\"><div class=\"label\">Requests / sec</div><div class=\"value\" id=\"rps\">—</div></div>
      <div class=\"card\"><div class=\"label\">Error %</div><div class=\"value\" id=\"err\">—</div></div>
      <div class=\"card\"><div class=\"label\">p50 latency</div><div class=\"value\" id=\"p50\">—</div></div>
      <div class=\"card\"><div class=\"label\">p95 latency</div><div class=\"value\" id=\"p95\">—</div></div>
    </section>

    <section class=\"row\">
      <div class=\"card\" style=\"height:260px\"><canvas id=\"spark\"></canvas></div>
      <div class=\"card\">
        <div class=\"label\">Tip</div>
        <div class=\"muted\">Pass <code>?token=YOUR_TOKEN</code> once; it will be stored and sent as a Bearer header to <code>/metrics.json</code> & <code>/errors.json</code>.</div>

      </div>
    </section>

    <section class=\"card\" style=\"margin-top:12px\">
      <div class=\"label\">Recent errors</div>
      <table>
        <thead><tr><th>Route</th><th>Status</th><th>Exception</th><th>ts (ms)</th></tr></thead>
        <tbody id=\"errs\"></tbody>
      </table>
    </section>
  </div>
</body>
</html>"""


def make_ui_blueprint(
    stats: StatsStore, *, bearer_token: str | None = None, ui_prefix: str = ""
) -> Blueprint:
    """Create a Sanic Blueprint that serves the Profilis dashboard and JSON endpoints.

    Usage:
        stats = StatsStore()
        bp = make_ui_blueprint(stats, ui_prefix="/profilis")
        app.blueprint(bp)
    """
    bp = Blueprint("profilis_ui", url_prefix=ui_prefix)

    def _check_auth(request: Request) -> HTTPResponse | None:
        if bearer_token is None:
            return None
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return text("Unauthorized", status=401)
        token = auth.split(" ", 1)[1]
        if token != bearer_token:
            return text("Unauthorized", status=401)
        return None

    def _jsonify(
        data: dict[str, Any],
    ) -> HTTPResponse:
        # Use Sanic's JSON helper to set correct headers.
        return sanic_json(data)

    @bp.get("/metrics.json")
    async def metrics_json(request: Request) -> HTTPResponse:
        auth_resp = _check_auth(request)
        if auth_resp is not None:
            return auth_resp
        return _jsonify(stats.snapshot())

    @bp.get("/errors.json")
    async def errors_json(request: Request) -> HTTPResponse:
        auth_resp = _check_auth(request)
        if auth_resp is not None:
            return auth_resp
        ring = get_error_ring()
        empty_list: list[dict[str, str | int | None]] = []
        payload = {"errors": ring.dump() if ring else empty_list}
        return _jsonify(payload)

    @bp.get("/")
    async def dashboard(request: Request) -> HTTPResponse:
        auth_resp = _check_auth(request)
        if auth_resp is not None:
            return auth_resp
        # Explicitly set HTML content type so browsers render the dashboard.
        return HTTPResponse(_HTML, content_type="text/html; charset=utf-8")

    return bp
