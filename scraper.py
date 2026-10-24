#!/usr/bin/env python3
"""
STIG scraper – hämtar data för alla förare.
Körs varje timme via GitHub Actions.
Scrapar gårdagen + idag. Hoppar över befintliga kvitton.

Manuell körning med datum:
  SCRAPE_FROM=2026-10-01 SCRAPE_TO=2026-10-03 python scraper.py

Exit-koder: 0 = ok, 1 = STIG nåddes inte / inloggning misslyckades,
2 = fel för någon förare, 3 = fel i passrapport-steget (resorna sparas ändå).
"""

import os
import sys
import time
import json
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from tripkey import TripIndex, is_superseded, shift_key
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# Status för varje körning skrivs till scrape_status.json (committas inte).
# Workflowet skickar den till Supabase så att appen kan visa om servern är uppe.
RUN_STARTED = datetime.utcnow().isoformat() + "Z"
_status_written = False


def write_status(result, message="", new_trips=None):
    global _status_written
    _status_written = True
    try:
        with open("scrape_status.json", "w", encoding="utf-8") as f:
            json.dump({"result": result, "message": message[:300], "started_at": RUN_STARTED,
                       "finished_at": datetime.utcnow().isoformat() + "Z", "new_trips": new_trips}, f)
    except Exception as e:
        print(f"Kunde inte skriva scrape_status.json: {e}")

STIG_URL = os.environ.get("STIG_BASE_URL", "https://stig.taxinet.se")
USERNAME = os.environ.get("STIG_USERNAME", "15201")
PASSWORD = os.environ.get("STIG_PASSWORD", "")

DRIVERS = [
    "154711", "169327", "179629", "179764", "179890",
    "417480", "459910", "472245", "631047", "682204",
    "693340", "710022", "738104", "788962", "829560", "844601"
]

LOGIN_ATTEMPTS = 3
LOGIN_TIMEOUT_MS = 60_000
LOGIN_BACKOFF_S = [30, 60]
MAX_KM_LOOKUPS = int(os.environ.get("MAX_KM_LOOKUPS", "30"))
REFETCHED = set()  # resor som redan hämtats om i denna körning


class StigUnreachable(Exception):
    pass


def open_login_page(page):
    """Öppna Login.aspx med omförsök. Kastar StigUnreachable om alla försök misslyckas."""
    last_error = None
    for attempt in range(1, LOGIN_ATTEMPTS + 1):
        try:
            page.goto(f"{STIG_URL}/Login.aspx", timeout=LOGIN_TIMEOUT_MS)
            page.wait_for_load_state("networkidle", timeout=LOGIN_TIMEOUT_MS)
            return
        except PlaywrightTimeoutError as e:
            last_error = e
            print(f"Login.aspx svarade inte (försök {attempt}/{LOGIN_ATTEMPTS})", flush=True)
            if attempt < LOGIN_ATTEMPTS:
                wait_s = LOGIN_BACKOFF_S[min(attempt - 1, len(LOGIN_BACKOFF_S) - 1)]
                print(f"  Väntar {wait_s} s innan nytt försök...", flush=True)
                time.sleep(wait_s)
    raise StigUnreachable(str(last_error).splitlines()[0] if last_error else "")


def login(page):
    open_login_page(page)
    page.select_option("select", label="Taxi Göteborg")
    page.fill("input[type='text']", USERNAME)
    page.fill("input[type='password']", PASSWORD)
    page.click("input[type='submit'], button, input[value*='Logga']")
    page.wait_for_load_state("networkidle")
    return "Login.aspx" not in page.url

# Fullständighetskontroll: en befintlig post hoppas bara över om den är KOMPLETT.
# Resa: kvittonr, förare, startdatum (ÅÅÅÅ-MM-DD), starttid (HH:MM), startzon, kredittyp och belopp måste finnas.
# Pass: passnr, förare, start, slut, tid och antal resor måste finnas (km hämtas separat och räknas inte här).
TRIP_REQUIRED = ("kvittonr", "forar", "startdatum", "starttid", "startzon", "kredittyp", "belopp")
SHIFT_REQUIRED = ("passnr", "forar", "start", "slut", "tid", "resor")


