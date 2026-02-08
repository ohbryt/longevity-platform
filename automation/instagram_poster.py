#!/usr/bin/env python3
"""
Instagram Auto-Poster for Longevity Lab

Publishes card news carousels to Instagram via the Graph API.
Images are hosted on GitHub Pages (gh-pages branch) for public URLs.

Flow:
1. Push slide PNGs to gh-pages branch → public URLs
2. Generate Korean caption with hashtags
3. Instagram Graph API carousel: create items → container → publish

Requires:
- INSTAGRAM_USER_ID: IG Business Account numeric ID
- INSTAGRAM_ACCESS_TOKEN: Long-lived User Access Token
- GitHub Pages enabled on gh-pages branch
"""

import os
import json
import asyncio
import subprocess
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class InstagramPoster:
    """Post card news carousels to Instagram via Graph API."""

    GRAPH_API = "https://graph.facebook.com/v22.0"

    HASHTAGS = {
        "base": ["건강수명", "장수과학", "노화연구", "LongevityLab"],
        "pubmed": ["의학연구", "PubMed"],
        "biorxiv": ["최신연구", "프리프린트"],
        "medrxiv": ["임상연구", "의료연구"],
        "clinical_trial": ["임상시험", "신약개발"],
    }

    MAX_HASHTAGS = 15

    def __init__(
        self,
        ig_user_id: str,
        access_token: str,
        github_repo: str,
        pages_base_url: str,
        dry_run: bool = False,
    ):
        self.ig_user_id = ig_user_id
        self.access_token = access_token
        self.github_repo = github_repo
        self.pages_base_url = pages_base_url.rstrip("/")
        self.dry_run = dry_run

    # ============ Step 1: Push images to gh-pages ============

    async def upload_to_gh_pages(self, card_news_dir: str) -> List[str]:
        """
        Push card news PNGs to the gh-pages branch for public hosting.

        Args:
            card_news_dir: Path to directory containing slide_1.png .. slide_4.png

        Returns:
            List of public URLs for each slide image.
        """
        card_path = Path(card_news_dir)
        if not card_path.exists():
            raise FileNotFoundError(f"Card news directory not found: {card_news_dir}")

        slides = sorted(card_path.glob("slide_*.png"))
        if not slides:
            raise FileNotFoundError(f"No slide_*.png files in {card_news_dir}")

        # Folder name in gh-pages (e.g., "2026-02-05_10-1002-ddr-70221")
        folder_name = card_path.name

        if self.dry_run:
            urls = [
                f"{self.pages_base_url}/card_news/{folder_name}/{s.name}"
                for s in slides
            ]
            print(f"   [DRY RUN] Would push {len(slides)} images to gh-pages")
            return urls

        worktree_dir = tempfile.mkdtemp(prefix="gh-pages-")
        try:
            repo_root = self._find_repo_root()

            # Ensure gh-pages branch exists
            self._run_git(
                ["git", "branch", "--list", "gh-pages"],
                cwd=repo_root,
            )
            # Try to add worktree for gh-pages
            try:
                self._run_git(
                    ["git", "worktree", "add", worktree_dir, "gh-pages"],
                    cwd=repo_root,
                )
            except subprocess.CalledProcessError:
                # gh-pages branch might not exist yet; create orphan
                self._run_git(
                    ["git", "worktree", "add", "--detach", worktree_dir],
                    cwd=repo_root,
                )
                self._run_git(
                    ["git", "checkout", "--orphan", "gh-pages"],
                    cwd=worktree_dir,
                )
                self._run_git(["git", "rm", "-rf", "."], cwd=worktree_dir)

            # Copy slides into worktree
            dest_dir = Path(worktree_dir) / "card_news" / folder_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            for slide in slides:
                shutil.copy2(slide, dest_dir / slide.name)

            # Commit and push
            self._run_git(["git", "add", "card_news/"], cwd=worktree_dir)

            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=worktree_dir,
                capture_output=True,
            )
            if result.returncode != 0:
                self._run_git(
                    [
                        "git", "commit", "-m",
                        f"Add card news: {folder_name}",
                    ],
                    cwd=worktree_dir,
                )
                self._run_git(
                    ["git", "push", "origin", "gh-pages"],
                    cwd=worktree_dir,
                )
                print(f"   ✅ Pushed {len(slides)} images to gh-pages/{folder_name}")
            else:
                print(f"   ℹ️ Images already on gh-pages for {folder_name}")

        finally:
            # Clean up worktree
            try:
                self._run_git(
                    ["git", "worktree", "remove", "--force", worktree_dir],
                    cwd=self._find_repo_root(),
                )
            except Exception:
                # Fallback: just remove the directory
                shutil.rmtree(worktree_dir, ignore_errors=True)

        urls = [
            f"{self.pages_base_url}/card_news/{folder_name}/{s.name}"
            for s in slides
        ]
        return urls

    def _find_repo_root(self) -> str:
        """Find the git repository root."""
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def _run_git(self, cmd: List[str], cwd: str) -> str:
        """Run a git command and return stdout."""
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    # ============ Step 2: Generate caption ============

    def generate_caption(self, data: dict) -> str:
        """
        Generate an Instagram caption from a content draft.

        Args:
            data: Content draft dict (same schema as JSON files)

        Returns:
            Caption string with title, summary, insight, URL, and hashtags.
        """
        title = data.get("korean_title", "") or data.get("english_title", "")

        summary = data.get("korean_summary", "")
        # Truncate summary to ~2 lines (approx 120 chars)
        if len(summary) > 120:
            summary = summary[:117].rsplit(" ", 1)[0] + "..."

        insights = data.get("key_insights", [])
        first_insight = insights[0] if insights else ""

        # Build hashtag list
        source = data.get("source", "pubmed")
        tags = list(self.HASHTAGS["base"])
        tags.extend(self.HASHTAGS.get(source, []))

        # Add topic-specific tags from paper
        paper = data.get("paper", {})
        if isinstance(paper, dict):
            topics = paper.get("topics", [])
            for topic in topics:
                if topic in self.HASHTAGS and topic != source:
                    tags.extend(self.HASHTAGS[topic])

        # Deduplicate and limit
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        tags = unique_tags[: self.MAX_HASHTAGS]
        hashtag_str = " ".join(f"#{tag}" for tag in tags)

        # Assemble caption
        parts = [title]
        if summary:
            parts.append(f"\n{summary}")
        if first_insight:
            parts.append(f"\n💡 {first_insight}")
        parts.append("\n👉 자세히 보기: longevity-lab.io")
        parts.append(f"\n{hashtag_str}")

        return "\n".join(parts)

    # ============ Step 3: Instagram Graph API ============

    async def create_carousel(self, image_urls: List[str], caption: str) -> str:
        """
        Post a carousel to Instagram using the Graph API.

        Steps:
        1. Create media container for each image (is_carousel_item=true)
        2. Create carousel container with children + caption
        3. Wait for container to be ready
        4. Publish the carousel

        Args:
            image_urls: Public URLs of slide images (must be HTTPS)
            caption: Post caption text

        Returns:
            Published media ID string.
        """
        import aiohttp

        if self.dry_run:
            print(f"   [DRY RUN] Would post carousel with {len(image_urls)} images")
            print(f"   [DRY RUN] Caption: {caption[:80]}...")
            return "dry_run_media_id"

        async with aiohttp.ClientSession() as session:
            # 3a: Create individual image containers
            creation_ids = []
            for i, url in enumerate(image_urls):
                container_id = await self._create_media_container(
                    session, url, is_carousel_item=True
                )
                creation_ids.append(container_id)
                print(f"   📸 Slide {i + 1} container: {container_id}")

            # 3b: Create carousel container
            carousel_id = await self._create_carousel_container(
                session, creation_ids, caption
            )
            print(f"   🎠 Carousel container: {carousel_id}")

            # 3c: Wait for container to be ready
            await self._wait_for_container(session, carousel_id)

            # 3d: Publish
            media_id = await self._publish_container(session, carousel_id)
            print(f"   ✅ Published: {media_id}")
            return media_id

    async def _create_media_container(
        self,
        session,
        image_url: str,
        is_carousel_item: bool = False,
    ) -> str:
        """Create a media container for a single image."""
        url = f"{self.GRAPH_API}/{self.ig_user_id}/media"
        params = {
            "image_url": image_url,
            "access_token": self.access_token,
        }
        if is_carousel_item:
            params["is_carousel_item"] = "true"

        data = await self._api_post(session, url, params)
        return data["id"]

    async def _create_carousel_container(
        self,
        session,
        children_ids: List[str],
        caption: str,
    ) -> str:
        """Create a carousel container referencing child media items."""
        url = f"{self.GRAPH_API}/{self.ig_user_id}/media"
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
            "access_token": self.access_token,
        }
        data = await self._api_post(session, url, params)
        return data["id"]

    async def _wait_for_container(
        self, session, container_id: str, max_polls: int = 5, delay: int = 10
    ):
        """Poll container status until it's ready or timeout."""
        url = f"{self.GRAPH_API}/{container_id}"
        params = {
            "fields": "status_code",
            "access_token": self.access_token,
        }

        for attempt in range(max_polls):
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                status = data.get("status_code", "")

                if status == "FINISHED":
                    return
                elif status == "ERROR":
                    raise RuntimeError(
                        f"Container {container_id} failed: {data}"
                    )

                print(f"   ⏳ Container status: {status} (poll {attempt + 1}/{max_polls})")
                await asyncio.sleep(delay)

        raise TimeoutError(
            f"Container {container_id} not ready after {max_polls * delay}s"
        )

    async def _publish_container(self, session, container_id: str) -> str:
        """Publish a ready media container."""
        url = f"{self.GRAPH_API}/{self.ig_user_id}/media_publish"
        params = {
            "creation_id": container_id,
            "access_token": self.access_token,
        }
        data = await self._api_post(session, url, params)
        return data["id"]

    async def _api_post(
        self, session, url: str, params: dict, max_retries: int = 3
    ) -> dict:
        """POST to Graph API with retry on rate limit."""
        for attempt in range(max_retries):
            async with session.post(url, data=params) as resp:
                data = await resp.json()

                if "error" in data:
                    error = data["error"]
                    code = error.get("code", 0)

                    # Token error — abort entirely
                    if code == 190:
                        raise PermissionError(
                            f"Instagram token error (code 190): {error.get('message')}"
                        )

                    # Rate limit — retry with backoff
                    if resp.status == 429 or code == 4:
                        if attempt < max_retries - 1:
                            wait = 30 * (attempt + 1)
                            print(f"   ⏳ Rate limit, waiting {wait}s...")
                            await asyncio.sleep(wait)
                            continue

                    raise RuntimeError(
                        f"Instagram API error ({code}): {error.get('message')}"
                    )

                return data

        raise RuntimeError("Max retries exceeded for Instagram API")

    # ============ High-level posting ============

    async def post_article(self, data: dict, card_news_dir: str) -> dict:
        """
        Post a single article's card news to Instagram.

        Args:
            data: Content draft dict
            card_news_dir: Path to directory with slide PNGs

        Returns:
            {"success": bool, "media_id": str|None, "error": str|None}
        """
        title = data.get("korean_title", "")[:40]
        try:
            # 1. Upload images to gh-pages
            print(f"   🔄 Uploading images for: {title}...")
            image_urls = await self.upload_to_gh_pages(card_news_dir)

            # 2. Generate caption
            caption = self.generate_caption(data)

            # 3. Post carousel
            print(f"   📱 Posting carousel...")
            media_id = await self.create_carousel(image_urls, caption)

            return {"success": True, "media_id": media_id, "error": None}

        except PermissionError as e:
            # Token error — propagate to abort batch
            raise
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            return {"success": False, "media_id": None, "error": str(e)}

    async def post_batch(
        self, drafts_with_dirs: List[Tuple[dict, str]]
    ) -> None:
        """
        Post multiple articles with a delay between each.

        Args:
            drafts_with_dirs: List of (draft_data, card_news_dir) tuples
        """
        if not drafts_with_dirs:
            print("   ℹ️ No articles to post")
            return

        results = []
        for i, (data, card_dir) in enumerate(drafts_with_dirs):
            title = data.get("korean_title", "")[:40]
            print(f"\n📱 [{i + 1}/{len(drafts_with_dirs)}] {title}...")

            try:
                result = await self.post_article(data, card_dir)
                results.append(result)
            except PermissionError as e:
                print(f"   🚫 Token error — aborting remaining posts: {e}")
                results.append({"success": False, "media_id": None, "error": str(e)})
                break

            # 60s delay between posts to avoid rate limits
            if i < len(drafts_with_dirs) - 1:
                print("   ⏳ 60초 대기...")
                await asyncio.sleep(60)

        # Summary
        success = sum(1 for r in results if r["success"])
        failed = len(results) - success
        print(f"\n📊 Instagram 포스팅 결과: {success} 성공, {failed} 실패")
        for i, r in enumerate(results):
            icon = "✅" if r["success"] else "❌"
            title = drafts_with_dirs[i][0].get("korean_title", "")[:40]
            print(f"   {icon} {title}")
            if r.get("error"):
                print(f"      → {r['error']}")
