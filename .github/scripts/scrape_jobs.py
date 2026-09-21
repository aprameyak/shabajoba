#!/usr/bin/env python3

import json
import os
import re
import time
import datetime
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

LISTINGS_FILE = Path('listings.json')
SEEN_FILE = Path('.github/data/seen_jobs.json')
CLASSIFICATIONS_FILE = Path('.github/data/title_classifications.json')
GEMINI_USAGE_FILE = Path('.github/data/gemini_usage.json')

CLAUDE_MODEL = 'claude-haiku-4-5-20251001'
ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'

EE_TITLE_KEYWORDS = [
    'electrical engineer', 'electrical engineering', 'electrical',
    'electronics engineer', 'electronics', 'interconnect',
    'hardware engineer', 'hardware engineering', 'hardware intern',
    'hardware r&d', 'hardware design', 'hardware development',
    'hardware systems', 'hardware developer', 'hardware quality',
    'hardware embedded',     'analog engineer', 'analog design', 'analog validation', 'analog ',
    'digital design', 'digital circuit',
    'rf engineer', 'rf design', 'rf cyber', 'rf technology', 'wireless',
    'power engineer', 'power design', 'signal integrity',
    'pcb design', 'pcb engineer', 'vlsi', 'asic', 'fpga', 'embedded hardware',
    'test engineer', 'test engineering', 'test solutions', 'signal processing',
    'circuit design', 'circuitry', 'circuit analysis', 'circuits',
    'soi design', 'soi ',
    'photonics', 'photonic', 'mixed signal', 'mixed-signal', 'power electronics',
    'silicon', 'semiconductor', 'ic design', 'chip design', 'chip simulation',
    'soc design', 'soc engineer', 'verification engineer', 'physical design',
    'layout engineer', 'layout design', 'field applications engineer',
    'hardware applications', 'power systems', 'electric vehicle',
    'battery systems', 'battery engineer', 'motor control', 'avionics',
    'electrical systems', 'microelectronics', 'optoelectronics', 'electro-optical',
    'radar', 'antenna', 'electromagnetics', 'high voltage', 'power conversion',
    'inverter', 'substation', 'relay protection', 'protection engineer',
    'silicon photonics', 'test development engineer',
    'hardware validation', 'hardware verification', 'chip validation',
    'characterization engineer', 'device characterization', 'device engineer',
    'dft ', 'design for test', 'electrical intern', 'analog intern', 'rf intern',
    'fpga intern', 'asic intern', 'vlsi intern', 'pcb intern',
    'rfid', 'electro-mechanical', 'electromechanical', 'power engineering',
    'grid engineering', 'transmission engineer', 'distribution engineer',
    'dram', 'sram', 'nand', 'flash design', 'computer architecture',
    'hardware technolog', 'mems', 'lithography', 'photomask',
    'process integration', 'wafer', 'chiplet', 'serdes', 'phy design',
    'design verification', 'dsp/', 'dsp engineer', 'optical',
    'show control hardware', 'hardware undergrad', 'hardware masters',
    'automated test', 'product test', 'board design', 'schematic',
    'hardware reliability', 'hardware test', 'electrical platform',
    'platform hardware', 'firmware/hardware', 'hardware/firmware',
    'integration and test', 'audio test', 'instrumentation', 'i&c',
    'high performance analog', 'electronics hardware', 'electronics design',
    'vehicle electronics', 'subsystem test', 'computer-aided design',
    'cad engineer',
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
    'entry level', 'entry-level', 'new grad', 'new graduate', 'full-time',
    'full time', 'process engineer', 'manufacturing process',
    'quality engineer', 'facilities', 'human resources',
    'software test', 'software quality', 'qa engineer', 'sdet',
    'servicenow', 'salesforce', 'product analyst', 'business intern',
    'embedded software', 'software development', 'gen-ai', 'gen ai',
    'machine learning software', 'ml software', 'ai software',
    'structural engineer', 'civil engineer', 'architect intern',
    'asset management', 'business intelligence', 'firmware engineer',
    'project engineer', 'grid data', 'digital grid management',
]


INTERNSHIP_KEYWORDS = [
    'intern', 'internship', 'co-op', 'coop', 'co op',
    'student', 'pathways', 'coöop',
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


US_STATE_NAMES = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY', 'district of columbia': 'DC',
}

CA_PROVINCE_NAMES = {
    'ontario': 'ON', 'quebec': 'QC', 'british columbia': 'BC', 'alberta': 'AB',
    'manitoba': 'MB', 'saskatchewan': 'SK', 'nova scotia': 'NS',
    'new brunswick': 'NB', 'newfoundland': 'NL', 'newfoundland and labrador': 'NL',
    'prince edward island': 'PE', 'northwest territories': 'NT', 'nunavut': 'NU',
    'yukon': 'YT',
}


