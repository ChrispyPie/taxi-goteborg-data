#!/usr/bin/env python3
"""
STIG scraper – Passrapport (historik) + Resaposter (pågående).
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

    from_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")

    # Fill using more specific approach
    page.evaluate(f"""
        () => {{
            const all = document.querySelectorAll('input[type="text"]');
            for (const el of all) {{
                const id = (el.id || '').toLowerCase();
                const name = (el.name || '').toLowerCase();
                if (id.includes('forar') || name.includes('forar')) el.value = '{forar_id}';
                if ((id.includes('start') && id.includes('fom')) || (name.includes('start') && name.includes('fom'))) el.value = '{from_date}';
                if ((id.includes('start') && id.includes('tom')) || (name.includes('start') && name.includes('tom'))) el.value = '{to_date}';
            }}
        }}
    """)

    # Click search
    page.click("input[type='submit'], button:has-text('Sök'), input[value*='Sök']")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    shifts = []
    rows = page.query_selector_all("table tr")
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) >= 6 and cells[0]:
            shifts.append({
                "raw": cells
            })
    return shifts

def fetch_resaposter(page, forar_id):
    page.goto(f"{STIG_URL}/Resaposter.aspx")
    page.wait_for_load_state("networkidle")

    from_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    page.evaluate(f"""
        () => {{
            const forar = document.getElementById('MainContent_tb_Forarid');
            const fom = document.getElementById('MainContent_tb_ResdatumFom');
            const tom = document.getElementById('MainContent_tb_ResdatumTom');
            if (forar) forar.value = '{forar_id}';
            if (fom) fom.value = '{from_date}';
            if (tom) tom.value = '{datetime.now().strftime("%Y-%m-%d")}';
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
            "shifts": shifts[:20],
            "trips": trips[:30]
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Sparat: {len(shifts)} skift, {len(trips)} körningar")
        browser.close()

if __name__ == "__main__":
    main()