#!/usr/bin/env python3
"""
Importerar månadsdata från STIG MedlemsRapporter.
Körs manuellt eller via GitHub Actions.
"""

import os
import json
import requests
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
    page.click("input[type='submit']")
    page.wait_for_load_state("networkidle")
    return "Login.aspx" not in page.url

def download_monthly(page, year_month):
    page.goto(f"{STIG_URL}/MedlemsRapporter.aspx")
    page.wait_for_load_state("networkidle")
    page.fill("#MainContent_tb_sok_Datum", year_month)
    page.click("#MainContent_btn_Sok")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)
    
    # Download pass file
    pass_data = page.evaluate("""
        async () => {
            const form = document.querySelector('form');
            const fd = new FormData(form);
            fd.set('__EVENTTARGET', 'ctl00$MainContent$gv_FileList');
            fd.set('__EVENTARGUMENT', 'Select$2');
            const resp = await fetch('/MedlemsRapporter.aspx', { method: 'POST', body: fd });
            return await resp.text();
        }
    """)
    
    # Download resapost file
    trip_data = page.evaluate("""
        async () => {
            const form = document.querySelector('form');
            const fd = new FormData(form);
            fd.set('__EVENTTARGET', 'ctl00$MainContent$gv_FileList');
            fd.set('__EVENTARGUMENT', 'Select$3');
            const resp = await fetch('/MedlemsRapporter.aspx', { method: 'POST', body: fd });
            return await resp.text();
        }
    """)
    
    return pass_data, trip_data

def parse_shifts(text):
    shifts = []
    for line in text.split('\n')[1:]:
        p = line.split(';')
        if len(p) < 16 or not p[2] or len(p[2]) < 5:
            continue
        start, slut = p[3], p[4]
        if len(start) < 12:
            continue
        start_fmt = f"{start[:8]} {start[8:10]}:{start[10:12]}"
        slut_fmt = f"{slut[:8]} {slut[8:10]}:{slut[10:12]}"
        sh, sm = int(start[8:10]), int(start[10:12])
        eh, em = int(slut[8:10]), int(slut[10:12])
        mins = (eh * 60 + em) - (sh * 60 + sm)
        if mins < 0:
            mins += 24 * 60
        tid = f"{mins // 60}:{mins % 60:02d}"
        shifts.append({
            "taxi": p[0], "start": start_fmt, "slut": slut_fmt,
            "tid": tid, "passnr": p[1], "resor": p[15],
            "forar": p[2], "inkort": p[16]
        })
    return shifts

def parse_trips(text):
    trips = []
    for line in text.split('\n')[1:]:
        p = line.split(';')
        if len(p) < 21 or not p[5] or len(p[5]) < 5:
            continue
        dat, tid, slut_tid = p[1], p[2], p[4]
        if len(dat) < 8:
            continue
        trips.append({
            "kvittonr": p[0], "forar": p[5],
            "startzon": p[19], "slutzon": p[20],
            "kilometer": f"{float(p[17])/10:.1f}".replace('.', ','),
            "dricks": f"{float(p[14] or 0):.2f}".replace('.', ','),
            "kredittyp": p[18],
            "belopp": f"{float(p[9] or 0):.2f}".replace('.', ','),
            "starttid": f"{tid[:2]}:{tid[2:4]}" if len(tid) >= 4 else "00:00",
            "sluttid": f"{slut_tid[8:10]}:{slut_tid[10:12]}" if len(slut_tid) >= 12 else "00:00",
            "startdatum": f"{dat[:4]}-{dat[4:6]}-{dat[6:8]}"
        })
    return trips

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas")
        return
    
    # Load existing data
    try:
        with open("data.json") as f:
            data = json.load(f)
    except:
        data = {"shifts": [], "trips": []}
    
    seen_shifts = {(s.get("passnr"), s.get("forar")) for s in data.get("shifts", [])}
    seen_trips = {(t.get("kvittonr"), t.get("forar")) for t in data.get("trips", [])}
    
    # Import months (edit this list)
    months = ["2026-09"]  # Add more: "2026-08", "2026-07", etc.
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return
        
        for ym in months:
            print(f"Importerar {ym}...")
            pass_text, trip_text = download_monthly(page, ym)
            
            new_shifts = parse_shifts(pass_text)
            new_trips = parse_trips(trip_text)
            
            added_s = added_t = 0
            for s in new_shifts:
                key = (s["passnr"], s["forar"])
                if key not in seen_shifts:
                    seen_shifts.add(key)
                    data["shifts"].append(s)
                    added_s += 1
            
            for t in new_trips:
                key = (t["kvittonr"], t["forar"])
                if key not in seen_trips:
                    seen_trips.add(key)
                    data["trips"].append(t)
                    added_t += 1
            
            print(f"  +{added_s} skift, +{added_t} körningar")
        
        browser.close()
    
    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    
    with open("data.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Totalt: {len(data['shifts'])} skift, {len(data['trips'])} körningar")

if __name__ == "__main__":
    main()