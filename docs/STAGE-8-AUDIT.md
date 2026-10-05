# Stage 8 (Market Intelligence): static audit

Date: 5 Oct 2026. Branch `stage-8-market`, not merged.

This audit was made by reading the code only. GitHub Actions is paused until the monthly allowance resets, so none of the tests below have run yet. Each rule names the code that enforces it and the test that will check it once CI runs.

## Findings fixed during the audit

| # | Rule | What was wrong | Fix |
| --- | --- | --- | --- |
| 1 | Asking vs transaction prices | "Time on market" counted ARCHIVED and EXPIRED listings as closed. Those are withdrawals, not sales. | Only listings currently SOLD or RENTED are counted, and the wording says the status is lister-reported, not a verified sale (`observed.median_days_to_marked_closed`). Every report now lists `transaction_prices` as unavailable (`not_collected`). |
| 2 | Asking vs transaction prices | The AI fallback template said "not a sale price" / "ليس سعر صفقة". That wording would also trip the new guard. | Reworded to "prices asked in listings" / "أسعار طلب معروضة في الإعلانات". |
| 3 | No currency mixing | A listing whose price moved from IQD to USD would have produced a percentage change across two currencies. | A change is measured only when the first and latest prices are in the same currency. |
| 4 | No currency mixing / like for like | The area comparison mixed every sale type (land with apartments) and picked a currency per area, so bars were not comparable. | The comparison uses one segment for the whole scope: the most common sale type in its currency (`areas_basis`). The page states that segment. |
| 5 | Minimum sample | `/market/summary`, which feeds the homepage "Market reading", returned medians for any count, even 1. | Medians are returned only with 5 or more priced listings (`minimum_sample` in the response). |
| 6 | Minimum sample | `MarketStatement` only required that a sample was present. | The model rejects OBSERVED statements with fewer than 5 observations or no observation period. |
| 7 | No fabricated or back-filled history | The month trend took today's price of listings that are still active and grouped them by publication month. A later price cut rewrote "what was asked in January", and listings that had closed disappeared. | The trend uses each listing's first recorded asking price (price history), across every listing that was ever public (excluding drafts, rejected and suspended). With no recorded initial price, nothing is invented and the trend is listed as unavailable. |
| 8 | No back-filled snapshots | `record_snapshot(db, day=...)` could write a snapshot dated in the past, built from today's listings. | It takes no day argument and always records today. Tests move the clock instead. |
| 9 | Demo inclusion | The statement demo flag came from the active listings only, so statements about closed listings, monthly cohorts or snapshots could hide demo data. | Each statement computes its own flag from the rows it used. Snapshots now store `demo_listings`. |
| 10 | Truthful confidence | Confidence used only the sample size and a demo yes/no. | It now also considers freshness (no listing in 90 days means low) and returns `confidence_reasons` (sample band, demo data, stale, asking prices only). |
| 11 | Provenance for every metric | Provenance existed only for the whole report. | Every statement carries `source`, `method`, `period_from` and `period_to`. The page shows "source · period" under each line, with the method as a tooltip. |
| 12 | Duplicates labelled possible | Already worded "may be duplicates". Above 3,000 listings the scan was skipped silently. | The wording is now "possible duplicates, not confirmed", the method key names the heuristic, and a skipped scan is listed as unavailable (`scope_too_large`). |
| 13 | AI cannot add claims | Guards blocked invented numbers and "guaranteed" only. A forecast or advice with no numbers would have passed. | A market-specific validator rejects forecasts, promises, advice and transaction-price claims in Arabic and English (English as whole words, Arabic inside words because of attached prefixes). A rejected output is replaced by the deterministic template. |
| 14 | Kinds stay distinct | "Area breakdown" was OBSERVED but is only a count of areas. The supply change was OBSERVED but compares two recorded counts. | Both are now FACT. Only the AI source may produce AI_INTERPRETATION, and the AI source can produce nothing else. ESTIMATE and SIMULATION are never emitted. |

## Rules already satisfied (verified by reading)

- **Segments:** grouped by type, purpose and currency; quartiles only with 5 or more priced listings; price per m² only with 5 or more listings that have an area.
- **District snapshots:** never inferred. A district scope reports `supply_trend: not_recorded_for_districts` and an empty `supply_history`.
- **Demo exclusion:** `include_demo=false` filters every query (active, cohort, closed, interest, areas, duplicates, snapshot rows).
- **Disclaimer:** the response always carries "not transaction prices or valuations", and the page shows it.

## Tests that will run in CI

`backend/tests/test_market_intelligence.py` has one or more tests per rule above: kinds, sample and period validation, forbidden wording (8 phrasings), template cleanliness, word boundaries, confidence, gaps, provenance, currency separation, demo exclusion, initial-price trend, no invented trend, same-currency changes, sold/rented only, one-segment area comparison, district limits, possible duplicates, guarded AI (4 attempts) and today-only snapshots. `backend/tests/test_market.py` checks the summary floor.

The live checks are in `scripts/live/acceptance.sh` step 11b (Basra, a second city, all of Iraq, and demo exclusion) and `scripts/live/browser_check.py` `market_intelligence` (1920 EN dark, 1440 AR light, 390 AR dark, 390 EN light; Basra and Baghdad; RTL and LTR; per-statement source, unavailable list, provenance and demo exclusion).
