# Contributing to Shabajoba (2027 EE Jobs)

Thank you for helping keep this the best EE internship & co-op list for students in the US and Canada.

---

## Ways to Contribute

| Action | How |
|--------|-----|
| Add a new job listing | Submit an issue or open a pull request |
| Update an application status | Open a PR marking the role 🔒 |
| Fix a broken link | Open a PR with the corrected URL |
| Remove a closed/expired listing | Open a PR deleting the entry |

---

## Adding a Job Listing

### Canonical source: `listings.json`

All listings live in `listings.json`. The README table is **always rebuilt** from that file — never edit table rows in the README directly.

After editing `listings.json`, rebuild the README:

```bash
python3 .github/scripts/rebuild_readme.py
```

### Required fields

| Field | Description |
|-------|-------------|
| `company` | Plain company name (no URL, no emoji flags) |
| `role` | Exact job title — no season/year in the title (e.g. not `Summer 2027`) |
| `location` | `City, ST` or `City, Province` (e.g. `San Jose, CA`, `Toronto, ON`). Multiple: semicolon-separated. Remote: `Remote (US)` or `Remote (Canada)` |
| `type` | `summer` or `offcycle` |
| `season` | e.g. `Summer 2027`, `Fall 2026`, `Co-op`, or `Spring 2027` |
| `education` | `Undergrad`, `Masters`, `PhD`, or semicolon-separated combinations |
| `url` | Direct application link. Use `""` when closed (README shows 🔒) |
| `sponsorship` | `Yes — sponsorship available`, `No — does NOT offer sponsorship`, or `Unknown` |
| `citizenship` | `Yes — U.S. citizenship required`, `No`, or `Unknown` |
| `date_added` | `YYYY-MM-DD` — set once when first added; do not change on reclassify |

### Table classification

| `type` | When to use |
|--------|-------------|
| `summer` | Summer 2027 internships only |
| `offcycle` | Fall/Spring/Winter internships, co-ops, non-Summer-2027 terms |

### Sponsorship flags in README

- 🛂 = company does not offer visa sponsorship
- 🇺🇸 = U.S. citizenship required

These are derived from `sponsorship` and `citizenship` when the README is rebuilt.

### Marking a role as closed

Set `"url": ""` in `listings.json`, then rebuild the README.

---

## Scope

**In scope:** electrical engineering internships and co-ops in the **United States, Canada, or Remote (US/Canada)** — including hardware, power systems, RF/analog/mixed-signal, embedded hardware, VLSI/ASIC/FPGA, PCB, test/validation, signal processing, photonics, and EE-focused avionics/systems.

**Out of scope:** pure software engineering, data science/ML (unless silicon/ASIC tooling is clearly EE), business/finance, marketing, HR, mechanical-only roles, manufacturing operations, full-time / new-grad / entry-level roles, and positions outside the US & Canada.

---

## Submitting a Pull Request

1. Fork this repository.
2. Create a branch from `main`:
   ```bash
   git checkout -b add/company-name-role
   ```
3. Edit `listings.json` and run `python3 .github/scripts/rebuild_readme.py`.
4. Commit your changes.
5. Open a pull request against `main`.

---

## Opening an Issue

Prefer not to submit a PR? [Open an issue](../../issues/new/choose) with the Add Job template. A maintainer can approve it with the `approved` label.

---

Thank you for contributing.
