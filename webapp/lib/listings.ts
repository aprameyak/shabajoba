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
  type: string;
  sponsorship: string;
  citizenship: string;
  region: 'US' | 'Canada' | 'Remote' | 'Mixed';
}

export interface ListingsData {
  listings: ProcessedRow[];
  summer: ProcessedRow[];
  offcycle: ProcessedRow[];
  total: number;
  open: number;
  summerOpen: number;
  offcycleOpen: number;
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

const CA_PROVINCES = new Set([
  'ab', 'bc', 'mb', 'nb', 'nl', 'ns', 'nt', 'nu', 'on', 'pe', 'qc', 'sk', 'yt',
]);

function detectRegion(location: string): ProcessedRow['region'] {
  const locs = location.split(';').map((l) => l.trim()).filter(Boolean);
  if (locs.length === 0) return 'US';
  let hasUS = false;
  let hasCA = false;
  let hasRemote = false;
  for (const loc of locs) {
    const lower = loc.toLowerCase();
    if (lower.startsWith('remote')) {
      hasRemote = true;
      if (lower.includes('canada')) hasCA = true;
      else hasUS = true;
      continue;
    }
    const m = loc.match(/,\s*([A-Z]{2})$/);
    if (m) {
      if (CA_PROVINCES.has(m[1].toLowerCase())) hasCA = true;
      else hasUS = true;
    }
  }
  if (hasUS && hasCA) return 'Mixed';
  if (hasCA && !hasUS) return 'Canada';
  if (hasRemote && !hasUS && !hasCA) return 'Remote';
  return 'US';
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
      type: entry.type?.trim() ?? 'summer',
      sponsorship: entry.sponsorship ?? 'Unknown',
      citizenship: entry.citizenship ?? 'Unknown',
      region: detectRegion(entry.location),
    });
  }

  return rows;
}

export function getAllListingsData(): ListingsData {
  const listings = getListings();
  const rows = processTable(listings);
  const summer = rows.filter((r) => r.type === 'summer');
  const offcycle = rows.filter((r) => r.type === 'offcycle');
  return {
    listings: rows,
    summer,
    offcycle,
    total: rows.length,
    open: rows.filter((r) => r.url).length,
    summerOpen: summer.filter((r) => r.url).length,
    offcycleOpen: offcycle.filter((r) => r.url).length,
  };
}
