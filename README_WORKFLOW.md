# 🗂️ Project Workflow & Deployment Guide

This document explains **how the CultFit MindLive Crawler, dataset, and React front-end work together** and how everything is automatically deployed to GitHub Pages.

---

## 1. High-Level Architecture

```
[CultFit API] ⇨ (Python crawler → JSON metadata) ⇨ [Repo]
                                            ↘                 ↘
                            (auto-generated README)          [React + Vite front-end]
                                                                 ↘
                                                    (static build) ⇨ GitHub Pages
```

1. **Crawler** (`cultfit_crawler.py`) scrapes CultFit MindLive content and saves:
   * `sections/*.json` – session metadata grouped by section.
   * `frontend/public/media_by_section.json` – single JSON consumed by the UI.
   * Root `README.md` – catalogue of all sessions with CDN streaming links.
2. **React Front-End** ( `/frontend` ) reads the JSON file at build-time and renders an SPA using Vite.
3. **GitHub Actions** automate both **weekly data refresh** and **continuous deployment** of the site to GitHub Pages.

---

## 2. Repository Layout (abridged)

| Path | Purpose |
|------|---------|
| `cultfit_crawler.py` | Main crawler script |
|(no media directory) | Content streams directly from cult.fit CDN |
| `sections/`, `hierarchical_content/` | Structured JSON metadata |
| `frontend/` | React + Vite codebase |
| `docs/` | Built site served by GitHub Pages (fallback if using "docs" mode) |
| `.github/workflows/` | CI/CD pipelines |

---

## 3. GitHub Pages Deployment Strategy

Two interchangeable options are supported:

1. **Pages via `docs/` folder (simple)**
   * The weekly workflow copies `frontend/dist` into `docs/` → changes land on `main` → Pages serves `/docs`.
2. **Pages via `gh-pages` branch (recommended)**
   * A dedicated `deploy_pages.yml` workflow builds the front-end and publishes the output artifact using `actions/deploy-pages`. No extra commits on `main`.
   * Repository settings: **Pages → Build & Deployment → Source: GitHub Actions**.

> The sample `deploy_pages.yml` provided in this repo follows option #2.

---

## 4. Automated Workflows

| File | Triggers | What it does |
|------|----------|--------------|
| `.github/workflows/update_readme.yml` | Every Sunday 03:00 UTC (cron) / manual | 🐍 Runs crawler → 📦 Builds front-end → ✍️ Updates `README.md` & pushes fresh data. |
| `.github/workflows/deploy_pages.yml` | Push to `main` affecting `frontend/**` or manual | 🏗️ Builds React app → 📤 Uploads artifact → 🚀 Deploys to GitHub Pages. |
| `.github/workflows/frontend_ci.yml` | PR / push touching `frontend/**` | ✅ Runs CI build to catch errors before merge. |

### Environment Variables / Secrets

* `CULTFIT_COOKIE_STRING` (optional) – supply a premium-account auth cookie to fetch paid packs. Store it in **Repository → Settings → Secrets → Actions**.

---

## 5. Development Flow

1. **Modify crawler** or **media scripts** → Commit → (optional) run locally.
2. **Update front-end** in `frontend/`.
3. When changes are pushed to `main`:
   * CI validates the build.
   * `deploy_pages.yml` publishes a new version automatically.
4. Every week the data refresh job lands new content and triggers another deploy.

---

## 6. Local Setup (macOS/Linux)

```bash
# 1. Clone & install Python deps
python -m pip install -r requirements.txt

# 2. Crawl (optional)
python cultfit_crawler.py

# 3. Run the dev server for the UI
cd frontend
npm ci
npm run dev
```

The dev server listens on <http://localhost:5173/>, automatically reloading on code changes.

---

## 7. Frequently Asked Questions

**Q: How big will the repo get over time?**  
Very small – we only store JSON metadata and the static front-end build. All audio/video is streamed from cult.fit CDN, so no large binaries bloat the repository.

**Q: Can I disable auto-updates?**  
Simply disable or delete `update_readme.yml` in the workflow tab.

**Q: I made a front-end change but the production site didn’t update.**  
Check that `deploy_pages.yml` ran successfully on your commit and that GitHub Pages isn’t returning an old cache (invalidate via the Pages settings if needed).

---

Happy hacking! 🙌 