def normalize_location(loc):
    """Normalize ATS locations to `City, ST` / `Remote (US|Canada)`."""
    if not loc:
        return loc
    loc = loc.strip()
    # Drop pure country-only
    if loc.lower() in ('united states', 'usa', 'us', 'u.s.', 'u.s.a.'):
        return 'Remote (US)'
    if loc.lower() in ('canada',):
        return 'Remote (Canada)'

    # Workday-style: US-MD-Baltimore / US-CA-EL SEGUNDO-R01 ~ ...
    m = re.match(r'^US-([A-Z]{2})-([A-Za-z0-9 .\'-]+)', loc)
    if m:
        city = re.split(r'\s*~\s*', m.group(2))[0].strip()
        city = re.sub(r'-\d+.*$', '', city).strip(' -')
        city = city.title() if city.isupper() or city.islower() else city
        return f'{city}, {m.group(1).upper()}'

    # United States-Maryland-Baltimore / Canada-Ontario-Toronto
    m = re.match(r'^United States-([A-Za-z ]+)-(.+)$', loc, re.I)
    if m:
        abbr = US_STATE_NAMES.get(m.group(1).strip().lower())
        if abbr:
            return f'{m.group(2).strip()}, {abbr}'
    m = re.match(r'^Canada-([A-Za-z ]+)-(.+)$', loc, re.I)
    if m:
        abbr = CA_PROVINCE_NAMES.get(m.group(1).strip().lower())
        if abbr:
            return f'{m.group(2).strip()}, {abbr}'

    # Strip trailing country / zip
    loc = re.sub(r',?\s*United States( of America)?\s*$', '', loc, flags=re.I)
    loc = re.sub(r',?\s*USA\s*$', '', loc, flags=re.I)
    loc = re.sub(r',?\s*Canada\s*$', '', loc, flags=re.I)
    loc = re.sub(r',\s*\d{5}(-\d{4})?\s*$', '', loc)
    loc = loc.strip(' ,')

    # City, FullState -> City, ST
    for name, abbr in {**US_STATE_NAMES, **CA_PROVINCE_NAMES}.items():
        m = re.match(rf'^(.+),\s*{re.escape(name)}\s*$', loc, re.I)
        if m:
            return f'{m.group(1).strip()}, {abbr}'

    # "Salem VA USA" / "City ST"
    m = re.match(r'^([A-Za-z .\'-]+?)\s+([A-Z]{2})\s*(USA)?$', loc)
    if m and m.group(2).lower() in US_CA_LOCATION_TOKENS:
        return f'{m.group(1).strip()}, {m.group(2).upper()}'

    # "MI - Detroit Sales Office"
    m = re.match(r'^([A-Z]{2})\s*[-–]\s*([A-Za-z .]+)', loc)
    if m and m.group(1).lower() in US_CA_LOCATION_TOKENS:
        city = re.sub(r'\s+(Sales Office|Office|Site|Campus).*$', '', m.group(2), flags=re.I)
        return f'{city.strip()}, {m.group(1).upper()}'

    # Existing City, ST — strip campus suffixes
    m = re.match(r'^(.+,\s*[A-Z]{2})\s*[-–\u2013].+$', loc)
    if m:
        return m.group(1).strip()

    return loc


def is_us_or_canada(location_text):
    if not location_text:
        return False
    loc = location_text.lower().strip()
    for phrase in US_CA_LOCATION_PHRASES:
        if phrase in loc:
            return True
    foreign_phrases = (
        'united kingdom', 'germany', 'france', 'india', 'china',
        'singapore', 'japan', 'south korea', 'taiwan', 'israel', 'australia',
        'netherlands', 'ireland', 'switzerland', 'sweden', 'mexico', 'brazil',
        'hong kong', 'united arab emirates', 'dubai', 'remote - europe', 'emea',
    )
    if any(f in loc for f in foreign_phrases):
        if not any(p in loc for p in ('united states', 'canada', 'u.s.', 'usa')):
            tokens = re.findall(r'\b([a-z]{2})\b', loc)
            if not any(t in US_CA_LOCATION_TOKENS for t in tokens):
                return False
    tokens = re.findall(r'\b([a-z]{2})\b', loc)
    return any(t in US_CA_LOCATION_TOKENS for t in tokens)


def is_ee_title(title):
    t = title.lower()
    if any(kw in t for kw in EXCLUDE_TITLE_KEYWORDS):
        return False
    # "Software / Hardware" and similar hybrids are usually SWE-primary
    if 'software' in t and 'hardware' in t:
        return False
    # Bare "systems engineer" is too ambiguous (often IT/SWE) — require EE signals
    if 'systems engineer' in t or 'systems engineering' in t:
        if not any(x in t for x in (
            'electrical', 'avionics', 'hardware', 'power', 'rf', 'embedded',
            'radar', 'antenna', 'fpga', 'asic', 'analog', 'digital',
        )):
            return False
    return any(kw in t for kw in EE_TITLE_KEYWORDS)


def is_internship(title):
    t = title.lower()
    if any(x in t for x in ('entry level', 'entry-level', 'new grad', 'new graduate')):
        return False
    return any(kw in t for kw in INTERNSHIP_KEYWORDS)


