"""Auto logo lookup from Simple Icons (CC0). Unknown names and Grok Bot become text badges."""
from __future__ import annotations

import re
import subprocess
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

import style as st

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "icons"
CACHE.mkdir(exist_ok=True)

# Simple Icons slugs. Only used when the speaker (or the spec) names the brand.
SLUGS = {
    "instagram": "instagram",
    "ig": "instagram",
    "tiktok": "tiktok",
    "linkedin": "linkedin",
    "youtube": "youtube",
    "yt": "youtube",
    "x": "x",
    "twitter": "x",
    "github": "github",
    "git hub": "github",
    "apple": "apple",
    "wikipedia": "wikipedia",
    "wiki": "wikipedia",
    "chatgpt": "openai",
    "chat gpt": "openai",
    "openai": "openai",
    "facebook": "facebook",
    "meta": "meta",
    "threads": "threads",
    "pinterest": "pinterest",
    "snapchat": "snapchat",
    "reddit": "reddit",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    "discord": "discord",
    "slack": "slack",
    "notion": "notion",
    "figma": "figma",
    "canva": "canva",
    "google": "google",
    "gmail": "gmail",
    "spotify": "spotify",
    "twitch": "twitch",
    "pinterest": "pinterest",
    "behance": "behance",
    "dribbble": "dribbble",
    "medium": "medium",
    "substack": "substack",
    "zoom": "zoom",
    "shopify": "shopify",
    "stripe": "stripe",
    "notion": "notion",
    "claude": "anthropic",
    "anthropic": "anthropic",
    "midjourney": "midjourney",
    "remotion": "remotion",
    "vercel": "vercel",
    "next.js": "nextdotjs",
    "nextjs": "nextdotjs",
}

# Names that must never become a third-party mark
BADGE_ONLY = {
    "grok bot",
    "grok",
    "xai",
    "x.ai",
}

CDN = "https://cdn.simpleicons.org/{slug}/ffffff"


def _norm(name: str) -> str:
    s = (name or "").strip().lower()
    s = s.replace("@", "").replace("#", "")
    s = re.sub(r"[^a-z0-9.+ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def resolve_slug(name: str) -> str | None:
    key = _norm(name)
    if not key or key in BADGE_ONLY:
        return None
    if key in SLUGS:
        return SLUGS[key]
    # last-token fallback (e.g. "the instagram")
    parts = key.split()
    if len(parts) > 1 and parts[-1] in SLUGS:
        return SLUGS[parts[-1]]
    # already a slug?
    if re.fullmatch(r"[a-z0-9]+", key) and key in SLUGS.values():
        return key
    return None


def _fetch_svg(slug: str) -> str | None:
    dest = CACHE / f"{slug}.svg"
    if dest.exists() and dest.stat().st_size > 40:
        return dest.read_text(encoding="utf-8")
    url = CDN.format(slug=slug)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "geo_broll/3"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        if not data or b"<svg" not in data[:200].lower() and b"<svg" not in data.lower():
            return None
        dest.write_bytes(data)
        return data.decode("utf-8", "replace")
    except Exception:
        return None


def _rasterize(svg: str, dest: Path, size: int) -> bool:
    size = max(16, int(size))
    # 1) cairosvg if present
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(dest), output_width=size, output_height=size)
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        pass
    # 2) project venv
    vpy = ROOT / ".venv" / "bin" / "python"
    if vpy.exists():
        try:
            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
                f.write(svg)
                src = f.name
            subprocess.run(
                [str(vpy), "-c",
                 "import cairosvg,sys; cairosvg.svg2png(url=sys.argv[1], write_to=sys.argv[2], output_width=int(sys.argv[3]), output_height=int(sys.argv[3]))",
                 src, str(dest), str(size)],
                check=True, capture_output=True, timeout=20,
            )
            return dest.exists() and dest.stat().st_size > 0
        except Exception:
            pass
    return False


def _logo_png(slug: str, size: int) -> Image.Image | None:
    size = max(16, int(size))
    dest = CACHE / f"{slug}_{size}.png"
    if dest.exists() and dest.stat().st_size > 0:
        try:
            return Image.open(dest).convert("RGBA")
        except Exception:
            pass
    svg = _fetch_svg(slug)
    if not svg:
        return None
    if _rasterize(svg, dest, size):
        try:
            return Image.open(dest).convert("RGBA")
        except Exception:
            return None
    return None


def text_badge(name: str, size: int, col=None) -> Image.Image:
    """Styled rounded badge with the name (or initials if long) for Grok Bot / unknown brands."""
    size = max(24, int(size))
    col = col or st.PALETTE["blue"]
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((1, 1, size - 2, size - 2), radius=int(size * 0.28), fill=col)
    label = (name or "?").strip()
    if len(label) > 8:
        parts = [p for p in label.split() if p]
        label = "".join(p[0] for p in parts[:2]).upper() if parts else "?"
    # fit text
    for sz in (int(size * 0.38), int(size * 0.32), int(size * 0.26), 11):
        f = st.font(max(10, sz), 800)
        tw, th = st.text_wh(f, label)
        if tw <= size - 8:
            d.text((size / 2, size / 2 + 1), label, font=f, fill=st.PALETTE["white"], anchor="mm")
            break
    return im


def get_logo(name: str, size: int = 64, col=None, allow_badge: bool = True) -> Image.Image | None:
    """Return a transparent RGBA logo. Brand marks from Simple Icons; else a text badge (or None)."""
    if not name:
        return None
    slug = resolve_slug(name)
    if slug:
        im = _logo_png(slug, size)
        if im is not None:
            if im.size != (size, size):
                im = im.resize((size, size), Image.LANCZOS)
            return im
    if allow_badge:
        return text_badge(name, size, col=col)
    return None


def looks_like_brand(name: str) -> bool:
    return resolve_slug(name) is not None
