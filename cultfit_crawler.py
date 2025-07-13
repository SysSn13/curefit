#!/usr/bin/env python3
"""
CultFit MindLive ⭐️ All-in-One Crawler
======================================

• Discovers every MindLive section from https://www.cult.fit/athome/MindLive
• Extracts *all* packs & session-level media (audio/video) from each section
• Streams content directly from the cult.fit CDN – **no media is downloaded or stored locally**.
• Generates a GitHub-friendly `README.md` that links straight to CDN media so sessions can be played instantly.

Running the script twice will reuse the cached JSON metadata; no unnecessary network calls are made.

Usage
-----
# Crawl & build README (default)
$ python3 cultfit_crawler.py

# Skip crawling and reuse cached JSON (fast rebuild)
$ python3 cultfit_crawler.py --no-crawl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import aiofiles
import aiohttp
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

###############################################################################
# Helper / utility functions
###############################################################################

def sanitize(text: str, max_len: int = 80) -> str:
    """Return a filesystem-safe slug."""
    text = text.strip().replace("\u200d", "")  # remove zero-width joiners
    text = re.sub(r"[<>:\\/\|\?\*]", "_", text)  # illegal fs chars
    text = re.sub(r"\s+", "_", text)  # collapse whitespace to _
    text = re.sub(r"_+", "_", text)  # collapse multiple _
    return text.strip("._")[:max_len] or "untitled"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

###############################################################################
# Core crawler class
###############################################################################

class CultFitCrawler:
    BASE_URL = "https://www.cult.fit"
    MAIN_MINDLIVE_URL = "https://www.cult.fit/athome/MindLive"

    def __init__(
        self,
        out_root: Path = Path("media"),
        data_root: Path = Path("data"),
        manifest_file: Path = Path("media/download_manifest.json"),
        max_concurrent: int = 8,
        delay_between_requests: float = 0.25,
    ) -> None:
        self.out_root = out_root
        self.data_root = data_root
        self.manifest_file = manifest_file
        self.max_concurrent = max_concurrent
        self.delay = delay_between_requests

        # flag to avoid spamming login warnings
        self._warned_login_required = False

        # In-memory stores
        self.sections: List[Dict[str, str]] = []
        self.media_items: List[Dict[str, Any]] = []
        self.media_by_section: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # network session
        self.session = requests.Session()
        self.session.headers.update(
            {
                "user-agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self._setup_session_retries()
        self._attach_cookie_header()

        # Prepare folders
        ensure_dir(self.out_root)
        ensure_dir(self.data_root)
        ensure_dir(self.manifest_file.parent)

        # Manifest cache (url -> {status, path})
        if self.manifest_file.exists():
            self.manifest: Dict[str, Dict[str, str]] = json.loads(self.manifest_file.read_text())
        else:
            self.manifest = {}

    def _setup_session_retries(self) -> None:
        """Attach a Retry-enabled adapter so transient network hiccups are retried automatically."""
        retry = Retry(
            total=5,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # ------------------------------------------------------------------
    # Optional authentication via .env cookies
    # ------------------------------------------------------------------

    COOKIE_ENV_MAP = {
        "CULTFIT_AT_COOKIE": "at",
        "CULTFIT_FBP_COOKIE": "_fbp",
        "CULTFIT_GA_COOKIE": "_ga",
        "CULTFIT_GA_V0XZM8114H_COOKIE": "_ga_V0XZM8114H",
        "CULTFIT_GCL_AU_COOKIE": "_gcl_au",
        "CULTFIT_GID_COOKIE": "_gid",
        "CULTFIT_S_COOKIE": "s",
        "CULTFIT_DEVICEID_COOKIE": "deviceId",
        "CULTFIT_ST_COOKIE": "st",
        "CULTFIT_G_ENABLED_IDPS_COOKIE": "G_ENABLED_IDPS",
        # add more mappings here if needed
    }

    def _attach_cookie_header(self) -> None:
        """Load .env and build Cookie header if values are present."""
        load_dotenv(override=False)

        cookie_parts = []
        for env_var, cookie_name in self.COOKIE_ENV_MAP.items():
            val = os.getenv(env_var, "").strip()
            if val and val.lower() != "none" and val != "your_at_cookie_value_here":
                cookie_parts.append(f"{cookie_name}={val}")

        # Also allow a pre-built cookie string
        manual_cookie = os.getenv("CULTFIT_COOKIE_STRING", "").strip()
        if manual_cookie:
            cookie_parts.append(manual_cookie)

        if cookie_parts:
            cookie_header = "; ".join(cookie_parts)
            self.session.headers["Cookie"] = cookie_header
            print("🔑 Using authentication cookies from .env (some content may require login).")
        else:
            print("🔓 No auth cookies found – running in public mode.")

    # ---------------------------------------------------------------------
    # Discovery helpers
    # ---------------------------------------------------------------------

    def discover_sections(self) -> List[Dict[str, str]]:
        """Find all /live/mindfulness/* section links on main MindLive page."""
        print("🔍 Discovering MindLive sections …", end=" ")
        try:
            resp = self.session.get(self.MAIN_MINDLIVE_URL, timeout=(10, 20))
            resp.raise_for_status()
        except Exception as e:
            print(f"❌  {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        sections: List[Dict[str, str]] = []

        for a in soup.select("a[href*='/live/mindfulness/']"):
            href = a.get("href") or ""
            full_url = urljoin(self.BASE_URL, str(href))
            # Derive a readable name (part after /mindfulness/ or link text)
            name_from_url = str(href).split("/live/mindfulness/")[-1].split("/")[0]
            section_name = sanitize(name_from_url.replace("-", " ").title())
            sections.append({"name": section_name, "url": full_url})

        # De-duplicate by url
        uniq = {s["url"]: s for s in sections}
        self.sections = list(uniq.values())
        print(f"found {len(self.sections)} sections.")
        return self.sections

    # ---------------------------------------------------------------------
    # Extraction helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _extract_preloaded_state(html: str) -> Optional[Dict[str, Any]]:
        """Robustly locate and parse the window.__PRELOADED_STATE__ object.

        Uses brace-counting so it works even if the JSON blob contains nested
        braces or no trailing semicolon.
        """
        soup = BeautifulSoup(html, "html.parser")

        for script in soup.find_all("script"):
            stext = getattr(script, "string", None)
            if not stext or "__PRELOADED_STATE__" not in stext:
                continue

            # Locate the beginning of the JSON object
            start_match = re.search(r"window\.__PRELOADED_STATE__\s*=\s*{", stext)
            if not start_match:
                continue

            idx = start_match.end() - 1  # points to the first '{'
            brace_count = 0
            end_idx = None

            for pos in range(idx, len(stext)):
                char = stext[pos]
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = pos + 1  # include this closing brace
                        break

            if end_idx is None:
                continue  # malformed

            json_str = stext[idx:end_idx]
            json_str = re.sub(r"undefined", "null", json_str)

            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Give up and try next script tag
                continue

        return None

    @staticmethod
    def _parse_curefit_url(cure_url: str) -> Dict[str, str]:
        if not (isinstance(cure_url, str) and cure_url.startswith("curefit://")):
            return {}
        _, query = cure_url.split("?", 1) if "?" in cure_url else (cure_url, "")
        params = parse_qs(query)
        info: Dict[str, str] = {}
        if "absoluteAudioUrl" in params:
            info["media_url"] = unquote(params["absoluteAudioUrl"][0])
            info["media_type"] = "audio"
        elif "absoluteVideoUrl" in params:
            info["media_url"] = unquote(params["absoluteVideoUrl"][0])
            info["media_type"] = "video"
        if "title" in params:
            info["session_title"] = params["title"][0]
        if "packId" in params:
            info["pack_id"] = params["packId"][0]
        if "contentId" in params:
            info["content_id"] = params["contentId"][0]
        return info

    def _build_local_path(self, section: str, pack: str, session_title: Optional[str], url: str) -> Path:
        ext = os.path.splitext(urlparse(url).path)[1] or (".mp3" if url.endswith("audio") else ".mp4")
        fname = sanitize(session_title or "session") + ext
        return self.out_root / sanitize(section) / sanitize(pack) / fname

    def _extract_media_from_item(
        self, item: Dict[str, Any], section: str, pack_title: str, pack_desc: str
    ) -> List[Dict[str, Any]]:
        media_items: List[Dict[str, Any]] = []
        sources = []
        if "packIntroAction" in item:
            sources.append((item["packIntroAction"], "Intro"))
        if "playAction" in item:
            sources.append((item["playAction"], "Main"))
        # deeper sessions under content (could be list of dicts OR a dict)
        content_field = item.get("content")
        if isinstance(content_field, list):
            for idx, content in enumerate(content_field):
                # case 1: nested playAction url (same format as top-level)
                if isinstance(content, dict) and "playAction" in content:
                    sources.append((content["playAction"], content.get("title", f"Session {idx+1}")))
                # case 2: direct downloadUrl / absoluteUrl (no curefit:// wrapper)
                elif isinstance(content, dict) and (
                    content.get("downloadUrl") or content.get("absoluteUrl") or content.get("URL")
                ):
                    media_url = (
                        content.get("downloadUrl")
                        or content.get("absoluteUrl")
                        or content.get("URL")
                    )
                    media_type = "audio" if media_url and media_url.endswith(".mp3") else "video"
                    session_title = content.get("title", f"Session {idx+1}")
                    if isinstance(media_url, str):
                        local_path = self._build_local_path(section, pack_title, session_title, media_url)
                    else:
                        continue
                    media_items.append(
                        {
                            "section": section,
                            "pack": pack_title,
                            "pack_description": pack_desc,
                            "session_title": session_title,
                            "media_type": media_type,
                            "cdn_url": media_url,
                            "local_path": str(local_path),
                        }
                    )
        elif isinstance(content_field, dict):
            # Single dict with direct URL (common in some packs)
            media_url = (
                content_field.get("downloadUrl")
                or content_field.get("absoluteUrl")
                or content_field.get("URL")
            )
            if isinstance(media_url, str):
                media_type = "audio" if media_url.endswith(".mp3") else "video"
                session_title = content_field.get("title", "Session")
                local_path = self._build_local_path(section, pack_title, session_title, media_url)
                media_items.append(
                    {
                        "section": section,
                        "pack": pack_title,
                        "pack_description": pack_desc,
                        "session_title": session_title,
                        "media_type": media_type,
                        "cdn_url": media_url,
                        "local_path": str(local_path),
                    }
                )

        # 3. Recursively search nested structures for media URLs not caught above
        media_items.extend(
            self._collect_media_recursive(content_field, section, pack_title, pack_desc)
        )

        # -------------------------------------------------------------
        # 4. Follow link/moreAction/slug to pack-detail page for extra sessions
        # -------------------------------------------------------------
        link_path = (
            item.get("link")
            or item.get("action")
            or (
                item.get("moreAction", {}).get("url")
                if isinstance(item.get("moreAction"), dict)
                else None
            )
            or item.get("deeplink")
            or item.get("slug")
        )
        if isinstance(link_path, str) and link_path.startswith("/"):
            pack_url = urljoin(self.BASE_URL, link_path)
            extra_media = self._extract_from_pack_detail(pack_url, section, pack_title, pack_desc)
            media_items.extend(extra_media)

        for play_url, default_title in sources:
            info = self._parse_curefit_url(play_url)
            if "media_url" not in info:
                # Special case: play_url may be a dict indicating login modal
                if isinstance(play_url, dict) and play_url.get("actionType") == "SHOW_LOGIN_MODAL" and not self._warned_login_required:
                    print("⚠️  Pack detail requires login — session cookies may be expired or missing.")
                    self._warned_login_required = True
                continue
            session_title = info.get("session_title", default_title)
            local_path = self._build_local_path(section, pack_title, session_title, info["media_url"])
            media_items.append(
                {
                    "section": section,
                    "pack": pack_title,
                    "pack_description": pack_desc,
                    "session_title": session_title,
                    "media_type": info.get("media_type", "audio"),
                    "cdn_url": info["media_url"],
                    "local_path": str(local_path),
                }
            )
        # -------------------------------------------------------------
        # De-duplicate within this item: it can expose the *same* CDN URL
        # through multiple routes (e.g. both `playAction` and a direct
        # `downloadUrl` inside `content`).  We keep the first occurrence,
        # unless a later one has a more descriptive title than a generic
        # "Session" label.
        # -------------------------------------------------------------
        dedup: Dict[str, Dict[str, Any]] = {}
        for entry in media_items:
            url = entry["cdn_url"]
            if url not in dedup:
                dedup[url] = entry
            else:
                # Prefer the entry whose session_title is *not* the generic
                # "Session" (or starts with it), so Yoga Nidra keeps the real
                # titles like "Deep Relaxation" over duplicates.
                prev_title = dedup[url]["session_title"].lower()
                new_title = entry["session_title"].lower()
                if prev_title.startswith("session") and not new_title.startswith("session"):
                    dedup[url] = entry

        return list(dedup.values())

    # recursive media collector
    def _collect_media_recursive(
        self,
        node: Any,
        section: str,
        pack_title: str,
        pack_desc: str,
        inherited_title: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        collected = []
        if isinstance(node, dict):
            # direct url keys
            url_key = None
            for k in ("downloadUrl", "absoluteUrl", "URL"):
                if k in node and isinstance(node[k], str):
                    url_key = k
                    break
            if url_key:
                media_url = node[url_key]
                media_type = "audio" if media_url.endswith(".mp3") else "video"
                session_title = (
                    node.get("title")
                    or node.get("subTitle")
                    or inherited_title
                    or "Session"
                )
                local_path = self._build_local_path(section, pack_title, session_title, media_url)
                collected.append(
                    {
                        "section": section,
                        "pack": pack_title,
                        "pack_description": pack_desc,
                        "session_title": session_title,
                        "media_type": media_type,
                        "cdn_url": media_url,
                        "local_path": str(local_path),
                    }
                )
            # recurse into values
            for v in node.values():
                collected.extend(
                    self._collect_media_recursive(
                        v, section, pack_title, pack_desc, inherited_title or node.get("title")
                    )
                )
        elif isinstance(node, list):
            for item in node:
                collected.extend(
                    self._collect_media_recursive(
                        item, section, pack_title, pack_desc, inherited_title
                    )
                )
        return collected

    # ------------------------------------------------------------------
    # Pack-detail extraction
    # ------------------------------------------------------------------

    def _extract_from_pack_detail(
        self, pack_url: str, section: str, pack_title: str, pack_desc: str
    ) -> List[Dict[str, Any]]:
        """Fetch pack detail page and extract all session media."""
        try:
            resp = self.session.get(pack_url, timeout=(10, 20))
            resp.raise_for_status()
            state = self._extract_preloaded_state(resp.text)
            if not state:
                return []

            # cultDIYPack contains pack by ID; get first dict value
            pack_dict = None
            if "cultDIYPack" in state and isinstance(state["cultDIYPack"], dict):
                for val in state["cultDIYPack"].values():
                    if isinstance(val, dict):
                        pack_dict = val
                        break
            if not pack_dict:
                return []

            media_items: List[Dict[str, Any]] = []

            # Extract from productWidgets first
            for widget in pack_dict.get("productWidgets", []):
                if not isinstance(widget, dict):
                    continue
                for itm in widget.get("items", []):
                    if not isinstance(itm, dict):
                        continue
                    # Same logic as earlier for playAction / direct urls
                    if "playAction" in itm and isinstance(itm["playAction"], str):
                        info = self._parse_curefit_url(itm["playAction"])
                        if "media_url" in info:
                            session_title = info.get("session_title", itm.get("title", "Session"))
                            local_path = self._build_local_path(section, pack_title, session_title, info["media_url"])
                            media_items.append(
                                {
                                    "section": section,
                                    "pack": pack_title,
                                    "pack_description": pack_desc,
                                    "session_title": session_title,
                                    "media_type": info.get("media_type", "audio"),
                                    "cdn_url": info["media_url"],
                                    "local_path": str(local_path),
                                }
                            )
                    elif isinstance(itm.get("playAction"), dict) and itm["playAction"].get("actionType") == "SHOW_LOGIN_MODAL" and not self._warned_login_required:
                        print(f"⚠️  Login required for some sessions in pack '{pack_title}'. Cookies may have expired.")
                        self._warned_login_required = True
                    else:
                        url_field = itm.get("downloadUrl") or itm.get("absoluteUrl") or itm.get("URL")
                        if isinstance(url_field, str):
                            session_title = itm.get("title", "Session")
                            media_type = "audio" if url_field.endswith(".mp3") else "video"
                            local_path = self._build_local_path(section, pack_title, session_title, url_field)
                            media_items.append(
                                {
                                    "section": section,
                                    "pack": pack_title,
                                    "pack_description": pack_desc,
                                    "session_title": session_title,
                                    "media_type": media_type,
                                    "cdn_url": url_field,
                                    "local_path": str(local_path),
                                }
                            )
                        elif isinstance(itm.get("content"), (list, dict)):
                            media_items.extend(
                                self._collect_media_recursive(
                                    itm["content"],
                                    section,
                                    pack_title,
                                    pack_desc,
                                    itm.get("title"),
                                )
                            )

            # Fallback: check pack_dict.content if that's a list/dict
            media_items.extend(
                self._collect_media_recursive(
                    pack_dict.get("content"),
                    section,
                    pack_title,
                    pack_desc,
                    pack_title,
                )
            )

            return media_items
        except Exception:
            return []

    # ---------------------------------------------------------------------
    # Public crawling API
    # ---------------------------------------------------------------------

    def crawl(self) -> None:
        if not self.sections:
            self.discover_sections()
        print("\n🚀 Crawling sections & extracting media …")
        for idx, sec in enumerate(self.sections, 1):
            print(f"[{idx}/{len(self.sections)}] {sec['name']}…", end=" ")
            try:
                resp = self.session.get(sec["url"], timeout=(10, 20))
                resp.raise_for_status()
            except Exception as e:
                print(f"❌  {e}")
                continue
            state = self._extract_preloaded_state(resp.text)
            if not state or "cultDIYPackBrowse" not in state:
                print("⚠️  no data")
                continue
            widgets = state["cultDIYPackBrowse"].get("widgets", [])
            pack_count = 0
            for w in widgets:
                for item in w.get("items", []):
                    pack_title = item.get("title", "Unknown Pack")
                    pack_desc = item.get("description", "")
                    med_list = self._extract_media_from_item(item, sec["name"], pack_title, pack_desc)
                    if med_list:
                        self.media_items.extend(med_list)
                        self.media_by_section[sec["name"]].extend(med_list)
                        pack_count += 1
            print(f"✅  {pack_count} packs, {len(self.media_by_section[sec['name']])} media")
            time.sleep(1)
        print(f"\n✨ Extracted {len(self.media_items)} total media files across {len(self.media_by_section)} sections.")
        # Persist data
        ensure_dir(self.data_root)
        Path(self.data_root / "all_media.json").write_text(json.dumps(self.media_items, indent=2))
        Path(self.data_root / "media_by_section.json").write_text(
            json.dumps(self.media_by_section, indent=2)
        )

    # ---------------------------------------------------------------------
    # Download logic with caching / retries
    # ---------------------------------------------------------------------

    async def _download_one(self, session: aiohttp.ClientSession, media: Dict[str, Any]) -> None:
        url = media["cdn_url"]
        local_path = Path(media["local_path"])
        ensure_dir(local_path.parent)

        # ------------------------------------------------------------------
        # Fast-path: media was already downloaded (either at this exact path
        # or elsewhere under a different pack) – no need to hit the network
        # again.  We *do not* overwrite an existing successful manifest entry
        # because that would discard the first (and only) actually downloaded
        # file path, thereby breaking the link for earlier README references.
        # Instead we simply bail out early and keep the original mapping.
        # ------------------------------------------------------------------
        if local_path.exists():
            # This exact path is already on disk – record/update manifest.
            self.manifest[url] = {"status": "success", "path": str(local_path)}
            return

        if self.manifest.get(url, {}).get("status") == "success":
            # File was supposedly downloaded before. Double-check the file is
            # really present on disk; corrupted/removed files should trigger
            # a re-download.
            existing_path = self.manifest[url].get("path")
            if existing_path and Path(existing_path).exists():
                # File truly exists → nothing to do.
                return
            else:
                # Cached entry stale – remove so we actually download again.
                self.manifest.pop(url, None)

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(local_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)
                    self.manifest[url] = {"status": "success", "path": str(local_path)}
                    print(f"✅ {local_path.relative_to(self.out_root)}")
                else:
                    self.manifest[url] = {"status": f"http_{resp.status}", "path": str(local_path)}
                    print(f"❌ {resp.status}  {url}")
        except Exception as e:
            self.manifest[url] = {"status": str(e), "path": str(local_path)}
            print(f"❌ error {e}  {url}")

    async def _download_all_async(self, to_download: List[Dict[str, Any]]):
        sem = asyncio.Semaphore(self.max_concurrent)

        timeout = aiohttp.ClientTimeout(total=120)
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:

            async def _bounded_download(media):
                async with sem:
                    await self._download_one(session, media)
                    await asyncio.sleep(self.delay)

            tasks = [_bounded_download(m) for m in to_download]
            await asyncio.gather(*tasks)

    def download_media(self, retry_failed_only: bool = False):
        """Download media respecting cache & manifest."""
        if not self.media_items and Path(self.data_root / "all_media.json").exists():
            self.media_items = json.loads(Path(self.data_root / "all_media.json").read_text())
        # Determine which items to download
        to_dl: List[Dict[str, Any]] = []
        for m in self.media_items:
            url = m["cdn_url"]
            entry = self.manifest.get(url, {})
            status = entry.get("status")
            cached_path = entry.get("path") or m["local_path"]

            file_on_disk = Path(cached_path).exists()

            if status == "success" and file_on_disk and not retry_failed_only:
                continue  # already done
            if retry_failed_only and status != "success":
                to_dl.append(m)
            elif not retry_failed_only:
                to_dl.append(m)

        if not to_dl:
            print("📝 No files to download – everything up-to-date.")
            return

        print(f"\n⬇️  Downloading {len(to_dl)} files (concurrency {self.max_concurrent}) …")
        asyncio.run(self._download_all_async(to_dl))
        # Persist manifest
        self.manifest_file.write_text(json.dumps(self.manifest, indent=2))
        print("✅ Download phase finished.")

    # ---------------------------------------------------------------------
    # README generator
    # ---------------------------------------------------------------------

    def _rel_path_for_md(self, abs_path: str) -> str:
        try:
            return str(Path(abs_path).relative_to(Path.cwd()))
        except ValueError:
            return abs_path

    def generate_readme(self) -> None:
        """(Re)create README.md using in-memory or cached JSON data.

        If crawling just failed (e.g. network timeout) we transparently fall back to
        the JSON files from the last successful run so the README never ends up
        blank.  When *no* data is available we simply keep the existing README
        instead of overwriting it with an empty shell.
        """

        # Load cached section → media mapping if necessary
        if not self.media_by_section and Path(self.data_root / "media_by_section.json").exists():
            try:
                self.media_by_section = json.loads(
                    Path(self.data_root / "media_by_section.json").read_text()
                )
            except Exception as e:
                print(f"⚠️  Failed to load cached section data: {e}")

        # Likewise for the flat media list used for statistics
        if not self.media_items and Path(self.data_root / "all_media.json").exists():
            try:
                self.media_items = json.loads(Path(self.data_root / "all_media.json").read_text())
            except Exception as e:
                print(f"⚠️  Failed to load cached media list: {e}")

        # If we still have no data after fallback, bail out early to avoid wiping
        # an existing rich README.
        if not self.media_by_section:
            print("🚫 No media data available — README not updated.")
            return

        lines: List[str] = []
        # Compute unique media count (guard against empty list)
        if self.media_items:
            total_unique = len({m["cdn_url"] for m in self.media_items})
        else:
            total_unique = 0
        lines.append("# 🧘‍♀️ CultFit MindLive Media Collection\n")
        lines.append(f"**Last update:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**Total sessions:** {total_unique}\n")
        lines.append("\n---\n")

        # Table of contents
        lines.append("## Contents\n")
        for sec in sorted(self.media_by_section.keys()):
            anchor = sec.lower().replace(" ", "-")
            lines.append(f"- [{sec}](#{anchor})")
        lines.append("\n")

        # ------------------------------------------------------------------
        # Fancy section layout: each section collapsible (<details>) and each
        # pack rendered as a Markdown table with icons for quick scanning.
        # ------------------------------------------------------------------

        def _icon_link(label: str, url: str | None = None) -> str:
            """Return an emoji button with optional link."""
            if url:
                return f"[ {label} ]({url})"
            else:
                return label

        for sec in sorted(self.media_by_section.keys()):
            total_in_sec = len(self.media_by_section[sec])

            # Collapsible section for tidiness
            lines.append(f"\n<details>")
            lines.append(f"<summary><strong>{sec}</strong> — {total_in_sec} sessions</summary>\n")

            packs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for m in self.media_by_section[sec]:
                packs[m["pack"]].append(m)

            for pack in sorted(packs.keys()):
                sessions = packs[pack]
                lines.append(f"\n#### {pack} ({len(sessions)} sessions)\n")
                lines.append("| # | Session | CDN |")
                lines.append("|:-:|:--|:-:|")

                for idx, m in enumerate(sessions, 1):
                    cdn_cell = _icon_link("🌐", m["cdn_url"])
                    lines.append(f"| {idx} | {m['session_title']} | {cdn_cell} |")

            lines.append("\n</details>\n")
        readme_text = "\n".join(lines) + "\n"

        Path("README.md").write_text(readme_text)
        print("📝 README.md regenerated (using cached data).")

    # ---------------------------------------------------------------------
    # Static HTML page generator for GitHub Pages streaming
    # ---------------------------------------------------------------------

    def generate_html(self) -> None:
        """Create docs/index.html with embedded audio/video players.

        We avoid heavy JS; just plain HTML+CSS so GitHub Pages renders it
        instantly.  Uses the same cached JSON data as README.
        """

        # Ensure media_by_section is loaded (same fallback as README)
        if not self.media_by_section and Path(self.data_root / "media_by_section.json").exists():
            try:
                self.media_by_section = json.loads(
                    Path(self.data_root / "media_by_section.json").read_text()
                )
            except Exception:
                return  # silently skip — README already warned

        docs_dir = Path("docs")
        ensure_dir(docs_dir)

        html_lines: list[str] = []
        html_lines.append("<!DOCTYPE html>")
        html_lines.append("<html lang='en'>")
        html_lines.append("<head>")
        html_lines.append("  <meta charset='utf-8' />")
        html_lines.append("  <meta name='viewport' content='width=device-width,initial-scale=1' />")
        html_lines.append("  <title>CultFit MindLive Sessions</title>")
        # Link to external stylesheet & script for maintainability
        html_lines.append("  <link rel='stylesheet' href='styles.css' />")
        html_lines.append("</head>")
        html_lines.append("<body>")
        html_lines.append("<h1>🧘‍♀️ CultFit MindLive – Streamable Sessions</h1>")
        html_lines.append("<p>All content streams directly from cult.fit CDN; no media is stored in this repo.</p>")

        # -----------------------------------------------------
        # Navigation menu with anchors to each section
        # -----------------------------------------------------
        html_lines.append("<nav><ul>")
        section_ids: Dict[str, str] = {}
        for sec in sorted(self.media_by_section.keys()):
            sid = sec.lower().replace(" ", "-")
            section_ids[sec] = sid
            html_lines.append(f"  <li><a href='#{sid}'>{sec}</a></li>")
        html_lines.append("</ul></nav><hr/>")

        for sec in sorted(self.media_by_section.keys()):
            sid = section_ids[sec]
            html_lines.append(f"<section id='{sid}'>")
            html_lines.append(f"<h2>{sec}</h2>")
            html_lines.append("<details open><summary>Show/Hide Packs</summary>")
            packs: Dict[str, list[dict[str, Any]]] = defaultdict(list)
            for m in self.media_by_section[sec]:
                packs[m["pack"]].append(m)

            for pack in sorted(packs.keys()):
                html_lines.append(f"<h3>{pack}</h3>")
                for m in packs[pack]:
                    title = m["session_title"]
                    url = m["cdn_url"]
                    html_lines.append(
                        f"<p><button class='play-btn' data-url='{url}' data-type='{m['media_type']}'>▶️ {title}</button></p>"
                    )
            html_lines.append("</details>")
            html_lines.append("</section>")

        # -----------------------------------------------------
        # Small JS snippet: when a new audio/video starts playing, pause all
        # others so only one plays at a time.
        # -----------------------------------------------------
        html_lines.append("  <script src='app.js'></script>")

        html_lines.append("</body>\n</html>")

        (docs_dir / "index.html").write_text("\n".join(html_lines))
        # -----------------------------------------------------------------
        # Write external assets (styles.css, app.js) for maintainability
        # -----------------------------------------------------------------

        # Copy static assets from site/ if present (more maintainable)
        try:
            import shutil, pkg_resources  # noqa
            static_css = Path("site/styles.css")
            static_js = Path("site/app.js")
            if static_css.exists():
                shutil.copy(static_css, docs_dir / "styles.css")
            if static_js.exists():
                shutil.copy(static_js, docs_dir / "app.js")
        except Exception as _:
            pass  # Fall back silently; assume already present

        print("🌐 docs site generated (index.html, styles.css, app.js).")

###############################################################################
# CLI entry point
###############################################################################

def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="CultFit MindLive all-in-one crawler")
    # Download functionality has been deprecated – we only work with CDN links now.
    parser.add_argument("--no-crawl", action="store_true", help="Skip crawling & reuse cached JSON")
    args = parser.parse_args(argv)

    c = CultFitCrawler()

    if not args.no_crawl:
        c.crawl()
    # Crawling (if enabled) updates the JSON cache that README + HTML rely on.
    c.generate_readme()

    print("\n🎉 All done! Happy meditating ✨")


if __name__ == "__main__":
    main() 