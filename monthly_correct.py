#!/usr/bin/env python3
"""
Månadskorrigering – söker efter -2 kvitton och ersätter -1.
Körs den 1:a varje månad kl 13:10.
"""

import os
import json
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

STIG_URL = "https://stig.taxinet.se"
USERNAME = os.environ.get("STIG_USERNAME", "15201")
PASSWORD = os.environ.get("STIG_PASSWORD", "")

DRIVERS = [
    "154711", "169327", "179629", "179764", "179890",
    "417480", "459910", "472245", "631047", "682204",
    "693340", "710022", "738104", "788962", "829560", "844601"
]

def login(page):
    page.goto(f"{STIG_URL}/Login.aspx")
    page.wait_for_load_state("networkidle")
    page.select_option("select", label="Taxi Göteborg")
    page.fill("input[type='text']", USERNAME)
    page.fill("input[type='password']", PASSWORD)
    page.click("input[type='submit'], button, input[value*='Logga']")
    page.wait_for_load_state("networkidle")
    return "Login.aspx" not in page.url

def scrape_month(page, forar_id, from_date, to_date):
    page.goto(f"{STIG_URL}/Resaposter.aspx")
    page.wait_for_load_state("networkidle")
    page.evaluate(f"""
        () => {{
            document.getElementById('MainContent_tb_Forarid').value = '{forar_id}';
            document.getElementById('MainContent_tb_ResdatumFom').value = '{from_date}';
            document.getElementById('MainContent_tb_ResdatumTom').value = '{to_date}';
        }}
    """)
    page.click("input[type='submit'], button:has-text('Sök')")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

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
        page.wait_for_timeout(300)
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

    try:
        with open("data.json", "r") as f:
            data = json.load(f)
    except:
        print("Ingen data.json")
        return

    existing = {t.get("kvittonr"): t for t in data.get("trips", [])}

    today = datetime.now()
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    from_str = last_month_start.strftime("%Y-%m-%d")
    to_str = last_month_end.strftime("%Y-%m-%d")

    print(f"Söker -2 kvitton för {from_str} till {to_str}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        replaced = 0
        for forar_id in DRIVERS:
            print(f"Förare {forar_id}:")
            receipts = scrape_month(page, forar_id, from_str, to_str)
            for kvitto in receipts:
                if kvitto.endswith("-2"):
                    base = kvitto[:-2]
                    old_kvitto = base + "-1"
                    if old_kvitto in existing:
                        print(f"  Ersätter {old_kvitto} med {kvitto}")
                        detail = scrape_trip_detail(page, kvitto)
                        del existing[old_kvitto]
                        existing[kvitto] = {"kvittonr": kvitto, "forar": forar_id, **detail}
                        replaced += 1

        data["trips"] = list(existing.values())
        data["last_updated"] = datetime.utcnow().isoformat() + "Z"

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Ersatte {replaced} kvitton")
        browser.close()

if __name__ == "__main__":
    main()