#!/usr/bin/env python3

import json
import os
import re
import subprocess
from pathlib import Path
import requests

LISTINGS_FILE = Path('listings.json')

US_STATES = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI',
    'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX',
    'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
    'district of columbia': 'DC',
}

CA_PROVINCES = {
    'alberta': 'AB', 'british columbia': 'BC', 'manitoba': 'MB',
    'new brunswick': 'NB', 'newfoundland': 'NL', 'labrador': 'NL',
    'nova scotia': 'NS', 'northwest territories': 'NT', 'nunavut': 'NU',
    'ontario': 'ON', 'prince edward island': 'PE', 'quebec': 'QC',
    'saskatchewan': 'SK', 'yukon': 'YT',
}


def normalize_url(url):
    url = url.strip().split('?')[0]
    for param in ['utm_source', 'utm_medium', 'utm_campaign', 'source', 'ref']:
        url = re.sub(rf'[?&]{param}=[^&]*', '', url)
    return url.rstrip('/')


def parse_issue_body(body):
    fields = {}
    sections = re.split(r'###\s+', body)
    for section in sections:
        if not section.strip():
            continue
        lines = section.strip().split('\n')
        key = lines[0].strip()
        value = '\n'.join(lines[1:]).strip()
        if value.startswith('_No response_'):
            value = ''
        fields[key] = value
    return fields


def normalize_location(location_text):
    parts = [p.strip() for p in location_text.split(';')]
    normalized = []
    for part in parts:
        low = part.lower()
        if 'remote' in low:
            if 'canada' in low:
                normalized.append('Remote (Canada)')
            else:
                normalized.append('Remote (US)')
            continue
        matched = False
        for state_name, abbr in US_STATES.items():
            if state_name in low:
                city_match = re.match(r'^([^,]+)', part)
                city = city_match.group(1).strip() if city_match else part
                normalized.append(f'{city}, {abbr}')
                matched = True
                break
        if not matched:
            for prov_name, abbr in CA_PROVINCES.items():
                if prov_name in low:
                    city_match = re.match(r'^([^,]+)', part)
                    city = city_match.group(1).strip() if city_match else part
                    normalized.append(f'{city}, {abbr}')
                    matched = True
                    break
        if not matched:
            normalized.append(part)
    return '; '.join(normalized)


def classify_listing(listing_type_str, season_str):
    s = season_str.lower()
    if 'co-op' in s or 'coop' in s or 'co op' in s:
        return 'offcycle', season_str
    if 'fall' in s or 'spring' in s or 'winter' in s:
        return 'offcycle', season_str
    if 'summer 2027' in s:
        return 'summer', 'Summer 2027'
    return 'summer', season_str


def get_approved_issues(token, repo):
    issues = []
    page = 1
    while True:
        resp = requests.get(
            f'https://api.github.com/repos/{repo}/issues',
            headers={
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github+json',
            },
            params={'state': 'open', 'labels': 'approved', 'per_page': 100, 'page': page},
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        issues.extend(batch)
        page += 1
    return issues


def close_issue(token, repo, issue_number, comment):
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github+json',
    }
    requests.post(
        f'https://api.github.com/repos/{repo}/issues/{issue_number}/comments',
        headers=headers,
        json={'body': comment},
        timeout=15,
    )
    requests.patch(
        f'https://api.github.com/repos/{repo}/issues/{issue_number}',
        headers=headers,
        json={'state': 'closed'},
        timeout=15,
    )


def main():
    token = os.environ['GITHUB_TOKEN']
    repo = os.environ['GITHUB_REPOSITORY']

    with open(LISTINGS_FILE) as f:
        listings = json.load(f)

    existing_urls = {normalize_url(e.get('url', '')) for e in listings}

    issues = get_approved_issues(token, repo)
    print(f'Found {len(issues)} approved issues')

    added = 0
    import datetime
    today = datetime.date.today().isoformat()

    for issue in issues:
        body = issue.get('body', '')
        number = issue['number']
        fields = parse_issue_body(body)

        company = fields.get('Company Name', '').strip()
        role = fields.get('Role / Job Title', '').strip()
        listing_type_str = fields.get('Listing Type', 'Internship')
        season_str = fields.get('Season / Term', 'Summer 2027')
        location_raw = fields.get('Location', '').strip()
        sponsorship = fields.get('Visa Sponsorship?', 'Unknown').strip()
        citizenship = fields.get('U.S. Citizenship Required?', 'Unknown').strip()
        education = fields.get('Education Level', 'Undergrad').strip()
        apply_link = fields.get('Direct Application Link', '').strip()

        if not all([company, role, location_raw, apply_link]):
            print(f'Issue #{number}: missing required fields, skipping')
            continue

        norm_url = normalize_url(apply_link)
        if norm_url in existing_urls:
            print(f'Issue #{number}: duplicate URL, closing')
            close_issue(token, repo, number, 'This listing already exists in the repository.')
            continue

        location = normalize_location(location_raw)
        listing_type, season = classify_listing(listing_type_str, season_str)

        entry = {
            'company': company,
            'role': role,
            'location': location,
            'type': listing_type,
            'season': season,
            'education': education,
            'url': apply_link,
            'sponsorship': sponsorship,
            'citizenship': citizenship,
            'date_added': today,
        }

        listings.append(entry)
        existing_urls.add(norm_url)
        added += 1
        print(f'Added: {company} — {role}')

        close_issue(token, repo, number, f'Added **{company} — {role}** to the listings. Thank you!')

    if added:
        with open(LISTINGS_FILE, 'w') as f:
            json.dump(listings, f, indent=2)
            f.write('\n')
        subprocess.run(['python3', '.github/scripts/rebuild_readme.py'], check=True)
        print(f'Added {added} listings')
    else:
        print('No new listings added')


if __name__ == '__main__':
    main()
