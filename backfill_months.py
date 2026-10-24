#!/usr/bin/env python3
"""Hämtar månadsrapporter (passfil + resapostfil) för flera månader i EN session, försiktigt.
- Filen väljs på NAMN (pass{ÅÅÅÅMM}Medl… / resapost{ÅÅÅÅMM}Medl…), aldrig på position i listan.
- Varje nedladdad fil kontrolleras: rätt rubrikrad och att datumen i filen gäller rätt månad.
- 2–3 min paus mellan månader, inget parallellt. Stoppar vid 429/5xx, svar > 15 s, inloggningsfel eller ändrad layout.
- Pausar (avslutar snällt) om klockan närmar sig timjobbet (:03–:12); kör om med de månader som är kvar.
- Sparar rådata i staging (private.probe_reports via RPC probe_put, kind bf_pass/bf_resa). Loggen visar bara antal.
Användning: BF_MONTHS="2026-01,2026-02" eller BF_YEAR=2025 (12 månader)."""
import os, re, sys, time, json, urllib.request
from datetime import datetime
from playwright.sync_api import sync_playwright

STIG_URL = os.environ.get("STIG_BASE_URL", "https://stig.taxinet.se")
USERNAME = os.environ.get("STIG_USERNAME", "")
PASSWORD = os.environ.get("STIG_PASSWORD", "")
SB_URL = "https://lpfdryvukqmjlgenuzpb.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
LIMIT_MS = 15_000
STEP_PAUSE_S = 5
MONTH_PAUSE_S = int(os.environ.get("BF_PAUSE_S", "150"))
HEAD = {"pass": "TAXINR;ARBPASSNR;ForarNr;PassStart;PassSlut", "resa": "KVITTONR;DAT_START;TID_START;DAT_SLUT;TID_SLUT;FORAR_ID"}
DATECOL = {"pass": 3, "resa": 1}   # 0-baserat: PassStart resp. DAT_START
PREFIX = {"pass": "pass", "resa": "resapost"}
bad = []


def months():
    if os.environ.get("BF_YEAR"):
        y = int(os.environ["BF_YEAR"])
        return [f"{y}-{m:02d}" for m in range(1, 13)]
    ms = [m.strip() for m in os.environ.get("BF_MONTHS", "").split(",") if m.strip()]
    for m in ms:
        if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", m):
            print(f"Ogiltig månad: {m}"); sys.exit(2)
    return ms


def put(month, kind, body):
    headers = {"apikey": KEY, "Content-Type": "application/json"}
    if not KEY.startswith("sb_"):
        headers["Authorization"] = "Bearer " + KEY
    req = urllib.request.Request(SB_URL + "/rest/v1/rpc/probe_put", method="POST", headers=headers,
        data=json.dumps({"p_month": month, "p_kind": kind, "p_body": body}).encode())
    with urllib.request.urlopen(req, timeout=60) as r:
        r.read()


def near_hourly():
    return 3 <= datetime.now().minute <= 12


def check_http():
    if bad:
        print(f"STOPP: HTTP-status {sorted(set(bad))}"); sys.exit(4)


GRID_JS = """() => { const g = document.getElementById('MainContent_gv_FileList'); if (!g) return null;
  return Array.from(g.querySelectorAll('tr')).map(r => Array.from(r.querySelectorAll('th,td')).map(c => c.innerText.trim())); }"""
DL_JS = """async (arg) => { const form = document.querySelector('form'); const fd = new FormData(form);
  fd.set('__EVENTTARGET', 'ctl00$MainContent$gv_FileList'); fd.set('__EVENTARGUMENT', 'Select$' + arg);
  const t = Date.now(); const resp = await fetch('/MedlemsRapporter.aspx', { method: 'POST', body: fd });
  const txt = await resp.text(); return {status: resp.status, ms: Date.now() - t, len: txt.length, text: txt}; }"""


def verify(kind, ym, text):
    lines = [l for l in text.replace("\r", "").split("\n") if l.strip()]
    if not lines or not lines[0].startswith(HEAD[kind]):
        return f"fel rubrikrad i {kind}-filen (ändrad layout eller utloggad)"
    want = ym.replace("-", "")
    dates = [l.split(";")[DATECOL[kind]][:6] for l in lines[1:] if len(l.split(";")) > DATECOL[kind]]
    if not dates:
        return None  # tom månad är ok
    share = sum(d == want for d in dates) / len(dates)
    if share < 0.8:
        return f"{kind}-filen gäller inte {ym} (bara {share:.0%} av raderna)"
    return None


