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
    page.goto(f"{STIG_URL}/Passrapport.aspx")
    page.wait_for_load_state("networkidle")

    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")

    # Fill fields more carefully
    page.fill("input[type='text']", forar_id)  # first text field is often forar
    inputs = page.query_selector_all("input[type='text']")
    if len(inputs) >= 3:
        inputs[0].fill(forar_id)
        inputs[1].fill(from_date)
        inputs[2].fill(to_date)

    page.click("input[type='submit'], button:has-text('Sök'), input[value*='Sök']")
    page.wait_for_load_state("networkidle")

    rows = page.query_selector_all("table tr")
    shifts = []
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) < 6:
            continue
        shifts.append({
            "raw": cells
        })
    return shifts

def fetch_resaposter(page, forar_id, from_date):
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
        if len(cells) < 8:
            continue
        trips.append({"raw": cells})
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
        trips = fetch_resaposter(page, forar_id, (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"))

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "forar": forar_id,
            "shifts": shifts[:10],
            "recent_trips": trips[:15]
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Sparat: {len(shifts)} skift, {len(trips)} körningar")
        browser.close()

if __name__ == "__main__":
    main()