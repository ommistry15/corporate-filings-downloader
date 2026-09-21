#!/usr/bin/env python3
"""
research_downloader.py
======================

Download and rename financial-research documents for Indian listed companies.

Document types:
    AR    Annual Reports         CompanyName_AR_YYYY                last 10 years
    DRHP  Draft Red Herring Pros. CompanyName_DRHP                  one-time, IPO-era only
    CC    Concall Transcripts    CompanyName_CC_Q[X]FY[YY]          last 4 years
    IP    Investor Presentations CompanyName_IP_Q[X]FY[YY]          last 4 years
    CR    Credit Ratings         CompanyName_CR_YYYY-MM-DD          last 2 years

Sources (best/most-complete result wins, deduped):
    1. Screener.in  -> AR, DRHP, CC, IP   (primary)
    2. BSE India    -> CR                (supplementary, may block)
    3. NSE India    -> CR                (supplementary, may block)

Usage:
    python research_downloader.py "Reliance Industries"
    python research_downloader.py "Reliance" --types ar,cc
    python research_downloader.py "Infosys" --output ./out --dry-run

This is a single self-contained file. See requirements.txt for dependencies.
Network scraping of third-party sites is inherently brittle; selectors are kept
in one place (the Source classes) so they are easy to adjust if a site changes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Prefer the fast lxml parser when available, but fall back to the stdlib parser
# so lxml is an optional dependency.
try:
    import lxml  # noqa: F401
    PARSER = "lxml"
except ImportError:
    PARSER = "html.parser"

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #

TODAY = dt.date.today()

DEPTH_YEARS = {
    "AR": 10,
    "CC": 4,
    "IP": 4,
    "CR": 2,
}

FOLDER_FOR_TYPE = {
    "AR": "Annual_Reports",
    "DRHP": "DRHP",
    "CC": "Concall_Transcripts",
    "IP": "Investor_Presentations",
    "CR": "Credit_Ratings",
}

# DRHP is a one-time IPO document, not a recurring report, so it has no
# DEPTH_YEARS entry and is never passed through within_depth().
ALL_TYPES = ["AR", "DRHP", "CC", "IP", "CR"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

MIN_DELAY, MAX_DELAY = 1.0, 3.0
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class Document:
    """A single document we intend to download."""
    doc_type: str            # AR / CC / IP / CR
    url: str
    label: str               # filename stem WITHOUT extension, e.g. Reliance_AR_2026
    source: str              # screener / bse / nse
    sort_key: tuple = ()     # for ordering newest-first within a type

    @property
    def filename(self) -> str:
        return f"{self.label}.pdf"


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _make_stdio_utf8() -> None:
    """Windows consoles default to cp1252 and choke on ✓/✗. Force UTF-8 output."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_make_stdio_utf8()

# Use plain glyphs that survive even if reconfigure failed on an exotic console.
OK_MARK, FAIL_MARK = "✓", "✗"  # ✓ ✗


def _print_sink(line: str) -> None:
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        safe = line.replace(OK_MARK, "OK").replace(FAIL_MARK, "x")
        print(safe.encode("ascii", "replace").decode("ascii"), flush=True)


# Overridable by callers that embed this module directly (e.g. the desktop
# GUI, which runs run() in a background thread and wants each line routed
# into its own log widget instead of stdout). CLI use leaves this as-is.
LOG_SINK = _print_sink


def log(company: str, msg: str) -> None:
    LOG_SINK(f"[{company}] {msg}")


def short_name(full_name: str) -> str:
    """'Reliance Industries Ltd' -> 'Reliance'. First meaningful token, alnum only."""
    cleaned = re.sub(r"[^A-Za-z0-9 &]", " ", full_name)
    tokens = [t for t in cleaned.split() if t]
    if not tokens:
        return "Company"
    first = tokens[0]
    # Avoid generic first words swallowing the real name.
    return re.sub(r"[^A-Za-z0-9]", "", first) or "Company"


def fy_from_calendar(year: int, month: int) -> int:
    """Indian financial year ends 31 March. Returns the FY end year (e.g. 2026 == FY26)."""
    return year + 1 if month >= 4 else year


