<p align="center">
  <img src="assets/icon.png" alt="Corporate Filings Downloader icon" width="128">
</p>

<h1 align="center">Corporate Filings Downloader</h1>

<p align="center">
  Type a company name, pick how many years you want, click <b>Download</b>.<br>
  Annual reports, DRHPs, concall transcripts, investor presentations and credit ratings
  for Indian listed companies, auto-named and neatly filed.
</p>

---

## What is this?

Equity research starts with collecting documents: the last ten annual reports, every
concall transcript, the investor decks, the credit rating letters. Doing that by hand
means clicking through Screener, BSE and NSE company by company, then renaming a
pile of files called `AnnPdfOpen.aspx.pdf`.

**Corporate Filings Downloader** does that collection for you. Give it a company name
and it finds the documents, downloads them, and files them under clean, consistent
names:

```
output/
  Reliance/
    Annual_Reports/          Reliance_AR_2026.pdf  ...
    Concall_Transcripts/     Reliance_CC_Q4FY26.pdf  ...
    Investor_Presentations/  Reliance_IP_Q4FY26.pdf  ...
    Credit_Ratings/          Reliance_CR_2026-07-03.pdf  ...
  Swiggy/
    DRHP/                    Swiggy_DRHP.pdf
```

It ships as a **single Windows `.exe` with a small desktop window** (no Python, no
command line, nothing to install) and also works as a plain **command-line tool**.

## Features

| Document | Naming | Default depth | Source |
|---|---|---|---|
| Annual Reports | `Company_AR_YYYY` | 10 years | Screener.in |
| DRHP (IPO prospectus) | `Company_DRHP` | one-time | Screener.in, resolved via SEBI's filing page |
| Concall Transcripts | `Company_CC_QxFYyy` | 4 years | Screener.in |
| Investor Presentations | `Company_IP_QxFYyy` | 4 years | Screener.in |
| Credit Ratings | `Company_CR_YYYY-MM-DD` | 2 years | BSE India, NSE India as fallback |

- **You choose how many years** of each report type (or untick a type entirely).
- **Preview mode** lists what would be downloaded without downloading anything.
- **Safe to re-run**: existing files are skipped, so you can top a company up later.
- **Polite by design**: realistic headers, 1-3 s random delays between requests,
  retries on rate limits, and a clear log instead of a crash when a site blocks or a
  link is dead (`failed_downloads.log` per company).
- **Fuzzy company lookup**: "reliance", "Reliance Industries" and "Swiggy" all resolve.
- **Pixel-art UI in a Claude-inspired palette**, with two bundled OFL-licensed fonts
  that are loaded privately, so nothing is installed system-wide.

## Get it (Windows)

1. Open the [**Releases**](../../releases) page and download
   `CorporateFilingsDownloader-vX.Y.Z-windows-x64.zip` from **Assets**.
2. Extract it somewhere you can write to (e.g. `Documents`), then double-click
   **`CorporateFilingsDownloader.exe`**.
3. Windows may show *"Windows protected your PC"* because the app isn't signed with a
   paid certificate. Click **More info -> Run anyway**.

That's it: one ~16 MB file, no installer, no Python. To use it on another PC, copy the
same file across.

> **Full step-by-step instructions** (requirements, SmartScreen, antivirus
> false-positives, verifying the download with SHA-256, troubleshooting, uninstalling)
> are in [`HOW_TO_INSTALL_ON_OTHER_PCS.txt`](HOW_TO_INSTALL_ON_OTHER_PCS.txt), which is
> also bundled inside the release zip.

**Requirements:** 64-bit Windows 10 or 11 and an internet connection.

## Using the app

1. Enter a **company name**.
2. Tick the document types you want and set the **years** with `-` / `+`.
3. Choose a **save folder** (default: an `output` folder next to the `.exe`).
4. Click **DOWNLOAD** and watch the **PROGRESS** box. Use **OPEN FOLDER** when done.

