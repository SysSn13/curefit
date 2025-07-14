# CultFit MindLive Crawler & Player 🚀

[![GitHub Pages](https://img.shields.io/badge/Live%20Demo-curefit-blue?logo=github)](https://syssn13.github.io/curefit)

> Browse & stream every CultFit / CureFit MindLive session straight from your browser – **no downloads required**.

---

## What’s Inside?

| Folder | Purpose |
| ------ | ------- |
| `cultfit_crawler.py` | Python 3.11 crawler that indexes every MindLive section and produces lightweight JSON metadata. |
| `data/` | Cached JSON produced by the crawler (packs, sessions, CDN URLs). |
| `frontend/` | React + Tailwind web app served via GitHub Pages. |

---

## Quick Start

1. **Clone & install dependencies**
   ```bash
   git clone https://github.com/syssn13/cultfit-crawler.git
   cd cultfit-crawler
   pip install -r requirements.txt
   ```
2. **Run the crawler (optional)** – skips network requests if cache already exists.
   ```bash
   python cultfit_crawler.py
   ```
3. **Launch the UI locally**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

Or just head to **[syssn13.github.io/curefit](https://syssn13.github.io/curefit)** and start exploring! ✨

---

## Automation

A GitHub Actions workflow re-crawls the site every Sunday and automatically commits any updates to `data/` so the UI is always fresh.

---

## Disclaimer 📜

*This project is **NOT** affiliated with CultFit/CureFit.* All trademarks, logos, names, audio and video content remain the property of their respective owners. This repository stores **only** publicly available metadata and CDN URLs; **no** media is downloaded or redistributed.

---

### Happy mindfulness! 🧘‍♀️ 