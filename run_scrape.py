#!/usr/bin/env python3
"""
Comprehensive EE internship scraper for 2027.
Run from repo root: python3 run_scrape.py
"""

import sys
import os
import json
import re
import time
import datetime
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent
LISTINGS_FILE = REPO_ROOT / 'listings.json'
SEEN_FILE = REPO_ROOT / '.github' / 'data' / 'seen_jobs.json'

# ---------------------------------------------------------------------------
# Import helper functions and scrapers from existing script
# ---------------------------------------------------------------------------
sys.path.insert(0, str(REPO_ROOT / '.github' / 'scripts'))
from scrape_jobs import (
    is_ee_title, is_internship, is_us_or_canada,
    classify_season, infer_education, add_listing, normalize_url,
    load_json, save_json,
    scrape_greenhouse, scrape_lever, scrape_ashby,
    scrape_workday, scrape_smartrecruiters,
    batch_classify_ee_claude, extract_job_metadata_claude,
)

# ---------------------------------------------------------------------------
# Extended company lists
# ---------------------------------------------------------------------------

GREENHOUSE_COMPANIES = [
    ('SpaceX', 'spacex'),
    ('Rocket Lab', 'rocketlab'),
    ('Waymo', 'waymo'),
    ('Verkada', 'verkada'),
    ('Lucid Motors', 'lucidmotors'),
    ('Tenstorrent', 'tenstorrent'),
    ('Astranis', 'astranis'),
    ('Nuro', 'nuro'),
    ('Lattice Semiconductor', 'lattice'),
    ('Flex Ltd', 'flex'),
    ('Mercury Systems', 'mercury'),
    ('Graphcore', 'graphcore'),
    ('Ampere Computing', 'amperecomputing'),
    ('SambaNova Systems', 'sambanova'),
    ('Joby Aviation', 'jobyaviation'),
    ('Lilium', 'lilium'),
    ('Saildrone', 'saildrone'),
    ('Fortive', 'fortive'),
]

LEVER_COMPANIES = [
    ('Blue Origin', 'blueorigin'),
    ('Shield AI', 'shieldai'),
    ('Zoox', 'zoox'),
    ('Exowatt', 'exowatt'),
    ('Plus', 'plus-ai'),
    ('Sarcos Technology', 'sarcos'),
    ('Epirus', 'epirus'),
]

ASHBY_COMPANIES = [
    ('Anduril Industries', 'anduril'),
    ('Applied Intuition', 'appliedintuition'),
    ('Astera Labs', 'asteralabs'),
    ('Cerebras Systems', 'cerebras'),
    ('Etched', 'etched'),
    ('Groq', 'groq'),
    ('Varda Space', 'varda'),
    ('Relativity Space', 'relativityspace'),
    ('Hermeus', 'hermeus'),
    ('Archer Aviation', 'archeraviation'),
    ('Wisk Aero', 'wisk'),
    ('Axcelis Technologies', 'axcelis'),
    ('Figure', 'figure-ai'),
    ('NextSilicon', 'nextsilicon'),
    ('Perceive', 'perceive'),
    ('Untether AI', 'untether-ai'),
    ('Charge Robotics', 'charge-robotics'),
    ('Form Energy', 'formenergy'),
    ('d-Matrix', 'd-matrix'),
    ('REGENT Craft', 'regent'),
    ('Rain Neuromorphics', 'rain'),
    ('Airspeed', 'airspeed'),
    ('ATLAS Space Operations', 'atlas'),
    ('Wayve', 'wayve'),
    ('Ghost Autonomy', 'ghost'),
    ('Atomic Semi', 'atomic-semi'),
    ('Fervo Energy', 'fervoenergy'),
    ('Electra Aero', 'electra'),
    ('Parallel Systems', 'parallel-systems'),
]

