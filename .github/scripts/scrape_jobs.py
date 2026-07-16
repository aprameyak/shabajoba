#!/usr/bin/env python3
"""
Scrape EE internship postings from major job boards and recruiting platforms.
Classifies roles via keyword matching + Gemini API, then adds confirmed listings
to listings.json / README and creates GitHub issues for lower-confidence matches.
"""

import json
import os
import re
import time
import datetime
from pathlib import Path
import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
LISTINGS_FILE = Path('listings.json')
SEEN_FILE = Path('.github/data/seen_jobs.json')
CLASSIFICATIONS_FILE = Path('.github/data/title_classifications.json')
GEMINI_USAGE_FILE = Path('.github/data/gemini_usage.json')

# ---------------------------------------------------------------------------
# EE-specific keyword configuration
# ---------------------------------------------------------------------------
EE_TITLE_KEYWORDS = [
    'electrical engineer', 'hardware engineer', 'analog engineer',
    'rf engineer', 'power engineer', 'signal integrity', 'pcb design',
    'vlsi', 'asic', 'fpga', 'embedded hardware', 'test engineer',
    'systems engineer', 'signal processing', 'circuit design',
    'photonics', 'mixed signal', 'power electronics', 'silicon',
    'semiconductor', 'ic design', 'chip design', 'soc design',
    'verification engineer', 'physical design', 'layout engineer',
    'product engineer', 'applications engineer', 'field applications',
    'power systems', 'electric vehicle', 'battery systems',
    'motor control', 'avionics', 'electrical systems',
]

EXCLUDE_TITLE_KEYWORDS = [
    'software engineer', 'software developer', 'data scientist',
    'machine learning engineer', 'ml engineer', 'data engineer',
    'backend engineer', 'frontend engineer', 'full stack',
    'devops', 'site reliability', 'marketing', 'sales', 'hr',
    'recruiter', 'finance', 'accounting', 'legal', 'mechanical engineer',
    'civil engineer', 'chemical engineer', 'product manager',
    'program manager', 'business analyst', 'supply chain',
]

INTERNSHIP_KEYWORDS = [
    'intern', 'internship', 'co-op', 'coop', 'co op',
    'student', 'summer 2027', 'fall 2026', 'spring 2027',
]

LOCATION_KEYWORDS_US_CA = [
    ', al', ', ak', ', az', ', ar', ', ca', ', co', ', ct', ', de',
    ', fl', ', ga', ', hi', ', id', ', il', ', in', ', ia', ', ks',
    ', ky', ', la', ', me', ', md', ', ma', ', mi', ', mn', ', ms',
    ', mo', ', mt', ', ne', ', nv', ', nh', ', nj', ', nm', ', ny',
    ', nc', ', nd', ', oh', ', ok', ', or', ', pa', ', ri', ', sc',
    ', sd', ', tn', ', tx', ', ut', ', vt', ', va', ', wa', ', wv',
    ', wi', ', wy', ', dc',
    ', ab', ', bc', ', mb', ', nb', ', nl', ', ns', ', nt', ', nu',
    ', on', ', pe', ', qc', ', sk', ', yt',
    'remote', 'united states', 'canada',
]

# ---------------------------------------------------------------------------
# Gemini rate-limit helpers
# ---------------------------------------------------------------------------
GEMINI_DAILY_LIMIT = 1400
GEMINI_DELAY = 4.2  # seconds between calls


def load_gemini_usage():
    if GEMINI_USAGE_FILE.exists():
        with open(GEMINI_USAGE_FILE) as f:
            data = json.load(f)
        today = datetime.date.today().isoformat()
        if data.get('date') != today:
            return {'date': today, 'count': 0}
        return data
    return {'date': datetime.date.today().isoformat(), 'count': 0}


