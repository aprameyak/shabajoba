#!/usr/bin/env python3
"""
Comprehensive EE internship scraper for 2027.
Run from repo root: python3 run_scrape.py

Uses companies.yml + .github/scripts/scrape_jobs.py (Greenhouse, Lever, Ashby,
Workday, SmartRecruiters, Workable, Oracle, iCIMS, USAJOBS).
Optionally scrapes LinkedIn via Playwright when installed.
"""

import sys
import os
import time
import datetime
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT / '.github' / 'scripts'))

from scrape_jobs import (  # noqa: E402
    is_ee_title,
    classify_season, infer_education, add_listing,
    sanitize_listing_role,
    load_json, save_json, CLASSIFICATIONS_FILE, LOCATION_CACHE_FILE,
    candidate_passes_scope, should_llm_classify_title,
    listing_exists, infer_metadata_keywords,
    resolve_ambiguous_candidates, batch_classify_ee_claude,
    batch_normalize_locations_claude, resolve_location,
    build_scrape_tasks, scrape_usajobs,
    LISTINGS_FILE, SEEN_FILE, normalize_url, is_internship, is_us_or_canada,
    normalize_location, location_passes_validation, batch_extract_metadata_claude,
    infer_metadata_keywords,
)


def scrape_linkedin(seen):
    """LinkedIn guest search via Playwright (optional dependency)."""
    jobs = []
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print('LinkedIn: playwright not installed, skipping.')
        return jobs

    queries = [
        'electrical engineer intern 2027',
        'electrical engineering co-op 2027',
        'hardware engineer intern 2027',
        'FPGA intern 2027',
        'ASIC intern 2027',
        'analog design intern 2027',
        'RF engineer intern 2027',
        'power systems intern 2027',
        'VLSI intern 2027',
        'PCB design intern 2027',
    ]

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
                    f'&location=United%20States'
                )
                print(f'LinkedIn: fetching "{query}" ...')
                try:
                    page.goto(url, timeout=20000, wait_until='domcontentloaded')
                    page.wait_for_timeout(3000)
                    items = page.query_selector_all('li.jobs-search__results-list > *')
                    if not items:
                        items = page.query_selector_all('div.base-card')
                    found = 0
                    for item in items[:40]:
                        try:
                            title_el = item.query_selector(
                                'h3.base-search-card__title, h3.job-search-card__title'
                            )
                            company_el = item.query_selector(
                                'h4.base-search-card__subtitle, a.hidden-nested-link'
                            )
                            location_el = item.query_selector(
                                'span.job-search-card__location'
                            )
                            link_el = item.query_selector(
                                'a.base-card__full-link, a[href*="/jobs/view/"]'
                            )
                            title = title_el.inner_text().strip() if title_el else ''
                            company = company_el.inner_text().strip() if company_el else ''
                            location = location_el.inner_text().strip() if location_el else ''
                            apply_url = link_el.get_attribute('href') if link_el else ''
                            if not title or not apply_url:
                                continue
                            if not is_internship(title) or not is_ee_title(title):
                                continue
                            if location and not is_us_or_canada(location):
                                continue
                            key = f'linkedin:{normalize_url(apply_url)}'
                            if key in seen:
                                continue
                            jobs.append({
                                'key': key,
                                'company': company or 'Unknown',
                                'title': title,
                                'location': location or 'United States',
                                'url': apply_url,
                            })
                            found += 1
                        except Exception:
                            continue
                    print(f'  LinkedIn "{query}": {found} matches')
                except PWTimeout:
                    print(f'  LinkedIn "{query}": timeout, skipping')
                except Exception as e:
                    print(f'  LinkedIn "{query}": {e}')
                time.sleep(2)

            # Also Canada search for a few high-signal queries
            for query in queries[:4]:
                kw = query.replace(' ', '+')
                url = (
                    f'https://www.linkedin.com/jobs/search/'
                    f'?keywords={kw}&f_TPR=r2592000&f_JT=I'
                    f'&location=Canada'
                )
                print(f'LinkedIn CA: fetching "{query}" ...')
                try:
                    page.goto(url, timeout=20000, wait_until='domcontentloaded')
                    page.wait_for_timeout(2500)
                    items = page.query_selector_all('div.base-card')
                    found = 0
                    for item in items[:30]:
                        try:
                            title_el = item.query_selector('h3.base-search-card__title')
                            company_el = item.query_selector(
                                'h4.base-search-card__subtitle, a.hidden-nested-link'
                            )
                            location_el = item.query_selector(
                                'span.job-search-card__location'
                            )
                            link_el = item.query_selector(
                                'a.base-card__full-link, a[href*="/jobs/view/"]'
                            )
                            title = title_el.inner_text().strip() if title_el else ''
                            company = company_el.inner_text().strip() if company_el else ''
                            location = location_el.inner_text().strip() if location_el else ''
                            apply_url = link_el.get_attribute('href') if link_el else ''
                            if not title or not apply_url:
                                continue
                            if not is_internship(title) or not is_ee_title(title):
                                continue
                            if location and not is_us_or_canada(location):
                                continue
                            key = f'linkedin:{normalize_url(apply_url)}'
                            if key in seen:
                                continue
                            jobs.append({
                                'key': key,
                                'company': company or 'Unknown',
                                'title': title,
                                'location': location or 'Canada',
                                'url': apply_url,
                            })
                            found += 1
                        except Exception:
                            continue
                    print(f'  LinkedIn CA "{query}": {found} matches')
                except Exception as e:
                    print(f'  LinkedIn CA "{query}": {e}')
                time.sleep(2)

            browser.close()
    except Exception as e:
        print(f'LinkedIn Playwright error: {e}')

    return jobs


