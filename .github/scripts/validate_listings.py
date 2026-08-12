#!/usr/bin/env python3
"""
Validate listings.json for the shabajaba EE internship repo.
Exits 0 if clean, 1 if violations are found.
"""

import json
import re
import sys
from pathlib import Path

LISTINGS_FILE = Path('listings.json')

VALID_EDUCATION = {'Undergrad', 'Masters', 'PhD',
                   'Undergrad; Masters', 'Undergrad; PhD', 'Masters; PhD',
                   'Undergrad; Masters; PhD'}

VALID_TYPES = {'summer', 'offcycle'}

VALID_SUMMER_SEASON = 'Summer 2027'

OFFCYCLE_SEASONS = {
    'Co-op', 'Fall 2027', 'Spring 2027', 'Winter 2027',
    'Fall 2026', 'Spring 2026', 'Winter 2026', 'Summer 2026',
}

VALID_SPONSORSHIP_PREFIXES = ('unknown', 'no —', 'yes —')

COMPANY_EMOJI = re.compile(r'[🛂🇺🇸]')

LOCATION_OK = re.compile(r',\s*[A-Z]{2}$|Remote\s*\(', re.I)

SEASON_IN_ROLE = re.compile(
    r'(^|[\s\-])(Summer|Fall|Spring|Winter)\s+20\d\d(\s|$|\)|\,)', re.I
)
YEAR_IN_ROLE = re.compile(r'(^20\d\d\s|\s20\d\d$)')
LOCATION_ANNOTATION_IN_ROLE = re.compile(
    r',?\s*(Onsite|On-site|Remote|Hybrid)$', re.I
)
COUNTRY_IN_LOCATION = re.compile(r'United States|Canada(?!\))', re.I)

LINKEDIN_TRACKING = re.compile(r'linkedin\.com.*\?(?!utm_source=aprameyak)')
INTERNAL_API_URL = re.compile(r'api\.smartrecruiters|/v1/candidates|/v1/')


def validate_entry(entry):
    violations = []
    company = entry.get('company', '')
    role = entry.get('role', '')
    location = entry.get('location', '')
    table = entry.get('type', '')
    season = entry.get('season', '')
    education = entry.get('education', '')
    sponsorship = entry.get('sponsorship', '')
    citizenship = entry.get('citizenship', '')
    url = entry.get('url', '')

    # Required fields
    for field in ['company', 'role', 'location', 'type', 'season', 'education',
                  'sponsorship', 'citizenship', 'date_added']:
        if field not in entry:
            violations.append(f'missing required field: {field}')

    # Education
    if education and education not in VALID_EDUCATION:
        violations.append(f'invalid education value: {education!r}')

    # Type
    if table and table not in VALID_TYPES:
        violations.append(f'invalid type: {table!r}')

    # Season / type consistency
    if table == 'summer' and season != VALID_SUMMER_SEASON:
        violations.append(f'summer table but season={season!r}')
    if table == 'offcycle' and not season.strip():
        violations.append('offcycle entry missing season value')
    if table == 'offcycle' and season and season not in OFFCYCLE_SEASONS:
        violations.append(f'offcycle but unrecognized season={season!r}')

    # Sponsorship / citizenship format
    sp = sponsorship.lower()
    if sp and not any(sp.startswith(p) for p in VALID_SPONSORSHIP_PREFIXES):
        violations.append(f'non-standard sponsorship value: {sponsorship!r}')
    cit = citizenship.lower()
    if cit and cit not in ('no', 'unknown') and not cit.startswith('yes —'):
        violations.append(f'non-standard citizenship value: {citizenship!r}')

    # Company emoji
    if COMPANY_EMOJI.search(company):
        violations.append('emoji in company field (flags come from sponsorship/citizenship fields)')

    # Role cleanliness
    if '_' in role:
        violations.append('underscore in role title')
    if SEASON_IN_ROLE.search(role):
        violations.append('season/year annotation in role title')
    if YEAR_IN_ROLE.search(role):
        violations.append('year annotation in role title')
    if LOCATION_ANNOTATION_IN_ROLE.search(role):
        violations.append('location annotation in role title')
    if company.lower() in role.lower():
        violations.append('company name appears in role title')

    # Location format (check each semicolon-separated segment)
    if url:  # only check live listings
        for seg in location.split(';'):
            seg = seg.strip()
            if not seg:
                continue
            if not LOCATION_OK.search(seg):
                violations.append(f'bad location format: {seg!r}')
                break
        if COUNTRY_IN_LOCATION.search(location):
            violations.append('country name in location field')

    # URL issues
    if url:
        if INTERNAL_API_URL.search(url):
            violations.append('internal API URL')
        if 'linkedin.com' in url and '?' in url:
            query = url.split('?', 1)[1]
            if query != 'utm_source=aprameyak':
                violations.append(f'LinkedIn URL with extra tracking params: {query!r}')

    return [(company, role, v) for v in violations]


def validate_duplicate_urls(listings):
    seen = {}
    violations = []
    for entry in listings:
        url = entry.get('url', '').strip()
        if not url:
            continue
        norm = url.split('?')[0].lower().rstrip('/')
        if norm in seen:
            other = seen[norm]
            violations.append((
                entry.get('company', ''),
                entry.get('role', ''),
                f'duplicate URL also used by {other.get("company")}: {other.get("role")!r}',
            ))
        else:
            seen[norm] = entry
    return violations


def main():
    if not LISTINGS_FILE.exists():
        print(f'{LISTINGS_FILE} not found')
        sys.exit(1)

    with open(LISTINGS_FILE) as f:
        listings = json.load(f)

    all_violations = []
    for entry in listings:
        all_violations.extend(validate_entry(entry))
    all_violations.extend(validate_duplicate_urls(listings))

    print(f'Validated {len(listings)} listing(s)')
    if all_violations:
        print(f'Found {len(all_violations)} violation(s):')
        for company, role, reason in all_violations:
            print(f'  - {company}: {role!r} — {reason}')
        sys.exit(1)

    print('All listings pass constitution checks')
    sys.exit(0)


if __name__ == '__main__':
    main()
