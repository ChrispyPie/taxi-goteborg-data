#!/usr/bin/env python3
"""
STIG scraper – loggar in, laddar ner pass-fil och bygger statistik.
"""

import os
import json
import csv
from datetime import datetime
from io import StringIO
from playwright.sync_api import sync_playwright

STIG_URL = "https://stig.taxinet.se"
USERNAME = os.environ.get("STIG_USERNAME", "15201")
PASSWORD = os.environ.get("STIG_PASSWORD", "")

def parse_pass_file(content: str) -> dict:
    """Parse semicolon-separated pass file and aggregate per driver."""
    drivers = {}
    reader = csv.DictReader(StringIO(content), delimiter=';')

    for row in reader:
        forar = row.get("ForarNr", "").strip()
        if not forar:
            continue

        if forar not in drivers:
            drivers[forar] = {
                "name": f"Förare {forar}",
                "inkort": 0.0,
                "timmar": 0.0,
                "mil": 0.0,
                "pass_count": 0,
                "senastePass": []
            }

        try:
            inkort = float(row.get("InkortPass", "0").replace(",", ".") or 0)
            tot_km = float(row.get("TotKmPass", "0").replace(",", ".") or 0)
            # Rough hours calculation from start/end if available
            start = row.get("PassStart", "")
            slut = row.get("PassSlut", "")
            hours = 0.0
            if len(start) == 12 and len(slut) == 12:
                try:
                    s = datetime.strptime(start, "%Y%m%d%H%M")
                    e = datetime.strptime(slut, "%Y%m%d%H%M")
                    hours = max(0, (e - s).total_seconds() / 3600)
                except:
                    pass

            d = drivers[forar]
            d["inkort"] += inkort
            d["mil"] += tot_km / 10  # km to mil
            d["timmar"] += hours
            d["pass_count"] += 1

            if len(d["senastePass"]) < 5:
                d["senastePass"].append({
                    "start": start,
                    "slut": slut,
                    "timmar": round(hours, 1),
                    "belopp": round(inkort)
                })
        except Exception:
            continue

    # Calculate averages
    for d in drivers.values():
        if d["timmar"] > 0:
            d["perTimme"] = round(d["inkort"] / d["timmar"])
        else:
            d["perTimme"] = 0
        if d["mil"] > 0:
            d["perMil"] = round(d["inkort"] / d["mil"], 1)
        else:
            d["perMil"] = 0
        d["inkort"] = round(d["inkort"])
        d["timmar"] = round(d["timmar"], 1)
        d["mil"] = round(d["mil"], 1)

    return drivers

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Loggar in...")
        page.goto(f"{STIG_URL}/Login.aspx")
        page.wait_for_load_state("networkidle")

        page.select_option("select", label="Taxi Göteborg")
        page.fill("input[type='text']", USERNAME)
        page.fill("input[type='password']", PASSWORD)
        page.click("input[type='submit'], button, input[value*='Logga']")
        page.wait_for_load_state("networkidle")

        if "Login.aspx" in page.url:
            print("Inloggning misslyckades")
            browser.close()
            return

        print("Inloggad. Hämtar pass-rapport...")
        page.goto(f"{STIG_URL}/MedlemsRapporter.aspx")
        page.wait_for_load_state("networkidle")

        content = ""
        try:
            with page.expect_download(timeout=60000) as download_info:
                # Klicka på en pass-fil (justera nth om nödvändigt)
                page.click("input[type='image'] >> nth=2")
            download = download_info.value
            path = download.path()
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            print(f"Nedladdning lyckades ({len(content)} tecken)")
        except Exception as e:
            print(f"Nedladdning misslyckades: {e}")

        drivers = parse_pass_file(content) if content else {}

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "status": "ok" if drivers else "ingen data",
            "drivers": drivers
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"data.json skapad med {len(drivers)} förare")
        browser.close()

if __name__ == "__main__":
    main()