def infer_education(title):
    t = title.lower()
    if 'phd' in t or 'doctoral' in t or 'doctorate' in t:
        return 'PhD'
    if 'master' in t or ' ms ' in t or 'graduate student' in t:
        return 'Masters'
    return 'Undergrad'


def sanitize_listing_role(company, role):
    """Normalize scraped titles so validate_listings.py passes."""
    role = re.sub(r',?\s*(Onsite|On-site|Remote|Hybrid)\s*$', '', role, flags=re.I)
    role = re.sub(r'\(Onsite\)|\(On-site\)|\(Remote\)|\(Hybrid\)', '', role, flags=re.I)
    role = re.sub(r'\s*\[(Summer|Fall|Spring|Winter)\s+20\d\d\]\s*', ' ', role, flags=re.I)
    role = re.sub(r'\s*\((Summer|Fall|Spring|Winter)\s+20\d\d\)\s*$', '', role, flags=re.I)
    role = re.sub(r'\s*\(Summer of 20\d\d\)\s*$', '', role, flags=re.I)
    role = re.sub(
        r'\s*\((?:Summer|Fall|Spring|Winter)(?:\s*/\s*(?:Summer|Fall|Spring|Winter))?\s*20\d\d\)\s*',
        ' ', role, flags=re.I,
    )
    role = re.sub(
        r'\s*\((?:Winter|Spring|Summer|Fall)\s*/\s*(?:Winter|Spring|Summer|Fall)(?:\s*20\d\d)?\)\s*',
        ' ', role, flags=re.I,
    )
    role = re.sub(
        r'\s*\((?:January|Jan|February|Feb|March|Mar|April|Apr|May|June|Jun|July|Jul|'
        r'August|Aug|September|Sep|October|Oct|November|Nov|December|Dec)'
        r'(?:\s*[-–—]\s*(?:January|Jan|February|Feb|March|Mar|April|Apr|May|June|Jun|July|Jul|'
        r'August|Aug|September|Sep|October|Oct|November|Nov|December|Dec))?'
        r'(?:\s+20\d\d)?\)\s*',
        ' ', role, flags=re.I,
    )
    role = re.sub(
        r'\s*[-–—]\s*(Winter|Spring|Summer|Fall)(?:\s*/\s*|\s+)(Winter|Spring|Summer|Fall)?\s*20\d\d.*$',
        '', role, flags=re.I,
    )
    role = re.sub(r'\s*[-–—]\s*(Summer|Fall|Spring|Winter)\s+20\d\d.*$', '', role, flags=re.I)
    role = re.sub(r'\s+(Summer|Fall|Spring|Winter)\s+20\d\d\s*$', '', role, flags=re.I)
    role = re.sub(r'^(Summer|Fall|Spring|Winter)\s+20\d\d\s+', '', role, flags=re.I)
    role = re.sub(r'^20\d\d\s+(Spring|Summer|Fall|Winter)\s+', '', role, flags=re.I)
    role = re.sub(r'^20\d\d\s+(US\s+)?', '', role, flags=re.I)
    role = re.sub(r'\s*[-–—]\s*20\d\d\b.*$', '', role)
    role = re.sub(r'\b20\d\d\b', '', role)
    role = re.sub(r'^NVIDIA 2027 Internships:\s*', '', role, flags=re.I)
    role = re.sub(r'\s*\(R\d+\)\s*$', '', role)
    role = re.sub(r'\s*[-–—]\s*Plus one semester\s*$', '', role, flags=re.I)
    role = re.sub(r'\s*[-–—]\s*Fall\s+20\d\d\s+Start Date\s*$', '', role, flags=re.I)
    role = re.sub(r'\s*\([A-Za-z .]+,\s*[A-Z]{2}\)\s*$', '', role)  # (Novi, MI)
    role = re.sub(r'^Intern(?:ship)?\s*[—–\-:]\s*', '', role, flags=re.I)
    role = re.sub(r'^Intern,\s*', '', role, flags=re.I)
    if company:
        role = re.sub(re.escape(company), '', role, flags=re.I)
    role = re.sub(r'\bCo-op/Intern\b', 'Intern/Co-op', role, flags=re.I)
    role = re.sub(r'\s+', ' ', role).strip(' -–—/')
    # Ensure internship/co-op signal survives aggressive year/season stripping
    if role and not re.search(r'intern|co-?op|student|pathways', role, re.I):
        role = role + ' Intern'
    return role


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


def listing_exists(listings, url, company, role):
    norm = normalize_url(url)
    for existing in listings:
        if existing.get('url') and normalize_url(existing['url']) == norm:
            return True
        if (existing['company'].lower() == company.lower()
                and existing['role'].lower() == role.lower()):
            return True
    return False


def add_listing(listings, entry):
    if listing_exists(listings, entry['url'], entry['company'], entry['role']):
        return False
    listings.append(entry)
    return True