Full downloads are intentionally slow-ish (several minutes for a company with a long
history) because of the polite delays between requests.

## Command-line use

The downloader is a normal Python script too. You need Python 3.10+.

```bash
pip install -r requirements.txt

python research_downloader.py "Reliance Industries"
python research_downloader.py "Infosys" --types ar,cc --output ./out
python research_downloader.py "Reliance" --years-ar 5 --years-cc 2 --years-ip 2 --years-cr 1
python research_downloader.py "Swiggy" --types drhp
python research_downloader.py "Infosys" --dry-run
```

| Flag | Meaning |
|---|---|
| `--types ar,drhp,cc,ip,cr` | Restrict to specific document types (default: all) |
| `--output DIR` | Output directory (default: `./output`) |
| `--dry-run` | List what would be downloaded, download nothing |
| `--years-ar N` | Years of Annual Reports (default 10) |
| `--years-cc N` | Years of Concall Transcripts (default 4) |
| `--years-ip N` | Years of Investor Presentations (default 4) |
| `--years-cr N` | Years of Credit Ratings (default 2) |

DRHP has no `--years-*` flag: it's a one-time IPO document, so it's either found or not.

### Run the desktop app from source

Double-click [`Run_App.bat`](Run_App.bat). It creates a local `.venv`, installs the
dependencies on first run, and opens the window. (Needs Python 3.10+ with Tcl/Tk, which
the python.org installer includes by default.)

## How it works

- **Screener.in** is the primary source for Annual Reports, Concall Transcripts,
  Investor Presentations and the DRHP button. The company is resolved through
  Screener's search API, then its public company page is parsed.
- **BSE India** is used for Credit Ratings, with **NSE India** as a fallback. A few
  quirks of those APIs are handled explicitly:
  - BSE rejects any date range over 12 months, so multi-year lookbacks are fetched
    in <=365-day chunks and merged.
  - BSE ignores its own `subcategory=Credit Rating` filter, so results are filtered
    client-side by category name.
  - BSE returns the scrip code inside an `ng-click` attribute rather than an `href`.
  - NSE's homepage often answers 403 to scripts even though its JSON API works, so a
    failed "cookie priming" request does not stop the real request. The NSE trading
    symbol is taken from Screener's URL slug rather than guessed from the name.
- **DRHP**: Screener links to SEBI's public filing page, which is usually an HTML
  landing page. The tool follows it one hop and extracts the actual PDF link.
- **Quarter mapping (CC / IP)**: the quarter and financial year are derived from the
  concall *date* shown on Screener (the PDF is never opened), using the Indian
  reporting calendar (FY ends 31 March):

  | Concall month | Maps to |
  |---|---|
  | Apr-Jun | Q4 of the just-ended FY |
  | Jul-Sep | Q1 of the new FY |
  | Oct-Dec | Q2 |
  | Jan-Mar | Q3 |

- **De-duplication**: documents that would get the same filename are downloaded once
  (Screener preferred for AR/DRHP/CC/IP, BSE for CR).

### Initiating-coverage reports are not auto-downloaded

Broker "initiating coverage" research is deliberately **not** part of the automated
pipeline. Those reports are scattered across dozens of brokerage sites with no common
structure, are frequently paywalled or login-gated, and are the brokers' own
copyrighted work. The app instead has a **Search Initiating Coverage** button that opens
a web search in your browser so *you* can review sources and decide what to save.

## Building the `.exe` yourself

```powershell
powershell -ExecutionPolicy Bypass -File build_release.ps1 -Version 1.0.0
```

This creates `.venv` if needed, installs `requirements-build.txt`, runs PyInstaller
against [`CorporateFilingsDownloader.spec`](CorporateFilingsDownloader.spec), and writes
`release/CorporateFilingsDownloader-v<version>-windows-x64.zip` (exe + install guide +
license) together with `release/SHA256SUMS.txt`.

