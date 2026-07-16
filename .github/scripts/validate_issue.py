#!/usr/bin/env python3
"""Validate job listing issue submissions."""

import os
import re
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
ISSUE_BODY = os.environ.get('ISSUE_BODY', '')
ISSUE_NUMBER = os.environ.get('ISSUE_NUMBER', '')
REPO = os.environ.get('GITHUB_REPOSITORY', '')

REQUIRED_FIELDS = [
    'Company Name',
    'Role / Job Title',
    'Listing Type',
    'Season / Term',
    'Location',
    'Direct Application Link',
]

VALID_LISTING_TYPES = {'Internship', 'Co-op'}

US_STATE_ABBRS = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC',
}

CA_PROVINCE_ABBRS = {
    'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT',
}


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


def validate_location(location_text):
    parts = [p.strip() for p in location_text.split(';')]
    for part in parts:
        low = part.lower()
        if 'remote' in low:
            continue
        if re.match(r'^.+,\s*[A-Z]{2}$', part):
            abbr = part.split(',')[-1].strip()
            if abbr in US_STATE_ABBRS or abbr in CA_PROVINCE_ABBRS:
                continue
        return False
    return bool(parts)


def post_comment(message):
    if not GITHUB_TOKEN or not REPO or not ISSUE_NUMBER:
        print(message)
        return
    requests.post(
        f'https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}/comments',
        headers={
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github+json',
        },
        json={'body': message},
        timeout=15,
    )


def main():
    fields = parse_issue_body(ISSUE_BODY)
    errors = []

    for field in REQUIRED_FIELDS:
        if not fields.get(field, '').strip():
            errors.append(f'- Missing required field: **{field}**')

    listing_type = fields.get('Listing Type', '').strip()
    if listing_type and listing_type not in VALID_LISTING_TYPES:
        errors.append(
            f'- Invalid Listing Type: `{listing_type}`. '
            f'Must be one of: {", ".join(sorted(VALID_LISTING_TYPES))}'
        )

    location = fields.get('Location', '').strip()
    if location and not validate_location(location):
        errors.append(
            '- Invalid Location format. '
            'Use `City, ST` (e.g. `Austin, TX`), `Remote (US)`, or `Remote (Canada)`. '
            'Separate multiple locations with semicolons.'
        )

    apply_link = fields.get('Direct Application Link', '').strip()
    if apply_link and not apply_link.startswith('http'):
        errors.append('- Application link must start with `http`.')

    if errors:
        comment = (
            'Thank you for your submission! There are a few issues to fix:\n\n'
            + '\n'.join(errors)
            + '\n\nPlease edit your issue to correct these and resubmit.'
        )
        post_comment(comment)
        print('Validation failed:')
        for e in errors:
            print(e)
    else:
        print('Validation passed.')


if __name__ == '__main__':
    main()
