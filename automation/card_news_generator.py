#!/usr/bin/env python3
"""
Instagram Card News Generator for Longevity Lab

Generates 1080x1080 Instagram carousel images from content drafts.
4 slides per article: Cover, Key Insights, Practical Tips, CTA.

Design: Warm premium palette matching longevity-lab.io
"""

import os
import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont


class CardNewsGenerator:
    """Generate Instagram card news images from content drafts."""

    SLIDE_SIZE = (1080, 1080)
    PADDING = 80

    # Color palette (matching site design system)
    COLORS = {
        "cream": "#FAF7F2",
        "white": "#FFFFFF",
        "warm_50": "#FFF8F0",
        "warm_500": "#A67C52",
        "warm_600": "#8B6544",
        "terracotta_500": "#C4603F",
        "terracotta_600": "#A84E32",
        "text_primary": "#1C1917",
        "text_secondary": "#44403C",
        "text_muted": "#78716C",
        "amber_100": "#FEF3C7",
        "amber_200": "#FDE68A",
        "divider": "#E7E0D8",
    }

    # Source badge labels
    SOURCE_LABELS = {
        "pubmed": "PubMed",
        "biorxiv": "bioRxiv",
        "medrxiv": "medRxiv",
        "clinical_trial": "ClinicalTrials.gov",
    }

    def __init__(self, fonts_dir: str = None):
        if fonts_dir is None:
            fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
        self.fonts_dir = fonts_dir
        self._load_fonts()

    def _load_fonts(self):
        """Load Noto Sans KR fonts at various sizes."""
        bold_path = os.path.join(self.fonts_dir, "NotoSansKR-Bold.otf")
        medium_path = os.path.join(self.fonts_dir, "NotoSansKR-Medium.otf")
        regular_path = os.path.join(self.fonts_dir, "NotoSansKR-Regular.ttf")

        # Title fonts
        self.font_title_lg = ImageFont.truetype(bold_path, 52)
        self.font_title_md = ImageFont.truetype(bold_path, 44)
        self.font_title_sm = ImageFont.truetype(bold_path, 38)

        # Body fonts
        self.font_body = ImageFont.truetype(regular_path, 34)
        self.font_body_sm = ImageFont.truetype(regular_path, 30)

        # Caption/badge fonts
        self.font_caption = ImageFont.truetype(medium_path, 26)
        self.font_badge = ImageFont.truetype(medium_path, 24)

        # Header fonts
        self.font_header = ImageFont.truetype(bold_path, 40)

        # Logo/brand font
        self.font_logo = ImageFont.truetype(bold_path, 32)
        self.font_url = ImageFont.truetype(medium_path, 36)
        self.font_tagline = ImageFont.truetype(regular_path, 28)

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        h = hex_color.lstrip("#")
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))

    def _color(self, name: str) -> Tuple[int, int, int]:
        """Get RGB color by name."""
        return self._hex_to_rgb(self.COLORS[name])

    def _new_slide(self) -> Image.Image:
        """Create a new blank slide with cream background."""
        return Image.new("RGB", self.SLIDE_SIZE, self._color("cream"))

    def _draw_rounded_rect(
        self,
        draw: ImageDraw.Draw,
        xy: Tuple[int, int, int, int],
        radius: int,
        fill: Tuple[int, int, int],
    ):
        """Draw a rounded rectangle."""
        x1, y1, x2, y2 = xy
        # Draw main rectangle
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        # Draw corners
        draw.pieslice([x1, y1, x1 + 2 * radius, y1 + 2 * radius], 180, 270, fill=fill)
        draw.pieslice(
            [x2 - 2 * radius, y1, x2, y1 + 2 * radius], 270, 360, fill=fill
        )
        draw.pieslice(
            [x1, y2 - 2 * radius, x1 + 2 * radius, y2], 90, 180, fill=fill
        )
        draw.pieslice([x2 - 2 * radius, y2 - 2 * radius, x2, y2], 0, 90, fill=fill)

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """Wrap text to fit within max_width pixels, respecting Korean word boundaries."""
        lines = []
        for paragraph in text.split("\n"):
            if not paragraph.strip():
                lines.append("")
                continue

            # For Korean text, we can break at almost any character
            # But try to break at spaces first
            words = paragraph.split()
            if not words:
                lines.append("")
                continue

            current_line = words[0]
            for word in words[1:]:
                test_line = current_line + " " + word
                bbox = font.getbbox(test_line)
                if bbox[2] - bbox[0] <= max_width:
                    current_line = test_line
                else:
                    # If current_line itself is too wide, break by characters
                    if font.getbbox(current_line)[2] - font.getbbox(current_line)[0] > max_width:
                        lines.extend(self._break_by_chars(current_line, font, max_width))
                    else:
                        lines.append(current_line)
                    current_line = word

            # Handle the last line
            if current_line:
                if font.getbbox(current_line)[2] - font.getbbox(current_line)[0] > max_width:
                    lines.extend(self._break_by_chars(current_line, font, max_width))
                else:
                    lines.append(current_line)

        return lines

    def _break_by_chars(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """Break text by individual characters when words are too long."""
        lines = []
        current = ""
        for char in text:
            test = current + char
            bbox = font.getbbox(test)
            if bbox[2] - bbox[0] > max_width:
                if current:
                    lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)
        return lines

    def _draw_source_badge(
        self, draw: ImageDraw.Draw, source: str, x: int, y: int
    ) -> Tuple[int, int]:
        """Draw a source badge and return its (width, height)."""
        label = self.SOURCE_LABELS.get(source, source or "PubMed")
        bbox = self.font_badge.getbbox(label)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad_x, pad_y = 20, 10
        badge_w = text_w + pad_x * 2
        badge_h = text_h + pad_y * 2

        self._draw_rounded_rect(
            draw, (x, y, x + badge_w, y + badge_h), 16, self._color("amber_100")
        )
        draw.text(
            (x + pad_x, y + pad_y),
            label,
            font=self.font_badge,
            fill=self._color("warm_600"),
        )
        return badge_w, badge_h

    def _draw_bottom_bar(self, draw: ImageDraw.Draw):
        """Draw the bottom brand bar with accent line."""
        # Thin accent line
        y_line = self.SLIDE_SIZE[1] - self.PADDING - 40
        draw.rectangle(
            [self.PADDING, y_line, self.SLIDE_SIZE[0] - self.PADDING, y_line + 3],
            fill=self._color("warm_500"),
        )
        # Brand text
        draw.text(
            (self.PADDING, y_line + 12),
            "Longevity Lab",
            font=self.font_caption,
            fill=self._color("warm_500"),
        )

    def _draw_header_with_icon(
        self, draw: ImageDraw.Draw, icon_type: str, text: str, y: int
    ) -> int:
        """Draw a section header with decorative icon. Returns y position after header."""
        # Draw decorative icon shape instead of emoji
        icon_x = self.PADDING
        icon_y = y + 8
        icon_size = 18

        if icon_type == "insights":
            # Circle target icon for insights
            draw.ellipse(
                [icon_x, icon_y, icon_x + icon_size * 2, icon_y + icon_size * 2],
                outline=self._color("terracotta_500"),
                width=3,
            )
            draw.ellipse(
                [icon_x + 6, icon_y + 6, icon_x + icon_size * 2 - 6, icon_y + icon_size * 2 - 6],
                fill=self._color("terracotta_500"),
            )
        elif icon_type == "tips":
            # Diamond icon for tips
            cx = icon_x + icon_size
            cy = icon_y + icon_size
            draw.polygon(
                [(cx, cy - icon_size), (cx + icon_size, cy), (cx, cy + icon_size), (cx - icon_size, cy)],
                fill=self._color("warm_500"),
            )

        text_x = self.PADDING + icon_size * 2 + 16
        draw.text(
            (text_x, y),
            text,
            font=self.font_header,
            fill=self._color("text_primary"),
        )
        # Underline
        line_y = y + 55
        draw.rectangle(
            [self.PADDING, line_y, self.PADDING + 200, line_y + 3],
            fill=self._color("terracotta_500"),
        )
        return line_y + 25

    def _choose_title_font(self, title: str) -> ImageFont.FreeTypeFont:
        """Choose appropriate font size based on title length."""
        if len(title) <= 20:
            return self.font_title_lg
        elif len(title) <= 35:
            return self.font_title_md
        else:
            return self.font_title_sm

    # ============ Slide Generators ============

    def _make_cover(self, data: Dict) -> Image.Image:
        """Slide 1: Cover with title, source badge, and branding."""
        img = self._new_slide()
        draw = ImageDraw.Draw(img)

        content_width = self.SLIDE_SIZE[0] - self.PADDING * 2

        # Source badge (top)
        source = data.get("source", "pubmed")
        self._draw_source_badge(draw, source, self.PADDING, self.PADDING)

        # Date
        created = data.get("created_at", "")
        date_str = created[:10] if created else datetime.now().strftime("%Y-%m-%d")
        date_bbox = self.font_caption.getbbox(date_str)
        date_w = date_bbox[2] - date_bbox[0]
        draw.text(
            (self.SLIDE_SIZE[0] - self.PADDING - date_w, self.PADDING + 5),
            date_str,
            font=self.font_caption,
            fill=self._color("text_muted"),
        )

        # Decorative top accent
        draw.rectangle(
            [self.PADDING, self.PADDING + 70, self.PADDING + 60, self.PADDING + 74],
            fill=self._color("terracotta_500"),
        )

        # Title (centered vertically)
        title = data.get("korean_title", "") or data.get("english_title", "제목 없음")
        title_font = self._choose_title_font(title)
        title_lines = self._wrap_text(title, title_font, content_width)

        # Calculate title block height for vertical centering
        line_height = int(title_font.size * 1.6)
        title_block_height = len(title_lines) * line_height

        # Center title in the middle area (between badge and bottom bar)
        available_top = self.PADDING + 100
        available_bottom = self.SLIDE_SIZE[1] - self.PADDING - 100
        title_y = available_top + (available_bottom - available_top - title_block_height) // 2

        for line in title_lines:
            draw.text(
                (self.PADDING, title_y),
                line,
                font=title_font,
                fill=self._color("text_primary"),
            )
            title_y += line_height

        # Summary (below title, if space allows)
        summary = data.get("korean_summary", "")
        if summary and summary != "요약 생성 실패" and title_y < available_bottom - 100:
            summary_y = title_y + 20
            summary_lines = self._wrap_text(summary, self.font_body_sm, content_width)
            for line in summary_lines[:3]:  # max 3 lines of summary
                if summary_y > available_bottom - 60:
                    break
                draw.text(
                    (self.PADDING, summary_y),
                    line,
                    font=self.font_body_sm,
                    fill=self._color("text_secondary"),
                )
                summary_y += int(self.font_body_sm.size * 1.5)

        # Bottom bar
        self._draw_bottom_bar(draw)

        return img

    def _make_insights(self, data: Dict) -> Image.Image:
        """Slide 2: Key Insights with numbered list."""
        img = self._new_slide()
        draw = ImageDraw.Draw(img)

        content_width = self.SLIDE_SIZE[0] - self.PADDING * 2 - 50  # indent for numbers

        # Header
        y = self.PADDING
        y = self._draw_header_with_icon(draw, "insights", "핵심 인사이트", y)
        y += 15

        # Insights list
        insights = data.get("key_insights", [])[:3]
        if not insights:
            insights = ["핵심 인사이트가 생성되지 않았습니다."]

        for i, insight in enumerate(insights, 1):
            # Number circle
            circle_x = self.PADDING + 5
            circle_y = y + 5
            circle_r = 22
            draw.ellipse(
                [
                    circle_x,
                    circle_y,
                    circle_x + circle_r * 2,
                    circle_y + circle_r * 2,
                ],
                fill=self._color("warm_500"),
            )
            # Number text centered in circle
            num_text = str(i)
            num_bbox = self.font_badge.getbbox(num_text)
            num_w = num_bbox[2] - num_bbox[0]
            num_h = num_bbox[3] - num_bbox[1]
            draw.text(
                (
                    circle_x + circle_r - num_w // 2,
                    circle_y + circle_r - num_h // 2 - 2,
                ),
                num_text,
                font=self.font_badge,
                fill=self._hex_to_rgb("#FFFFFF"),
            )

            # Insight text
            text_x = self.PADDING + 60
            lines = self._wrap_text(insight, self.font_body, content_width)
            line_height = int(self.font_body.size * 1.6)

            for line in lines:
                draw.text(
                    (text_x, y + 8),
                    line,
                    font=self.font_body,
                    fill=self._color("text_primary"),
                )
                y += line_height

            y += 30  # gap between insights

            # Card separator (not after last item)
            if i < len(insights):
                draw.rectangle(
                    [text_x, y - 15, self.SLIDE_SIZE[0] - self.PADDING, y - 13],
                    fill=self._color("divider"),
                )

        # Bottom bar
        self._draw_bottom_bar(draw)

        return img

    def _make_tips(self, data: Dict) -> Image.Image:
        """Slide 3: Practical Tips with bulleted list."""
        img = self._new_slide()
        draw = ImageDraw.Draw(img)

        content_width = self.SLIDE_SIZE[0] - self.PADDING * 2 - 50

        # Header
        y = self.PADDING
        y = self._draw_header_with_icon(draw, "tips", "실생활 적용", y)
        y += 15

        # Tips list
        tips = data.get("practical_applications", [])[:3]
        if not tips:
            tips = ["실생활 적용 정보가 생성되지 않았습니다."]

        for i, tip in enumerate(tips):
            # Terracotta accent marker (diamond shape)
            marker_x = self.PADDING + 12
            marker_y = y + 18
            marker_size = 8
            draw.polygon(
                [
                    (marker_x, marker_y - marker_size),
                    (marker_x + marker_size, marker_y),
                    (marker_x, marker_y + marker_size),
                    (marker_x - marker_size, marker_y),
                ],
                fill=self._color("terracotta_500"),
            )

            # Tip text
            text_x = self.PADDING + 50
            lines = self._wrap_text(tip, self.font_body, content_width)
            line_height = int(self.font_body.size * 1.6)

            for line in lines:
                draw.text(
                    (text_x, y + 5),
                    line,
                    font=self.font_body,
                    fill=self._color("text_primary"),
                )
                y += line_height

            y += 30

            # Separator
            if i < len(tips) - 1:
                draw.rectangle(
                    [text_x, y - 15, self.SLIDE_SIZE[0] - self.PADDING, y - 13],
                    fill=self._color("divider"),
                )

        # Bottom bar
        self._draw_bottom_bar(draw)

        return img

    def _make_cta(self, data: Dict) -> Image.Image:
        """Slide 4: Call to Action with URL and branding."""
        img = self._new_slide()
        draw = ImageDraw.Draw(img)

        center_x = self.SLIDE_SIZE[0] // 2

        # Decorative top element
        bar_w = 80
        draw.rectangle(
            [center_x - bar_w // 2, self.PADDING + 40, center_x + bar_w // 2, self.PADDING + 44],
            fill=self._color("terracotta_500"),
        )

        # "더 자세한 내용은?" header
        header = "더 자세한 내용은?"
        header_bbox = self.font_header.getbbox(header)
        header_w = header_bbox[2] - header_bbox[0]
        draw.text(
            (center_x - header_w // 2, 300),
            header,
            font=self.font_header,
            fill=self._color("text_primary"),
        )

        # URL card (rounded rect background)
        url_text = "longevity-lab.io"
        url_bbox = self.font_url.getbbox(url_text)
        url_w = url_bbox[2] - url_bbox[0]
        card_pad_x, card_pad_y = 40, 20
        card_w = url_w + card_pad_x * 2
        card_h = url_bbox[3] - url_bbox[1] + card_pad_y * 2
        card_x = center_x - card_w // 2
        card_y = 400

        self._draw_rounded_rect(
            draw,
            (card_x, card_y, card_x + card_w, card_y + card_h),
            20,
            self._color("warm_500"),
        )
        draw.text(
            (card_x + card_pad_x, card_y + card_pad_y),
            url_text,
            font=self.font_url,
            fill=self._hex_to_rgb("#FFFFFF"),
        )

        # Tagline
        tagline = "매주 최신 건강수명 인사이트"
        tagline_bbox = self.font_tagline.getbbox(tagline)
        tagline_w = tagline_bbox[2] - tagline_bbox[0]
        draw.text(
            (center_x - tagline_w // 2, card_y + card_h + 50),
            tagline,
            font=self.font_tagline,
            fill=self._color("text_secondary"),
        )

        # Sub-tagline
        sub = "과학이 증명하는 건강한 습관을 매주 만나보세요"
        sub_bbox = self.font_caption.getbbox(sub)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(
            (center_x - sub_w // 2, card_y + card_h + 100),
            sub,
            font=self.font_caption,
            fill=self._color("text_muted"),
        )

        # Brand logo area
        logo_y = self.SLIDE_SIZE[1] - self.PADDING - 80
        # Accent line
        draw.rectangle(
            [center_x - 100, logo_y, center_x + 100, logo_y + 3],
            fill=self._color("terracotta_500"),
        )
        # Brand name
        brand = "Longevity Lab"
        brand_bbox = self.font_logo.getbbox(brand)
        brand_w = brand_bbox[2] - brand_bbox[0]
        draw.text(
            (center_x - brand_w // 2, logo_y + 20),
            brand,
            font=self.font_logo,
            fill=self._color("warm_500"),
        )

        return img

    # ============ Public API ============

    def generate_from_json(self, data: Dict, output_dir: str = None) -> List[str]:
        """
        Generate card news slides from a content draft JSON dict.

        Args:
            data: Content draft dictionary (same schema as JSON files)
            output_dir: Output directory. Defaults to automation/card_news/{date}_{slug}/

        Returns:
            List of saved PNG file paths.
        """
        if output_dir is None:
            base_dir = os.path.join(os.path.dirname(__file__), "card_news")
            # Build folder name from date and DOI
            created = data.get("created_at", "")
            date_str = created[:10] if created else datetime.now().strftime("%Y-%m-%d")
            paper = data.get("paper", {})
            doi = paper.get("doi", "") if isinstance(paper, dict) else ""
            slug = doi.replace("/", "-").replace(".", "-").lower()[:40] if doi else "untitled"
            output_dir = os.path.join(base_dir, f"{date_str}_{slug}")

        os.makedirs(output_dir, exist_ok=True)

        slides = [
            self._make_cover(data),
            self._make_insights(data),
            self._make_tips(data),
            self._make_cta(data),
        ]

        paths = []
        for i, slide in enumerate(slides, 1):
            path = os.path.join(output_dir, f"slide_{i}.png")
            slide.save(path, "PNG", optimize=True)
            paths.append(path)

        return paths

    def generate_for_draft(self, draft) -> List[str]:
        """
        Generate card news from a ContentDraft dataclass instance.

        Args:
            draft: ContentDraft dataclass instance

        Returns:
            List of saved PNG file paths.
        """
        from dataclasses import asdict

        data = asdict(draft)
        return self.generate_from_json(data)

    def generate_all_from_dir(
        self, drafts_dir: str = None, output_base: str = None
    ) -> Dict[str, List[str]]:
        """
        Generate card news for all JSON drafts in a directory.

        Returns:
            Dict mapping JSON filename to list of generated PNG paths.
        """
        if drafts_dir is None:
            drafts_dir = os.path.join(os.path.dirname(__file__), "content_drafts")

        results = {}
        for filename in sorted(os.listdir(drafts_dir)):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(drafts_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                paths = self.generate_from_json(data, output_dir=output_base)
                results[filename] = paths
                title = data.get("korean_title", "")[:40]
                print(f"  \u2705 {filename}: {len(paths)} slides ({title}...)")
            except Exception as e:
                print(f"  \u274C {filename}: {e}")
                results[filename] = []

        return results


if __name__ == "__main__":
    import sys

    gen = CardNewsGenerator()

    if len(sys.argv) > 1:
        # Generate from specific JSON file
        json_path = sys.argv[1]
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        paths = gen.generate_from_json(data)
        print(f"Generated {len(paths)} slides:")
        for p in paths:
            print(f"  {p}")
    else:
        # Generate for all drafts
        print("\U0001F3A8 Instagram Card News Generator")
        print("=" * 50)
        results = gen.generate_all_from_dir()
        total = sum(len(v) for v in results.values())
        print(f"\n\U0001F4F8 Total: {total} slides from {len(results)} articles")
