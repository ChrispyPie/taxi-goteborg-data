#!/usr/bin/env python3
"""
STIG scraper – tvingar detaljhämtning för test.
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

def scrape_trip_detail(page, kvitto):
    try:
        page.click(f"text={kvitto}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

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

        # Go to resaposter and search
        page.goto(f"{STIG_URL}/Resaposter.aspx")
        page.wait_for_load_state("networkidle")
        page.evaluate(f"""
            () => {{
                document.getElementById('MainContent_tb_Forarid').value = '{forar_id}';
                document.getElementById('MainContent_tb_ResdatumFom').value = '2026-10-15';
                document.getElementById('MainContent_tb_ResdatumTom').value = '2026-10-16';
            }}
        """)
        page.click("input[type='submit'], button:has-text('Sök')")
        page.wait_for_load_state("networkidle")

        # Force scrape last 2 trips
        trips = []
        for kvitto in ["030100-01", "030099-01"]:
            print(f"Hämtar {kvitto}...")
            detail = scrape_trip_detail(page, kvitto)
            trips.append({"kvittonr": kvitto, **detail})
            print(detail)

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "forar": forar_id,
            "trips": trips
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("Sparat")
        browser.close()

if __name__ == "__main__":
    main()