def quarter_for_concall(year: int, month: int) -> tuple[int, int] | None:
    """
    Map a *concall/result month* to the quarter it reports on, plus that FY end year.

    Indian results are typically announced ~1-1.5 months after quarter end:
        Apr/May        -> Q4 (Jan-Mar) of the just-ended FY
        Jul/Aug        -> Q1 (Apr-Jun)
        Oct/Nov        -> Q2 (Jul-Sep)
        Jan/Feb        -> Q3 (Oct-Dec)
    Returns (quarter, fy_end_year) or None if the month is ambiguous.
    """
    # quarter, and how to derive the FY end year from the concall date
    if month in (4, 5, 6):
        return 4, year                 # Q4 of FY ending this March
    if month in (7, 8, 9):
        return 1, year + 1             # Q1 of new FY
    if month in (10, 11, 12):
        return 2, year + 1             # Q2
    if month in (1, 2, 3):
        return 3, year                 # Q3 of FY ending this March
    return None


MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_month_year(text: str) -> tuple[int, int] | None:
    """Parse strings like 'May 2024', 'Feb 2025' -> (month, year)."""
    m = re.search(r"([A-Za-z]{3,9})[ '\-]*\s*(\d{4})", text)
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower()[:4]) or MONTHS.get(m.group(1).lower()[:3])
    if not mon:
        return None
    return mon, int(m.group(2))


def within_depth(doc_type: str, year: int, depth_years: dict) -> bool:
    return year >= TODAY.year - depth_years[doc_type] + 1


def nse_symbol_from_screener_url(url: str) -> str | None:
    """
    Screener's company-page URL slug is the NSE trading symbol for NSE-listed
    companies, e.g. https://www.screener.in/company/RELIANCE/consolidated/
    -> 'RELIANCE'. BSE-only companies get a numeric slug instead; return None
    for those since it isn't an NSE symbol.
    """
    parts = [p for p in url.rstrip("/").split("/") if p]
    if not parts:
        return None
    slug = parts[-1]
    if slug.lower() == "consolidated" and len(parts) >= 2:
        slug = parts[-2]
    if not slug or slug.isdigit() or not re.fullmatch(r"[A-Za-z0-9&-]+", slug):
        return None
    return slug.upper()


def resolve_drhp_pdf(http: Http, landing_url: str) -> str | None:
    """
    Screener's DRHP button links to SEBI's public filing page for the
    document (e.g. sebi.gov.in/filings/public-issues/.../..._prospectus.html),
    which is usually an HTML page rather than a direct PDF. Follow it one hop
    and pull out the actual PDF link; if the URL already serves a PDF
    directly, use it as-is.
    """
    try:
        resp = http.get(landing_url, polite=True)
    except requests.RequestException:
        return None
    if not resp or resp.status_code != 200:
        return None
    ctype = resp.headers.get("Content-Type", "").lower()
    if resp.content[:4] == b"%PDF" or "pdf" in ctype:
        return landing_url
    if "html" not in ctype:
        return None
    soup = BeautifulSoup(resp.text, PARSER)
    candidates = [a["href"] for a in soup.find_all("a", href=True)
                  if a["href"].lower().split("?")[0].endswith(".pdf")]
    if not candidates:
        return None
    return urljoin(landing_url, candidates[0])


# --------------------------------------------------------------------------- #
# HTTP session with retries, headers, polite delays
# --------------------------------------------------------------------------- #

class Http:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self._headers())

    @staticmethod
    def _headers() -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _sleep(self):
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    def get(self, url: str, *, referer: str | None = None,
            extra_headers: dict | None = None, stream: bool = False,
            polite: bool = True) -> requests.Response | None:
        headers = {}
        if referer:
            headers["Referer"] = referer
        if extra_headers:
            headers.update(extra_headers)
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if polite:
                    self._sleep()
                # rotate UA occasionally
                self.session.headers["User-Agent"] = random.choice(USER_AGENTS)
                resp = self.session.get(
                    url, headers=headers, timeout=REQUEST_TIMEOUT, stream=stream,
                    allow_redirects=True,
                )
                if resp.status_code in (429, 503):
                    wait = attempt * 4
                    time.sleep(wait)
                    continue
                if resp.status_code == 200:
                    return resp
                if resp.status_code in (401, 403):
                    # Likely login wall or bot block; caller decides.
                    return resp
                if resp.status_code == 404:
                    return resp
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(attempt * 2)
        if last_exc:
            raise last_exc
        return None


