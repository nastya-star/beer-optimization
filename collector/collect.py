"""Daily Radler price collector + data.json validator. Standard library only.

Usage: python collector/collect.py            # collect enabled sources, validate, write
       python collector/collect.py --check    # validate data.json only

Source status (checked 2026-10-13; see README):
  kaufland  ENABLED   public store-level offer data on filiale.kaufland.de (allowed by robots.txt)
  rewe      DISABLED  offer pages answer with a captcha / bot challenge
  aldi_sued DISABLED  Akamai "Access Denied" (403) even for robots.txt
  lidl      DISABLED  no store-level prices; weekly offer URLs change; Radler shelf prices not published
  penny     DISABLED  offers depend on a JS-selected market cookie; static pages show a non-local region
Blocked sources are never bypassed. A failed source keeps its previous records untouched.
"""
import datetime as dt, html, json, re, sys, urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data.json"
UA = "beer-optimization/1.0 (+https://nastya-star.github.io/beer-optimization/)"
KL = "https://filiale.kaufland.de"
CITIES = {"München": "Munich", "Garching": "Garching", "Garching b. München": "Garching"}
CHAINS = {"REWE", "Lidl", "Kaufland", "ALDI Süd", "Penny"}
TODAY = dt.date.today().isoformat()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de-DE"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def json_objects(text, start='{"offerId"'):
    """Yield JSON objects embedded in HTML that begin with `start`."""
    i = text.find(start)
    while i != -1:
        depth, j, in_str, esc = 0, i, False, False
        while j < len(text):
            c = text[j]
            if in_str:
                esc, in_str = (not esc and c == "\\"), in_str and (esc or c != '"')
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        try:
            yield json.loads(text[i:j + 1])
        except ValueError:
            pass
        i = text.find(start, j)


def num(s):
    m = re.search(r"\d+(?:[.,]\d+)?", str(s or ""))
    return float(m.group().replace(",", ".")) if m else None


def radler_varieties(o):
    """Return alcoholic Radler variety names named explicitly in a Kaufland offer."""
    desc = html.unescape(o.get("detailDescription") or "")
    head = html.unescape(f'{o.get("subtitle") or ""}').strip()
    body = desc.split("(+")[0]
    out = []
    for part in re.split(r",\s+| oder | und |/", body):  # keep "0,0 %" intact
        p = part.strip()
        if re.search(r"radler|alster", p, re.I) and not re.search(r"0,0|alkoholfrei|alkfrei", p, re.I):
            out.append(p)
    free = re.search(r"0,0|alkoholfrei|alkfrei", head + " " + body, re.I)
    partly = re.search(r"z\.\s*T\.|teilweise|auch alkoholfrei", body, re.I)
    if not out and re.search(r"radler|alster", head, re.I) and (not free or partly):
        out.append(head)  # e.g. subtitle "Radler", varieties not itemised
    return out


def kaufland():
    stores = [s for s in json.loads(get(KL + "/.klstorefinder.json")) if s.get("t") in CITIES]
    offers = {}
    for page in ("/angebote/uebersicht.html", "/angebote/aktuell.html"):
        for o in json_objects(get(KL + page)):
            offers.setdefault(o.get("klNr"), o)
    recs = []
    for s in stores:
        avail = {x["klNr"] for x in json.loads(get(f'{KL}/.kloffers.storeName={s["n"]}.json'))}
        for kl in avail & offers.keys():
            o = offers[kl]
            names = radler_varieties(o)
            if not names:
                continue
            unit = html.unescape(o.get("unit") or "")
            m = re.search(r"(?:(\d+)\s*x\s*)?(\d+(?:,\d+)?)\s*-?\s*l\b", unit)
            if not m:
                continue
            count, vol = int(m.group(1) or 1), num(m.group(2))
            desc = html.unescape(o.get("detailDescription") or "")
            dep = re.search(r"\+\s*(\d+[.,]\d+)\s*Pfand", desc)
            mq = re.search(r"ab\s+(\d+)\s+(?:Stück|Stk|Fl|Dosen|Flaschen|Packungen|Kästen|Kisten)", desc, re.I)
            loyal = o.get("loyaltyFormattedPrice")
            price = num(loyal) if loyal else (o.get("price") or None)
            if not price:
                continue
            for name in names:
                recs.append({
                    "id": f'kl-{s["n"]}-{kl}-{re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")}',
                    "brand": html.unescape(o.get("title") or "").title(),
                    "product": name,
                    "alcoholic": True, "radler": True,
                    "chain": "Kaufland", "branch": s["cn"],
                    "address": f'{s["sn"]}, {s["pc"]} {s["t"]}', "city": CITIES[s["t"]],
                    "price": round(price, 2), "count": count, "volume_l": vol,
                    "deposit": num(dep.group(1)) if dep else None,
                    "single": count == 1,
                    "price_type": "loyalty" if loyal else "offer",
                    "loyalty_public": True if loyal else None,
                    "min_qty": int(mq.group(1)) if mq else 1,
                    "conditions": ("With Kaufland Card (free public loyalty programme). " if loyal else "")
                                  + f"Offer text: {unit} · {desc}. While stocks last.",
                    "valid_from": o.get("salesFrom") or o.get("dateFrom"),
                    "valid_to": o.get("salesTo") or o.get("dateTo"),
                    "observed": TODAY,
                    "source": KL + "/angebote/uebersicht.html",
                    "status": "verified",
                    "origin": "kaufland-auto",
                })
    return recs


