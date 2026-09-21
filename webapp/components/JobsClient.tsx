'use client';

import { useState, useMemo } from 'react';
import type { ListingsData, ProcessedRow } from '@/lib/listings';

type TabKey = 'all' | 'summer' | 'offcycle';

function ApplyButton({ url }: { url: string }) {
  if (!url) {
    return <span title="Position closed">🔒</span>;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 transition-colors whitespace-nowrap"
    >
      Apply
    </a>
  );
}

function LocationCell({ locations }: { locations: string[] }) {
  const [open, setOpen] = useState(false);
  if (locations.length <= 1) {
    return <span>{locations[0] ?? ''}</span>;
  }
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-blue-600 underline decoration-dotted text-left hover:text-blue-800"
      >
        {locations.length} locations
      </button>
      {open && (
        <div className="absolute z-10 mt-1 w-56 rounded border border-gray-200 bg-white shadow-lg text-sm">
          <ul className="divide-y divide-gray-100">
            {locations.map((loc) => (
              <li key={loc} className="px-3 py-1.5">
                {loc}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function JobTable({
  rows,
  search,
  seasonFilter,
  openOnly,
  region,
  education,
}: {
  rows: ProcessedRow[];
  search: string;
  seasonFilter: string;
  openOnly: boolean;
  region: string;
  education: string;
}) {
  const displayRows = useMemo(() => {
    const resolved: (ProcessedRow & { resolvedCompany: string })[] = [];
    let lastCompany = '';
    for (const row of rows) {
      const resolvedCompany = row.isGrouped ? lastCompany : row.companyDisplay;
      if (!row.isGrouped) lastCompany = row.companyDisplay;
      resolved.push({ ...row, resolvedCompany });
    }

    const filtering = !!(search || seasonFilter || openOnly || region || education);

    return resolved.filter((row) => {
      if (openOnly && !row.url) return false;
      if (seasonFilter && row.season !== seasonFilter) return false;
      if (region === 'US' && row.region !== 'US' && row.region !== 'Mixed' && row.region !== 'Remote') {
        return false;
      }
      if (region === 'Canada' && row.region !== 'Canada' && row.region !== 'Mixed') {
        return false;
      }
      if (education && !row.education.toLowerCase().includes(education.toLowerCase())) {
        return false;
      }
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        row.resolvedCompany.toLowerCase().includes(q) ||
        row.role.toLowerCase().includes(q) ||
        row.location.toLowerCase().includes(q) ||
        row.season.toLowerCase().includes(q) ||
        row.education.toLowerCase().includes(q)
      );
    }).map((row) => ({
      ...row,
      // when filtering, always show full company name
      _showFull: filtering,
    }));
  }, [rows, search, seasonFilter, openOnly, region, education]);

  if (displayRows.length === 0) {
    return (
      <div className="py-12 text-center text-gray-500">
        No listings match your filters. Try clearing search or switching tabs.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <div className="px-4 py-2 text-xs text-gray-500 border-b border-gray-100 bg-gray-50">
        Showing <span className="font-medium text-gray-700">{displayRows.length}</span> roles
      </div>
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
            <th className="px-4 py-3 w-44">Company</th>
            <th className="px-4 py-3">Role</th>
            <th className="px-4 py-3 w-40">Location</th>
            <th className="px-4 py-3 w-28">Season</th>
            <th className="px-4 py-3 w-28">Education</th>
            <th className="px-4 py-3 w-20">Apply</th>
            <th className="px-4 py-3 w-20">Added</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {displayRows.map((row, i) => {
            const filtering = row._showFull;
            const displayCompany = filtering ? row.resolvedCompany : row.companyDisplay;
            const isContinuation = !filtering && row.isGrouped;

            return (
              <tr
                key={`${row.resolvedCompany}-${row.role}-${row.url}-${i}`}
                className="hover:bg-blue-50 transition-colors"
              >
                <td className="px-4 py-2.5 align-top font-medium text-gray-900">
                  {isContinuation ? (
                    <span className="text-gray-400 select-none">↳</span>
                  ) : (
                    displayCompany
                  )}
                </td>
                <td className="px-4 py-2.5 align-top text-gray-700">{row.role}</td>
                <td className="px-4 py-2.5 align-top text-gray-600">
                  <LocationCell locations={row.locations} />
                </td>
                <td className="px-4 py-2.5 align-top text-gray-600 whitespace-nowrap">
                  {row.season}
                </td>
                <td className="px-4 py-2.5 align-top text-gray-600">{row.education}</td>
                <td className="px-4 py-2.5 align-top">
                  <ApplyButton url={row.url} />
                </td>
                <td className="px-4 py-2.5 align-top text-gray-500 whitespace-nowrap">
                  {row.dateFormatted}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const SEASONS = [
  'Summer 2027',
  'Fall 2026',
  'Fall 2027',
  'Winter 2027',
  'Spring 2027',
  'Co-op',
];

const TABS: { key: TabKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'summer', label: 'Summer 2027' },
  { key: 'offcycle', label: 'Off-Cycle & Co-ops' },
];

export default function JobsClient({ data }: { data: ListingsData }) {
  const [search, setSearch] = useState('');
  const [seasonFilter, setSeasonFilter] = useState('');
  const [openOnly, setOpenOnly] = useState(true);
  const [region, setRegion] = useState('');
  const [education, setEducation] = useState('');
  const [tab, setTab] = useState<TabKey>('all');

  const rows =
    tab === 'summer' ? data.summer : tab === 'offcycle' ? data.offcycle : data.listings;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-blue-600">
                Premier EE list · Updated hourly · US &amp; Canada
              </p>
              <h1 className="mt-1 text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
                2027 EE Internships &amp; Co-ops
              </h1>
              <p className="mt-2 text-sm text-gray-600 max-w-2xl">
                Electrical engineering only — hardware, RF, analog, power, VLSI/ASIC, FPGA,
                PCB, test, photonics, and avionics. No software-only roles.
              </p>
            </div>
            <a
              href="https://github.com/aprameyak/shabajoba"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="View on GitHub"
              className="text-gray-400 hover:text-gray-700 transition-colors mt-1 shrink-0"
            >
              <svg height="22" width="22" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
              </svg>
            </a>
          </div>

          <div className="mt-5 flex flex-wrap gap-3 text-sm">
            <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2">
              <span className="font-semibold text-blue-800">{data.open}</span>
              <span className="text-blue-700"> open</span>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-gray-600">
              <span className="font-semibold text-gray-800">{data.summerOpen}</span> Summer 2027
            </div>
            <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-gray-600">
              <span className="font-semibold text-gray-800">{data.offcycleOpen}</span> Off-cycle / Co-op
            </div>
            <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-gray-500">
              {data.total} total tracked
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <div className="mb-4 flex flex-wrap gap-2 border-b border-gray-200">
          {TABS.map((t) => {
            const count =
              t.key === 'summer'
                ? data.summer.length
                : t.key === 'offcycle'
                  ? data.offcycle.length
                  : data.total;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => {
                  setTab(t.key);
                  setSeasonFilter('');
                }}
                className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  active
                    ? 'border-blue-600 text-blue-700'
                    : 'border-transparent text-gray-500 hover:text-gray-800'
                }`}
              >
                {t.label}
                <span className="ml-1.5 text-xs text-gray-400">{count}</span>
              </button>
            );
          })}
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <input
            type="search"
            placeholder="Search company, role, location, subfield..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full max-w-md rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm shadow-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <select
            value={seasonFilter}
            onChange={(e) => setSeasonFilter(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All seasons</option>
            {SEASONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">US &amp; Canada</option>
            <option value="US">United States</option>
            <option value="Canada">Canada</option>
          </select>
          <select
            value={education}
            onChange={(e) => setEducation(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All education</option>
            <option value="Undergrad">Undergrad</option>
            <option value="Masters">Masters</option>
            <option value="PhD">PhD</option>
          </select>
          <label className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm cursor-pointer select-none">
            <input
              type="checkbox"
              checked={openOnly}
              onChange={(e) => setOpenOnly(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Open only
          </label>
          <div className="relative group">
            <button
              className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-300 text-xs text-gray-400 hover:border-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Legend"
            >
              ?
            </button>
            <div className="pointer-events-none absolute left-0 top-10 z-20 w-64 rounded-lg border border-gray-200 bg-white p-3 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity text-xs text-gray-600">
              <p className="mb-2 font-semibold text-gray-800">Legend</p>
              <ul className="space-y-1.5">
                <li><span className="font-medium">🛂</span> — visa sponsorship not offered</li>
                <li><span className="font-medium">🇺🇸</span> — US citizenship required</li>
                <li><span className="font-medium">🔒</span> — position closed</li>
                <li><span className="font-medium">↳</span> — additional role at same company</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
          <JobTable
            rows={rows}
            search={search}
            seasonFilter={seasonFilter}
            openOnly={openOnly}
            region={region}
            education={education}
          />
        </div>

        <p className="mt-4 text-center text-xs text-gray-400">
          EE internships &amp; co-ops in the US and Canada · scraped hourly from company career pages ·{' '}
          <a
            href="https://github.com/aprameyak/shabajoba"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-gray-600"
          >
            star on GitHub
          </a>
          {' '}to help others find it
        </p>
      </main>
    </div>
  );
}