# --------------------------------------------------------------------------- #
# Source: Screener.in (primary -> AR, CC, IP)
# --------------------------------------------------------------------------- #

class Screener:
    BASE = "https://www.screener.in"
    SEARCH = BASE + "/api/company/search/?q={q}"

    def __init__(self, http: Http):
        self.http = http

    # -- company resolution (fuzzy) ----------------------------------------- #
    def resolve(self, query: str) -> dict | None:
        """Return {'name':..., 'url':..., 'id':...} for the best match, or None."""
        url = self.SEARCH.format(q=requests.utils.quote(query))
        resp = self.http.get(url, referer=self.BASE,
                             extra_headers={"X-Requested-With": "XMLHttpRequest",
                                            "Accept": "application/json"})
        if not resp or resp.status_code != 200:
            return None
        try:
            results = resp.json()
        except ValueError:
            return None
        if not results:
            return None
        # Prefer an exact-ish name match, else the first hit.
        q = query.lower()
        scored = sorted(
            results,
            key=lambda r: (
                0 if r.get("name", "").lower().startswith(q) else
                1 if q in r.get("name", "").lower() else 2
            ),
        )
        best = scored[0]
        # The search 'url' may point to /company/<code>/ or /company/<code>/consolidated/
        return {"name": best.get("name", query),
                "url": urljoin(self.BASE, best.get("url", "")),
                "id": best.get("id")}

    def fetch_page(self, company_url: str) -> BeautifulSoup | None:
        # Prefer consolidated view (richer doc list) but fall back to whatever resolves.
        urls = [company_url]
        if not company_url.rstrip("/").endswith("consolidated"):
            urls.insert(0, company_url.rstrip("/") + "/consolidated/")
        for u in urls:
            resp = self.http.get(u, referer=self.BASE)
            if resp and resp.status_code == 200 and "documents" in resp.text.lower():
                return BeautifulSoup(resp.text, PARSER)
        # last resort: plain page even without docs marker
        resp = self.http.get(company_url, referer=self.BASE)
        if resp and resp.status_code == 200:
            return BeautifulSoup(resp.text, PARSER)
        return None

    # -- document extraction ------------------------------------------------ #
    def annual_reports(self, soup: BeautifulSoup, name: str,
                        depth_years: dict) -> list[Document]:
        docs: list[Document] = []
        section = soup.find(class_=re.compile(r"annual-reports"))
        anchors = section.find_all("a", href=True) if section else []
        if not anchors:
            # Fallback: any link whose text mentions 'Financial Year'
            anchors = [a for a in soup.find_all("a", href=True)
                       if "financial year" in a.get_text(" ", strip=True).lower()]
        seen_years = set()
        for a in anchors:
            text = a.get_text(" ", strip=True)
            ym = re.search(r"(20\d{2})", text)
            if not ym:
                continue
            year = int(ym.group(1))
            if year in seen_years or not within_depth("AR", year, depth_years):
                continue
            seen_years.add(year)
            docs.append(Document(
                doc_type="AR", url=urljoin(self.BASE, a["href"]),
                label=f"{name}_AR_{year}", source="screener",
                sort_key=(year,),
            ))
        return docs

    def concalls(self, soup: BeautifulSoup, name: str,
                 depth_years: dict) -> list[Document]:
        """Extract Transcript (CC) and PPT (IP) links from the concalls block."""
        cc: list[Document] = []
        ip: list[Document] = []
        section = soup.find(class_=re.compile(r"concalls"))
        rows: Iterable = section.find_all("li") if section else []
        for li in rows:
            row_text = li.get_text(" ", strip=True)
            my = parse_month_year(row_text)
            if not my:
                continue
            month, year = my
            q = quarter_for_concall(year, month)
            if not q:
                continue
            quarter, fy_end = q
            fy2 = fy_end % 100
            # CC and IP share a depth window; use the looser (larger) of the two
            # requested depths so a document isn't dropped for one type but kept
            # for the other.
            depth = max(depth_years.get("CC", 0), depth_years.get("IP", 0))
            if not within_depth("CC", fy_end, {"CC": depth}):
                continue
            for a in li.find_all("a", href=True):
                atext = a.get_text(" ", strip=True).lower()
                href = urljoin(self.BASE, a["href"])
                if "transcript" in atext:
                    cc.append(Document(
                        doc_type="CC", url=href,
                        label=f"{name}_CC_Q{quarter}FY{fy2:02d}",
                        source="screener", sort_key=(fy_end, quarter),
                    ))
                elif "ppt" in atext or "presentation" in atext:
                    ip.append(Document(
                        doc_type="IP", url=href,
                        label=f"{name}_IP_Q{quarter}FY{fy2:02d}",
                        source="screener", sort_key=(fy_end, quarter),
                    ))
        return cc + ip

    def drhp_link(self, soup: BeautifulSoup) -> str | None:
        """
        The DRHP button sits in the same 'documents annual-reports' block as
        the Annual Report links, as a separate button linking out to SEBI's
        public filing page - only present for companies that had an IPO
        recent enough for Screener to have indexed it.
        """
        section = soup.find(class_=re.compile(r"annual-reports"))
        if not section:
            return None
        for a in section.find_all("a", href=True):
            if a.get_text(strip=True).upper() == "DRHP":
                return urljoin(self.BASE, a["href"])
        return None

    def collect(self, soup: BeautifulSoup, name: str,
                types: set[str], depth_years: dict) -> list[Document]:
        out: list[Document] = []
        if "AR" in types:
            out += self.annual_reports(soup, name, depth_years)
        if "DRHP" in types:
            link = self.drhp_link(soup)
            if link:
                pdf_url = resolve_drhp_pdf(self.http, link)
                if pdf_url:
                    out.append(Document(
                        doc_type="DRHP", url=pdf_url, label=f"{name}_DRHP",
                        source="screener", sort_key=(0,),
                    ))
                else:
                    log(name, f"DRHP: found a link on Screener ({link}) but "
                              f"couldn't reach it to pull out the PDF; skipping.")
        if "CC" in types or "IP" in types:
            for d in self.concalls(soup, name, depth_years):
                if d.doc_type in types:
                    if not within_depth(d.doc_type, d.sort_key[0], depth_years):
                        continue
                    out.append(d)
        return out