def save_gemini_usage(usage):
    with open(GEMINI_USAGE_FILE, 'w') as f:
        json.dump(usage, f)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def load_json(path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def normalize_url(url):
    url = url.strip().split('?')[0]
    for param in ['utm_source', 'utm_medium', 'utm_campaign', 'source', 'ref']:
        url = re.sub(rf'[?&]{param}=[^&]*', '', url)
    return url.rstrip('/')


def is_us_or_canada(location_text):
    loc = location_text.lower()
    return any(kw in loc for kw in LOCATION_KEYWORDS_US_CA)


def is_ee_title_keyword(title):
    t = title.lower()
    if any(kw in t for kw in EXCLUDE_TITLE_KEYWORDS):
        return False
    return any(kw in t for kw in EE_TITLE_KEYWORDS)


def is_internship_keyword(title):
    t = title.lower()
    return any(kw in t for kw in INTERNSHIP_KEYWORDS)


def infer_education(title):
    t = title.lower()
    if 'phd' in t or 'doctoral' in t or 'doctorate' in t:
        return 'PhD'
    if 'master' in t or 'graduate' in t or ' ms ' in t:
        return 'Masters'
    return 'Undergrad'


def classify_season(title):
    t = title.lower()
    if 'fall 2026' in t or 'fall2026' in t:
        return ('offcycle', 'Fall 2026')
    if 'spring 2027' in t or 'spring2027' in t:
        return ('offcycle', 'Spring 2027')
    if 'winter 2027' in t or 'winter2027' in t:
        return ('offcycle', 'Winter 2027')
    if 'co-op' in t or 'coop' in t or 'co op' in t:
        return ('offcycle', 'Co-op')
    return ('summer', 'Summer 2027')


# ---------------------------------------------------------------------------
# Gemini classification
# ---------------------------------------------------------------------------
def classify_titles_gemini(titles, api_key, usage):
    """Batch-classify job titles via Gemini. Returns dict title->bool."""
    if not api_key or usage['count'] >= GEMINI_DAILY_LIMIT:
        return {}

    results = {}
    for title in titles:
        if usage['count'] >= GEMINI_DAILY_LIMIT:
            break
        prompt = (
            f'Is the following job title an electrical engineering role '
            f'(hardware, EE, RF, analog, power, VLSI, ASIC, FPGA, PCB, test, '
            f'signal processing, photonics, or similar)? '
            f'Answer only "yes" or "no".\n\nTitle: "{title}"'
        )
        try:
            resp = requests.post(
                'https://generativelanguage.googleapis.com/v1beta/models/'
                f'gemini-1.5-flash:generateContent?key={api_key}',
                json={'contents': [{'parts': [{'text': prompt}]}]},
                timeout=15,
            )
            if resp.status_code == 429:
                time.sleep(60)
                continue
            resp.raise_for_status()
            text = resp.json()['candidates'][0]['content']['parts'][0]['text']
            results[title] = text.strip().lower().startswith('yes')
            usage['count'] += 1
            save_gemini_usage(usage)
            time.sleep(GEMINI_DELAY)
        except Exception as e:
            print(f'Gemini error for "{title}": {e}')
    return results


# ---------------------------------------------------------------------------
# Platform scrapers
# ---------------------------------------------------------------------------
def scrape_greenhouse(company, board_token, seen):
    """Fetch jobs from Greenhouse v1 API."""
    jobs = []
    try:
        url = f'https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true'
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for job in data.get('jobs', []):
            title = job.get('title', '')
            location = job.get('location', {}).get('name', '')
            apply_url = job.get('absolute_url', '')
            job_id = str(job.get('id', ''))
            key = f'greenhouse:{board_token}:{job_id}'
            if key in seen:
                continue
            if not is_internship_keyword(title):
                continue
            if not is_us_or_canada(location):
                continue
            jobs.append({
                'key': key,
                'company': company,
                'title': title,
                'location': location,
                'url': apply_url,
            })
    except Exception as e:
        print(f'Greenhouse error for {company}: {e}')
    return jobs


def scrape_lever(company, lever_slug, seen):
    """Fetch jobs from Lever public API."""
    jobs = []
    try:
        url = f'https://api.lever.co/v0/postings/{lever_slug}?mode=json'
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        for posting in resp.json():
            title = posting.get('text', '')
            location = posting.get('categories', {}).get('location', '')
            apply_url = posting.get('hostedUrl', '')
            job_id = posting.get('id', '')
            key = f'lever:{lever_slug}:{job_id}'
            if key in seen:
                continue
            if not is_internship_keyword(title):
                continue
            if location and not is_us_or_canada(location):
                continue
            jobs.append({
                'key': key,
                'company': company,
                'title': title,
                'location': location or 'United States',
                'url': apply_url,
            })
    except Exception as e:
        print(f'Lever error for {company}: {e}')
    return jobs


def scrape_ashby(company, ashby_id, seen):
    """Fetch jobs from Ashby public API."""
    jobs = []
    try:
        url = f'https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams'
        payload = {
            'operationName': 'ApiJobBoardWithTeams',
            'variables': {'organizationHostedJobsPageName': ashby_id},
            'query': '''
              query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
                jobBoard: jobBoardWithTeams(
                  organizationHostedJobsPageName: $organizationHostedJobsPageName
                ) {
                  jobPostings {
                    id title locationName isRemote
                    externalLink
                  }
                }
              }
            ''',
        }
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        postings = (
            resp.json()
            .get('data', {})
            .get('jobBoard', {})
            .get('jobPostings', [])
        )
        for p in postings:
            title = p.get('title', '')
            location = p.get('locationName', '')
            if p.get('isRemote'):
                location = 'Remote (US)'
            apply_url = p.get('externalLink', '') or f'https://jobs.ashbyhq.com/{ashby_id}/{p["id"]}'
            key = f'ashby:{ashby_id}:{p["id"]}'
            if key in seen:
                continue
            if not is_internship_keyword(title):
                continue
            if location and not is_us_or_canada(location):
                continue
            jobs.append({
                'key': key,
                'company': company,
                'title': title,
                'location': location or 'United States',
                'url': apply_url,
            })
    except Exception as e:
        print(f'Ashby error for {company}: {e}')
    return jobs


# ---------------------------------------------------------------------------
# GitHub issue creation
# ---------------------------------------------------------------------------
def create_github_issue(token, repo, company, role, location, url, season):
    """Create a 'needs review' issue for a lower-confidence match."""
    title = f'[JOB] {company} — {role} ({season})'
    body = (
        f'### Company Name\n{company}\n\n'
        f'### Role / Job Title\n{role}\n\n'
        f'### Listing Type\nInternship\n\n'
        f'### Season / Term\n{season}\n\n'
        f'### Location\n{location}\n\n'
        f'### Visa Sponsorship?\nUnknown\n\n'
        f'### U.S. Citizenship Required?\nUnknown\n\n'
        f'### Education Level\nUndergrad\n\n'
        f'### Direct Application Link\n{url}\n\n'
        f'### Additional Notes\n_Auto-discovered — needs human review_\n'
    )
    try:
        resp = requests.post(
            f'https://api.github.com/repos/{repo}/issues',
            headers={
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github+json',
            },
            json={'title': title, 'body': body, 'labels': ['new listing', 'needs review']},
            timeout=15,
        )
        resp.raise_for_status()
        print(f'Created issue: {title}')
    except Exception as e:
        print(f'Issue creation error: {e}')


# ---------------------------------------------------------------------------
# Add confirmed listing
# ---------------------------------------------------------------------------
def add_listing(listings, entry):
    """Add entry to listings list if not a duplicate."""
    norm = normalize_url(entry['url'])
    for existing in listings:
        if normalize_url(existing.get('url', '')) == norm:
            return False
        if (existing['company'].lower() == entry['company'].lower()
                and existing['role'].lower() == entry['role'].lower()):
            return False
    listings.append(entry)
    return True


# ---------------------------------------------------------------------------
# Platforms config
# ---------------------------------------------------------------------------
GREENHOUSE_COMPANIES = [
    ('Analog Devices', 'analogdevices'),
    ('Anduril', 'anduril'),
    ('Aurora Innovation', 'aurora'),
    ('Broadcom', 'broadcom'),
    ('Cadence Design Systems', 'cadence'),
    ('Cirrus Logic', 'cirruslogic'),
    ('Eaton', 'eaton'),
    ('GE Aerospace', 'geaerospace'),
    ('Keysight Technologies', 'keysight'),
    ('Lattice Semiconductor', 'latticesemiconductor'),
    ('Lumentum', 'lumentum'),
    ('Lucid Motors', 'lucidmotors'),
    ('Marvell Technology', 'marvell'),
    ('Microchip Technology', 'microchip'),
    ('Micron Technology', 'micron'),
    ('Monolithic Power Systems', 'mps'),
    ('NVIDIA', 'nvidia'),
    ('NXP Semiconductors', 'nxp'),
    ('ON Semiconductor', 'onsemi'),
    ('Qualcomm', 'qualcomm'),
    ('Rocket Lab', 'rocketlab'),
    ('Skyworks Solutions', 'skyworks'),
    ('SpaceX', 'spacex'),
    ('Teradyne', 'teradyne'),
    ('Texas Instruments', 'ti'),
    ('Tenstorrent', 'tenstorrent'),
    ('Verkada', 'verkada'),
    ('Waymo', 'waymo'),
    ('Wolfspeed', 'wolfspeed'),
]

LEVER_COMPANIES = [
    ('Blue Origin', 'blueorigin'),
    ('Plus', 'plus-ai'),
    ('Shield AI', 'shieldai'),
    ('Zoox', 'zoox'),
]

ASHBY_COMPANIES = [
    ('Anduril Industries', 'anduril'),
    ('Applied Intuition', 'appliedintuition'),
    ('Astera Labs', 'asteralabs'),
    ('Cerebras Systems', 'cerebras'),
    ('Etched', 'etched'),
    ('Groq', 'groq'),
    ('Tenstorrent', 'tenstorrent'),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    github_token = os.environ.get('GITHUB_TOKEN', '')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    gemini_key = os.environ.get('GEMINI_API_KEY', '')

    listings = load_json(LISTINGS_FILE, [])
    seen = load_json(SEEN_FILE, {})
    classifications = load_json(CLASSIFICATIONS_FILE, {})
    gemini_usage = load_gemini_usage()

    today = datetime.date.today().isoformat()
    candidates = []

    # --- Greenhouse ---
    for company, token in GREENHOUSE_COMPANIES:
        for job in scrape_greenhouse(company, token, seen):
            candidates.append(job)
        time.sleep(0.5)

    # --- Lever ---
    for company, slug in LEVER_COMPANIES:
        for job in scrape_lever(company, slug, seen):
            candidates.append(job)
        time.sleep(0.5)

    # --- Ashby ---
    for company, slug in ASHBY_COMPANIES:
        for job in scrape_ashby(company, slug, seen):
            candidates.append(job)
        time.sleep(0.5)

    print(f'Found {len(candidates)} candidate postings')

    # --- Classify ---
    titles_to_classify = [
        c['title'] for c in candidates
        if c['title'] not in classifications
    ]
    if titles_to_classify and gemini_key:
        new_classifications = classify_titles_gemini(
            titles_to_classify, gemini_key, gemini_usage
        )
        classifications.update(new_classifications)
        save_json(CLASSIFICATIONS_FILE, classifications)

    confirmed = []
    needs_review = []
    for c in candidates:
        title = c['title']
        keyword_match = is_ee_title_keyword(title)
        gemini_result = classifications.get(title)

        if gemini_result is True or (gemini_result is None and keyword_match):
            confirmed.append(c)
        elif keyword_match:
            needs_review.append(c)

    print(f'Confirmed: {len(confirmed)}, Needs review: {len(needs_review)}')

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
            'sponsorship': 'Unknown',
            'citizenship': 'Unknown',
            'date_added': today,
        }
        if add_listing(listings, entry):
            added += 1
            print(f'Added: {c["company"]} — {c["title"]}')
        seen[c['key']] = today

    if added:
        save_json(LISTINGS_FILE, listings)
        import subprocess
        subprocess.run(['python3', '.github/scripts/rebuild_readme.py'], check=True)

    if github_token and repo:
        for c in needs_review:
            listing_type, season = classify_season(c['title'])
            create_github_issue(
                github_token, repo,
                c['company'], c['title'], c['location'], c['url'], season
            )
            seen[c['key']] = today
            time.sleep(1)

    save_json(SEEN_FILE, seen)
    print('Done.')


if __name__ == '__main__':
    main()
