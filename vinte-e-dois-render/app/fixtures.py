"""Calendario real de futebol sem chave: tenta fontes publicas em ordem.
Cada fonte devolve lista de dicts: ext_id, title, league, slug, ts (epoch s), source."""
import gzip
import json
import time
import urllib.error
import urllib.request
from datetime import datetime

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
       "Accept": "application/json, text/plain, */*", "Referer": "https://www.sofascore.com/"}


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={**_UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        if b[:2] == b"\x1f\x8b":
            b = gzip.decompress(b)
        return json.loads(b.decode("utf-8", "ignore"))


def from_sofascore(ds):
    d = _get("https://api.sofascore.com/api/v1/sport/football/scheduled-events/" + ds)
    out = []
    for e in d.get("events") or []:
        t = e.get("tournament") or {}
        home = (e.get("homeTeam") or {}).get("name")
        away = (e.get("awayTeam") or {}).get("name")
        if not home or not away:
            continue
        out.append({"ext_id": "ss-" + str(e.get("id")), "title": home + " x " + away,
                    "league": ((t.get("name") or "") + " \u00b7 " + ((t.get("country") or {}).get("name") or "")).strip(" \u00b7"),
                    "slug": (t.get("slug") or "").lower(), "ts": e.get("startTimestamp"), "source": "SofaScore"})
    return out


def from_thesportsdb(ds):
    d = _get("https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d=" + ds + "&s=Soccer")
    out = []
    for e in d.get("event") or []:
        home, away = e.get("strHomeTeam"), e.get("strAwayTeam")
        if not home or not away or not e.get("dateEvent"):
            continue
        ts = int(time.mktime(time.strptime(e["dateEvent"] + " " + (e.get("strTime") or "18:00:00"), "%Y-%m-%d %H:%M:%S")))
        league = e.get("strLeague") or ""
        if e.get("strCountry"):
            league += " \u00b7 " + e["strCountry"]
        out.append({"ext_id": "tsdb-" + str(e.get("idEvent")), "title": home + " x " + away,
                    "league": league, "slug": league.lower(), "ts": ts, "source": "TheSportsDB"})
    return out


def from_espn(ds):
    d = _get("https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard?dates=" + ds.replace("-", ""))
    lmap = {str(l.get("id")): (l.get("name") or "") for l in d.get("leagues") or []}
    lslug = {str(l.get("id")): (l.get("slug") or "") for l in d.get("leagues") or []}
    out = []
    for e in d.get("events") or []:
        comps = (((e.get("competitions") or [{}])[0]).get("competitors") or [])
        home = away = None
        for c in comps:
            t = (c.get("team") or {}).get("displayName")
            if c.get("homeAway") == "home":
                home = t
            elif c.get("homeAway") == "away":
                away = t
        if not home or not away:
            continue
        lg = e.get("league")
        if isinstance(lg, dict):
            lname = lg.get("name") or ""
            lsl = lg.get("slug") or ""
        else:
            lname = lmap.get(str(e.get("leagueId")), "")
            lsl = lslug.get(str(e.get("leagueId")), "")
        dt = e.get("date")
        try:
            ts = int(datetime.fromisoformat(dt.replace("Z", "+00:00")).timestamp())
        except Exception:
            ts = 0
        out.append({"ext_id": "espn-" + str(e.get("id")), "title": home + " x " + away,
                    "league": lname or "Futebol", "slug": (lsl or "futebol").lower(), "ts": ts, "source": "ESPN"})
    return out


def fetch_day(ds):
    """Retorna (eventos, fonte, erro)."""
    erros = []
    for nome, fn in (("ESPN", from_espn), ("SofaScore", from_sofascore), ("TheSportsDB", from_thesportsdb)):
        try:
            evs = fn(ds)
            return evs, nome, None
        except Exception as ex:
            erros.append(nome + ": " + type(ex).__name__ + " " + str(ex)[:90])
    return [], None, " | ".join(erros)


_XG = [ (("brasileirao serie a", "brazil serie a", "brazilian serie a", "brasileir\u00e3o"), (1.50, 1.18)),
       (("copa do brasil",), (1.45, 1.10)),
       (("libertadores",), (1.25, 1.05)),
       (("sudamericana",), (1.15, 1.00)),
       (("premier league",), (1.55, 1.20)),
       (("la liga", "primera division"), (1.40, 1.12)),
       (("bundesliga",), (1.60, 1.25)),
       (("ligue 1",), (1.40, 1.15)),
       (("eredivisie",), (1.50, 1.30)),
       (("serie b", "copa do nordeste"), (1.35, 1.10)),
       (("friendly", "amistoso"), (1.30, 1.15)),
       (("serie a",), (1.35, 1.10))]


def xg_for(slug="", league="", ext_id=""):
    s = (str(slug) + " " + str(league)).lower()
    base = (1.35, 1.12)
    for keys, p in _XG:
        if any(k in s for k in keys):
            base = p
            break
    j = (sum(ord(c) for c in str(ext_id)) % 7 - 3) * 0.02
    return round(base[0] + j, 2), round(base[1] + j * 0.5, 2)
