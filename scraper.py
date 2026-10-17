#!/usr/bin/env python3
"""
STIG scraper – hämta pass för förare 710022.
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

def fetch_passrapport(page, forar_id):
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
    page.wait_for_timeout(2000)

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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        print("Hämtar Passrapport...")
        shifts = fetch_passrapport(page, forar_id)
        print(f"Hittade {len(shifts)} skift")

        try:
            with open("data.json", "r") as f:
                existing = json.load(f)
        except:
            existing = {"trips": []}

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "forar": forar_id,
            "shifts": shifts,
            "trips": existing.get("trips", [])
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Sparat {len(shifts)} skift")
        browser.close()

if __name__ == "__main__":
    main()