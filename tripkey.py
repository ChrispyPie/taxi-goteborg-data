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
