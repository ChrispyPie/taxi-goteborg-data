#!/usr/bin/env python3
"""
STIG scraper – Passrapport (historik) + Resaposter (pågående).
Testar med förare 710022.
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

def fetch_passrapport(page, forar_id):
    page.goto(f"{STIG_URL}/Passrapport.aspx")
    page.wait_for_load_state("networkidle")

    # Fill driver ID and dates
    page.evaluate(f"""
        () => {{
            const inputs = document.querySelectorAll('input[type="text"]');
            if (inputs.length >= 1) inputs[0].value = '{forar_id}';
            if (inputs.length >= 2) inputs[1].value = '{(datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")}';
            if (inputs.length >= 3) inputs[2].value = '{datetime.now().strftime("%Y-%m-%d")}';
        }}
    """)
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")

    shifts = []
    rows = page.query_selector_all("table tr")
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) >= 8:
            shifts.append({
                "taxi": cells[0],
                "start": cells[1],
                "slut": cells[2],
                "forar": cells[6] if len(cells) > 6 else forar_id,
                "passnr": cells[7] if len(cells) > 7 else "",
                "resor": cells[8] if len(cells) > 8 else "",
                "belopp": cells[-1] if cells else ""
            })
    return shifts

def fetch_resaposter(page, forar_id):
    page.goto(f"{STIG_URL}/Resaposter.aspx")
    page.wait_for_load_state("networkidle")

    from_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    page.evaluate(f"""
        () => {{
            document.getElementById('MainContent_tb_Forarid').value = '{forar_id}';
            document.getElementById('MainContent_tb_ResdatumFom').value = '{from_date}';
            document.getElementById('MainContent_tb_ResdatumTom').value = '{datetime.now().strftime("%Y-%m-%d")}';
        }}
    """)
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")

    trips = []
    rows = page.query_selector_all("table tr")
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) >= 10:
            trips.append({
                "passnr": cells[3],
                "kvittonr": cells[4],
                "belopp": cells[7],
                "startdatum": cells[8],
                "starttid": cells[10],
                "sluttid": cells[11] if len(cells) > 11 else ""
            })
    return trips

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

        print(f"Hämtar data för {forar_id}...")
        shifts = fetch_passrapport(page, forar_id)
        trips = fetch_resaposter(page, forar_id)

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "forar": forar_id,
            "shifts": shifts,
            "trips": trips
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Sparat: {len(shifts)} skift, {len(trips)} körningar")
        browser.close()

if __name__ == "__main__":
    main()