COLLECTORS = {"kaufland": kaufland}  # only sources with permitted, reliable access

REQ = {"id": str, "brand": str, "product": str, "alcoholic": bool, "radler": bool, "chain": str,
       "branch": str, "address": str, "city": str, "price": (int, float), "count": int,
       "volume_l": (int, float), "single": bool, "price_type": str, "observed": str,
       "source": str, "status": str}
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate(d):
    errs = []
    for i, r in enumerate(d.get("records", [])):
        w = f'records[{i}] {r.get("id", "?")}: '
        for k, t in REQ.items():
            if not isinstance(r.get(k), t) or isinstance(r.get(k), bool) != (t is bool):
                errs.append(w + f"{k} missing or wrong type")
        if r.get("chain") not in CHAINS: errs.append(w + "unknown chain")
        if r.get("city") not in ("Garching", "Munich"): errs.append(w + "city must be Garching or Munich")
        if r.get("price_type") not in ("regular", "offer", "loyalty"): errs.append(w + "bad price_type")
        if r.get("status") not in ("verified", "unverified", "personalized"): errs.append(w + "bad status")
        if not (isinstance(r.get("price"), (int, float)) and 0 < r["price"] < 500): errs.append(w + "price out of range")
        if not (isinstance(r.get("count"), int) and 1 <= r["count"] <= 48): errs.append(w + "count out of range")
        if not (isinstance(r.get("volume_l"), (int, float)) and 0.1 <= r["volume_l"] <= 5): errs.append(w + "volume_l out of range")
        if r.get("deposit") is not None and not (isinstance(r["deposit"], (int, float)) and 0 <= r["deposit"] < 20): errs.append(w + "bad deposit")
        for k in ("valid_from", "valid_to", "observed"):
            if r.get(k) is not None and not ISO.match(str(r[k])): errs.append(w + f"{k} must be YYYY-MM-DD")
    ids = [r.get("id") for r in d.get("records", [])]
    if len(ids) != len(set(ids)): errs.append("duplicate record ids")
    return errs


def main():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    if "--check" not in sys.argv:
        for name, fn in COLLECTORS.items():
            src = d.setdefault("sources", {}).setdefault(name, {})
            src["last_attempt"] = TODAY
            try:
                new = fn()
            except Exception as e:  # keep previous records; record the failure
                src["last_error"] = f"{TODAY}: {type(e).__name__}: {e}"[:300]
                print(f"{name}: FAILED, keeping previous records ({e})")
                continue
            d["records"] = [r for r in d["records"] if r.get("origin") != f"{name}-auto"] + new
            src.update(last_success=TODAY, last_count=len(new), last_error=None)
            print(f"{name}: {len(new)} Radler records")
    errs = validate(d)
    if errs:
        print("\n".join(errs)); sys.exit(1)
    if "--check" not in sys.argv:
        DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("data.json valid:", len(d["records"]), "records")


if __name__ == "__main__":
    main()