WORKDAY_COMPANIES = [
    ('Analog Devices', 'analogdevices', 'External', '1'),
    ('Intel', 'intel', 'External', '1'),
    ('NVIDIA', 'nvidia', 'NVIDIAExternalCareerSite', '5'),
    ('Micron Technology', 'micron', 'External', '1'),
    ('Leidos', 'leidos', 'External', '5'),
    ('ON Semiconductor', 'onsemi', 'External', '1'),
    ('Lam Research', 'lamresearch', 'External', '1'),
    ('KLA Corporation', 'kla', 'External', '1'),
    ('Marvell Technology', 'marvell', 'External', '1'),
    ('Keysight Technologies', 'keysight', 'External', '1'),
    ('Coherent Corp', 'coherent', 'External', '1'),
    ('Raytheon', 'rtx', 'External', '1'),
    ('Northrop Grumman', 'ngc', 'External', '1'),
    ('L3Harris', 'l3harris', 'External', '1'),
    ('Honeywell', 'honeywell', 'External', '1'),
    ('TE Connectivity', 'te', 'External', '1'),
    ('Broadcom', 'broadcom', 'External', '1'),
    ('Qualcomm', 'qualcomm', 'External', '1'),
]

SMARTRECRUITERS_COMPANIES = [
    ('Western Digital', 'WesternDigital'),
    ('Vishay Intertechnology', 'Vishay'),
    ('Teradyne', 'Teradyne'),
]

# ---------------------------------------------------------------------------
# LinkedIn scraping via Playwright
# ---------------------------------------------------------------------------