def main():
    ms = months()
    if not (USERNAME and PASSWORD and KEY and ms):
        print("Uppgifter eller månader saknas"); sys.exit(1)
    done = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(); page = ctx.new_page()
        page.on("response", lambda r: bad.append(r.status) if (r.status == 429 or r.status >= 500) else None)

        def login():
            t = time.time()
            page.goto(f"{STIG_URL}/Login.aspx", timeout=LIMIT_MS)
            page.wait_for_load_state("networkidle", timeout=LIMIT_MS)
            page.select_option("select", label="Taxi Göteborg")
            page.fill("input[type='text']", USERNAME)
            page.fill("input[type='password']", PASSWORD)
            page.click("input[type='submit'], button, input[value*='Logga']")
            page.wait_for_load_state("networkidle", timeout=LIMIT_MS)
            print(f"inloggning: {int((time.time()-t)*1000)} ms", flush=True)
            check_http()
            if "Login.aspx" in page.url:
                print("STOPP: inloggning misslyckades"); sys.exit(1)
            time.sleep(STEP_PAUSE_S)

        def file_list():
            t = time.time()
            page.goto(f"{STIG_URL}/MedlemsRapporter.aspx", timeout=LIMIT_MS)
            page.wait_for_load_state("networkidle", timeout=LIMIT_MS)
            grid = page.evaluate(GRID_JS)
            print(f"fillista: {int((time.time()-t)*1000)} ms, {max(0, len(grid or []) - 1)} filer", flush=True)
            check_http()
            if "Login.aspx" in page.url:
                return None
            if not grid or len(grid) < 2 or not grid[0] or grid[0][0] != "Filnamn":
                print("STOPP: ändrad layout på fillistan"); sys.exit(6)
            time.sleep(STEP_PAUSE_S)
            return [r[0] for r in grid[1:]]

        try:
            login()
            names = file_list()
            relogged = False
            for i, ym in enumerate(ms):
                if i > 0:
                    print(f"paus {MONTH_PAUSE_S} s", flush=True)
                    time.sleep(MONTH_PAUSE_S)
                if near_hourly():
                    print(f"PAUS för timjobbet. Klara: {','.join(done) or '-'}. Kvar: {','.join(ms[i:])}")
                    break
                for kind in ("pass", "resa"):
                    fname = f"{PREFIX[kind]}{ym.replace('-', '')}Medl"
                    hits = [j for j, n in enumerate(names) if n.startswith(fname)]
                    if len(hits) != 1:
                        print(f"STOPP: hittade {len(hits)} filer som heter {fname}…"); sys.exit(6)
                    r = page.evaluate(DL_JS, hits[0])
                    print(f"{ym} {kind}: status {r['status']}, {r['ms']} ms, {r['len']} byte", flush=True)
                    check_http()
                    if r["status"] != 200 or r["ms"] > LIMIT_MS:
                        print("STOPP: fel status eller för långsamt"); sys.exit(4)
                    err = verify(kind, ym, r["text"])
                    if err and not relogged and "rubrikrad" in err:
                        print("sessionen verkar ha gått ut; loggar in igen (en gång)")
                        relogged = True
                        login(); names = file_list()
                        if names is None:
                            print("STOPP: kom inte in igen"); sys.exit(1)
                        hits = [j for j, n in enumerate(names) if n.startswith(fname)]
                        if len(hits) != 1:
                            print("STOPP: filen saknas efter ny inloggning"); sys.exit(6)
                        r = page.evaluate(DL_JS, hits[0]); check_http()
                        err = verify(kind, ym, r["text"])
                    if err:
                        print(f"STOPP: {err}"); sys.exit(7)
                    n = len([l for l in r["text"].split("\n") if l.strip()]) - 1
                    put(ym, "bf_" + kind, r["text"])
                    print(f"  {ym} {kind}: {n} rader kontrollerade och sparade", flush=True)
                    time.sleep(STEP_PAUSE_S)
                done.append(ym)
                print(f"KLAR {ym}", flush=True)
            print(f"Klara månader: {','.join(done) or '-'}")
        finally:
            try:
                lo = page.locator("a:has-text('Logga ut'), input[value*='Logga ut'], a[href*='Logout'], a[href*='LoggaUt']")
                if lo.count():
                    lo.first.click(timeout=LIMIT_MS); page.wait_for_load_state("networkidle", timeout=LIMIT_MS)
                    print("utloggad")
            except Exception as e:
                print(f"utloggning: {type(e).__name__}")
            ctx.close(); b.close()


if __name__ == "__main__":
    main()