def title_excluded_by_keyword(title):
    t = title.lower()
    return any(kw in t for kw in EXCLUDE_TITLE_KEYWORDS)


def should_llm_classify_title(title, classifications):
    if title in classifications:
        return False
    if is_ee_title(title) or title_excluded_by_keyword(title):
        if title not in classifications:
            classifications[title] = is_ee_title(title)
        return False
    return True


def candidate_passes_scope(c):
    return is_internship(c['title']) and is_us_or_canada(c['location'])


def resolve_ambiguous_candidates(candidates, classifications, claude_key, gemini_key, gemini_usage):
    """Retry LLM for titles that failed first pass; returns newly confirmed jobs."""
    if not candidates:
        return []
    titles = list({c['title'] for c in candidates if c['title'] not in classifications})
    if titles and claude_key:
        classifications.update(batch_classify_ee_claude(titles, claude_key))
    elif titles and gemini_key:
        classifications.update(
            classify_titles_gemini(titles, gemini_key, gemini_usage)
        )
    confirmed = []
    for c in candidates:
        title = c['title']
        llm_result = classifications.get(title)
        if llm_result is True or (llm_result is None and is_ee_title(title)):
            confirmed.append(c)
        elif llm_result is None:
            classifications[title] = False
            print(f'Skip (unclassified): {c["company"]} — {title}')
    return confirmed


def strip_html(html_text):
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r'<[^>]+>', ' ', html_text or '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def infer_metadata_keywords(text):
    """Cheap keyword pass; avoids Claude when posting language is explicit."""
    if not text:
        return {'sponsorship': 'Unknown', 'citizenship': 'Unknown'}
    t = text.lower()
    sponsorship = 'Unknown'
    citizenship = 'Unknown'
    no_sponsor = (
        'will not sponsor', 'will not provide sponsorship', 'unable to sponsor',
        'no sponsorship', 'not provide sponsorship', 'without immigration sponsorship',
        'must be authorized to work', 'must have authorization to work',
        'eligible to work in the us without sponsorship',
    )
    yes_sponsor = (
        'visa sponsorship available', 'will sponsor', 'provide sponsorship',
        'h-1b', 'h1b visa', 'immigration sponsorship',
    )
    if any(p in t for p in no_sponsor):
        sponsorship = 'No — does NOT offer sponsorship'
    elif any(p in t for p in yes_sponsor):
        sponsorship = 'Yes — sponsorship available'
    cit_req = (
        'u.s. citizenship required', 'us citizenship required', 'must be a u.s. citizen',
        'must be us citizen', 'united states citizen required', 'top secret clearance',
        'ts/sci', 'secret clearance required', 'ability to obtain security clearance',
    )
    if any(p in t for p in cit_req):
        citizenship = 'Yes — U.S. citizenship required'
    elif 'citizenship is not required' in t or 'without regard to citizenship' in t:
        citizenship = 'No'
    return {'sponsorship': sponsorship, 'citizenship': citizenship}


def extract_job_metadata(title, description_text, api_key):
    inferred = infer_metadata_keywords(description_text)
    if inferred['sponsorship'] != 'Unknown' and inferred['citizenship'] != 'Unknown':
        return inferred
    if not api_key or not description_text:
        return inferred
    claude = extract_job_metadata_claude(title, description_text, api_key)
    return {
        'sponsorship': (
            claude.get('sponsorship')
            if claude.get('sponsorship') not in (None, 'Unknown') else inferred['sponsorship']
        ),
        'citizenship': (
            claude.get('citizenship')
            if claude.get('citizenship') not in (None, 'Unknown') else inferred['citizenship']
        ),
    }