def _filled(v):
    return v is not None and str(v).strip() != ""


def trip_complete(t):
    return all(_filled(t.get(k)) for k in TRIP_REQUIRED) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(t.get("startdatum"))) is not None


def shift_complete(s):
    return all(_filled(s.get(k)) for k in SHIFT_REQUIRED)


def merge_fields(old, new):
    """Fyll i/uppdatera fält från ny hämtning, men skriv aldrig över med tomma värden."""
    for k, v in new.items():
        if _filled(v):
            old[k] = v
    return old


def scrape_day(page, forar_id, date_str):
    page.goto(f"{STIG_URL}/Resaposter.aspx")
    page.wait_for_load_state("networkidle")
    page.evaluate(f"""
        () => {{
            document.getElementById('MainContent_tb_Forarid').value = '{forar_id}';
            document.getElementById('MainContent_tb_ResdatumFom').value = '{date_str}';
            document.getElementById('MainContent_tb_ResdatumTom').value = '{date_str}';
        }}
    """)
    page.click("input[value='Sök']")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    receipts = []
    tables = page.query_selector_all("table")
    for table in tables:
        header = table.query_selector("tr")
        if header and "Kvittonr" in header.inner_text():
            rows = table.query_selector_all("tr")
            for row in rows[1:]:
                cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
                if len(cells) >= 5 and "-" in cells[4]:
                    receipts.append(cells[4])
            break
    return receipts

def scrape_trip_detail(page, kvitto):
    try:
        page.click(f"text={kvitto}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(300)
        detail = page.evaluate("""
            () => {
                const get = (id) => {
                    const el = document.getElementById(id);
                    return el ? el.value : '';
                };
                return {
                    startzon: get('MainContent_tb_valdresa_Startzon'),
                    slutzon: get('MainContent_tb_valdresa_Slutzon'),
                    kilometer: get('MainContent_tb_valdresa_Kilometer2'),
                    dricks: get('MainContent_tb_valdresa_Dricks'),
                    kredittyp: get('MainContent_ddl_valdresa_Kredittyp'),
                    belopp: get('MainContent_tb_valdresa_Taxameterbelopp'),
                    starttid: get('MainContent_tb_valdresa_Starttid'),
                    sluttid: get('MainContent_tb_valdresa_Sluttid'),
                    startdatum: get('MainContent_tb_valdresa_Startdatum')
                };
            }
        """)
        page.go_back()
        page.wait_for_load_state("networkidle")
        return detail
    except Exception as e:
        print(f"Detalj misslyckades för {kvitto}: {e}")
        return {}

# Läser alla passrader som ren data i ett enda page.evaluate-anrop.
# Inga ElementHandles hålls kvar mellan navigeringar (det var det som kraschade).
READ_SHIFT_ROWS_JS = """
() => {
    const out = [];
    for (const row of document.querySelectorAll('tr')) {
        const cells = Array.from(row.querySelectorAll(':scope > td')).map(c => c.innerText.trim());
        if (cells.length >= 8 && cells[0].startsWith('A')) out.push(cells);
    }
    return out;
}
"""

# Klickar på detaljknappen för raden med exakt detta passnr. Returnerar true om klick skedde.
CLICK_SHIFT_JS = """
(passnr) => {
    for (const row of document.querySelectorAll('tr')) {
        const cells = row.querySelectorAll(':scope > td');
        if (cells.length > 8 && cells[8].innerText.trim() === passnr) {
            const btn = row.querySelector('input[type="image"]');
            if (btn) { btn.click(); return true; }
        }
    }
    return false;
}
"""


def search_passrapport(page, forar_id, from_date, to_date):
    page.goto(f"{STIG_URL}/Passrapport.aspx")
    page.wait_for_load_state("networkidle")
    page.evaluate(
        """([forar, fom, tom]) => {
            document.getElementById('MainContent_tbxForarId').value = forar;
            document.getElementById('MainContent_tbxFromDat').value = fom;
            document.getElementById('MainContent_tbxTomDat').value = tom;
        }""",
        [forar_id, from_date, to_date],
    )
    page.click("input[value='Sök']")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)