# --------------------------------------------------------------------------- #
# Source: BSE India (supplementary -> CR, and IP/AR fallback)
# --------------------------------------------------------------------------- #

class BSE:
    """
    BSE exposes a JSON announcements API. It frequently rate-limits or blocks
    automated requests; every call is wrapped so a block degrades to a warning.
    """
    WEB = "https://www.bseindia.com"
    API = "https://api.bseindia.com/BseIndiaAPI/api"

    def __init__(self, http: Http):
        self.http = http

    def _api_headers(self) -> dict:
        return {
            "Accept": "application/json, text/plain, */*",
            "Origin": self.WEB,
            "Referer": self.WEB + "/",
        }

    def scrip_code(self, query: str) -> tuple[str, str] | None:
        """Return (scrip_code, company_name) or None.

        BSE's search returns an HTML fragment of <li> rows whose scrip code
        lives in an `ng-click="liclick('500325','NAME')"` attribute, not in a
        normal <a href>, so it has to be pulled out with a targeted regex
        rather than BeautifulSoup anchor parsing.
        """
        url = (self.API + "/PeerSmartSearch/w?Type=SS&text="
               + requests.utils.quote(query))
        try:
            resp = self.http.get(url, extra_headers=self._api_headers())
        except requests.RequestException:
            return None
        if not resp or resp.status_code != 200:
            return None
        m = re.search(r"liclick\(\s*'(\d+)'\s*,\s*'([^']+)'\s*\)", resp.text)
        if not m:
            return None
        return m.group(1), m.group(2).strip() or query

    def credit_ratings(self, scrip: str, name: str, depth_years: dict) -> list[Document]:
        """
        Pull 'Credit Rating' announcements for the requested CR depth window.

        Two quirks of this API drive the logic below:
        - It hard-rejects any strPrevDate/strToDate span over 12 months
          ({"Status": false, "Message": "Date range cannot exceed 12 months."}),
          so a multi-year depth has to be split into <=365-day chunks.
        - `subcategory=Credit%20Rating` is not actually applied server-side; it
          returns every announcement for the scrip regardless of category, so
          rows must be filtered client-side on SUBCATNAME/NEWSSUB.
        """
        years = max(1, depth_years["CR"])
        cutoff = TODAY - dt.timedelta(days=365 * years)
        docs: list[Document] = []
        seen = set()
        window_end = TODAY
        while window_end > cutoff:
            window_start = max(window_end - dt.timedelta(days=364), cutoff)
            frm = window_start.strftime("%Y%m%d")
            to = window_end.strftime("%Y%m%d")
            url = (f"{self.API}/AnnSubCategoryGetData/w?pageno=1&strCat=-1&strPrevDate={frm}"
                   f"&strScrip={scrip}&strSearch=P&strToDate={to}&strType=C"
                   f"&subcategory=Credit%20Rating")
            try:
                resp = self.http.get(url, extra_headers=self._api_headers())
            except requests.RequestException:
                break
            if not resp or resp.status_code != 200:
                break
            try:
                data = resp.json()
            except ValueError:
                break
            rows = data.get("Table", []) if isinstance(data, dict) else []
            for row in rows:
                subcat = (row.get("SUBCATNAME") or row.get("NEWSSUB") or "").lower()
                if "credit rating" not in subcat:
                    continue
                pdf = (row.get("ATTACHMENTNAME") or "").strip()
                date_raw = (row.get("NEWS_DT") or row.get("News_submission_dt") or "")[:10]
                if not pdf or not date_raw:
                    continue
                try:
                    d = dt.date.fromisoformat(date_raw)
                except ValueError:
                    continue
                key = (d.isoformat(), pdf)
                if key in seen:
                    continue
                seen.add(key)
                file_url = f"{self.WEB}/xml-data/corpfiling/AttachLive/{pdf}"
                docs.append(Document(
                    doc_type="CR", url=file_url,
                    label=f"{name}_CR_{d.isoformat()}",
                    source="bse", sort_key=(d.year, d.month, d.day),
                ))
            window_end = window_start - dt.timedelta(days=1)
        return docs


