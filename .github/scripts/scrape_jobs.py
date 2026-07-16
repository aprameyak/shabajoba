#!/usr/bin/env python3

import json
import os
import re
import time
import datetime
import subprocess
from pathlib import Path
import requests

LISTINGS_FILE = Path('listings.json')
SEEN_FILE = Path('.github/data/seen_jobs.json')
CLASSIFICATIONS_FILE = Path('.github/data/title_classifications.json')
GEMINI_USAGE_FILE = Path('.github/data/gemini_usage.json')

EE_TITLE_KEYWORDS = [
    'electrical engineer', 'hardware engineer', 'analog engineer',
    'rf engineer', 'rf design', 'power engineer', 'signal integrity',
    'pcb design', 'pcb engineer', 'vlsi', 'asic', 'fpga', 'embedded hardware',
    'test engineer', 'systems engineer', 'signal processing', 'circuit design',
    'photonics', 'mixed signal', 'mixed-signal', 'power electronics', 'silicon',
    'semiconductor', 'ic design', 'chip design', 'soc design', 'soc engineer',
    'verification engineer', 'physical design', 'layout engineer',
    'product engineer', 'applications engineer', 'field applications engineer',
    'power systems', 'electric vehicle', 'battery systems', 'battery engineer',
    'motor control', 'avionics', 'electrical systems', 'microelectronics',
    'optoelectronics', 'electro-optical', 'radar engineer', 'antenna engineer',
    'electromagnetics', 'high voltage', 'power conversion', 'inverter',
    'substations', 'silicon photonics', 'test development engineer',
    'hardware validation', 'hardware verification', 'chip validation',
    'characterization engineer', 'process integration', 'device engineer',
]

EXCLUDE_TITLE_KEYWORDS = [
    'software engineer', 'software developer', 'data scientist',
    'machine learning engineer', 'ml engineer', 'data engineer',
    'backend engineer', 'frontend engineer', 'full stack', 'fullstack',
    'devops', 'site reliability', 'sre', 'marketing', 'sales', 'hr',
    'recruiter', 'finance', 'accounting', 'legal', 'mechanical engineer',
    'civil engineer', 'chemical engineer', 'product manager',
    'program manager', 'business analyst', 'supply chain', 'counsel',
    'industrial engineer', 'manufacturing engineer', 'operations analyst',
]

INTERNSHIP_KEYWORDS = [
    'intern', 'internship', 'co-op', 'coop', 'co op',
    'student', 'summer 2027', 'fall 2026', 'spring 2027', 'winter 2027',
    'pathways', 'college hire', 'early career',
]

US_CA_LOCATION_TOKENS = {
    'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga',
    'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la', 'me', 'md',
    'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj',
    'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc',
    'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy', 'dc',
    'ab', 'bc', 'mb', 'nb', 'nl', 'ns', 'nt', 'nu', 'on', 'pe', 'qc', 'sk', 'yt',
}

US_CA_LOCATION_PHRASES = [
    'remote', 'united states', 'canada', 'u.s.', 'usa', 'u.s.a',
]

GEMINI_DAILY_LIMIT = 1400
GEMINI_DELAY = 4.2


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
    url = re.sub(r'[?&](utm_\w+|source|ref|gh_src)=[^&]*', '', url)
    return url.rstrip('/')


def is_us_or_canada(location_text):
    if not location_text:
        return True
    loc = location_text.lower()
    for phrase in US_CA_LOCATION_PHRASES:
        if phrase in loc:
            return True
    tokens = re.findall(r'\b([a-z]{2})\b', loc)
    return any(t in US_CA_LOCATION_TOKENS for t in tokens)


def is_ee_title(title):
    t = title.lower()
    if any(kw in t for kw in EXCLUDE_TITLE_KEYWORDS):
        return False
    return any(kw in t for kw in EE_TITLE_KEYWORDS)


def is_internship(title):
    t = title.lower()
    return any(kw in t for kw in INTERNSHIP_KEYWORDS)