def parse_shift_rows(rows):
    shifts = []
    for cells in rows:
        shifts.append({
            "taxi": cells[0],
            "start": cells[1],
            "slut": cells[2],
            "tid": cells[3],
            "passnr": cells[8] if len(cells) > 8 else "",
            "resor": cells[9] if len(cells) > 9 else "",
            "forar": cells[7] if len(cells) > 7 else "",
        })
    return shifts


def shift_date(start):
    """'20261018 \xa018:08' -> '2026-10-18' (eller '' om okänt format)."""
    d = (start or "").replace("\xa0", " ").split()
    if d and len(d[0]) == 8 and d[0].isdigit():
        return f"{d[0][:4]}-{d[0][4:6]}-{d[0][6:8]}"
    return ""


def get_shift_km(page, shift):
    """Hämta km för ett pass med en ny sökning (förare + datum), aldrig page.go_back()."""
    date_str = shift_date(shift.get("start"))
    if not date_str or not shift.get("passnr"):
        return None
    search_passrapport(page, shift.get("forar", ""), date_str, date_str)
    if not page.evaluate(CLICK_SHIFT_JS, shift["passnr"]):
        return None
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    match = re.search(r'Totalt antal km i pass:\s*([\d,]+)', page.inner_text("body"))
    return match.group(1).replace(',', '.') if match else None


def fetch_all_shifts(page, from_date, to_date, existing_km):
    """Sök passrapport en gång för alla förare, hämta sedan km för pass som saknar det."""
    search_passrapport(page, "", from_date, to_date)
    shifts = parse_shift_rows(page.evaluate(READ_SHIFT_ROWS_JS))

    lookups = 0
    for s in shifts:
        key = shift_key(s)
        if existing_km.get(key):
            s["km"] = existing_km[key]
            continue
        if lookups >= MAX_KM_LOOKUPS:
            s["km"] = None
            continue
        lookups += 1
        try:
            s["km"] = get_shift_km(page, s)
        except Exception as e:
            print(f"  km misslyckades för pass {s['passnr']}: {str(e).splitlines()[0]}")
            s["km"] = None
    print(f"  {len(shifts)} pass i passrapporten, {lookups} km-uppslag")
    return shifts


def save_data(data):
    """Skriv data.json atomiskt så att en krasch aldrig lämnar en halv fil."""
    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    tmp = "data.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, "data.json")


