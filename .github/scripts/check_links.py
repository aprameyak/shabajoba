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
    return data.get('workday', {}).get('boards', {})


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
    match = re.search(r'/(apply|job)/([^/]+)', url)
    if not match:
        return None
    job_id = match.group(2)
    fixed = f'https://{board_id}.wd1.myworkdayjobs.com/en-US/External/job/{job_id}'
    if check_url(fixed):
        return fixed
    return None


def main():
    with open(LISTINGS_FILE) as f:
        listings = json.load(f)

    workday_boards = load_workday_boards()

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
                print(f'Fixed Workday URL for {entry["company"]}: {fixed}')
                entry['url'] = fixed
                changed = True
                time.sleep(REQUEST_DELAY)
            else:
                print(f'Marking closed: {entry["company"]} — {entry["role"]}')
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
