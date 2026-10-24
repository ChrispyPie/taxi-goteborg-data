#!/usr/bin/env python3
"""Synkar resedata (JSON-filer) till Supabase.

Användning:  python sync_supabase.py [fil[=dataset] ...]
             python sync_supabase.py --pull DATASET FIL   (hämta dataset till fil, t.ex. data.json)
             python sync_supabase.py --status FIL [--failed]  (skicka körningsstatus)
  Utan argument: data.json -> dataset 'current'.
  data-YYYY-MM.json         -> 'YYYY-MM'
  monthly/data-YYYY-MM.json -> 'monthly/YYYY-MM'

Kräver miljövariabeln SUPABASE_SERVICE_KEY (GitHub-secret med samma namn).
Saknas den avslutas skriptet utan fel, så att scrapern fortsätter som vanligt.
Nyckeln skrivs aldrig ut.
"""
import json, os, re, sys, urllib.request, urllib.error

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://lpfdryvukqmjlgenuzpb.supabase.co').rstrip('/')
KEY = os.environ.get('SUPABASE_SERVICE_KEY', '').strip()


def dataset_for(path):
    base = os.path.basename(path)
    if base == 'data.json':
        return 'current'
    m = re.fullmatch(r'data-(\d{4}-\d{2})\.json', base)
    if not m:
        return None
    parent = os.path.basename(os.path.dirname(os.path.normpath(path)))
    return ('monthly/' if parent == 'monthly' else '') + m.group(1)


def call(fn, payload, timeout=120):
    body = json.dumps(payload).encode('utf-8')
    headers = {'apikey': KEY, 'Content-Type': 'application/json'}
    if not KEY.startswith('sb_'):  # äldre service_role-nyckel (JWT)
        headers['Authorization'] = 'Bearer ' + KEY
    req = urllib.request.Request(SUPABASE_URL + '/rest/v1/rpc/' + fn, data=body, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or 'null')


def pull(name, path):
    """Hämtar ett dataset från Supabase och skriver det som JSON-fil (samma format som data.json)."""
    doc = call('export_dataset', {'p_name': name})
    if not doc or not isinstance(doc.get('trips'), list):
        raise RuntimeError(f'dataset {name} saknas i Supabase')
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    print(f'Hämtade {name} -> {path}: {len(doc["trips"])} resor, {len(doc.get("shifts", []))} pass')


def send_status(path, failed):
    st = {}
    try:
        with open(path, encoding='utf-8') as f:
            st = json.load(f)
    except Exception:
        pass
    if not st.get('result'):
        st = {'result': 'error' if failed else 'ok', 'message': 'ingen statusfil'}
    run = os.environ.get('GITHUB_RUN_ID')
    res = call('record_scrape_status', {
        'p_result': st['result'], 'p_message': st.get('message'), 'p_started_at': st.get('started_at'),
        'p_finished_at': st.get('finished_at'), 'p_new_trips': st.get('new_trips'),
        'p_workflow': os.environ.get('GITHUB_WORKFLOW'), 'p_run_id': run}, timeout=30)
    print(f'Status skickad: {res}')


def dedupe_trips(doc):
    """Spärr mot dubbletter (nyckel taxi + förare + kvittonr + startdatum, se tripkey.py):
    en rad som är EXAKT lika en tidigare rad med samma nyckel skickas inte. Rader som delar nyckel
    men skiljer sig behålls (och varnas för)."""
    from tripkey import norm, same_trip
    groups, out, dropped, differ = {}, [], 0, 0
    for t in doc.get('trips', []):
        norm(t)
        g = groups.setdefault(str(t.get('kvittonr') or ''), [])
        twins = [o for o in g if same_trip(o, t)]
        if any({k: v for k, v in o.items() if k != 'taxi'} == {k: v for k, v in t.items() if k != 'taxi'}
               and (not o.get('taxi') or not t.get('taxi') or o['taxi'] == t['taxi']) for o in twins):
            dropped += 1
            continue
        if twins:
            differ += 1
        g.append(t)
        out.append(t)
    doc['trips'] = out
    if dropped or differ:
        print(f'Dubblettspärr: {dropped} identiska borttagna, {differ} med samma nyckel men olika fält behållna')
    return doc


def ingest(path, name):
    with open(path, encoding='utf-8') as f:
        doc = json.load(f)
    doc = dedupe_trips(doc)
    return call('ingest_dataset', {'p_name': name, 'p_doc': doc, 'p_source': path})


def main():
    argv = sys.argv[1:]
    if argv[:1] == ['--pull']:
        if not KEY:
            print('::error::SUPABASE_SERVICE_KEY saknas - kan inte hämta data')
            return 1
        try:
            pull(argv[1], argv[2])
            return 0
        except Exception as e:
            print(f'::error::Kunde inte hämta {argv[1]} från Supabase: {type(e).__name__}: {e}')
            return 1
    if argv[:1] == ['--status']:
        if not KEY:
            print('SUPABASE_SERVICE_KEY saknas - hoppar över status.')
            return 0
        try:
            send_status(argv[1], '--failed' in argv)
        except Exception as e:
            print(f'Kunde inte skicka status: {type(e).__name__}: {e}')
        return 0
    if not KEY:
        print('SUPABASE_SERVICE_KEY saknas - hoppar över synk till Supabase.')
        return 0
    args = argv or ['data.json']
    failed = 0
    for a in args:
        path, _, name = a.partition('=')
        name = name or dataset_for(path)
        if not name or not os.path.exists(path):
            print(f'Hoppar över {path} (okänt namn eller saknas)')
            continue
        try:
            res = ingest(path, name)
            print(f'OK {path} -> {name}: {res}')
        except urllib.error.HTTPError as e:
            failed += 1
            print(f'FEL {path} -> {name}: HTTP {e.code} {e.read().decode("utf-8", "replace")[:300]}')
        except Exception as e:
            failed += 1
            print(f'FEL {path} -> {name}: {type(e).__name__}: {e}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