# --------------------------------------------------------------------------- #
# Source: NSE India (supplementary -> CR fallback)
# --------------------------------------------------------------------------- #

class NSE:
    """
    NSE requires first hitting the homepage to obtain cookies, then calling the
    JSON API with those cookies. It blocks aggressively; failures degrade to a
    warning.
    """
    WEB = "https://www.nseindia.com"
    API = "https://www.nseindia.com/api"

    def __init__(self, http: Http):
        self.http = http
        self._primed = False

    def _prime(self) -> bool:
        try:
            r = self.http.get(self.WEB, referer="https://www.google.com/")
        except requests.RequestException:
            return False
        self._primed = bool(r and r.status_code == 200)
        return self._primed

    @staticmethod
    def _parse_date(row: dict) -> dt.date | None:
        """
        `sort_date` is ISO-formatted ("2025-12-23 20:02:19"); `an_dt` is not
        ("23-Dec-2025 20:02:19"), so it needs its own strptime rather than a
        naive fromisoformat() on a truncated slice.
        """
        sort_date = (row.get("sort_date") or "").strip()
        if sort_date:
            try:
                return dt.date.fromisoformat(sort_date[:10])
            except ValueError:
                pass
        an_dt = (row.get("an_dt") or "").strip()
        if an_dt:
            try:
                return dt.datetime.strptime(an_dt.split(" ")[0], "%d-%b-%Y").date()
            except ValueError:
                pass
        return None

    def credit_ratings(self, symbol: str, name: str, depth_years: dict) -> list[Document]:
        if not symbol:
            return []
        # Priming is best-effort: the corporate-announcements API has been
        # observed to work even when the homepage itself 403s, so a failed
        # prime should not block the actual request.
        if not self._primed:
            self._prime()
        headers = {
            "Accept": "application/json",
            "Referer": self.WEB + "/get-quotes/equity?symbol=" + symbol,
            "X-Requested-With": "XMLHttpRequest",
        }
        frm = (TODAY - dt.timedelta(days=365 * max(1, depth_years["CR"]))).strftime("%d-%m-%Y")
        to = TODAY.strftime("%d-%m-%Y")
        url = (f"{self.API}/corporate-announcements?index=equities&symbol={symbol}"
               f"&from_date={frm}&to_date={to}")
        try:
            resp = self.http.get(url, extra_headers=headers)
        except requests.RequestException:
            return []
        if not resp or resp.status_code != 200:
            return []
        try:
            rows = resp.json()
        except ValueError:
            return []
        if isinstance(rows, dict):
            rows = rows.get("data", [])
        docs: list[Document] = []
        seen = set()
        for row in rows or []:
            subject = (row.get("desc") or row.get("subject") or "").lower()
            attced = row.get("attchmntFile") or row.get("attachmentFile") or ""
            if "credit rating" not in subject and "rating" not in subject:
                continue
            if not attced:
                continue
            d = self._parse_date(row)
            if d is None:
                continue
            if attced in seen:
                continue
            seen.add(attced)
            docs.append(Document(
                doc_type="CR", url=attced,
                label=f"{name}_CR_{d.isoformat()}",
                source="nse", sort_key=(d.year, d.month, d.day),
            ))
        return docs


