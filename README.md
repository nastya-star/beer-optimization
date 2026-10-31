# Beer Price Optimization

Cheapest alcoholic Radler in Garching and Munich (REWE, Lidl, Kaufland, ALDI Süd, Penny, EDEKA).
Live: https://nastya-star.github.io/beer-optimization/

Files: `index.html` (page), `data.json` (prices), `collector/collect.py` (daily collector + validator),
`.github/workflows/update.yml` (runs it daily and on every change to `data.json`).

## Editing prices

Edit `data.json` on GitHub (pencil icon) and add an object to `"records"`:

```json
{
 "id": "rewe-garching-paulaner-2026-10-13",
 "brand": "Paulaner", "product": "Natur-Radler",
 "alcoholic": true, "radler": true,
 "chain": "REWE", "branch": "REWE Garching", "address": "Street 1, 85748 Garching",
 "city": "Garching",
 "price": 0.99, "count": 1, "volume_l": 0.5, "deposit": 0.08,
 "single": true,
 "price_type": "regular", "loyalty_public": null, "min_qty": 1,
 "conditions": "",
 "valid_from": null, "valid_to": null,
 "observed": "2026-10-13",
 "source": "Shelf label photo, 2026-10-13", "source_type": "shelf_photo",
 "status": "verified"
}
```

| Field | Meaning |
|---|---|
| `city` | `"Garching"` or `"Munich"` |
| `chain` | `"REWE"`, `"Lidl"`, `"Kaufland"`, `"ALDI Süd"`, `"Penny"`, `"EDEKA"` |
| `price` | price of the whole package in €, without deposit |
| `count`, `volume_l` | containers in the package, litres per container |
| `deposit` | refundable deposit for the whole package in € (`null` if unknown) |
| `single` | `true` only if one container can be bought on its own at this price |
| `price_type` | `"regular"`, `"offer"` or `"loyalty"` |
| `loyalty_public` | `true` for app discounts anyone can get; `false` for personalised coupons |
| `min_qty` | minimum number of packages required for the price |
| `valid_from`, `valid_to`, `observed` | `YYYY-MM-DD` (`null` if not applicable) |
| `source_type` | `"shelf_photo"` (no public link; photos stay private, never commit them) , `"retailer_website"` or `"official_online"` (`source` must be the https URL, shown as a link) |
| `status` | `"verified"` (ranked), `"unverified"`, `"personalized"` or `"reference"` (listed, not ranked; `"reference"` = official price without a confirmed branch, `city`/`branch`/`address` may be `null`) |

Rules applied by the page: only alcoholic Radler, `status: "verified"`, public discounts and offers
inside their validity dates are ranked. "Single bottle/can" needs `single: true`, `count: 1`, `min_qty: 1`
and a known deposit (price + deposit). "Per litre" = `price / (count × volume_l)`, without deposit.
Records older than 14 days are flagged as possibly outdated.

After a commit, the workflow validates the file; a red ❌ under *Actions* means a typo (the log names the record).
Local check: `python collector/collect.py --check`.

## Automatic sources (checked 2026-10-13)

| Source | Status | Reason |
|---|---|---|
| Kaufland | **enabled** (Munich stores) | Public store-level offer data on filiale.kaufland.de, allowed by robots.txt. Offers and Kaufland Card prices only; no regular shelf prices. No Kaufland in Garching. |
| REWE | disabled | Offer pages answer with a captcha / bot challenge. |
| ALDI Süd | disabled | Akamai blocks automated requests (403), even robots.txt. |
| Lidl | disabled | No store-level Radler prices online; weekly offer URLs change. |
| Penny | disabled | Regional offers need a JavaScript market selection; static pages show another region. |
| EDEKA | manual only | Added 2026-10-31. No automatic source has been checked or implemented; prices come from shelf-label photos. |

Blocked sites are never bypassed. If a collector fails, its previous records stay unchanged with their
original observation date, and offers drop out of the ranking once their validity ends.

## Price reports

The "Report a different price" form no longer uses FormSubmit. It sends each report to a Google Apps Script
web app owned by the site owner (source: [`apps-script/Code.gs`](apps-script/Code.gs)):

- **Request:** `POST` to the `/exec` URL in `ENDPOINT` (`index.html`), body = JSON sent as
  `Content-Type: text/plain;charset=utf-8` (avoids a CORS preflight), `credentials: "omit"`.
  Fields: `id` (report id, reused on retries), `supermarket`, `address`, `submittedAt`, `website` (honeypot),
  `fillMs` (time since the form was opened) and `photos` (array of `{name, type, data}` with base64 data).
- **Receiver:** validates the fields, checks that photos really are JPG/PNG (max 10 photos, 10 MB total),
  drops spam (filled honeypot or `fillMs` under 3 s; the page waits so real visitors are never below 3 s),
  limits volume to 30 reports per hour and ignores duplicate ids. It saves the photos and a `report.txt` to the
  private Drive folder "Radler price reports", then emails them to the owner (subject "New Radler Price Information").
- **Response:** `{"ok": true, "emailed": true|false}` once the report is stored in Drive (`emailed: false` means
  the notification email failed but the report was saved), or `{"ok": false, "error", "message"}`.
- **Page behaviour:** success is shown only after a readable JSON answer with `ok: true`. Network errors,
  timeouts, unreadable or opaque responses and `ok: false` show an error; the entries, photos and report id
  are kept for a retry, and only one request can run at a time.

Reports never change `data.json` automatically.

Setup / redeploy: script.google.com → New project → paste `apps-script/Code.gs` → Deploy → New deployment →
Web app (Execute as: Me, Who has access: Anyone) → authorize → copy the `/exec` URL into `ENDPOINT` in
`index.html`. After editing the script, use Deploy → Manage deployments → Edit → New version to keep the same URL.
Free quotas (consumer Google account): about 100 emails/day; requests up to ~50 MB.
