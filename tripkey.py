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


class TripIndex:
    def __init__(self, trips=()):
        self.by = {}
        for t in trips:
            self.add(t)

    def add(self, t):
        norm(t)
        self.by.setdefault(str(t.get("kvittonr") or ""), []).append(t)

    def find(self, kvittonr, forar, startdatum=None, taxi=None):
        probe = {"kvittonr": kvittonr, "forar": forar, "startdatum": startdatum, "taxi": taxi}
        for t in self.by.get(str(kvittonr or ""), []):
            if same_trip(t, probe):
                return t
        return None

    def all(self):
        return [t for ts in self.by.values() for t in ts]


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
    """Tar bort rader som ersatts av en högre version. Returnerar (behållna, borttagna)."""
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
    return [t for t in trips if id(t) not in drop], [t for t in trips if id(t) in drop]


def is_superseded(index, kvittonr, forar, startdatum=None, taxi=None):
    """True om index (TripIndex) redan har en högre version av kvittot – då behöver det inte hämtas."""
    base, n = split_kvitto(kvittonr)
    probe = {"kvittonr": kvittonr, "forar": forar, "startdatum": startdatum, "taxi": taxi}
    for k, ts in index.by.items():
        if split_kvitto(k)[0] == base and split_kvitto(k)[1] > n:
            if any(_supersedes(t, probe) for t in ts):
                return True
    return False
