#!/usr/bin/env python3

import json
import re
import subprocess
import time
from pathlib import Path
import requests
import yaml

LISTINGS_FILE = Path('listings.json')
README_FILE = Path('README.md')
COMPANIES_FILE = Path('companies.yml')

SKIP_DOMAINS = [
    'ibm.com',
    'tesla.com',
    'lockheedmartin.com',
]

REQUEST_DELAY = 0.75
REQUEST_TIMEOUT = 12


def load_workday_boards():
    if not COMPANIES_FILE.exists():
        return {}
    with open(COMPANIES_FILE) as f:
        data = yaml.safe_load(f)
    workday = data.get('workday', {})
    # Legacy dict form: {boards: {Company: tenant}}
    if isinstance(workday, dict) and 'boards' in workday:
        return workday.get('boards', {})
    # New list form: [{name, tenant, site, board_num}, ...]
    if isinstance(workday, list):
        return {e['name']: e.get('tenant', '') for e in workday if isinstance(e, dict)}
    return {}


def skip_domain(url):
    return any(d in url for d in SKIP_DOMAINS)


def check_url(url):
    if not url:
        return False
    if skip_domain(url):
        return True
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; link-checker/1.0)'},
        )
        return resp.status_code < 400
    except Exception:
        return False


def try_workday_fix(url, workday_boards, company_name):
    if 'myworkdayjobs.com' not in url and 'workday.com' not in url:
        return None
    board_id = workday_boards.get(company_name)
    if not board_id:
        return None
    # Keep the full Workday job path (location + posting slug). Capturing only
    # the first segment collapses distinct jobs onto the same location page.
    match = re.search(r'/(?:apply|job)/(.+?)(?:\?|$)', url)
    if not match:
        return None
    job_path = match.group(1).rstrip('/')
    if not job_path or '/' not in job_path:
        return None
    fixed = f'https://{board_id}.wd1.myworkdayjobs.com/en-US/External/job/{job_path}'
    if fixed.rstrip('/') == url.split('?')[0].rstrip('/'):
        return None
    if check_url(fixed):
        return fixed
    return None


def url_key(url):
    return url.split('?', 1)[0].lower().rstrip('/')


def main():
    with open(LISTINGS_FILE) as f:
        listings = json.load(f)

    workday_boards = load_workday_boards()
    used_urls = {
        url_key(e.get('url', ''))
        for e in listings
        if e.get('url', '').strip()
    }

    changed = False
    for entry in listings:
        url = entry.get('url', '').strip()
        if not url:
            continue

        is_live = check_url(url)
        time.sleep(REQUEST_DELAY)

        if not is_live:
            fixed = try_workday_fix(url, workday_boards, entry.get('company', ''))
            if fixed:
                fixed_key = url_key(fixed)
                old_key = url_key(url)
                if fixed_key != old_key and fixed_key in used_urls:
                    # Same posting already listed under the canonical Workday URL.
                    print(
                        f'Dropping duplicate after Workday fix: '
                        f'{entry["company"]} — {entry["role"]}'
                    )
                    used_urls.discard(old_key)
                    entry['url'] = ''
                    changed = True
                else:
                    print(f'Fixed Workday URL for {entry["company"]}: {fixed}')
                    used_urls.discard(old_key)
                    used_urls.add(fixed_key)
                    entry['url'] = fixed
                    changed = True
                    time.sleep(REQUEST_DELAY)
            else:
                print(f'Marking closed: {entry["company"]} — {entry["role"]}')
                used_urls.discard(url_key(url))
                entry['url'] = ''
                changed = True

    if changed:
        with open(LISTINGS_FILE, 'w') as f:
            json.dump(listings, f, indent=2)
            f.write('\n')
        subprocess.run(['python3', '.github/scripts/rebuild_readme.py'], check=True)
        print('Updated listings and README.')
    else:
        print('All links are live, no changes needed.')


if __name__ == '__main__':
    main()
