# Changelog

## 1.0.1

- Fix: every company failed with "Could not resolve on Screener". Requests
  advertised Brotli (`br`) compression, but without the optional `brotli`
  package it cannot decode Brotli replies, so Screener's search JSON was
  unreadable. The tool now asks only for gzip/deflate.

## 1.0.0

First public release.

- Downloads and auto-renames Annual Reports, DRHP (IPO prospectus), Concall
  Transcripts, Investor Presentations and Credit Ratings for Indian listed
  companies, with a configurable number of years per report type.
- Sources: Screener.in (AR / DRHP / CC / IP), BSE India with NSE India fallback
  (Credit Ratings).
- Desktop app with a pixel-art take on Claude's colour palette (bundled
  Press Start 2P + VT323 fonts, OFL-licensed) and a custom app icon.
- Standalone single-file Windows `.exe` (no Python required) plus
  `HOW_TO_INSTALL_ON_OTHER_PCS.txt`.
- Command-line interface with `--types`, `--years-*`, `--output`, `--dry-run`.
- Reproducible build via `build_release.ps1` / `CorporateFilingsDownloader.spec`.

### Fixes since the first prototype

- BSE: scrip-code parsing (the code lives in an `ng-click` attribute, not an
  `href`), the 12-month date-range limit (now fetched in <=365-day chunks) and
  the server ignoring its `subcategory` filter (now filtered client-side).
- NSE: no longer gives up when the homepage cookie-priming request returns 403;
  dates are parsed from the ISO `sort_date` field; the trading symbol is taken
  from Screener's URL instead of being guessed from the company name.
