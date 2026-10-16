#!/usr/bin/env python3
"""
STIG scraper – Passrapport (historik) + Resaposter (pågående skift).
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

def fetch_passrapport(page, forar_id, days_back=14):
    """Hämta avslutade skift från Passrapport."""
    page.goto(f"{STIG_URL}/Passrapport.aspx")
    page.wait_for_load_state("networkidle")

    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")

    page.fill("input[id*='Forar'], input[name*='Forar']", forar_id)
    page.fill("input[id*='start'][id*='fom'], input[name*='start'][name*='fom']", from_date)
    page.fill("input[id*='start'][id*='tom'], input[name*='start'][name*='tom']", to_date)
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")

    # Parse table rows (simplified – adjust selectors as needed)
    rows = page.query_selector_all("table tr")
    shifts = []
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) < 8:
            continue
        shifts.append({
            "taxi": cells[0] if cells else "",
            "start": cells[1] if len(cells) > 1 else "",
            "slut": cells[2] if len(cells) > 2 else "",
            "forar": cells[6] if len(cells) > 6 else forar_id,
            "passnr": cells[7] if len(cells) > 7 else "",
            "resor": cells[8] if len(cells) > 8 else "",
            "belopp": cells[-1] if cells else ""
        })
    return shifts

def fetch_resaposter(page, forar_id, from_date):
    """Hämta enskilda körningar från Resaposter."""
    page.goto(f"{STIG_URL}/Resaposter.aspx")
    page.wait_for_load_state("networkidle")

    page.fill("#MainContent_tb_Forarid", forar_id)
    page.fill("#MainContent_tb_ResdatumFom", from_date)
    page.fill("#MainContent_tb_ResdatumTom", datetime.now().strftime("%Y-%m-%d"))
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")

    rows = page.query_selector_all("table tr")
    trips = []
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) < 10:
            continue
        trips.append({
            "kvittonr": cells[4] if len(cells) > 4 else "",
            "belopp": cells[7] if len(cells) > 7 else "",
            "startdatum": cells[8] if len(cells) > 8 else "",
            "starttid": cells[10] if len(cells) > 10 else "",
            "sluttid": cells[11] if len(cells) > 11 else "",
            "passnr": cells[3] if len(cells) > 3 else ""
        })
    return trips

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas")
        return

    forar_id = "710022"  # testförare

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        print(f"Hämtar data för {forar_id}...")
        shifts = fetch_passrapport(page, forar_id)
        trips = fetch_resaposter(page, forar_id, (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"))

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "forar": forar_id,
            "shifts": shifts,
            "recent_trips": trips
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Sparat: {len(shifts)} skift, {len(trips)} körningar")
        browser.close()

if __name__ == "__main__":
    main()