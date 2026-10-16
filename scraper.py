#!/usr/bin/env python3
"""
STIG scraper – förenklad.
- Resaposter-översikt: hitta nya körningar
- Körningsdetalj: hämta all data för nya körningar
- Passrapport: skiftstart/slut (en gång per dygn)
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

def get_new_receipts(page, forar_id, known_receipts):
    """Hämta översikt och returnera nya kvittonummer."""
    page.goto(f"{STIG_URL}/Resaposter.aspx")
    page.wait_for_load_state("networkidle")

    from_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    page.evaluate(f"""
        () => {{
            document.getElementById('MainContent_tb_Forarid').value = '{forar_id}';
            document.getElementById('MainContent_tb_ResdatumFom').value = '{from_date}';
            document.getElementById('MainContent_tb_ResdatumTom').value = '{datetime.now().strftime("%Y-%m-%d")}';
        }}
    """)
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")

    rows = page.query_selector_all("table tr")
    new_receipts = []
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) >= 5:
            kvitto = cells[4]
            if kvitto and kvitto not in known_receipts:
                new_receipts.append(kvitto)
    return new_receipts

def scrape_trip_detail(page, kvitto):
    """Öppna en körning och hämta detaljer."""
    # Click the receipt link
    try:
        page.click(f"text={kvitto}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Extract fields from detail view
        detail = page.evaluate("""
            () => {
                const get = (label) => {
                    const el = Array.from(document.querySelectorAll('*')).find(e => e.innerText && e.innerText.includes(label));
                    return el ? el.nextElementSibling?.innerText?.trim() || '' : '';
                };
                return {
                    startzon: get('Startzon'),
                    slutzon: get('Slutzon'),
                    kilometer: get('Kilometer'),
                    dricks: get('Dricks'),
                    kredittyp: get('Kredittyp')
                };
            }
        """)
        page.go_back()
        page.wait_for_load_state("networkidle")
        return detail
    except Exception as e:
        print(f"Kunde inte hämta detalj för {kvitto}: {e}")
        return {}

def fetch_passrapport(page, forar_id):
    page.goto(f"{STIG_URL}/Passrapport.aspx")
    page.wait_for_load_state("networkidle")

    from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    page.evaluate(f"""
        () => {{
            const inputs = document.querySelectorAll('input[type="text"]');
            for (const el of inputs) {{
                const id = (el.id || '').toLowerCase();
                if (id.includes('forar')) el.value = '{forar_id}';
                if (id.includes('start') && id.includes('fom')) el.value = '{from_date}';
                if (id.includes('start') && id.includes('tom')) el.value = '{datetime.now().strftime("%Y-%m-%d")}';
            }}
        }}
    """)
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")

    shifts = []
    rows = page.query_selector_all("table tr")
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) >= 8 and cells[0]:
            shifts.append({
                "taxi": cells[0],
                "start": cells[1],
                "slut": cells[2],
                "tid": cells[3],
                "passnr": cells[7] if len(cells) > 7 else "",
                "resor": cells[8] if len(cells) > 8 else ""
            })
    return shifts

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas")
        return

    forar_id = "710022"

    # Load existing data
    try:
        with open("data.json", "r") as f:
            existing = json.load(f)
    except:
        existing = {"trips": [], "shifts": []}

    known_receipts = {t.get("kvittonr") for t in existing.get("trips", [])}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        print("Söker nya körningar...")
        new_receipts = get_new_receipts(page, forar_id, known_receipts)
        print(f"Hittade {len(new_receipts)} nya körningar")

        # Scrape details for new trips
        new_trips = []
        for kvitto in new_receipts[:5]:  # limit for testing
            print(f"Hämtar detalj för {kvitto}...")
            detail = scrape_trip_detail(page, kvitto)
            new_trips.append({"kvittonr": kvitto, **detail})

        print("Hämtar Passrapport...")
        shifts = fetch_passrapport(page, forar_id)

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "forar": forar_id,
            "shifts": shifts,
            "trips": existing.get("trips", []) + new_trips
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Sparat: {len(shifts)} skift, {len(data['trips'])} körningar totalt")
        browser.close()

if __name__ == "__main__":
    main()