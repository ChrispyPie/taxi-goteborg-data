"""Gemensam regel för när en resa redan finns (alla skrapare, månadsimport, bakåthämtning och dubblettspärren).

Nyckel: taxi + förare + kvittonr + startdatum.
- Förare och kvittonr måste alltid vara lika (saknad förare = 710022, gamla testrader).
- Startdatum måste vara lika när båda raderna har datum; saknas datum på någon rad räknas det som jokertecken.
- Taxi måste vara lika när båda raderna har taxi; saknas taxi på någon rad räknas det som jokertecken
  (så befintliga rader utan taxi aldrig ger dubbletter). Saknad taxi fylls i från källfilen när resan
  tydligt stämmer (samma förare, kvitto, datum, starttid och belopp) – aldrig gissning."""
from datetime import date

DEFAULT_FORAR = "710022"


def _d(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def norm(t):
    if not t.get("forar"):
        t["forar"] = DEFAULT_FORAR
    return t


def same_trip(a, b):
    """True om a och b är samma resa enligt nyckeln ovan."""
    if str(a.get("kvittonr") or "") != str(b.get("kvittonr") or ""):
        return False
    if str(a.get("forar") or DEFAULT_FORAR) != str(b.get("forar") or DEFAULT_FORAR):
        return False
    da, db = _d(a.get("startdatum")), _d(b.get("startdatum"))
    if da and db and da != db:
        return False
    ta, tb = str(a.get("taxi") or ""), str(b.get("taxi") or "")
    return not (ta and tb and ta != tb)


def clearly_same(a, b):
    """Strikt kontroll innan taxi fylls i: samma förare, kvitto, datum, starttid och belopp."""
    return all(str(a.get(k) or "") == str(b.get(k) or "") and str(a.get(k) or "") != ""
               for k in ("kvittonr", "startdatum", "starttid", "belopp")) and \
        str(a.get("forar") or DEFAULT_FORAR) == str(b.get("forar") or DEFAULT_FORAR)


_KV = __import__('re').compile(r"(\d+)-(\d+)")


class TripIndex:
    def __init__(self, trips=()):
        self.by = {}
        self.rows = []      # behåller ursprunglig ordning
        self.bases = {}     # grundnummer -> kvittonr, för snabb koll av rättelser
        for t in trips:
            self.add(t)

    def add(self, t):
        norm(t)
        k = str(t.get("kvittonr") or "")
        self.by.setdefault(k, []).append(t)
        self.rows.append(t)
        m = _KV.fullmatch(k.strip())
        if m:
            self.bases.setdefault(m.group(1), set()).add(k)

    def find(self, kvittonr, forar, startdatum=None, taxi=None):
        probe = {"kvittonr": kvittonr, "forar": forar, "startdatum": startdatum, "taxi": taxi}
        for t in self.by.get(str(kvittonr or ""), []):
            if same_trip(t, probe):
                return t
        return None

    def all(self):
        return list(self.rows)


# --- Rättade kvitton -------------------------------------------------------------------------
# Ett kvitto som slutar på -02 är en rättad version av samma grundnummer -01, -03 rättar -02 osv.
# Högsta löpnumret gäller; lägre versioner räknas aldrig. Samma resa = samma grundnummer, samma förare,
# samma taxi (när båda har taxi) och den högre versionen har startdatum samma dag eller upp till
# CORRECTION_WINDOW_DAYS senare (i alla verkliga exempel hittills: samma dag och starttid).
import re as _re

CORRECTION_WINDOW_DAYS = 31


def split_kvitto(k):
    m = _re.fullmatch(r"\s*(\d+)-(\d+)\s*", str(k or ""))
    return (m.group(1), int(m.group(2))) if m else (str(k or ""), 0)


def _supersedes(hi, lo):
    """True om raden hi är en högre (rättad) version av raden lo."""
    bh, nh = split_kvitto(hi.get("kvittonr"))
    bl, nl = split_kvitto(lo.get("kvittonr"))
    if bh != bl or nh <= nl:
        return False
    if str(hi.get("forar") or DEFAULT_FORAR) != str(lo.get("forar") or DEFAULT_FORAR):
        return False
    th, tl = str(hi.get("taxi") or ""), str(lo.get("taxi") or "")
    if th and tl and th != tl:
        return False
    dh, dl = _d(hi.get("startdatum")), _d(lo.get("startdatum"))
    if dh and dl and not (0 <= (dh - dl).days <= CORRECTION_WINDOW_DAYS):
        return False
    return True


def apply_corrections(trips):
    """Skiljer ut rader som ersatts av en högre version. Returnerar (räknade, ersatta originals med ersatt_av).
    Originalen sparas separat (Supabase private.ersatta_kvitton) och räknas/visas aldrig."""
    groups = {}
    for t in trips:
        groups.setdefault((split_kvitto(t.get("kvittonr"))[0], str(t.get("forar") or DEFAULT_FORAR)), []).append(t)
    drop = set()
    for g in groups.values():
        if len(g) < 2:
            continue
        for lo in g:
            if any(_supersedes(hi, lo) for hi in g if hi is not lo):
                drop.add(id(lo))
    kept = [t for t in trips if id(t) not in drop]
    replaced = []
    for g in groups.values():
        for lo in g:
            if id(lo) in drop:
                his = [hi for hi in g if hi is not lo and _supersedes(hi, lo) and id(hi) not in drop]
                his = his or [hi for hi in g if hi is not lo and _supersedes(hi, lo)]
                best = max(his, key=lambda h: split_kvitto(h.get("kvittonr"))[1])
                replaced.append(dict(lo, ersatt_av=best.get("kvittonr")))
    return kept, replaced


def is_superseded(index, kvittonr, forar, startdatum=None, taxi=None):
    """True om index (TripIndex) redan har en högre version av kvittot – då behöver det inte hämtas."""
    base, n = split_kvitto(kvittonr)
    probe = {"kvittonr": kvittonr, "forar": forar, "startdatum": startdatum, "taxi": taxi}
    if base is None:
        return False
    for k in index.bases.get(base, ()):
        if split_kvitto(k)[1] > n and any(_supersedes(t, probe) for t in index.by.get(k, [])):
            return True
    return False


def shift_key(s):
    """Nyckel för pass: passnr + förare + startdatum (passnr återanvänds, ibland efter två veckor)."""
    d = _re.sub(r"\D", "", (s.get("start") or ""))[:8]
    return (s.get("passnr") or "", s.get("forar") or "710022", d)