# --------------------------------------------------------------------------- #
# Downloader / orchestration
# --------------------------------------------------------------------------- #

class Downloader:
    def __init__(self, output_root: str, dry_run: bool, http: Http,
                 display_name: str, company_dir_name: str):
        self.output_root = output_root
        self.dry_run = dry_run
        self.http = http
        self.display = display_name
        self.company_dir = os.path.join(output_root, company_dir_name)
        self.fail_log = os.path.join(self.company_dir, "failed_downloads.log")
        self.counts = {"downloaded": 0, "skipped": 0, "failed": 0}

    def _dir_for(self, doc: Document) -> str:
        return os.path.join(self.company_dir, FOLDER_FOR_TYPE[doc.doc_type])

    def _log_failure(self, doc: Document, reason: str) -> None:
        os.makedirs(self.company_dir, exist_ok=True)
        ts = dt.datetime.now().isoformat(timespec="seconds")
        with open(self.fail_log, "a", encoding="utf-8") as fh:
            fh.write(f"{ts}\t{doc.doc_type}\t{doc.filename}\t{doc.source}\t"
                     f"{doc.url}\t{reason}\n")

    def download(self, doc: Document) -> None:
        target_dir = self._dir_for(doc)
        path = os.path.join(target_dir, doc.filename)

        if os.path.exists(path) and os.path.getsize(path) > 0:
            log(self.display, f"  {doc.filename} already exists - skipping")
            self.counts["skipped"] += 1
            return

        if self.dry_run:
            log(self.display, f"  [dry-run] would download {doc.filename}  <- {doc.url}")
            return

        log(self.display, f"  Downloading {doc.filename} ...")
        try:
            referer = {"screener": Screener.BASE, "bse": BSE.WEB,
                       "nse": NSE.WEB}.get(doc.source)
            resp = self.http.get(doc.url, referer=referer, stream=True)
            if resp is None:
                raise RuntimeError("no response")
            if resp.status_code in (401, 403):
                raise RuntimeError(f"blocked/login-wall (HTTP {resp.status_code})")
            if resp.status_code == 404:
                raise RuntimeError("not found (HTTP 404)")
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")

            ctype = resp.headers.get("Content-Type", "").lower()
            first = resp.raw.read(5) if hasattr(resp, "raw") else b""
            # Some servers send octet-stream; accept if it sniffs as PDF.
            looks_pdf = first.startswith(b"%PDF") or "pdf" in ctype
            if not looks_pdf and "html" in ctype:
                raise RuntimeError("not a PDF (got HTML - likely a redirect/login page)")

            os.makedirs(target_dir, exist_ok=True)
            tmp = path + ".part"
            with open(tmp, "wb") as fh:
                if first:
                    fh.write(first)
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        fh.write(chunk)
            if os.path.getsize(tmp) == 0:
                os.remove(tmp)
                raise RuntimeError("empty file")
            os.replace(tmp, path)
            log(self.display, f"  Downloading {doc.filename} ... {OK_MARK}")
            self.counts["downloaded"] += 1
        except Exception as exc:  # noqa: BLE001 - we want to keep going
            log(self.display, f"  Downloading {doc.filename} ... {FAIL_MARK} ({exc})")
            self._log_failure(doc, str(exc))
            self.counts["failed"] += 1


