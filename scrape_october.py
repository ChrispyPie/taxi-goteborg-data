#!/usr/bin/env python3
"""
Engångsscrape för hela oktober.
Scrapar dag för dag, hoppar över befintliga kvitton.
"""

import os
import json
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

STIG_URL = "https://stig.taxinet.se"
USERNAME = os.environ.get("STIG_USERNAME", "15201")
PASSWORD = os.environ.get("STIG_PASSWORD", "")

DRIVERS = [
    "154711", "169327", "179629", "179764", "179890",
    "417480", "459910", "472245", "631047", "682204",
    "693340", "710022", "738104", "788962", "829560", "844601"
]

def login(page):
    page.goto(f"{STIG_URL}/Login.aspx")
    page.wait_for_load_state("networkidle")
    page.select_option("select", label="Taxi Göteborg")
    page.fill("input[type='text']", USERNAME)
    page.fill("input[type='password']", PASSWORD)
    page.click("input[type='submit'], button, input[value*='Logga']")
    page.wait_for_load_state("networkidle")
    return "Login.aspx" not in page.url

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
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)

    receipts = []
    rows = page.query_selector_all("table tr")
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) >= 5 and "-" in cells[4]:
            receipts.append(cells[4])
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

def fetch_shifts(page, forar_id, from_date, to_date):
    page.goto(f"{STIG_URL}/Passrapport.aspx")
    page.wait_for_load_state("networkidle")
    page.evaluate(f"""
        () => {{
            document.getElementById('MainContent_tbxForarId').value = '{forar_id}';
            document.getElementById('MainContent_tbxFromDat').value = '{from_date}';
            document.getElementById('MainContent_tbxTomDat').value = '{to_date}';
        }}
    """)
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    shifts = []
    rows = page.query_selector_all("table tr")
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) >= 8 and cells[0].startswith('A'):
            shifts.append({
                "taxi": cells[0],
                "start": cells[1],
                "slut": cells[2],
                "tid": cells[3],
                "passnr": cells[8] if len(cells) > 8 else "",
                "resor": cells[9] if len(cells) > 9 else "",
                "forar": forar_id
            })
    return shifts

def scrape_driver(page, forar_id, existing, start_date, end_date):
    new_count = 0
    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        receipts = scrape_day(page, forar_id, date_str)
        for kvitto in receipts:
            if kvitto in existing:
                continue
            detail = scrape_trip_detail(page, kvitto)
            existing[kvitto] = {"kvittonr": kvitto, "forar": forar_id, **detail}
            new_count += 1
            print(f"    Ny: {kvitto}")
        current += timedelta(days=1)
    return new_count

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas")
        return

    try:
        with open("data.json", "r") as f:
            data = json.load(f)
    except:
        data = {"trips": [], "shifts": []}

    existing = {t.get("kvittonr"): t for t in data.get("trips", [])}

    seen = set()
    all_shifts = []
    for s in data.get("shifts", []):
        forar = s.get("forar") or "710022"
        key = (s.get("passnr"), forar)
        if key not in seen:
            seen.add(key)
            s["forar"] = forar
            all_shifts.append(s)

    # Oktober 1 till idag
    start_date = datetime(2026, 10, 1)
    end_date = datetime.now()
    from_str = start_date.strftime("%Y-%m-%d")
    to_str = end_date.strftime("%Y-%m-%d")

    print(f"Scrapar {from_str} till {to_str}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        total_new = 0
        for forar_id in DRIVERS:
            print(f"Förare {forar_id}:")
            new_count = scrape_driver(page, forar_id, existing, start_date, end_date)
            total_new += new_count
            new_shifts = fetch_shifts(page, forar_id, from_str, to_str)
            added = 0
            for s in new_shifts:
                key = (s.get("passnr"), forar_id)
                if key not in seen:
                    seen.add(key)
                    all_shifts.append(s)
                    added += 1
            print(f"  {new_count} nya kvitton, {added} nya skift")

        data["trips"] = list(existing.values())
        data["shifts"] = all_shifts
        data["last_updated"] = datetime.utcnow().isoformat() + "Z"

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Totalt {total_new} nya kvitton, {len(all_shifts)} skift")
        browser.close()

if __name__ == "__main__":
    main()