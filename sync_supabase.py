#!/usr/bin/env python3
"""Synkar resedata (JSON-filer) till Supabase.

Användning:  python sync_supabase.py [fil[=dataset] ...]
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


def ingest(path, name):
    with open(path, encoding='utf-8') as f:
        doc = json.load(f)
    body = json.dumps({'p_name': name, 'p_doc': doc, 'p_source': path}).encode('utf-8')
    headers = {'apikey': KEY, 'Content-Type': 'application/json'}
    if not KEY.startswith('sb_'):  # äldre service_role-nyckel (JWT)
        headers['Authorization'] = 'Bearer ' + KEY
    req = urllib.request.Request(SUPABASE_URL + '/rest/v1/rpc/ingest_dataset', data=body, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or 'null')


def main():
    if not KEY:
        print('SUPABASE_SERVICE_KEY saknas - hoppar över synk till Supabase.')
        return 0
    args = sys.argv[1:] or ['data.json']
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
