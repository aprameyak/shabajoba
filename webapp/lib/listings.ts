import path from 'path';
import fs from 'fs';

export interface Listing {
  company: string;
  role: string;
  location: string;
  type: string;
  season: string;
  education: string;
  url: string;
  sponsorship: string;
  citizenship: string;
  date_added: string;
}

export interface ProcessedRow {
  companyDisplay: string;
  isGrouped: boolean;
  role: string;
  location: string;
  locations: string[];
  season: string;
  education: string;
  url: string;
  dateFormatted: string;
}

export interface ListingsData {
  listings: ProcessedRow[];
  total: number;
}

function getListings(): Listing[] {
  const filePath = path.resolve(process.cwd(), '..', 'listings.json');
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(raw) as Listing[];
}

function formatCompany(listing: Listing): string {
  let name = listing.company.trim();
  const sp = listing.sponsorship ?? '';
  const cit = listing.citizenship ?? '';
  if (sp.toLowerCase().includes('not') || sp.toLowerCase().includes('no —')) {
    name += ' 🛂';
  }
  if (cit.toLowerCase().includes('yes —')) {
    name += ' 🇺🇸';
  }
  return name;
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

function companySortKey(name: string): string {
  return name.replace(/[\u{1F000}-\u{1FFFF}\u2600-\u26FF\u2700-\u27BF]/gu, '').trim().toLowerCase();
}

function processTable(listings: Listing[]): ProcessedRow[] {
  const sorted = [...listings].sort((a, b) => {
    const da = new Date(a.date_added).getTime();
    const db = new Date(b.date_added).getTime();
    if (db !== da) return db - da;
    return companySortKey(a.company).localeCompare(companySortKey(b.company));
  });

  const rows: ProcessedRow[] = [];
  const groupTracker = new Map<string, boolean>();

  for (const entry of sorted) {
    const key = `${companySortKey(entry.company)}::${entry.date_added}`;
    const isGrouped = groupTracker.has(key);
    if (!isGrouped) groupTracker.set(key, true);

    const locations = entry.location
      .split(';')
      .map((l) => l.trim())
      .filter(Boolean);

    rows.push({
      companyDisplay: formatCompany(entry),
      isGrouped,
      role: entry.role.trim(),
      location: entry.location.trim(),
      locations,
      season: entry.season?.trim() ?? '',
      education: entry.education?.trim() ?? 'Undergrad',
      url: entry.url?.trim() ?? '',
      dateFormatted: formatDate(entry.date_added),
    });
  }

  return rows;
}

export function getAllListingsData(): ListingsData {
  const listings = getListings();
  const rows = processTable(listings);
  return {
    listings: rows,
    total: rows.length,
  };
}
