#!/usr/bin/env python3

import json
import re
import sys
from datetime import datetime
from pathlib import Path

LISTINGS_FILE = Path('listings.json')
README_FILE = Path('README.md')


def _company_sort_key(name):
    name = re.sub(r'[\U0001F000-\U0001FFFF\u2600-\u26FF\u2700-\u27BF]', '', name)
    return name.strip().lower()


def format_company(entry):
    name = entry['company'].strip()
    sponsorship = entry.get('sponsorship', '')
    citizenship = entry.get('citizenship', '')
    if 'not' in sponsorship.lower() or 'no —' in sponsorship.lower():
        name += ' 🛂'
    if 'yes —' in citizenship.lower():
        name += ' 🇺🇸'
    return name


def format_location(location):
    location = location.strip()
    if ';' not in location:
        return location
    parts = [p.strip() for p in location.split(';') if p.strip()]
    if len(parts) <= 1:
        return parts[0] if parts else location
    inner = '</br>'.join(parts)
    return f'<details><summary>**{len(parts)} locations**</summary>{inner}</details>'


def format_date(date_added):
    try:
        dt = datetime.strptime(date_added, '%Y-%m-%d')
        return dt.strftime('%b %d').replace(' 0', ' ')
    except Exception:
        return date_added


def apply_btn(url):
    if not url:
        return '🔒'
    return (
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">'
        f'<img src="https://i.imgur.com/u1KNU8z.png" width="118" alt="Apply">'
        f'</a>'
    )


def format_row(entry, company_col):
    role = entry['role'].strip()
    location = format_location(entry['location'])
    season = entry.get('season', 'Summer 2027').strip()
    education = entry.get('education', 'Undergrad').strip()
    url = entry.get('url', '').strip()
    date = format_date(entry['date_added'])
    btn = apply_btn(url)
    return f'| {company_col} | {role} | {location} | {season} | {education} | {btn} | {date} |'


def build_table(entries):
    def sort_key(e):
        try:
            dt = datetime.strptime(e['date_added'], '%Y-%m-%d')
        except Exception:
            dt = datetime.min
        return (-dt.timestamp(), _company_sort_key(e['company']))

    sorted_entries = sorted(entries, key=sort_key)
    rows = []
    group_tracker = {}

    for entry in sorted_entries:
        company_key = _company_sort_key(entry['company'])
        date_str = entry['date_added']
        group_key = (company_key, date_str)
        company_display = format_company(entry)

        if group_key in group_tracker:
            company_col = '↳'
        else:
            company_col = company_display
            group_tracker[group_key] = True

        rows.append(format_row(entry, company_col))

    return rows


def replace_table(content, marker, rows):
    start_marker = f'<!-- TABLE_START {marker} -->'
    end_marker = f'<!-- TABLE_END {marker} -->'
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    if start_idx == -1 or end_idx == -1:
        print(f'ERROR: Could not find markers for table: {marker}')
        sys.exit(1)

    after_start = content[start_idx:]
    sep_match = re.search(r'\| [-| :]+\|\n', after_start)
    if not sep_match:
        print(f'ERROR: Could not find separator row for table: {marker}')
        sys.exit(1)

    header_end = start_idx + sep_match.end()
    header = content[start_idx:header_end]
    footer = content[end_idx:]

    body = '\n'.join(rows) + '\n' if rows else ''
    return content[:start_idx] + header + body + footer


def main():
    if not LISTINGS_FILE.exists():
        print('ERROR: listings.json not found')
        sys.exit(1)
    if not README_FILE.exists():
        print('ERROR: README.md not found')
        sys.exit(1)

    with open(LISTINGS_FILE) as f:
        listings = json.load(f)

    print(f'Loaded {len(listings)} listings')

    with open(README_FILE, encoding='utf-8') as f:
        content = f.read()

    content = replace_table(content, 'listings', build_table(listings))

    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    print('README.md rebuilt successfully')


if __name__ == '__main__':
    main()
