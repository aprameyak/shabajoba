#!/usr/bin/env python3
"""
Backfill sponsorship and citizenship fields for existing listings using Claude Haiku.

Fetches job descriptions from Greenhouse and Lever ATS APIs for listings
that currently have sponsorship='Unknown' or citizenship='Unknown', then
calls Claude Haiku to extract the correct values.

Run from repo root:
    ANTHROPIC_API_KEY=sk-ant-... python3 .github/scripts/backfill_sponsorship.py

Dry run (no writes):
    ANTHROPIC_API_KEY=sk-ant-... python3 .github/scripts/backfill_sponsorship.py --dry-run
"""

import json
import os
import re
import sys
import subprocess
import time
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent))
from scrape_jobs import strip_html, extract_job_metadata_claude

LISTINGS_FILE = Path('listings.json')
DRY_RUN = '--dry-run' in sys.argv


def fetch_greenhouse_description(url):
    """Extract description from a Greenhouse job URL."""
    # https://job-boards.greenhouse.io/{token}/jobs/{id}
    m = re.search(r'greenhouse\.io/([^/]+)/jobs/(\d+)', url)
    if not m:
        return ''
    board_token, job_id = m.group(1), m.group(2)
    try:
        api_url = f'https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?content=true'
        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        return strip_html(resp.json().get('content', ''))
    except Exception as e:
        print(f'  Greenhouse fetch error ({url[:60]}): {e}')
        return ''


def fetch_lever_description(url):
    """Extract description from a Lever job URL."""
    # https://jobs.lever.co/{slug}/{id}
    m = re.search(r'lever\.co/([^/]+)/([a-f0-9-]+)', url)
    if not m:
        return ''
    slug, job_id = m.group(1), m.group(2)
    try:
        api_url = f'https://api.lever.co/v0/postings/{slug}/{job_id}'
        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        desc_html = data.get('descriptionHtml', '') or data.get('description', '')
        lists_html = ' '.join(item.get('content', '') for item in data.get('lists', []))
        return strip_html(desc_html + ' ' + lists_html)
    except Exception as e:
        print(f'  Lever fetch error ({url[:60]}): {e}')
        return ''


def fetch_description(entry):
    """Fetch job description for a listing based on its URL."""
    url = entry.get('url', '')
    if not url:
        return ''
    if 'greenhouse.io' in url:
        return fetch_greenhouse_description(url)
    if 'lever.co' in url:
        return fetch_lever_description(url)
    return ''


def main():
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print('Error: ANTHROPIC_API_KEY not set.')
        sys.exit(1)

    with open(LISTINGS_FILE) as f:
        listings = json.load(f)

    targets = [
        e for e in listings
        if e.get('url') and (
            e.get('sponsorship') == 'Unknown' or e.get('citizenship') == 'Unknown'
        )
    ]

    print(f'Backfilling {len(targets)} listings with Unknown sponsorship/citizenship ...')
    if DRY_RUN:
        print('(DRY RUN — no writes)')

    changed = 0
    for entry in targets:
        print(f'\n  {entry["company"]} — {entry["role"][:60]}')

        description = fetch_description(entry)
        if not description:
            print('    No description available, skipping.')
            continue

        time.sleep(0.5)

        meta = extract_job_metadata_claude(entry['role'], description, api_key)
        new_sp = meta.get('sponsorship', 'Unknown')
        new_ci = meta.get('citizenship', 'Unknown')

        sp_changed = new_sp != 'Unknown' and new_sp != entry.get('sponsorship')
        ci_changed = new_ci != 'Unknown' and new_ci != entry.get('citizenship')

        if sp_changed:
            print(f'    sponsorship: {entry["sponsorship"]} → {new_sp}')
            entry['sponsorship'] = new_sp
        if ci_changed:
            print(f'    citizenship: {entry["citizenship"]} → {new_ci}')
            entry['citizenship'] = new_ci

        if sp_changed or ci_changed:
            changed += 1

        time.sleep(0.3)

    print(f'\nUpdated {changed} listings.')

    if changed and not DRY_RUN:
        with open(LISTINGS_FILE, 'w') as f:
            json.dump(listings, f, indent=2)
            f.write('\n')
        subprocess.run(['python3', '.github/scripts/rebuild_readme.py'], check=True)
        print('Saved listings.json and rebuilt README.')
    elif changed and DRY_RUN:
        print('Dry run — no files written.')
    else:
        print('No changes — all fields already filled or no descriptions available.')


if __name__ == '__main__':
    main()
