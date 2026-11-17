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

It runs on **Windows and macOS**: a single Windows `.exe` or a Mac `.app` with a small
desktop window (no Python, no command line), and also works as a plain
**command-line tool** on either.

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

## Get it

| | Windows 10 / 11 (64-bit) | macOS 11+ |
|---|---|---|
| Download from [**Releases**](../../releases) | `...-windows-x64.zip` | `...-macos-arm64.zip` (Apple Silicon) / `...-macos-x86_64.zip` (Intel) |
| Run | `CorporateFilingsDownloader.exe` | `Corporate Filings Downloader.app` |
| Full guide | [`HOW_TO_INSTALL_ON_OTHER_PCS.txt`](HOW_TO_INSTALL_ON_OTHER_PCS.txt) | [`HOW_TO_INSTALL_ON_MAC.txt`](HOW_TO_INSTALL_ON_MAC.txt) |
| Run from source | double-click `Run_App.bat` | double-click `Run_App.command` |
| Build it yourself | `build_release.ps1` | `./build_release_mac.sh` |

### Windows

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

### macOS

1. From [**Releases**](../../releases), download the zip for your chip:
   `-macos-arm64.zip` for Apple Silicon (M1/M2/M3/M4), `-macos-x86_64.zip` for Intel.
   (Apple menu -> About This Mac shows which you have.)
2. Unzip it and drag **`Corporate Filings Downloader.app`** into **Applications**.
3. The app isn't signed with a paid Apple certificate, so the first launch is blocked
   once. On macOS 15+: try to open it, then **System Settings -> Privacy & Security ->
   Open Anyway**. On macOS 14 and older: **right-click the app -> Open -> Open**.

Downloads go to `Documents/Corporate Filings Downloader/` by default. If no Mac zip is
attached to a release yet, build the app in one command (see
[Building the Mac `.app`](#building-the-mac-app-yourself)); full details are in
[`HOW_TO_INSTALL_ON_MAC.txt`](HOW_TO_INSTALL_ON_MAC.txt).

**Requirements:** macOS 11 (Big Sur) or newer and an internet connection.

## Using the app

1. Enter a **company name**.
2. Tick the document types you want and set the **years** with `-` / `+`.
3. Choose a **save folder** (default: an `output` folder next to the `.exe` on Windows,
   `Documents/Corporate Filings Downloader` for the Mac app).
4. Click **DOWNLOAD** and watch the **PROGRESS** box. Use **OPEN FOLDER** when done
   (opens Explorer / Finder).

Full downloads are intentionally slow-ish (several minutes for a company with a long
history) because of the polite delays between requests.

## Command-line use

The downloader is a normal Python script too. You need Python 3.10+ (on a Mac, the
built-in Python 3.9 is too old: install one from python.org, and use `python3`/`pip3`).

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

- **Windows:** double-click [`Run_App.bat`](Run_App.bat).
- **macOS:** double-click [`Run_App.command`](Run_App.command) (if macOS won't run it,
  run `chmod +x Run_App.command` once in Terminal).

Either one creates a local `.venv`, installs the dependencies on first run, and opens
the window. (Needs Python 3.10+ with Tcl/Tk, which the python.org installers include
by default. On a Mac without it, `Run_App.command` also accepts
[`uv`](https://docs.astral.sh/uv/) and will fetch a suitable Python itself.)

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

## Building the Mac `.app` yourself

```bash
./build_release_mac.sh 1.1.0             # build + zip
./build_release_mac.sh 1.1.0 --install   # ...and copy it into /Applications
```

This creates `.venv` if needed, installs `requirements-build.txt`, runs PyInstaller
against [`CorporateFilingsDownloader-mac.spec`](CorporateFilingsDownloader-mac.spec), and
writes `release/CorporateFilingsDownloader-v<version>-macos-<arch>.zip` (app + install
guide + license) with `release/SHA256SUMS-macos-<arch>.txt`. The app is built for the
chip of the Mac you build on; build once on Apple Silicon and once on Intel to cover
both. Upload the zip(s) to the GitHub release next to the Windows zip.

To regenerate the app icons (`.ico`, `.png`, `.icns`): `python tools/make_icon.py`
(needs Pillow).

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
- **macOS differences** live in a few helpers at the top of `gui.py`:
  - Fonts are registered process-only through CoreText
    (`CTFontManagerRegisterFontsForURL`, process scope), the Mac counterpart of the
    Windows GDI trick. This must happen **before** `tk.Tk()` is created: Tk on macOS
    snapshots the font list at startup.
  - Aqua ignores colours on a native `tk.Button`, so on macOS buttons are click-bound
    `tk.Label`s (`_make_button`). Windows still uses real buttons.
  - Tk on macOS treats 1 pt as 1 px (72 dpi) while Windows uses 96 dpi, so the app sets
    `tk scaling` to 96/72 on macOS to get the same layout.
  - Inside a `.app` the executable's folder is read-only, so the default save folder
    is `~/Documents/Corporate Filings Downloader`.
  - The Mac spec is a one-folder build wrapped in a `.app` BUNDLE (PyInstaller has
    deprecated single-file `.app`s). `argv_emulation` stays off so the `--cli-worker`
    arguments reach the re-invoked binary.

## Project layout

```
gui.py                              Desktop app (also the exe's entry point / worker)
research_downloader.py              The downloader: CLI + all scraping logic
CorporateFilingsDownloader.spec     PyInstaller build definition
build_release.ps1                   One-command build + zip + checksums
version_info.txt                    Windows file-properties metadata for the exe
HOW_TO_INSTALL_ON_OTHER_PCS.txt     End-user install guide (bundled in the release zip)
Run_App.bat                         Run the desktop app from source (Windows)
Run_App.command                     Run the desktop app from source (macOS)
CorporateFilingsDownloader-mac.spec PyInstaller build definition for the Mac .app
build_release_mac.sh                One-command Mac build + zip + checksums
HOW_TO_INSTALL_ON_MAC.txt           End-user install guide for Mac (bundled in the Mac zip)
requirements.txt                    Runtime dependencies
requirements-build.txt              Build dependencies (adds PyInstaller, Pillow)
assets/icon.ico, icon.png, icon.icns App icon (Windows, window, macOS)
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
- The `.exe` and `.app` are **not code-signed**, so Windows SmartScreen, macOS
  Gatekeeper and some antivirus tools may warn about them (see the install guides).
  Every release publishes SHA-256 checksums so you can verify your copy.
- Supported desktop platforms are **Windows 10/11 and macOS 11+**. On Linux the
  command-line tool and `python gui.py` should work but are untested.

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
License 1.1 (license texts in [`assets/fonts/`](assets/fonts)). The `.exe` and `.app` bundle Python,
Tcl/Tk, [Requests](https://requests.readthedocs.io/) and
[Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/), each under its own
license.