def batch_classify_ee_claude(titles, api_key):
    """
    Classify a batch of job titles as EE-relevant using Claude Haiku.
    Returns dict of title -> bool. Falls back to keyword matching on error.
    """
    if not api_key or not titles:
        return {}
    results = {}
    batch_size = 40
    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        numbered = '\n'.join(f'{j + 1}. "{t}"' for j, t in enumerate(batch))
        prompt = (
            'EE hardware/electrical intern/co-op titles only. '
            'true=EE/hardware/RF/VLSI/ASIC/FPGA/PCB/test/avionics/power silicon; '
            'false=SWE/DS/ML/ME/civil/business/HR.\n'
            f'{numbered}\n'
            'JSON booleans only, same order.'
        )
        try:
            resp = requests.post(
                ANTHROPIC_API_URL,
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                json={
                    'model': CLAUDE_MODEL,
                    'max_tokens': 128,
                    'messages': [{'role': 'user', 'content': prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json()['content'][0]['text'].strip()
            parsed = json.loads(raw)
            for j, title in enumerate(batch):
                if j < len(parsed):
                    results[title] = bool(parsed[j])
            time.sleep(0.5)
        except Exception as e:
            print(f'Claude batch classify error (batch {i // batch_size}): {e}')
    return results


def extract_job_metadata_claude(title, description_text, api_key):
    """
    Extract sponsorship and citizenship info from a job description using Claude Haiku.
    Returns dict with 'sponsorship' and 'citizenship' keys.
    """
    if not api_key or not description_text:
        return {'sponsorship': 'Unknown', 'citizenship': 'Unknown'}
    truncated = description_text[:1200]
    prompt = (
        'JSON only: {"sponsorship":"Yes — sponsorship available"|'
        '"No — does NOT offer sponsorship"|"Unknown",'
        '"citizenship":"Yes — U.S. citizenship required"|"No"|"Unknown"}\n'
        f'Title: {title}\n{truncated}'
    )
    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': CLAUDE_MODEL,
                'max_tokens': 64,
                'messages': [{'role': 'user', 'content': prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()['content'][0]['text'].strip()
        return json.loads(raw)
    except Exception as e:
        print(f'Claude metadata error [{title[:50]}]: {e}')
        return {'sponsorship': 'Unknown', 'citizenship': 'Unknown'}


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
            description = strip_html(job.get('content', ''))
            jobs.append({'key': key, 'company': company, 'title': title,
                         'location': location, 'url': apply_url,
                         'description': description})
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
            desc_html = posting.get('descriptionHtml', '') or posting.get('description', '')
            lists_html = ' '.join(
                item.get('content', '') for item in posting.get('lists', [])
            )
            description = strip_html(desc_html + ' ' + lists_html)
            jobs.append({'key': key, 'company': company, 'title': title,
                         'location': location or 'United States', 'url': apply_url,
                         'description': description})
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
    """Search Workday campus boards with EE/intern keywords and paginate."""
    jobs = []
    base = f'https://{tenant}.wd{board_num}.myworkdayjobs.com'
    endpoint = f'{base}/wday/cxs/{tenant}/{site}/jobs'
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; shabajoba-scraper/1.0)',
        'Accept': 'application/json',
    }
    search_terms = [
        'intern', 'internship', 'co-op', 'electrical', 'hardware', 'FPGA', 'ASIC', '2027',
    ]
    seen_paths = set()
    limit = 20
    max_pages_per_term = 4

    for term in search_terms:
        offset = 0
        for _ in range(max_pages_per_term):
            payload = {
                'appliedFacets': {},
                'limit': limit,
                'offset': offset,
                'searchText': term,
            }
            try:
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)
                if resp.status_code in (404, 403):
                    break
                if resp.status_code != 200:
                    break
                data = resp.json()
                job_postings = data.get('jobPostings', [])
                if not job_postings:
                    break
                for job in job_postings:
                    title = job.get('title', '')
                    location = normalize_location(
                        job.get('locationsText', '') or job.get('primaryLocationText', '')
                    )
                    external_path = job.get('externalPath', '')
                    if not external_path or external_path in seen_paths:
                        continue
                    seen_paths.add(external_path)
                    apply_url = f'{base}/en-US/{site}{external_path}' if external_path else ''
                    # Prefer cleaner URL form used by boards
                    if external_path.startswith('/'):
                        apply_url = f'{base}{external_path}'
                    key = f'workday:{tenant}:{external_path}'
                    if key in seen or not is_internship(title):
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
                total = data.get('total', 0)
                offset += len(job_postings)
                if offset >= total or len(job_postings) < limit:
                    break
                time.sleep(0.12)
            except Exception as e:
                print(f'Workday error [{company}] "{term}": {e}')
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
                if country and country.lower() not in ('us', 'ca', 'usa', 'can', 'united states', 'canada', ''):
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


def scrape_workable(company, slug, seen):
    jobs = []
    try:
        resp = requests.get(
            f'https://apply.workable.com/api/v1/widget/accounts/{slug}',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=20,
        )
        if resp.status_code != 200:
            return jobs
        for job in resp.json().get('jobs', []):
            title = job.get('title', '')
            loc = job.get('location', {}) or {}
            country = (loc.get('countryCode') or loc.get('country') or '').lower()
            remote = bool(loc.get('remote', False))
            city = loc.get('city', '') or ''
            region = loc.get('region', '') or ''
            if country and country not in ('us', 'ca', 'usa', 'united states', 'canada') and not remote:
                continue
            if remote and country in ('ca', 'canada'):
                location = 'Remote (Canada)'
            elif remote:
                location = 'Remote (US)'
            elif city and region:
                location = f'{city}, {region}'
            elif city:
                location = city
            else:
                location = 'United States' if country in ('us', 'usa', '') else country.upper()
            if not is_internship(title):
                continue
            if location and not is_us_or_canada(location):
                continue
            job_id = job.get('shortcode', job.get('id', ''))
            key = f'workable:{slug}:{job_id}'
            if key in seen:
                continue
            jobs.append({
                'key': key,
                'company': company,
                'title': title,
                'location': location,
                'url': f'https://apply.workable.com/{slug}/j/{job_id}/',
            })
    except Exception as e:
        print(f'Workable error [{company}]: {e}')
    return jobs


def scrape_oracle(company, host, site_number, seen):
    """Oracle HCM Candidate Experience recruiting API."""
    host = host.strip().removeprefix('https://').removeprefix('http://').rstrip('/')
    site_number = str(site_number).strip()
    api_base = (
        f'https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions'
    )
    headers = {'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    search_terms = [
        'intern', 'internship', 'co-op', 'electrical', 'hardware', 'FPGA', 'ASIC', '2027',
    ]
    jobs = []
    seen_ids = set()
    page_size = 50

    for search_term in search_terms:
        offset = 0
        for _ in range(3):
            finder = (
                f'findReqs;siteNumber={site_number},'
                'facetsList=LOCATIONS;WORK_LOCATIONS;WORKPLACE_TYPES;TITLES;'
                'CATEGORIES;ORGANIZATIONS;JOB_FAMILY;JOB_FUNCTION;WORK_LEVEL;'
                f'WORKER_TYPES,limit={page_size},offset={offset},'
                f'keyword={search_term}'
            )
            try:
                resp = requests.get(
                    api_base,
                    params={
                        'onlyData': 'true',
                        'expand': 'requisitionList.secondaryLocations',
                        'finder': finder,
                    },
                    headers=headers,
                    timeout=30,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                items = data.get('items') or []
                block = items[0] if items else {}
                reqs = block.get('requisitionList') or []
                if not reqs:
                    break
                for job in reqs:
                    job_id = str(job.get('Id') or '').strip()
                    if not job_id or job_id in seen_ids:
                        continue
                    title = (job.get('Title') or '').strip()
                    location = normalize_location((job.get('PrimaryLocation') or '').strip())
                    if not title or not is_internship(title):
                        continue
                    if location and not is_us_or_canada(location):
                        continue
                    seen_ids.add(job_id)
                    key = f'oracle:{site_number}:{job_id}'
                    if key in seen:
                        continue
                    url = (
                        f'https://{host}/hcmUI/CandidateExperience/en/sites/'
                        f'{site_number}/job/{job_id}'
                    )
                    jobs.append({
                        'key': key,
                        'company': company,
                        'title': title,
                        'location': location or 'United States',
                        'url': url,
                    })
                total = block.get('TotalJobsCount') or block.get('totalJobsCount')
                offset += len(reqs)
                if total is not None and offset >= int(total):
                    break
                if len(reqs) < page_size:
                    break
                time.sleep(0.2)
            except Exception as e:
                print(f'Oracle error [{company}] "{search_term}": {e}')
                break
    return jobs


def scrape_icims(company, host, seen, keywords=None):
    """Best-effort iCIMS campus search scrape."""
    import html as _html
    keywords = keywords or [
        '2027', 'Intern', 'Internship', 'co-op', 'Electrical', 'Hardware', 'FPGA', 'ASIC',
    ]
    jobs = []
    seen_ids = set()
    base = f'https://{host}'
    headers = {'User-Agent': 'Mozilla/5.0'}

    for keyword in keywords:
        for page in range(0, 3):
            try:
                resp = requests.get(
                    f'{base}/jobs/search',
                    params={
                        'ss': '1',
                        'searchKeyword': keyword,
                        'searchRelation': 'keyword_all',
                        'in_iframe': '1',
                        'pr': str(page),
                    },
                    headers=headers,
                    timeout=20,
                )
                if resp.status_code != 200:
                    break
                html = resp.text
                cards = re.findall(
                    r'<li class="iCIMS_JobCardItem">(.*?)</li>',
                    html,
                    re.S | re.I,
                )
                if not cards:
                    break
                found_new = False
                for card in cards:
                    m = re.search(
                        r'href="(https?://[^"]+/jobs/(\d+)/[^"]+/job)[^"]*"[^>]*'
                        r'class="iCIMS_Anchor"[^>]*title="([^"]+)"',
                        card,
                        re.I,
                    )
                    if not m:
                        m = re.search(
                            r'href="(/jobs/(\d+)/[^"]+/job)[^"]*"[^>]*'
                            r'class="iCIMS_Anchor"[^>]*title="([^"]+)"',
                            card,
                            re.I,
                        )
                    if not m:
                        continue
                    url, job_id, title_attr = m.group(1), m.group(2), m.group(3)
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    found_new = True
                    title = re.sub(r'^\d+\s*-\s*', '', _html.unescape(title_attr)).strip()
                    h3 = re.search(r'<h3[^>]*>(.*?)</h3>', card, re.S | re.I)
                    if h3:
                        title = re.sub(r'<[^>]+>', '', _html.unescape(h3.group(1))).strip() or title
                    loc_m = re.search(
                        r'Job Locations?</span>.*?<span[^>]*>\s*([^<]+)',
                        card,
                        re.S | re.I,
                    )
                    location = ''
                    if loc_m:
                        raw = loc_m.group(1).strip()
                        parts = []
                        for piece in re.split(r'\s*\|\s*', raw):
                            mm = re.match(r'^US-([A-Z]{2})-(.+)$', piece.strip(), re.I)
                            if mm:
                                parts.append(f'{mm.group(2).strip()}, {mm.group(1).upper()}')
                            else:
                                parts.append(piece.strip())
                        location = normalize_location('; '.join(parts))
                    if not location:
                        location = 'United States'
                    if url.startswith('/'):
                        url = f'{base}{url}'
                    url = re.sub(r'\?.*$', '', url)
                    key = f'icims:{host}:{job_id}'
                    if key in seen or not is_internship(title):
                        continue
                    if location and not is_us_or_canada(location):
                        continue
                    jobs.append({
                        'key': key,
                        'company': company,
                        'title': title,
                        'location': location,
                        'url': url,
                    })
                if not found_new:
                    break
                time.sleep(0.15)
            except Exception as e:
                print(f'iCIMS error [{company}] "{keyword}" p{page}: {e}')
                break
    return jobs


def scrape_simplify(seen):
    """Pull Hardware/EE roles from SimplifyJobs Summer2027 listings feed."""
    url = (
        'https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/'
        'dev/.github/scripts/listings.json'
    )
    jobs = []
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f'Simplify error: {e}')
        return jobs

    for e in data:
        cat = e.get('category') or ''
        title = (e.get('title') or '').strip()
        company = (e.get('company_name') or '').strip()
        apply_url = (e.get('url') or '').strip()
        locs = e.get('locations') or []
        location = '; '.join(locs)
        active = e.get('active', True)
        if not company or not title:
            continue
        if cat not in ('Hardware', 'Hardware Engineering') and not is_ee_title(title):
            continue
        if not is_internship(title) or not is_ee_title(title):
            continue
        if location and not is_us_or_canada(location):
            continue
        terms = ' '.join(e.get('terms') or []).lower()
        if '2026' in terms and '2027' not in terms and 'fall 2026' not in terms:
            continue
        key = f"simplify:{e.get('id') or normalize_url(apply_url) or title}"
        if key in seen:
            continue
        jobs.append({
            'key': key,
            'company': company,
            'title': title,
            'location': location or 'United States',
            'url': apply_url if active else '',
            'terms': e.get('terms') or [],
            'degrees': e.get('degrees') or [],
            'sponsorship_raw': e.get('sponsorship') or '',
        })
    print(f'Simplify: {len(jobs)} EE/hardware candidates')
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
        'electrical engineering co-op',
        'pathways electrical',
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


def load_companies():
    """Load ATS company boards from companies.yml (YAML-driven scraping)."""
    try:
        import yaml
    except ImportError:
        print('PyYAML not installed — using empty company lists')
        return {}
    path = Path('companies.yml')
    if not path.exists():
        print('companies.yml not found')
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def build_scrape_tasks(seen):
    """Build (fn, args, label) tasks from companies.yml."""
    cfg = load_companies()
    tasks = []

    for e in cfg.get('greenhouse', []):
        tasks.append((scrape_greenhouse, (e['name'], e['slug'], seen), e['name']))
    for e in cfg.get('lever', []):
        tasks.append((scrape_lever, (e['name'], e['slug'], seen), e['name']))
    for e in cfg.get('ashby', []):
        tasks.append((scrape_ashby, (e['name'], e['slug'], seen), e['name']))
    for e in cfg.get('smartrecruiters', []):
        tasks.append((
            scrape_smartrecruiters,
            (e['name'], e['identifier'], seen),
            e['name'],
        ))
    for e in cfg.get('workday', []):
        tasks.append((
            scrape_workday,
            (e['name'], e['tenant'], e['site'], str(e.get('board_num', '1')), seen),
            e['name'],
        ))
    for e in cfg.get('workable', []):
        tasks.append((scrape_workable, (e['name'], e['slug'], seen), e['name']))
    for e in cfg.get('oracle', []):
        tasks.append((
            scrape_oracle,
            (e['name'], e['host'], e['site'], seen),
            e['name'],
        ))
    for e in cfg.get('icims', []):
        tasks.append((
            scrape_icims,
            (e['name'], e['host'], seen, e.get('keywords')),
            e['name'],
        ))
    return tasks


def main():
    claude_key = os.environ.get('ANTHROPIC_API_KEY', '')
    gemini_key = os.environ.get('GEMINI_API_KEY', '')

    listings = load_json(LISTINGS_FILE, [])
    seen = load_json(SEEN_FILE, {})
    classifications = load_json(CLASSIFICATIONS_FILE, {})
    gemini_usage = load_gemini_usage()

    today = datetime.date.today().isoformat()
    candidates = []

    tasks = build_scrape_tasks(seen)
    print(f'Scraping {len(tasks)} ATS boards ...')

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
            except Exception as e:
                print(f'  {company} error: {e}')

    print('=== USAJOBS ===')
    usajobs_found = scrape_usajobs(seen)
    candidates.extend(usajobs_found)
    if usajobs_found:
        print(f'  USAJOBS: {len(usajobs_found)} candidates')

    print('=== SimplifyJobs Hardware/EE ===')
    simplify_found = scrape_simplify(seen)
    candidates.extend(simplify_found)

    print(f'\nTotal candidates: {len(candidates)}')

    in_scope = [c for c in candidates if candidate_passes_scope(c)]
    out_scope = len(candidates) - len(in_scope)
    if out_scope:
        print(f'Out of scope (not intern/co-op or not US/Canada): {out_scope}')

    titles_to_classify = list({
        c['title'] for c in in_scope
        if should_llm_classify_title(c['title'], classifications)
    })

    if titles_to_classify and claude_key:
        print(f'Classifying {len(titles_to_classify)} titles with LLM ...')
        new_cls = batch_classify_ee_claude(titles_to_classify, claude_key)
        classifications.update(new_cls)
        save_json(CLASSIFICATIONS_FILE, classifications)
    elif titles_to_classify and gemini_key:
        print(f'Classifying {len(titles_to_classify)} titles with Gemini (fallback) ...')
        new_cls = classify_titles_gemini(titles_to_classify, gemini_key, gemini_usage)
        classifications.update(new_cls)
        save_json(CLASSIFICATIONS_FILE, classifications)

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
        elif llm_result is None and not keyword_match and (claude_key or gemini_key):
            ambiguous.append(c)
        elif llm_result is None and not keyword_match:
            print(f'Skip (no LLM): {c["company"]} — {title}')

    if ambiguous:
        print(f'Ambiguous after first pass: {len(ambiguous)} — retrying LLM')
        confirmed.extend(
            resolve_ambiguous_candidates(
                ambiguous, classifications, claude_key, gemini_key, gemini_usage,
            )
        )
        save_json(CLASSIFICATIONS_FILE, classifications)

    print(f'Confirmed for add: {len(confirmed)}')

    for c in confirmed:
        role = sanitize_listing_role(c['company'], c['title'])
        if listing_exists(listings, c['url'], c['company'], role):
            continue
        desc = c.get('description', '')
        if not desc:
            continue
        before = infer_metadata_keywords(desc)
        meta = extract_job_metadata(c['title'], desc, claude_key)
        c['sponsorship'] = meta.get('sponsorship', 'Unknown')
        c['citizenship'] = meta.get('citizenship', 'Unknown')
        if claude_key and (
            before['sponsorship'] == 'Unknown' or before['citizenship'] == 'Unknown'
        ):
            time.sleep(0.2)

    added = 0
    for c in confirmed:
        listing_type, season = classify_season(c['title'])
        # Prefer Simplify term metadata when present
        terms = c.get('terms') or []
        if terms:
            joined = ' '.join(terms).lower()
            if 'summer 2027' in joined:
                listing_type, season = 'summer', 'Summer 2027'
            elif 'fall 2026' in joined:
                listing_type, season = 'offcycle', 'Fall 2026'
            elif 'spring 2027' in joined:
                listing_type, season = 'offcycle', 'Spring 2027'
            elif 'co-op' in joined or 'coop' in joined:
                listing_type, season = 'offcycle', 'Co-op'
        role = sanitize_listing_role(c['company'], c['title'])
        education = infer_education(c['title'])
        degrees = c.get('degrees') or []
        if degrees:
            parts = []
            joined = ' '.join(d.lower() for d in degrees)
            if 'bachelor' in joined or 'undergrad' in joined:
                parts.append('Undergrad')
            if 'master' in joined:
                parts.append('Masters')
            if 'phd' in joined or 'doctor' in joined:
                parts.append('PhD')
            if parts:
                education = '; '.join(parts)
        sponsorship = c.get('sponsorship', 'Unknown')
        raw_sp = (c.get('sponsorship_raw') or '').lower()
        if raw_sp:
            if 'does not' in raw_sp or raw_sp in ('no', 'unavailable'):
                sponsorship = 'No — does NOT offer sponsorship'
            elif 'available' in raw_sp or raw_sp == 'yes':
                sponsorship = 'Yes — sponsorship available'
        entry = {
            'company': c['company'],
            'role': role,
            'location': normalize_location(c['location']),
            'type': listing_type,
            'season': season,
            'education': education,
            'url': c['url'],
            'sponsorship': sponsorship,
            'citizenship': c.get('citizenship', 'Unknown'),
            'date_added': today,
        }
        if add_listing(listings, entry):
            added += 1
            print(f'Added: {c["company"]} — {c["title"]}')

    if added:
        save_json(LISTINGS_FILE, listings)
        subprocess.run(['python3', '.github/scripts/rebuild_readme.py'], check=True)

    for c in candidates:
        seen[c['key']] = today

    save_json(CLASSIFICATIONS_FILE, classifications)
    save_json(SEEN_FILE, seen)
    if gemini_key:
        save_gemini_usage(gemini_usage)
    print(f'Done. Added {added} new listings.')


if __name__ == '__main__':
    main()
