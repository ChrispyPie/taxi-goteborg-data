#!/usr/bin/env python3
"""
STIG scraper – förenklad.
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
    page.goto(f"{STIG_URL}/Resaposter.aspx")
    page.wait_for_load_state("networkidle")

    from_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
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

    rows = page.query_selector_all("table tr")
    new_receipts = []
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) >= 5:
            kvitto = cells[4]
            if kvitto and kvitto not in known_receipts and "-" in kvitto:
                new_receipts.append(kvitto)
    return new_receipts

def scrape_trip_detail(page, kvitto):
    try:
        page.click(f"text={kvitto}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        detail = page.evaluate("""
            () => {
                const text = document.body.innerText;
                const get = (label) => {
                    const idx = text.indexOf(label);
                    if (idx === -1) return '';
                    const after = text.substring(idx + label.length, idx + label.length + 40);
                    return after.split('\\n')[0].replace(':', '').trim();
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
        print(f"Detalj misslyckades för {kvitto}: {e}")
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
                if (id.includes('fom')) el.value = '{from_date}';
                if (id.includes('tom')) el.value = '{datetime.now().strftime("%Y-%m-%d")}';
            }}
        }}
    """)
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")

    shifts = []
    rows = page.query_selector_all("table tr")
    for row in rows[1:]:
        cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
        if len(cells) >= 9 and cells[0].startswith('A'):
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
            existing = json.load(f)
    except:
        existing = {"trips": [], "shifts": []}

    known = {t.get("kvittonr") for t in existing.get("trips", []) if t.get("kvittonr")}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        print("Söker nya körningar...")
        new_receipts = get_new_receipts(page, forar_id, known)
        print(f"Nya: {new_receipts}")

        new_trips = []
        for kvitto in new_receipts[:3]:
            print(f"Detalj: {kvitto}")
            detail = scrape_trip_detail(page, kvitto)
            new_trips.append({"kvittonr": kvitto, **detail})

        shifts = fetch_passrapport(page, forar_id)

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "forar": forar_id,
            "shifts": shifts,
            "trips": [t for t in existing.get("trips", []) if t.get("kvittonr") and "-" in t.get("kvittonr", "")] + new_trips
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Sparat {len(data['trips'])} körningar, {len(shifts)} skift")
        browser.close()

if __name__ == "__main__":
    main()