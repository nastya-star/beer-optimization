# Beer Price Optimization

Cheapest alcoholic Radler in Garching and Munich (REWE, Lidl, Kaufland, ALDI Süd, Penny).
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
 "source": "photo report 2026-10-13",
 "status": "verified"
}
```

| Field | Meaning |
|---|---|
| `city` | `"Garching"` or `"Munich"` |
| `chain` | `"REWE"`, `"Lidl"`, `"Kaufland"`, `"ALDI Süd"`, `"Penny"` |
| `price` | price of the whole package in €, without deposit |
| `count`, `volume_l` | containers in the package, litres per container |
| `deposit` | refundable deposit for the whole package in € (`null` if unknown) |
| `single` | `true` only if one container can be bought on its own at this price |
| `price_type` | `"regular"`, `"offer"` or `"loyalty"` |
| `loyalty_public` | `true` for app discounts anyone can get; `false` for personalised coupons |
| `min_qty` | minimum number of packages required for the price |
| `valid_from`, `valid_to`, `observed` | `YYYY-MM-DD` (`null` if not applicable) |
| `status` | `"verified"` (ranked), `"unverified"` or `"personalized"` (listed, not ranked) |

Rules applied by the page: only alcoholic Radler, `status: "verified"`, public discounts and offers
inside their validity dates are ranked. "Single bottle/can" needs `single: true`, `count: 1`, `min_qty: 1`
and a known deposit (price + deposit). "Per litre" = `price / (count × volume_l)`, without deposit.
Records older than 14 days are flagged as possibly outdated. The `demo` list is simulated data and never ranked.

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

Blocked sites are never bypassed. If a collector fails, its previous records stay unchanged with their
original observation date, and offers drop out of the ranking once their validity ends.

## Price reports

The "Report a different price" form emails reports via FormSubmit to the owner. Reports never change
`data.json` automatically.