def scrape_driver(page, forar_id, existing, start_date, end_date):
    new_count = 0
    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        receipts = scrape_day(page, forar_id, date_str)
        for kvitto in receipts:
            key = (kvitto, forar_id, date_str)
            found = existing.find(kvitto, forar_id, date_str)
            if found is None and is_superseded(existing, kvitto, forar_id, date_str):
                continue  # en rättad version (-02 o.s.v.) finns redan; -01 hämtas inte
            if found is not None:
                # Komplett post: hoppa över (sparar anrop). Ofullständig: hämta om, högst en gång per körning.
                if trip_complete(found) or key in REFETCHED:
                    continue
                REFETCHED.add(key)
                detail = scrape_trip_detail(page, kvitto)
                merge_fields(found, {"kvittonr": kvitto, "forar": forar_id, **detail})
                print(f"    Kompletterad: {kvitto}")
                continue
            detail = scrape_trip_detail(page, kvitto)
            existing.add({"kvittonr": kvitto, "forar": forar_id, **detail})
            new_count += 1
            print(f"    Ny: {kvitto}")
        current += timedelta(days=1)
    return new_count

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas")
        write_status("error", "inloggningsuppgifter saknas")
        return

    try:
        with open("data.json", "r") as f:
            data = json.load(f)
    except:
        data = {"trips": [], "shifts": []}

    # Äldre testposter saknar ibland "forar"; de gäller 710022 (samma regel som i Supabase-importen)
    trips_list = data.get("trips", [])
    existing = TripIndex(trips_list)   # nyckel: taxi + förare + kvittonr + startdatum (se tripkey.py)

    seen = set()
    all_shifts = []
    existing_km = {}
    for s in data.get("shifts", []):
        forar = s.get("forar") or "710022"
        s["forar"] = forar
        key = shift_key(s)
        if key not in seen:
            seen.add(key)
            all_shifts.append(s)
            if s.get("km"):
                existing_km[key] = s.get("km")

    today = datetime.now()
    from_env = os.environ.get("SCRAPE_FROM", "")
    to_env = os.environ.get("SCRAPE_TO", "")

    if from_env:
        start_date = datetime.strptime(from_env, "%Y-%m-%d")
    else:
        start_date = today - timedelta(days=1)

    if to_env:
        end_date = datetime.strptime(to_env, "%Y-%m-%d")
    else:
        end_date = today

    from_str = start_date.strftime("%Y-%m-%d")
    to_str = end_date.strftime("%Y-%m-%d")

    print(f"Scrapar {from_str} till {to_str}")
    print(f"Skift med km: {len(existing_km)}")

    exit_code = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            logged_in = login(page)
        except StigUnreachable as e:
            print(f"::error::STIG unreachable (Login.aspx timeout) efter {LOGIN_ATTEMPTS} försök")
            print(f"STIG unreachable (Login.aspx timeout): {e}")
            write_status("unreachable", "Login.aspx svarade inte")
            browser.close()
            sys.exit(1)

        if not logged_in:
            print("Inloggning misslyckades (fel användarnamn/lösenord eller ändrad inloggningssida)")
            write_status("login_failed", "inloggningen misslyckades")
            browser.close()
            sys.exit(1)

        # 1) Kvitton/resor
        total_new = 0
        for forar_id in DRIVERS:
            print(f"Förare {forar_id}:")
            try:
                new_count = scrape_driver(page, forar_id, existing, start_date, end_date)
            except Exception as e:
                print(f"  FEL för förare {forar_id}: {str(e).splitlines()[0]}")
                exit_code = 2
                continue
            total_new += new_count
            print(f"  {new_count} nya kvitton")

        # Spara resorna direkt, innan passteget, så att de aldrig går förlorade
        data["trips"] = existing.all()
        data["shifts"] = all_shifts
        save_data(data)
        print(f"Sparade {len(data['trips'])} resor ({total_new} nya)")

        # 2) Pass/skift
        print("Söker passrapport...")
        try:
            new_shifts = fetch_all_shifts(page, from_str, to_str, existing_km)
            added = refreshed = 0
            for s in new_shifts:
                key = shift_key(s)
                if key not in seen:
                    seen.add(key)
                    all_shifts.append(s)
                    added += 1
                    continue
                # Befintligt pass som saknar fält kompletteras från passrapporten (inga extra anrop)
                for existing_s in all_shifts:
                    if shift_key(existing_s) == key and not shift_complete(existing_s):
                        merge_fields(existing_s, {k: v for k, v in s.items() if k != "km"})
                        refreshed += 1
                        break
                if s.get("km") and key not in existing_km:
                    for existing_s in all_shifts:
                        if shift_key(existing_s) == key:
                            existing_s["km"] = s.get("km")
                            existing_km[key] = s.get("km")
                            break
            print(f"{added} nya skift, {refreshed} kompletterade")
            data["shifts"] = all_shifts
            save_data(data)
        except Exception as e:
            print(f"::error::FEL i passrapport-steget (resorna är redan sparade): {type(e).__name__}: {str(e).splitlines()[0]}")
            exit_code = 3

        print(f"Totalt {total_new} nya kvitton, {len(all_shifts)} skift")
        write_status("ok" if exit_code == 0 else "partial", f"exit {exit_code}", total_new)
        browser.close()

    if exit_code:
        sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except PlaywrightTimeoutError as e:
        if not _status_written:
            write_status("unreachable", f"timeout: {str(e).splitlines()[0]}")
        raise
    except SystemExit:
        raise
    except Exception as e:
        if not _status_written:
            write_status("error", f"{type(e).__name__}")
        raise