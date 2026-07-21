#!/usr/bin/env python
"""Fetch a researcher's works from OpenAlex by ORCID.

Writes two files next to this script:
  papers.json  full structured data for building the page, including each work's
               citations-by-year (counts_by_year) for the charts
  papers.csv   a skim spreadsheet (open in Excel): title, year, venue, type,
               lifetime citations, co-authors -- so you can check the list by eye

Usage:
  python -X utf8 fetch_papers.py [ORCID]

Run with -X utf8 so Windows can write Greek letters (alpha, beta) and other
special characters in titles without crashing. ORCID defaults to Nick Shulman's.

Only the Python standard library is used, so there is nothing to pip install.
"""
import sys
import os
import re
import json
import csv
import time
import urllib.request
import urllib.error

# Always read/write alongside this script, so it works no matter where it is run from.
HERE = os.path.dirname(os.path.abspath(__file__))

MAILTO = "nickshulman@hotmail.com"          # OpenAlex "polite pool" -> faster, kinder
DEFAULT_ORCID = "0000-0003-1674-0794"        # Nicholas Shulman, University of Washington
API = "https://api.openalex.org/works"


def fetch_url(url, tries=6):
    """GET a URL as JSON, waiting and retrying if OpenAlex asks us to slow down."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"mailto:{MAILTO}"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            # 429 = too many requests; 5xx = server hiccup. Back off and retry.
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                wait = 2 ** attempt
                print(f"  OpenAlex busy (HTTP {e.code}); waiting {wait}s and retrying...")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            if attempt < tries - 1:
                wait = 2 ** attempt
                print(f"  network issue ({e.reason}); waiting {wait}s and retrying...")
                time.sleep(wait)
                continue
            raise


def fetch_all(orcid):
    """Page through every work for an ORCID using a cursor."""
    works = []
    cursor = "*"
    while cursor:
        url = (f"{API}?filter=author.orcid:{orcid}"
               f"&per-page=200&cursor={cursor}&mailto={MAILTO}")
        data = fetch_url(url)
        works.extend(data["results"])
        total = data["meta"]["count"]
        print(f"  fetched {len(works)}/{total} ...")
        cursor = data["meta"].get("next_cursor")
        if not data["results"]:
            break
    return works


def simplify(w):
    """Pull just the fields the page needs out of a full OpenAlex work."""
    loc = w.get("primary_location") or {}
    source = loc.get("source") or {}
    return {
        "id": w.get("id"),
        "doi": w.get("doi"),
        "title": w.get("display_name"),
        "year": w.get("publication_year"),
        "type": w.get("type"),
        "venue": source.get("display_name"),
        "url": loc.get("landing_page_url") or w.get("doi") or w.get("id"),
        "cited_by_count": w.get("cited_by_count", 0),
        "counts_by_year": w.get("counts_by_year", []),  # [{year, cited_by_count}, ...]
        "authors": [
            (a.get("author") or {}).get("display_name")
            for a in (w.get("authorships") or [])
        ],
    }


def load_exclusions():
    """Read exclusions.json (cleaning choices) if present; otherwise no cleaning."""
    path = os.path.join(HERE, "exclusions.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def normalize_title(t):
    """Collapse a title to letters+digits only, for matching preprint<->article pairs."""
    t = re.sub(r"<[^>]+>", "", t or "")   # drop HTML tags like <i>
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def clean(papers, exclusions):
    """Apply the reusable cleaning choices from exclusions.json."""
    # 1. Fix mis-typed works (e.g. a journal article OpenAlex tagged as 'preprint').
    retype = exclusions.get("retype", {})
    for p in papers:
        if p["id"] in retype:
            p["type"] = retype[p["id"]]
    # 2. Remove works explicitly marked as not mine / unwanted.
    exclude_ids = set(exclusions.get("exclude_ids", []))
    papers = [p for p in papers if p["id"] not in exclude_ids]
    # 3. Drop a preprint only when a published version of the same title exists.
    #    (Keeps genuine preprint-only work; removes duplicate preprint/article pairs.)
    if exclusions.get("drop_duplicate_preprints"):
        published = {normalize_title(p["title"]) for p in papers if p["type"] != "preprint"}
        papers = [p for p in papers
                  if not (p["type"] == "preprint" and normalize_title(p["title"]) in published)]
    return papers


def main():
    orcid = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ORCID
    print(f"Fetching works for ORCID {orcid} from OpenAlex...")
    raw = fetch_all(orcid)
    papers = [simplify(w) for w in raw]
    papers.sort(key=lambda p: (p["year"] or 0), reverse=True)

    # Keep the full, unfiltered fetch as an audit trail.
    with open(os.path.join(HERE, "papers.raw.json"), "w", encoding="utf-8") as f:
        json.dump({"orcid": orcid, "count": len(papers), "papers": papers},
                  f, ensure_ascii=False, indent=2)

    raw_count = len(papers)
    papers = clean(papers, load_exclusions())

    with open(os.path.join(HERE, "papers.json"), "w", encoding="utf-8") as f:
        json.dump({"orcid": orcid, "count": len(papers), "papers": papers},
                  f, ensure_ascii=False, indent=2)

    with open(os.path.join(HERE, "papers.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "year", "venue", "type", "cited_by_count", "co_authors"])
        for p in papers:
            writer.writerow([
                p["title"], p["year"], p["venue"], p["type"], p["cited_by_count"],
                "; ".join(a for a in p["authors"] if a),
            ])

    # Summary: total works and a breakdown by type
    by_type = {}
    total_citations = 0
    for p in papers:
        by_type[p["type"]] = by_type.get(p["type"], 0) + 1
        total_citations += p["cited_by_count"] or 0

    print()
    print(f"Fetched {raw_count} works -> papers.raw.json (full audit trail)")
    print(f"After cleaning: {len(papers)} works -> papers.json and papers.csv "
          f"({raw_count - len(papers)} dropped)")
    print(f"Lifetime citations (sum): {total_citations}")
    print("By type:")
    for t, n in sorted(by_type.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {t:<15} {n}")


if __name__ == "__main__":
    main()
