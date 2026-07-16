# Contributing to 2027 EE Jobs

Thank you for helping keep this list accurate and up to date!

---

## Ways to Contribute

| Action | How |
|--------|-----|
| Add a new job listing | Submit an issue or open a pull request |
| Update an application status | Open a PR marking the role 🔒 |
| Fix a broken link | Open a PR with the corrected URL |
| Remove a closed/expired listing | Open a PR deleting the row |

---

## Adding a Job Listing

### Canonical source: `listings.json`

All listings live in `listings.json`. The README tables are **always rebuilt** from that file — never edit table rows in the README directly.

After editing `listings.json`, rebuild the README:

```bash
python3 .github/scripts/rebuild_readme.py
```

### Required fields

Each entry in `listings.json` must include:

| Field | Description |
|-------|-------------|
| `company` | Plain company name (no URL) |
| `role` | Exact job title |
| `location` | `City, ST` or `City, Province` (e.g. `San Francisco, CA`, `Toronto, ON`). Multiple: semicolon-separated (`New York, NY; Chicago, IL`). Remote: `Remote (US)` or `Remote (Canada)` |
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

These are derived from `sponsorship` and `citizenship` fields when the README is rebuilt.

### Marking a role as closed

Set `"url": ""` in `listings.json`, then rebuild the README. The Apply button becomes 🔒.

---

## Scope

This repository is **exclusively for electrical engineering internships and co-ops** in the **United States, Canada, or Remote** (US/Canada).

In scope: electrical engineering, hardware engineering, power systems, RF/analog/mixed-signal design, embedded systems hardware, VLSI/ASIC design, PCB design, test engineering, systems engineering (EE-focused), signal processing, photonics.

Out of scope: pure software engineering, data science, business/finance, marketing, HR, mechanical engineering (unless dual EE/ME), manufacturing operations roles.

---

## Submitting a Pull Request

1. **Fork** this repository.
2. **Create a branch** from `main`:
   ```bash
   git checkout -b add/company-name-role
   ```
3. **Edit `listings.json`** and run `python3 .github/scripts/rebuild_readme.py`.
4. **Commit** your changes.
5. **Open a pull request** against `main`.

---

## Opening an Issue

If you prefer not to submit a PR, [open an issue](../../issues/new/choose) using the Add Job template. A maintainer can approve it with the `approved` label, which triggers the automated add workflow.

---

Thank you for contributing!