def infer_education(title):
    t = title.lower()
    if 'phd' in t or 'doctoral' in t or 'doctorate' in t:
        return 'PhD'
    if 'master' in t or ' ms ' in t or 'graduate student' in t:
        return 'Masters'
    return 'Undergrad'


def classify_season(title):
    t = title.lower()
    if 'fall 2026' in t:
        return ('offcycle', 'Fall 2026')
    if 'spring 2027' in t:
        return ('offcycle', 'Spring 2027')
    if 'winter 2027' in t:
        return ('offcycle', 'Winter 2027')
    if 'co-op' in t or 'coop' in t or 'co op' in t:
        return ('offcycle', 'Co-op')
    return ('summer', 'Summer 2027')


def add_listing(listings, entry):
    norm = normalize_url(entry['url'])
    for existing in listings:
        if existing.get('url') and normalize_url(existing['url']) == norm:
            return False
        if (existing['company'].lower() == entry['company'].lower()
                and existing['role'].lower() == entry['role'].lower()):
            return False
    listings.append(entry)
    return True


def classify_titles_gemini(titles, api_key, usage):
    if not api_key or usage['count'] >= GEMINI_DAILY_LIMIT:
        return {}
    results = {}
    for title in titles:
        if usage['count'] >= GEMINI_DAILY_LIMIT:
            break
        prompt = (
            'Is the following job title an electrical engineering role '
            '(hardware, EE, RF, analog, power, VLSI, ASIC, FPGA, PCB, test, '
            'signal processing, photonics, radar, avionics, or similar hardware discipline)? '
            'Answer only "yes" or "no".\n\n'
            f'Title: "{title}"'
        )
        try:
            resp = requests.post(
                'https://generativelanguage.googleapis.com/v1beta/models/'
                'gemini-1.5-flash:generateContent?key=' + api_key,
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


def scrape_greenhouse(company, board_token, seen):
    jobs = []
    try:
        url = f'https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true'
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        for job in resp.json().get('jobs', []):
            title = job.get('title', '')
            location = job.get('location', {}).get('name', '')
            apply_url = job.get('absolute_url', '')
            job_id = str(job.get('id', ''))
            key = f'greenhouse:{board_token}:{job_id}'
            if key in seen or not is_internship(title) or not is_us_or_canada(location):
                continue
            jobs.append({'key': key, 'company': company, 'title': title,
                         'location': location, 'url': apply_url})
    except Exception as e:
        print(f'Greenhouse error [{company}]: {e}')
    return jobs


def scrape_lever(company, slug, seen):
    jobs = []
    try:
        url = f'https://api.lever.co/v0/postings/{slug}?mode=json'
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        for posting in resp.json():
            title = posting.get('text', '')
            location = posting.get('categories', {}).get('location', '')
            apply_url = posting.get('hostedUrl', '')
            job_id = posting.get('id', '')
            key = f'lever:{slug}:{job_id}'
            if key in seen or not is_internship(title):
                continue
            if location and not is_us_or_canada(location):
                continue
            jobs.append({'key': key, 'company': company, 'title': title,
                         'location': location or 'United States', 'url': apply_url})
    except Exception as e:
        print(f'Lever error [{company}]: {e}')
    return jobs


def scrape_ashby(company, ashby_id, seen):
    jobs = []
    try:
        payload = {
            'operationName': 'ApiJobBoardWithTeams',
            'variables': {'organizationHostedJobsPageName': ashby_id},
            'query': (
                'query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {'
                '  jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {'
                '    jobPostings { id title locationName isRemote externalLink }'
                '  }'
                '}'
            ),
        }
        resp = requests.post(
            'https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams',
            json=payload, timeout=15,
        )
        resp.raise_for_status()
        postings = (resp.json().get('data', {})
                    .get('jobBoard', {}).get('jobPostings', []))
        for p in postings:
            title = p.get('title', '')
            location = p.get('locationName', '') or ''
            if p.get('isRemote'):
                location = 'Remote (US)'
            apply_url = (p.get('externalLink') or
                         f'https://jobs.ashbyhq.com/{ashby_id}/{p["id"]}')
            key = f'ashby:{ashby_id}:{p["id"]}'
            if key in seen or not is_internship(title):
                continue
            if location and not is_us_or_canada(location):
                continue
            jobs.append({'key': key, 'company': company, 'title': title,
                         'location': location or 'United States', 'url': apply_url})
    except Exception as e:
        print(f'Ashby error [{company}]: {e}')
    return jobs


def scrape_workday(company, tenant, site, board_num, seen):
    jobs = []
    base = f'https://{tenant}.wd{board_num}.myworkdayjobs.com'
    endpoint = f'{base}/wday/cxs/{tenant}/{site}/jobs'
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0',
    }
    offset = 0
    limit = 20
    while True:
        payload = {
            'appliedFacets': {},
            'limit': limit,
            'offset': offset,
            'searchText': 'intern',
        }
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)
            if resp.status_code in (404, 403):
                break
            resp.raise_for_status()
            data = resp.json()
            job_postings = data.get('jobPostings', [])
            if not job_postings:
                break
            for job in job_postings:
                title = job.get('title', '')
                location = job.get('locationsText', '') or job.get('primaryLocationText', '')
                job_id = job.get('bulletFields', [''])[0] if job.get('bulletFields') else ''
                external_path = job.get('externalPath', '')
                apply_url = f'{base}/{site}/job/{external_path}' if external_path else ''
                key = f'workday:{tenant}:{external_path or title}'
                if key in seen or not is_internship(title):
                    continue
                if location and not is_us_or_canada(location):
                    continue
                jobs.append({'key': key, 'company': company, 'title': title,
                             'location': location or 'United States', 'url': apply_url})
            if len(job_postings) < limit:
                break
            offset += limit
            time.sleep(0.5)
        except Exception as e:
            print(f'Workday error [{company}]: {e}')
            break
    return jobs


