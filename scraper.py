#!/usr/bin/env python3
"""
STIG scraper – hämta ALLA körningar för förare 710022, oktober 2026.
Hanterar paginering.
"""

import os
import json
from datetime import datetime
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

def scrape_trip_detail(page, kvitto):
    try:
        page.click(f"text={kvitto}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)

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

def get_all_receipts(page):
    receipts = []
    page_num = 1
    while True:
        print(f"Sida {page_num}...")
        rows = page.query_selector_all("table tr")
        for row in rows[1:]:
            cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
            if len(cells) >= 5 and "-" in cells[4]:
                receipts.append(cells[4])

        # Check for next page
        next_btn = page.query_selector("a:has-text('>'), input[value='>'], button:has-text('>')")
        if not next_btn:
            break
        next_btn.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        page_num += 1
        if page_num > 10:
            break
    return receipts

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas")
        return

    forar_id = "710022"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        page.goto(f"{STIG_URL}/Resaposter.aspx")
        page.wait_for_load_state("networkidle")
        page.evaluate(f"""
            () => {{
                document.getElementById('MainContent_tb_Forarid').value = '{forar_id}';
                document.getElementById('MainContent_tb_ResdatumFom').value = '2026-10-01';
                document.getElementById('MainContent_tb_ResdatumTom').value = '2026-10-17';
            }}
        """)
        page.click("input[type='submit'], button:has-text('Sök')")
        page.wait_for_load_state("networkidle")

        receipts = get_all_receipts(page)
        print(f"Totalt {len(receipts)} körningar")

        trips = []
        for i, kvitto in enumerate(receipts):
            print(f"Hämtar {i+1}/{len(receipts)}: {kvitto}")
            detail = scrape_trip_detail(page, kvitto)
            trips.append({"kvittonr": kvitto, **detail})

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "forar": forar_id,
            "trips": trips
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Sparat {len(trips)} körningar")
        browser.close()

if __name__ == "__main__":
    main()