To regenerate the app icon: `python tools/make_icon.py` (needs Pillow).

### Design notes worth knowing before you change anything

- **The GUI never runs downloads in a thread inside its own process.** It re-invokes
  *itself* as a subprocess with a hidden `--cli-worker` flag, which dispatches straight
  to `research_downloader.main()`. In testing, a network call made from a background
  thread in a process that has a live Tk root hung indefinitely, while the identical call
  in a plain thread or a separate process was instant. Piping a subprocess's stdout into
  the log box avoids the problem, and it is also what makes a single-file PyInstaller
  build workable (a frozen exe can't be pointed at a second `.py` file).
- **`lxml` is excluded from the exe** even though it's in `requirements.txt`.
  PyInstaller can miss BeautifulSoup's runtime-dispatched `lxml` import, and the code
  already falls back cleanly to Python's built-in `html.parser`.
- **The default output folder is next to the `.exe`** (`sys.executable`), never
  PyInstaller's temporary extraction folder (`sys._MEIPASS`), which is deleted on exit.
  `_MEIPASS` is only used for read-only bundled resources (fonts, icon).
- **UPX compression is off** in the spec: UPX-packed executables trigger antivirus
  heuristics far more often.

## Project layout

```
gui.py                              Desktop app (also the exe's entry point / worker)
research_downloader.py              The downloader: CLI + all scraping logic
CorporateFilingsDownloader.spec     PyInstaller build definition
build_release.ps1                   One-command build + zip + checksums
version_info.txt                    Windows file-properties metadata for the exe
HOW_TO_INSTALL_ON_OTHER_PCS.txt     End-user install guide (bundled in the release zip)
Run_App.bat                         Run the desktop app from source
requirements.txt                    Runtime dependencies
requirements-build.txt              Build dependencies (adds PyInstaller, Pillow)
assets/icon.ico, icon.png           App icon
assets/fonts/                       Press Start 2P + VT323 and their OFL licenses
tools/make_icon.py                  Regenerates the icon
CHANGELOG.md                        Release notes
```

## Limitations

- **Scrapers are brittle by nature.** Screener, BSE and NSE can change their pages or
  APIs at any time. Selectors live in one place per source (`Screener`, `BSE`, `NSE`
  classes) to make fixes quick; if a source breaks, open an issue.
- Some documents will fail with HTTP 404 because the company's own website removed the
  file. These are logged to `failed_downloads.log`, not treated as fatal.
- DRHPs exist only for recently listed companies, and following Screener's link needs
  `sebi.gov.in` to be reachable from your network.
- The quarter/FY for concalls is inferred from dates, so an unusual results calendar can
  occasionally misfile a quarter.
- The `.exe` is **not code-signed**, so Windows SmartScreen and some antivirus tools may
  warn about it (see the install guide). Every release publishes SHA-256 checksums so you
  can verify your copy.
- The desktop app and `.exe` are **Windows-only**. The command-line tool is plain Python
  and should work anywhere Python 3.10+ does, but has only been tested on Windows.

## Disclaimer

This is an independent, unofficial tool for **personal research**. It is not affiliated
with, endorsed by, or connected to Screener.in, BSE Ltd, NSE, SEBI or any company whose
documents it fetches. It reads only publicly accessible pages, never logs in, and never
bypasses paywalls. You are responsible for complying with the terms of use of the sites
it accesses and for how you use and share the downloaded documents. Nothing produced by
this tool is investment advice.

## License

Released under the [MIT License](LICENSE).

The bundled fonts, [Press Start 2P](https://fonts.google.com/specimen/Press+Start+2P) and
[VT323](https://fonts.google.com/specimen/VT323), are licensed under the SIL Open Font
License 1.1 (license texts in [`assets/fonts/`](assets/fonts)). The `.exe` bundles Python,
Tcl/Tk, [Requests](https://requests.readthedocs.io/) and
[Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/), each under its own
license.