def main():
    print('=' * 60)
    print('Comprehensive EE Internship Scraper 2027')
    print('=' * 60)

    claude_key = os.environ.get('ANTHROPIC_API_KEY', '')

    listings = load_json(LISTINGS_FILE, [])
    seen = load_json(SEEN_FILE, {})
    classifications = load_json(CLASSIFICATIONS_FILE, {})
    location_cache = load_json(LOCATION_CACHE_FILE, {})
    today = datetime.date.today().isoformat()
    candidates = []

    tasks = build_scrape_tasks(seen)
    print(f'\nRunning {len(tasks)} ATS scrapers ...')
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {
            pool.submit(fn, *args): label
            for fn, args, label in tasks
        }
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

    print('\n=== USAJOBS ===')
    usajobs_found = scrape_usajobs(seen)
    candidates.extend(usajobs_found)
    if usajobs_found:
        print(f'  USAJOBS: {len(usajobs_found)} candidates')

    print('\n=== SimplifyJobs Hardware/EE ===')
    from scrape_jobs import scrape_simplify
    simplify_found = scrape_simplify(seen)
    candidates.extend(simplify_found)

    print('\nRunning LinkedIn scraper ...')
    linkedin_found = scrape_linkedin(seen)
    if linkedin_found:
        print(f'  LinkedIn total: {len(linkedin_found)} candidates')
        candidates.extend(linkedin_found)

    print(f'\nTotal raw candidates: {len(candidates)}')

    in_scope = [c for c in candidates if candidate_passes_scope(c)]
    print(f'In scope (intern/co-op, US/Canada): {len(in_scope)}')

    titles_to_classify = list({
        c['title'] for c in in_scope
        if should_llm_classify_title(c['title'], classifications)
    })
    claude_titles_tried = set()
    if titles_to_classify and claude_key:
        print(f'Classifying {len(titles_to_classify)} ambiguous titles via LLM ...')
        classifications.update(batch_classify_ee_claude(titles_to_classify, claude_key))
        claude_titles_tried.update(titles_to_classify)
        for t in titles_to_classify:
            if t not in classifications:
                classifications[t] = False

    confirmed = []
    ambiguous = []
    for c in in_scope:
        title = c['title']
        keyword_match = is_ee_title(title)
        llm_result = classifications.get(title)
        if llm_result is True or (llm_result is None and keyword_match):
            confirmed.append(c)
        elif llm_result is False:
            pass
        elif llm_result is None and not keyword_match and claude_key:
            ambiguous.append(c)

    if ambiguous:
        print(f'Resolving {len(ambiguous)} ambiguous titles without re-billing Claude ...')
        confirmed.extend(
            resolve_ambiguous_candidates(
                ambiguous, classifications, claude_key, '', {},
                already_tried_claude=claude_titles_tried,
            )
        )

    print(f'After EE filter: {len(confirmed)}')

    to_add = []
    for c in confirmed:
        role = sanitize_listing_role(c['company'], c['title'])
        if listing_exists(listings, c['url'], c['company'], role):
            continue
        if not c.get('description'):
            continue
        c['_role'] = role
        to_add.append(c)

    if to_add and claude_key:
        batch_extract_metadata_claude(to_add, claude_key)
    else:
        for c in to_add:
            inferred = infer_metadata_keywords(c.get('description', ''))
            c['sponsorship'] = inferred['sponsorship']
            c['citizenship'] = inferred['citizenship']

    added = 0
    needs_loc_llm = [
        c['location'] for c in to_add
        if not location_passes_validation(normalize_location(c['location']))
    ]
    if needs_loc_llm and claude_key:
        batch_normalize_locations_claude(needs_loc_llm, claude_key, location_cache)

    for c in to_add:
        listing_type, season = classify_season(c['title'])
        location = resolve_location(c['location'], location_cache)
        if not location:
            print(
                f'  Skip (bad location): {c["company"]} — {c["title"]} '
                f'({c["location"]!r})'
            )
            continue
        entry = {
            'company': c['company'],
            'role': c.get('_role') or sanitize_listing_role(c['company'], c['title']),
            'location': location,
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
        seen[c['key']] = today

    for c in candidates:
        seen[c['key']] = today

    print(f'\nNew listings added: {added}')

    save_json(LISTINGS_FILE, listings)
    save_json(SEEN_FILE, seen)
    save_json(CLASSIFICATIONS_FILE, classifications)
    save_json(LOCATION_CACHE_FILE, location_cache)

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