# --------------------------------------------------------------------------- #
# Dedup + ordering
# --------------------------------------------------------------------------- #

def dedupe(docs: list[Document]) -> list[Document]:
    """
    Drop duplicates. Two docs are 'the same' if they would produce the same
    filename (same type + same period/year). Prefer Screener for AR/CC/IP and
    BSE for CR; otherwise first-seen wins.
    """
    preferred = {"AR": "screener", "DRHP": "screener", "CC": "screener",
                 "IP": "screener", "CR": "bse"}
    best: dict[str, Document] = {}
    for d in docs:
        key = d.label  # filename stem is the natural identity
        cur = best.get(key)
        if cur is None:
            best[key] = d
            continue
        pref = preferred.get(d.doc_type)
        if cur.source != pref and d.source == pref:
            best[key] = d
    return list(best.values())


def order(docs: list[Document]) -> list[Document]:
    return sorted(docs, key=lambda d: (ALL_TYPES.index(d.doc_type),
                                       tuple(-x for x in d.sort_key)))


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #

def gather(query: str, types: set[str], http: Http,
           depth_years: dict) -> tuple[str, str, list[Document]]:
    """Resolve the company and gather candidate documents across sources."""
    screener = Screener(http)

    resolved = screener.resolve(query)
    if resolved:
        display_full = resolved["name"]
    else:
        display_full = query
        log(short_name(query), "Could not resolve on Screener; continuing best-effort.")

    name = short_name(display_full)
    docs: list[Document] = []

    # --- Screener: AR / DRHP / CC / IP ---
    if types & {"AR", "DRHP", "CC", "IP"} and resolved:
        soup = screener.fetch_page(resolved["url"])
        if soup:
            found = screener.collect(soup, name, types, depth_years)
            for t in ("AR", "DRHP", "CC", "IP"):
                if t in types:
                    n = sum(1 for d in found if d.doc_type == t)
                    label = {"AR": "Annual Reports", "DRHP": "DRHP",
                             "CC": "Concall Transcripts",
                             "IP": "Investor Presentations"}[t]
                    if t == "DRHP" and n == 0:
                        log(name, "DRHP: none found (only recently-IPO'd "
                                  "companies have one on Screener).")
                    else:
                        log(name, f"Fetching {label} from Screener... found {n}")
            docs += found
        else:
            log(name, "Screener page could not be loaded; skipping AR/DRHP/CC/IP.")

    # --- BSE / NSE: Credit Ratings ---
    if "CR" in types:
        cr_docs: list[Document] = []
        bse = BSE(http)
        try:
            sc = bse.scrip_code(display_full)
            if sc:
                cr_docs += bse.credit_ratings(sc[0], name, depth_years)
                log(name, f"Fetching Credit Ratings from BSE... found {len(cr_docs)}")
            else:
                log(name, "BSE: could not resolve scrip code (blocked or no match).")
        except Exception as exc:  # noqa: BLE001
            log(name, f"BSE lookup failed ({exc}); skipping.")

        if not cr_docs:
            nse = NSE(http)
            try:
                # Screener's company-page URL slug is the real NSE trading
                # symbol for NSE-listed companies; fall back to a guess from
                # the short name only if that isn't available.
                symbol = None
                if resolved:
                    symbol = nse_symbol_from_screener_url(resolved["url"])
                if not symbol:
                    symbol = re.sub(r"[^A-Za-z]", "", name).upper()
                nse_docs = nse.credit_ratings(symbol, name, depth_years)
                if nse_docs:
                    log(name, f"Fetching Credit Ratings from NSE... found {len(nse_docs)}")
                    cr_docs += nse_docs
                else:
                    log(name, "NSE: no credit ratings found (blocked or none).")
            except Exception as exc:  # noqa: BLE001
                log(name, f"NSE lookup failed ({exc}); skipping.")
        docs += cr_docs

    return display_full, name, docs