def scrape_linkedin(seen):
    """Try to scrape LinkedIn public job search pages with Playwright."""
    jobs = []
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print('LinkedIn: playwright not installed, skipping.')
        return jobs

    queries = [
        'electrical engineer intern 2027',
        'hardware engineer intern 2027',
        'EE intern summer 2027',
    ]

    def _extract_jobs_from_page(page, query):
        found = []
        try:
            items = page.query_selector_all('li.jobs-search__results-list > *')
            if not items:
                items = page.query_selector_all('div.base-card')
            for item in items[:30]:
                try:
                    title_el = item.query_selector('h3.base-search-card__title, h3.job-search-card__title')
                    company_el = item.query_selector('h4.base-search-card__subtitle, a.hidden-nested-link')
                    location_el = item.query_selector('span.job-search-card__location')
                    link_el = item.query_selector('a.base-card__full-link, a[href*="/jobs/view/"]')

                    title = title_el.inner_text().strip() if title_el else ''
                    company = company_el.inner_text().strip() if company_el else ''
                    location = location_el.inner_text().strip() if location_el else ''
                    url = link_el.get_attribute('href') if link_el else ''

                    if not title or not url:
                        continue
                    if not is_internship(title) or not is_ee_title(title):
                        continue
                    if location and not is_us_or_canada(location):
                        continue

                    key = f'linkedin:{normalize_url(url)}'
                    if key in seen:
                        continue
                    found.append({
                        'key': key,
                        'company': company or 'Unknown',
                        'title': title,
                        'location': location or 'United States',
                        'url': url,
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f'LinkedIn parse error: {e}')
        return found

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0.0.0 Safari/537.36'
                )
            )
            page = context.new_page()

            for query in queries:
                kw = query.replace(' ', '+')
                url = (
                    f'https://www.linkedin.com/jobs/search/'
                    f'?keywords={kw}&f_TPR=r2592000&f_JT=I'
                )
                print(f'LinkedIn: fetching "{query}" ...')
                try:
                    page.goto(url, timeout=20000, wait_until='domcontentloaded')
                    page.wait_for_timeout(3000)
                    found = _extract_jobs_from_page(page, query)
                    print(f'  LinkedIn "{query}": {len(found)} matches')
                    jobs.extend(found)
                except PWTimeout:
                    print(f'  LinkedIn "{query}": timeout, skipping')
                except Exception as e:
                    print(f'  LinkedIn "{query}": {e}')
                time.sleep(2)

            browser.close()
    except Exception as e:
        print(f'LinkedIn Playwright error: {e}')

    return jobs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('=' * 60)
    print('Comprehensive EE Internship Scraper 2027')
    print('=' * 60)

    claude_key = os.environ.get('ANTHROPIC_API_KEY', '')

    listings = load_json(LISTINGS_FILE, [])
    seen = load_json(SEEN_FILE, {})

    today = datetime.date.today().isoformat()
    candidates = []

    # ---- Build task list ----
    tasks = (
        [(scrape_greenhouse, (c, t, seen)) for c, t in GREENHOUSE_COMPANIES] +
        [(scrape_lever, (c, s, seen)) for c, s in LEVER_COMPANIES] +
        [(scrape_ashby, (c, s, seen)) for c, s in ASHBY_COMPANIES] +
        [(scrape_smartrecruiters, (c, i, seen)) for c, i in SMARTRECRUITERS_COMPANIES]
    )

    print(f'\nRunning {len(tasks)} parallel API scrapers ...')
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(fn, *args): args[0] for fn, args in tasks}
        for future in as_completed(futures):
            company = futures[future]
            try:
                found = future.result()
                if found:
                    print(f'  {company}: {len(found)} candidates')
                    candidates.extend(found)
                else:
                    print(f'  {company}: 0')
            except Exception as e:
                print(f'  {company} thread error: {e}')

    # ---- Workday (sequential to avoid rate limiting) ----
    print('\nRunning Workday scrapers sequentially ...')
    for company, tenant, site, board_num in WORKDAY_COMPANIES:
        found = scrape_workday(company, tenant, site, board_num, seen)
        if found:
            print(f'  {company}: {len(found)} candidates')
            candidates.extend(found)
        else:
            print(f'  {company}: 0')

    # ---- LinkedIn ----
    print('\nRunning LinkedIn scraper ...')
    linkedin_found = scrape_linkedin(seen)
    if linkedin_found:
        print(f'  LinkedIn total: {len(linkedin_found)} candidates')
        candidates.extend(linkedin_found)

    print(f'\nTotal raw candidates: {len(candidates)}')

    # ---- EE title classification (LLM preferred, keyword fallback) ----
    internship_candidates = [c for c in candidates if is_internship(c['title'])]
    titles_needing_llm = [
        c['title'] for c in internship_candidates
        if not is_ee_title(c['title'])  # only send ambiguous titles to LLM
    ]
    llm_classifications = {}
    if titles_needing_llm and claude_key:
        print(f'Classifying {len(titles_needing_llm)} ambiguous titles via LLM ...')
        llm_classifications = batch_classify_ee_claude(list(set(titles_needing_llm)), claude_key)

    confirmed = []
    for c in internship_candidates:
        if is_ee_title(c['title']) or llm_classifications.get(c['title']):
            confirmed.append(c)

    print(f'After EE+internship filter: {len(confirmed)}')

    # ---- Sponsorship/citizenship extraction from descriptions ----
    if claude_key:
        print('Extracting sponsorship/citizenship from job descriptions ...')
        for c in confirmed:
            desc = c.get('description', '')
            if desc:
                meta = extract_job_metadata_claude(c['title'], desc, claude_key)
                c['sponsorship'] = meta.get('sponsorship', 'Unknown')
                c['citizenship'] = meta.get('citizenship', 'Unknown')
                time.sleep(0.3)

    # ---- Add to listings ----
    added = 0
    for c in confirmed:
        listing_type, season = classify_season(c['title'])
        entry = {
            'company': c['company'],
            'role': c['title'],
            'location': c['location'],
            'type': listing_type,
            'season': season,
            'education': infer_education(c['title']),
            'url': c['url'],
            'sponsorship': c.get('sponsorship', 'Unknown'),
            'citizenship': c.get('citizenship', 'Unknown'),
            'date_added': today,
        }
        if add_listing(listings, entry):
            added += 1
            print(f'  Added: {c["company"]} — {c["title"]}')
        # Always mark seen
        seen[c['key']] = today

    # Also mark all candidates as seen (even filtered-out ones) to avoid re-processing
    for c in candidates:
        seen[c['key']] = today

    print(f'\nNew listings added: {added}')

    # ---- Save files ----
    save_json(LISTINGS_FILE, listings)
    save_json(SEEN_FILE, seen)
    print('Saved listings.json and seen_jobs.json')

    # ---- Rebuild README ----
    print('\nRebuilding README ...')
    result = subprocess.run(
        ['python3', '.github/scripts/rebuild_readme.py'],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print('README rebuilt successfully.')
    else:
        print(f'README rebuild warning: {result.stderr[:200]}')

    print('\nDone. Total new listings added:', added)
    return added


if __name__ == '__main__':
    main()