def scrape_smartrecruiters(company, company_id, seen):
    jobs = []
    offset = 0
    limit = 100
    while True:
        try:
            resp = requests.get(
                f'https://api.smartrecruiters.com/v1/companies/{company_id}/postings',
                params={'limit': limit, 'offset': offset},
                timeout=15,
            )
            if resp.status_code in (404, 403):
                break
            resp.raise_for_status()
            data = resp.json()
            postings = data.get('content', [])
            if not postings:
                break
            for p in postings:
                title = p.get('name', '')
                city = p.get('location', {}).get('city', '')
                region = p.get('location', {}).get('region', '')
                country = p.get('location', {}).get('country', '')
                remote = p.get('location', {}).get('remote', False)
                location = f'{city}, {region}' if city and region else city or region or country
                if remote:
                    location = 'Remote (US)'
                job_id = p.get('id', '')
                apply_url = f'https://jobs.smartrecruiters.com/{company_id}/{job_id}'
                key = f'smartrecruiters:{company_id}:{job_id}'
                if key in seen or not is_internship(title):
                    continue
                if country and country.upper() not in ('US', 'CA', 'USA', 'CAN', ''):
                    continue
                if location and not is_us_or_canada(location) and not remote:
                    continue
                jobs.append({'key': key, 'company': company, 'title': title,
                             'location': location or 'United States', 'url': apply_url})
            if len(postings) < limit:
                break
            offset += limit
            time.sleep(0.5)
        except Exception as e:
            print(f'SmartRecruiters error [{company}]: {e}')
            break
    return jobs