def run(query: str, types: set[str], output: str, dry_run: bool,
        depth_years: dict | None = None) -> int:
    depth_years = depth_years or DEPTH_YEARS
    http = Http()
    try:
        display_full, name, docs = gather(query, types, http, depth_years)
    except requests.RequestException as exc:
        # No internet, DNS failure, firewall/VPN/proxy block, site down...
        # Report it plainly instead of dying with a raw traceback.
        log(short_name(query),
            f"Couldn't connect to the website ({type(exc).__name__}). Check "
            f"your internet connection (and any VPN, firewall or proxy), then "
            f"try again.")
        return 2

    docs = dedupe(docs)
    docs = [d for d in docs if d.doc_type in types]
    docs = order(docs)

    if not docs:
        log(name, "No documents found. Nothing to do.")
        return 1

    dl = Downloader(output, dry_run, http, display_name=name,
                    company_dir_name=name)
    log(name, f"Resolved to '{display_full}'. {len(docs)} document(s) queued.")
    for doc in docs:
        dl.download(doc)

    c = dl.counts
    log(name, f"Done. {c['downloaded']} downloaded, "
              f"{c['skipped']} skipped (already exist), {c['failed']} failed.")
    if c["failed"]:
        log(name, f"Failures logged to {dl.fail_log}")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_types(raw: str) -> set[str]:
    wanted = {t.strip().upper() for t in raw.split(",") if t.strip()}
    invalid = wanted - set(ALL_TYPES)
    if invalid:
        raise argparse.ArgumentTypeError(
            f"unknown type(s): {', '.join(sorted(invalid))}. "
            f"Valid: {', '.join(t.lower() for t in ALL_TYPES)}")
    return wanted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="research_downloader.py",
        description="Download & rename financial research docs for Indian listed companies.",
    )
    parser.add_argument("company", help='Company name, e.g. "Reliance Industries"')
    parser.add_argument("--types", type=parse_types, default=set(ALL_TYPES),
                        help="Comma list of doc types to fetch: ar,drhp,cc,ip,cr (default: all)")
    parser.add_argument("--output", default="./output",
                        help="Output directory (default: ./output)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be downloaded without downloading")
    parser.add_argument("--years-ar", type=int, default=DEPTH_YEARS["AR"],
                        help=f"Years of Annual Reports to fetch (default: {DEPTH_YEARS['AR']})")
    parser.add_argument("--years-cc", type=int, default=DEPTH_YEARS["CC"],
                        help=f"Years of Concall Transcripts to fetch (default: {DEPTH_YEARS['CC']})")
    parser.add_argument("--years-ip", type=int, default=DEPTH_YEARS["IP"],
                        help=f"Years of Investor Presentations to fetch (default: {DEPTH_YEARS['IP']})")
    parser.add_argument("--years-cr", type=int, default=DEPTH_YEARS["CR"],
                        help=f"Years of Credit Ratings to fetch (default: {DEPTH_YEARS['CR']})")
    args = parser.parse_args(argv)

    depth_years = {
        "AR": max(1, args.years_ar), "CC": max(1, args.years_cc),
        "IP": max(1, args.years_ip), "CR": max(1, args.years_cr),
    }

    try:
        return run(args.company, args.types, args.output, args.dry_run, depth_years)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
