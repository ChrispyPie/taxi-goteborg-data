#!/usr/bin/env python3
"""Engångs-testhämtning av månadsrapport (en session, försiktigt).
Sparar rådata i Supabase-staging (private.probe_reports) via RPC probe_put.
Skriver bara antal/status i loggen (repot är publikt) – aldrig persondata eller hemligheter.
Stoppar vid fel, HTTP 429/5xx eller svar långsammare än 15 s."""
import os, re, sys, time, json, urllib.request
from playwright.sync_api import sync_playwright

STIG_URL = os.environ.get("STIG_BASE_URL", "https://stig.taxinet.se")
USERNAME = os.environ.get("STIG_USERNAME", "")
PASSWORD = os.environ.get("STIG_PASSWORD", "")
MONTH = os.environ.get("PROBE_MONTH", "2026-08")
OLD_MONTH = os.environ.get("PROBE_OLD_MONTH", "2020-01")
SB_URL = "https://lpfdryvukqmjlgenuzpb.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
LIMIT_MS = 15_000
PAUSE_S = 5
bad = []

def put(kind, body, month=MONTH):
    headers = {"apikey": KEY, "Content-Type": "application/json"}
    if not KEY.startswith("sb_"):
        headers["Authorization"] = "Bearer " + KEY
    req = urllib.request.Request(SB_URL + "/rest/v1/rpc/probe_put", method="POST", headers=headers,
        data=json.dumps({"p_month": month, "p_kind": kind, "p_body": body}).encode())
    with urllib.request.urlopen(req, timeout=60) as r:
        r.read()

def step(name, fn):
    t = time.time()
    res = fn()
    ms = int((time.time() - t) * 1000)
    print(f"{name}: {ms} ms", flush=True)
    if bad:
        print(f"STOPP: HTTP-status {sorted(set(bad))}"); raise SystemExit(4)
    if ms > LIMIT_MS + 3000:  # +3 s för fasta väntetider i steget
        print("STOPP: för långsamt svar"); raise SystemExit(5)
    time.sleep(PAUSE_S)
    return res

GRID_JS = """() => { const g = document.getElementById('MainContent_gv_FileList'); if (!g) return null;
  return Array.from(g.querySelectorAll('tr')).map(r => Array.from(r.querySelectorAll('th,td')).map(c => c.innerText.trim())); }"""
SELECTS_JS = """() => Array.from(document.querySelectorAll('select')).map(s => ({id: s.id || s.name,
  opts: Array.from(s.options).map(o => o.text.trim())}))"""
INPUTS_JS = """() => Array.from(document.querySelectorAll('input')).filter(i => i.type !== 'hidden' && i.type !== 'password')
  .map(i => ({id: i.id, type: i.type, value: i.type === 'text' ? i.value : '', ph: i.placeholder || ''}))"""
DL_JS = """async (arg) => { const form = document.querySelector('form'); const fd = new FormData(form);
  fd.set('__EVENTTARGET', 'ctl00$MainContent$gv_FileList'); fd.set('__EVENTARGUMENT', 'Select$' + arg);
  const t = Date.now(); const resp = await fetch('/MedlemsRapporter.aspx', { method: 'POST', body: fd });
  const txt = await resp.text(); return {status: resp.status, ms: Date.now() - t, len: txt.length, text: txt}; }"""

def search(page, ym):
    page.goto(f"{STIG_URL}/MedlemsRapporter.aspx", timeout=LIMIT_MS)
    page.wait_for_load_state("networkidle", timeout=LIMIT_MS)
    page.fill("#MainContent_tb_sok_Datum", ym)
    page.click("#MainContent_btn_Sok")
    page.wait_for_load_state("networkidle", timeout=LIMIT_MS)
    page.wait_for_timeout(1500)
    return page.evaluate(GRID_JS)

def main():
    if not (USERNAME and PASSWORD and KEY):
        print("Uppgifter saknas"); sys.exit(1)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(); page = ctx.new_page()
        page.on("response", lambda r: bad.append(r.status) if (r.status == 429 or r.status >= 500) else None)
        try:
            def login():
                page.goto(f"{STIG_URL}/Login.aspx", timeout=LIMIT_MS)
                page.wait_for_load_state("networkidle", timeout=LIMIT_MS)
                page.select_option("select", label="Taxi Göteborg")
                page.fill("input[type='text']", USERNAME)
                page.fill("input[type='password']", PASSWORD)
                page.click("input[type='submit'], button, input[value*='Logga']")
                page.wait_for_load_state("networkidle", timeout=LIMIT_MS)
                return "Login.aspx" not in page.url
            if not step("inloggning", login):
                print("STOPP: inloggning misslyckades"); sys.exit(1)

            grid = step(f"sök {MONTH}", lambda: search(page, MONTH))
            meta = {"selects": page.evaluate(SELECTS_JS), "inputs": page.evaluate(INPUTS_JS), "grid": grid}
            put("meta", json.dumps(meta, ensure_ascii=False))
            dates = sorted({m for s in meta["selects"] for o in s["opts"] for m in re.findall(r"(?:19|20)\d\d-?\d\d", o)})
            print(f"väljare: {len(meta['selects'])} st, datumliknande val: {len(dates)} st, tidigast {dates[0] if dates else '-'}")
            if not grid or len(grid) < 2:
                print("STOPP: ingen fillista"); sys.exit(6)
            rows = grid[1:]
            print(f"filer för {MONTH}: {len(rows)} st")
            def find(word):
                hits = [i for i, r in enumerate(rows) if any(word in c.lower() for c in r)]
                return hits[0] if len(hits) == 1 else None
            ip, it = find("pass"), find("resa")
            if ip is None or it is None:
                print(f"Namnsökning otydlig (pass={ip}, resa={it}); använder index 2/3 som import_monthly.py")
                ip, it = 2, 3
            for kind, idx in (("pass", ip), ("resa", it)):
                r = step(f"hämta {kind}", lambda: page.evaluate(DL_JS, idx))
                print(f"  {kind}: status {r['status']}, {r['ms']} ms, {r['len']} byte")
                if r["status"] != 200 or r["ms"] > LIMIT_MS:
                    print("STOPP"); sys.exit(4)
                put(kind, r["text"])

            old = step(f"sök {OLD_MONTH} (bara lista)", lambda: search(page, OLD_MONTH))
            put("meta_old", json.dumps({"grid": old}, ensure_ascii=False), OLD_MONTH)
            print(f"filer för {OLD_MONTH}: {max(0, len(old) - 1) if old else 0} st")
        finally:
            try:
                lo = page.locator("a:has-text('Logga ut'), input[value*='Logga ut'], a[href*='Logout'], a[href*='LoggaUt']")
                if lo.count():
                    lo.first.click(timeout=LIMIT_MS); page.wait_for_load_state("networkidle", timeout=LIMIT_MS)
                    print("utloggad")
                else:
                    print("ingen utloggningslänk hittad; stänger sessionen")
            except Exception as e:
                print(f"utloggning: {type(e).__name__}")
            ctx.close(); b.close()

if __name__ == "__main__":
    main()
