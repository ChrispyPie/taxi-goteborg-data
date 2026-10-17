#!/usr/bin/env python3
"""
STIG scraper – hämtar körningar dag för dag.
Börjar från 1 oktober för att bygga databasen.
-2 kvitton ersätter motsvarande -1.
"""

import os
import json
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

STIG_URL = "https://stig.taxinet.se"
USERNAME = os.environ.get("STIG_USERNAME", "15201")
PASSWORD = os.environ.get("STIG_PASSWORD", "")

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
    page.wait_for_timeout(800)

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
        page.wait_for_timeout(400)
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

def fetch_shifts(page, forar_id):
    page.goto(f"{STIG_URL}/Passrapport.aspx")
    page.wait_for_load_state("networkidle")
    page.evaluate(f"""
        () => {{
            document.getElementById('MainContent_tbxForarId').value = '{forar_id}';
            document.getElementById('MainContent_tbxFromDat').value = '2026-10-01';
            document.getElementById('MainContent_tbxTomDat').value = '2026-10-17';
        }}
    """)
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)

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
                "resor": cells[9] if len(cells) > 9 else ""
            })
    return shifts

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas")
        return

    forar_id = "710022"

    try:
        with open("data.json", "r") as f:
            data = json.load(f)
    except:
        data = {"trips": [], "shifts": []}

    trips = data.get("trips", [])
    existing_kvitton = {t.get("kvittonr") for t in trips}

    # För databasbygge: börja från 1 oktober
    # Senare: börja från igår
    start_date = datetime(2026, 10, 1)
    today = datetime.now()

    print(f"Börjar från: {start_date.strftime('%Y-%m-%d')}")
    print(f"Till: {today.strftime('%Y-%m-%d')}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        new_trips = []
        replaced = 0
        current = start_date
        while current <= today:
            date_str = current.strftime("%Y-%m-%d")
            print(f"Söker {date_str}...")
            receipts = scrape_day(page, forar_id, date_str)
            for kvitto in receipts:
                if kvitto.endswith("-02"):
                    base = kvitto[:-3] + "-01"
                    trips = [t for t in trips if t.get("kvittonr") != base]
                    print(f"  Ersätter {base} med {kvitto}")
                    detail = scrape_trip_detail(page, kvitto)
                    trips.append({"kvittonr": kvitto, **detail})
                    replaced += 1
                elif kvitto not in existing_kvitton:
                    print(f"  Hämtar {kvitto}")
                    detail = scrape_trip_detail(page, kvitto)
                    new_trips.append({"kvittonr": kvitto, **detail})
                    existing_kvitton.add(kvitto)
            current += timedelta(days=1)

        print("Hämtar skift...")
        shifts = fetch_shifts(page, forar_id)

        data["trips"] = trips + new_trips
        data["shifts"] = shifts
        data["last_updated"] = datetime.utcnow().isoformat() + "Z"
        data["forar"] = forar_id

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Lade till {len(new_trips)} nya, ersatte {replaced}")
        browser.close()

if __name__ == "__main__":
    main()