def scrape_icims(company, customer_id, seen):
    jobs = []
    try:
        feed_url = f'https://careers.icims.com/jobs/search?pr=1&schemaId=&jobFamily=&jobType=&loctype=&startrow=1&listformat=j&in_iframe=1&customerId={customer_id}&searchKeyword=intern'
        resp = requests.get(feed_url, timeout=15,
                            headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code != 200:
            return jobs
        matches = re.findall(r'"jobtitle"\s*:\s*"([^"]+)"', resp.text)
        ids = re.findall(r'"jobid"\s*:\s*"([^"]+)"', resp.text)
        locs = re.findall(r'"joblocation"\s*:\s*"([^"]+)"', resp.text)
        for i, title in enumerate(matches):
            job_id = ids[i] if i < len(ids) else str(i)
            location = locs[i] if i < len(locs) else ''
            apply_url = f'https://careers.icims.com/jobs/{job_id}/job'
            key = f'icims:{customer_id}:{job_id}'
            if key in seen or not is_internship(title):
                continue
            if location and not is_us_or_canada(location):
                continue
            jobs.append({'key': key, 'company': company, 'title': title,
                         'location': location or 'United States', 'url': apply_url})
    except Exception as e:
        print(f'iCIMS error [{company}]: {e}')
    return jobs


def scrape_usajobs(seen):
    jobs = []
    api_key = os.environ.get('USAJOBS_API_KEY', '')
    email = os.environ.get('USAJOBS_EMAIL', '')
    if not api_key or not email:
        print('USAJOBS: skipping (no API key/email configured)')
        return jobs

    keywords = [
        'electrical engineer intern',
        'hardware engineer intern',
        'electronics engineer intern',
        'rf engineer intern',
        'FPGA intern',
        'ASIC intern',
        'power systems intern',
        'avionics intern',
        'signal processing intern',
    ]
    headers = {
        'Authorization-Key': api_key,
        'User-Agent': email,
        'Host': 'data.usajobs.gov',
    }
    seen_usajobs = set()
    for keyword in keywords:
        try:
            resp = requests.get(
                'https://data.usajobs.gov/api/search',
                params={
                    'Keyword': keyword,
                    'ResultsPerPage': 50,
                    'StudentIndicator': 'true',
                },
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            items = (resp.json()
                     .get('SearchResult', {})
                     .get('SearchResultItems', []))
            for item in items:
                mv = item.get('MatchedObjectDescriptor', {})
                title = mv.get('PositionTitle', '')
                apply_url = mv.get('PositionURI', '')
                job_id = mv.get('PositionID', '')
                locations = mv.get('PositionLocation', [])
                location = '; '.join(
                    f'{l.get("CityName", "")}, {l.get("CountrySubDivisionCode", "")}'.strip(', ')
                    for l in locations
                ) if locations else 'United States'
                key = f'usajobs:{job_id}'
                if key in seen or job_id in seen_usajobs:
                    continue
                seen_usajobs.add(job_id)
                if not is_internship(title) and 'pathways' not in title.lower():
                    continue
                org = mv.get('OrganizationName', 'U.S. Government')
                jobs.append({'key': key, 'company': org, 'title': title,
                             'location': location, 'url': apply_url})
            time.sleep(0.5)
        except Exception as e:
            print(f'USAJOBS error [{keyword}]: {e}')
    return jobs


def scrape_national_lab(company, base_url, workday_tenant, workday_site, workday_num, seen):
    return scrape_workday(company, workday_tenant, workday_site, workday_num, seen)


def create_github_issue(token, repo, company, role, location, url, season):
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
            json={'title': title, 'body': body,
                  'labels': ['new listing', 'needs review']},
            timeout=15,
        )
        resp.raise_for_status()
        print(f'Created issue: {title}')
    except Exception as e:
        print(f'Issue creation error: {e}')


GREENHOUSE_COMPANIES = [
    ('Analog Devices', 'analogdevices'),
    ('Broadcom', 'broadcom'),
    ('Cadence Design Systems', 'cadence'),
    ('Cirrus Logic', 'cirruslogic'),
    ('Lattice Semiconductor', 'latticesemiconductor'),
    ('Lumentum', 'lumentum'),
    ('Marvell Technology', 'marvell'),
    ('Microchip Technology', 'microchip'),
    ('Micron Technology', 'micron'),
    ('Monolithic Power Systems', 'mps'),
    ('NVIDIA', 'nvidia'),
    ('NXP Semiconductors', 'nxp'),
    ('ON Semiconductor', 'onsemi'),
    ('Qualcomm', 'qualcomm'),
    ('Skyworks Solutions', 'skyworks'),
    ('Tenstorrent', 'tenstorrent'),
    ('Wolfspeed', 'wolfspeed'),
    ('Anduril', 'anduril'),
    ('Aurora Innovation', 'aurora'),
    ('Rocket Lab', 'rocketlab'),
    ('SpaceX', 'spacex'),
    ('Lucid Motors', 'lucidmotors'),
    ('Rivian', 'rivian'),
    ('Keysight Technologies', 'keysight'),
    ('Teradyne', 'teradyne'),
    ('Eaton', 'eaton'),
    ('GE Aerospace', 'geaerospace'),
    ('Waymo', 'waymo'),
    ('Verkada', 'verkada'),
    ('Texas Instruments', 'ti'),
]

LEVER_COMPANIES = [
    ('Blue Origin', 'blueorigin'),
    ('Shield AI', 'shieldai'),
    ('Zoox', 'zoox'),
    ('Sarcos Technology', 'sarcos'),
    ('Electra', 'electra'),
    ('Joby Aviation', 'jobyaviation'),
]

ASHBY_COMPANIES = [
    ('Anduril Industries', 'anduril'),
    ('Applied Intuition', 'appliedintuition'),
    ('Astera Labs', 'asteralabs'),
    ('Cerebras Systems', 'cerebras'),
    ('Etched', 'etched'),
    ('Groq', 'groq'),
    ('Tenstorrent', 'tenstorrent'),
    ('Astranis', 'astranis'),
    ('Varda Space', 'varda'),
    ('Relativity Space', 'relativityspace'),
    ('Hermeus', 'hermeus'),
    ('Archer Aviation', 'archeraviation'),
    ('Wisk Aero', 'wisk'),
]

WORKDAY_COMPANIES = [
    ('Intel', 'intel', 'External', '1'),
    ('Texas Instruments', 'ti', 'TICareersSite', '3'),
    ('Analog Devices', 'analogdevices', 'External', '1'),
    ('Qualcomm', 'qualcomm', 'External', '1'),
    ('NVIDIA', 'nvidia', 'NVIDIAExternalCareerSite', '1'),
    ('AMD', 'amd', 'External', '1'),
    ('Micron Technology', 'micron', 'External', '5'),
    ('Skyworks Solutions', 'skyworks', 'External', '1'),
    ('Qorvo', 'qorvo', 'ExternalCareerSite', '1'),
    ('GlobalFoundries', 'globalfoundries', 'External', '1'),
    ('Boeing', 'boeing', 'EXTERNAL_CAREER_SITE', '5'),
    ('Northrop Grumman', 'northropgrumman', 'External', '1'),
    ('Raytheon', 'rtx', 'RTXCareers', '5'),
    ('Lockheed Martin', 'lmt', 'LMCareers', '3'),
    ('BAE Systems', 'baesystems', 'External', '1'),
    ('Blue Origin', 'blueorigin', 'External', '1'),
    ('L3Harris Technologies', 'l3harris', 'ExternalCareerSite', '5'),
    ('General Dynamics', 'gd', 'External', '1'),
    ('Leidos', 'leidos', 'External', '1'),
    ('SAIC', 'saic', 'ExternalCareers', '1'),
    ('Rivian', 'rivian', 'External', '1'),
    ('Ford Motor Company', 'ford', 'fordmotorcompany', '5'),
    ('General Motors', 'gm', 'External', '5'),
    ('Tesla', 'tesla', 'TeslaCareers', '1'),
    ('Schneider Electric', 'schneider', 'External', '1'),
    ('Eaton Corporation', 'eaton', 'External', '5'),
    ('Siemens', 'siemens', 'External', '1'),
    ('GE Vernova', 'gevernova', 'External', '1'),
    ('Keysight Technologies', 'keysight', 'External', '1'),
    ('National Instruments / NI', 'ni', 'External', '1'),
    ('Sandia National Laboratories', 'sandia', 'ExternalCareers', '1'),
    ('Oak Ridge National Laboratory', 'ornl', 'External', '1'),
    ('NREL', 'nrel', 'External', '1'),
    ('Los Alamos National Laboratory', 'lanl', 'External', '1'),
    ('Amphenol', 'amphenol', 'External', '1'),
    ('TE Connectivity', 'te', 'TEConnectivity', '5'),
    ('Moog', 'moog', 'ExternalCareers', '1'),
    ('Curtiss-Wright', 'curtisswright', 'External', '1'),
    ('Viasat', 'viasat', 'External', '1'),
    ('Garmin', 'garmin', 'External', '1'),
    ('Motorola Solutions', 'motorolasolutions', 'External', '1'),
]

SMARTRECRUITERS_COMPANIES = [
    ('Canva', 'Canva'),
    ('Western Digital', 'WesternDigital'),
    ('Vishay Intertechnology', 'Vishay'),
    ('Iteris', 'Iteris'),
    ('Benchmark Electronics', 'BenchmarkElectronics'),
]

ICIMS_COMPANIES = [
    ('BAE Systems US', '3767'),
    ('Collins Aerospace', '3771'),
    ('Parker Hannifin', '3024'),
    ('Textron', '2236'),
]

NATIONAL_LABS = [
    ('Sandia National Laboratories', 'https://sandia.gov/careers', 'sandia', 'ExternalCareers', '1'),
    ('Oak Ridge National Laboratory', 'https://ornl.gov/careers', 'ornl', 'External', '1'),
    ('NREL', 'https://nrel.gov/careers', 'nrel', 'External', '1'),
    ('Los Alamos National Laboratory', 'https://lanl.gov/careers', 'lanl', 'External', '1'),
]


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

    print('=== Greenhouse ===')
    for company, token in GREENHOUSE_COMPANIES:
        found = scrape_greenhouse(company, token, seen)
        candidates.extend(found)
        if found:
            print(f'  {company}: {len(found)} candidates')
        time.sleep(0.4)

    print('=== Lever ===')
    for company, slug in LEVER_COMPANIES:
        found = scrape_lever(company, slug, seen)
        candidates.extend(found)
        if found:
            print(f'  {company}: {len(found)} candidates')
        time.sleep(0.4)

    print('=== Ashby ===')
    for company, slug in ASHBY_COMPANIES:
        found = scrape_ashby(company, slug, seen)
        candidates.extend(found)
        if found:
            print(f'  {company}: {len(found)} candidates')
        time.sleep(0.4)

    print('=== Workday ===')
    for company, tenant, site, num in WORKDAY_COMPANIES:
        found = scrape_workday(company, tenant, site, num, seen)
        candidates.extend(found)
        if found:
            print(f'  {company}: {len(found)} candidates')
        time.sleep(0.6)

    print('=== SmartRecruiters ===')
    for company, company_id in SMARTRECRUITERS_COMPANIES:
        found = scrape_smartrecruiters(company, company_id, seen)
        candidates.extend(found)
        if found:
            print(f'  {company}: {len(found)} candidates')
        time.sleep(0.4)

    print('=== iCIMS ===')
    for company, customer_id in ICIMS_COMPANIES:
        found = scrape_icims(company, customer_id, seen)
        candidates.extend(found)
        if found:
            print(f'  {company}: {len(found)} candidates')
        time.sleep(0.4)

    print('=== USAJOBS ===')
    usajobs_found = scrape_usajobs(seen)
    candidates.extend(usajobs_found)
    if usajobs_found:
        print(f'  USAJOBS: {len(usajobs_found)} candidates')

    print(f'\nTotal candidates: {len(candidates)}')

    titles_to_classify = list({
        c['title'] for c in candidates
        if c['title'] not in classifications
    })
    if titles_to_classify and gemini_key:
        new_cls = classify_titles_gemini(titles_to_classify, gemini_key, gemini_usage)
        classifications.update(new_cls)
        save_json(CLASSIFICATIONS_FILE, classifications)

    confirmed = []
    needs_review = []
    for c in candidates:
        title = c['title']
        keyword_match = is_ee_title(title)
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
        subprocess.run(['python3', '.github/scripts/rebuild_readme.py'], check=True)

    if github_token and repo:
        for c in needs_review:
            _, season = classify_season(c['title'])
            create_github_issue(
                github_token, repo,
                c['company'], c['title'], c['location'], c['url'], season,
            )
            seen[c['key']] = today
            time.sleep(1)

    save_json(SEEN_FILE, seen)
    print('Done.')


if __name__ == '__main__':
    main()
