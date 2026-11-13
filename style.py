"""Shared style, typography, easing, and drawing primitives for geo_broll."""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"

W, H = 1080, 1920
FPS = 30
SAFE_TOP = 230          # keep clear of platform UI (~12%)
SAFE_BOTTOM = 1536      # keep clear of captions / platform UI (~20%)
SAFE_LEFT = 64
SAFE_RIGHT = 1016
SAFE_W = SAFE_RIGHT - SAFE_LEFT
SAFE_H = SAFE_BOTTOM - SAFE_TOP

PALETTE = {
    "blue": (21, 128, 255),
    "orange": (255, 106, 0),
    "pink": (255, 46, 154),
    "amber": (255, 154, 0),
    "teal": (0, 184, 165),
    "violet": (139, 92, 246),
    "white": (255, 255, 255),
    "gray": (163, 169, 180),
    "muted": (110, 116, 128),
    "dark": (18, 20, 28),
    "black": (0, 0, 0),
    "card": (12, 14, 20),
}
CYCLE = ["blue", "orange", "pink", "amber", "teal", "violet"]


def apply_insets(safe_top=None, safe_bottom=None, safe_left=None, safe_right=None):
    """Override safe-zone insets for a spec (e.g. to clear Style Agent callouts)."""
    global SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT, SAFE_W, SAFE_H
    if safe_top is not None:
        SAFE_TOP = int(safe_top)
    if safe_bottom is not None:
        SAFE_BOTTOM = int(safe_bottom)
    if safe_left is not None:
        SAFE_LEFT = int(safe_left)
    if safe_right is not None:
        SAFE_RIGHT = int(safe_right)
    SAFE_W = SAFE_RIGHT - SAFE_LEFT
    SAFE_H = SAFE_BOTTOM - SAFE_TOP
    # templates.py imports these as names; keep them in sync
    import sys
    for name, mod in list(sys.modules.items()):
        if name == "templates" or name.endswith(".templates"):
            for k in ("SAFE_TOP", "SAFE_BOTTOM", "SAFE_LEFT", "SAFE_RIGHT", "SAFE_W", "SAFE_H"):
                if hasattr(mod, k):
                    setattr(mod, k, globals()[k])
    return SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT
def _first_font(*candidates) -> str | None:
    for c in candidates:
        if not c:
            continue
        path = Path(c)
        if path.is_file():
            return str(path)
    return None


INTER = _first_font(
    FONTS / "Inter" / "Inter-VariableFont_opsz,wght.ttf",
)
LIBERATION_BOLD = _first_font(
    FONTS / "LiberationSans" / "LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
LIBERATION = _first_font(
    FONTS / "LiberationSans" / "LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def apply_palette(updates: dict | None):
    """Merge a spec-provided palette into the module-level PALETTE.

    Values may be '#RRGGBB' strings, RGB tuples, or existing palette names.
    Unknown keys are added; known keys are overwritten for this process.
    """
    if not updates:
        return PALETTE
    for key, val in updates.items():
        PALETTE[str(key)] = color(val, default="blue")
    return PALETTE

_font_cache: dict[tuple, ImageFont.FreeTypeFont] = {}
_bg_cache: Image.Image | None = None
_glow_cache: dict[tuple, Image.Image] = {}


def color(name_or_rgb, default="blue"):
    if isinstance(name_or_rgb, (tuple, list)) and len(name_or_rgb) >= 3:
        return tuple(int(c) for c in name_or_rgb[:3])
    if isinstance(name_or_rgb, str):
        key = name_or_rgb.strip().lower()
        if key.startswith("#") and len(key) == 7:
            return tuple(int(key[i : i + 2], 16) for i in (1, 3, 5))
        if key in PALETTE:
            return PALETTE[key]
    return PALETTE[default]


def cycle_color(i: int):
    return color(CYCLE[i % len(CYCLE)])


def font(size: int, weight: int = 700, opsz: int | None = None) -> ImageFont.FreeTypeFont:
    size = max(10, int(size))
    weight = int(weight)
    if opsz is None:
        opsz = 32 if size >= 56 else 18 if size >= 28 else 14
    key = (size, weight, int(opsz))
    f = _font_cache.get(key)
    if f is None:
        try:
            if not INTER:
                raise FileNotFoundError("bundled Inter not found")
            f = ImageFont.truetype(INTER, size)
            f.set_variation_by_axes([float(opsz), float(weight)])
        except Exception:
            path = (LIBERATION_BOLD if weight >= 600 else LIBERATION) or "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            f = ImageFont.truetype(path, size)
        _font_cache[key] = f
    return f


def clamp01(t: float) -> float:
    return 0.0 if t <= 0 else 1.0 if t >= 1 else float(t)


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t: float) -> float:
    t = clamp01(t)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def appear(t: float, start: float, dur: float = 0.35, kind: str = "cubic") -> float:
    k = clamp01((t - start) / max(dur, 0.001))
    return ease_out_back(k) if kind == "back" else ease_out_cubic(k)


def mix(c1, c2, t: float):
    t = clamp01(t)
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def with_alpha(c, a: int):
    return (c[0], c[1], c[2], int(max(0, min(255, a))))


def text_bbox(font_obj, text: str):
    if not text:
        return (0, 0, 0, 0)
    return font_obj.getbbox(text)


def text_wh(font_obj, text: str):
    b = text_bbox(font_obj, text)
    return b[2] - b[0], b[3] - b[1]


def wrap_text(text: str, font_obj, max_width: int, max_lines: int = 3) -> list[str]:
    text = " ".join((text or "").split())
    if not text:
        return []
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = w if not cur else cur + " " + w
        if text_wh(font_obj, trial)[0] <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) <= max_lines:
        return lines
    # collapse overflow into last allowed line with an ellipsis if needed
    kept = lines[: max_lines - 1]
    rest = " ".join(lines[max_lines - 1 :])
    ell = rest
    while ell and text_wh(font_obj, ell + "…")[0] > max_width:
        ell = ell[:-1].rstrip()
    kept.append((ell + "…") if ell != rest else rest)
    return kept


def fit_text(
    text: str,
    max_w: int,
    max_h: int,
    max_size: int,
    min_size: int = 22,
    weight: int = 700,
    max_lines: int = 3,
    line_gap: float = 0.22,
):
    """Return (font, lines, size, total_h, line_h). Shrinks until it fits."""
    text = (text or "").strip()
    if not text:
        f = font(min_size, weight)
        return f, [], min_size, 0, 0
    size = max_size
    while size >= min_size:
        f = font(size, weight)
        lines = wrap_text(text, f, max_w, max_lines)
        # if a single word overflowed past max_w, wrap_text may still be wide
        widest = max((text_wh(f, ln)[0] for ln in lines), default=0)
        line_h = int(size * (1 + line_gap))
        total = line_h * len(lines) - int(size * line_gap)
        if widest <= max_w + 1 and total <= max_h:
            return f, lines, size, total, line_h
        size -= 2
    f = font(min_size, weight)
    lines = wrap_text(text, f, max_w, max_lines)
    line_h = int(min_size * (1 + line_gap))
    total = line_h * max(len(lines), 1) - int(min_size * line_gap)
    return f, lines, min_size, total, line_h


def draw_lines(draw, cx, top, lines, font_obj, fill, line_h, align="center"):
    y = top
    for ln in lines:
        if align == "center":
            draw.text((cx, y), ln, font=font_obj, fill=fill, anchor="mt")
        elif align == "left":
            draw.text((cx, y), ln, font=font_obj, fill=fill, anchor="lt")
        else:
            draw.text((cx, y), ln, font=font_obj, fill=fill, anchor="rt")
        y += line_h
    return y


def make_background() -> Image.Image:
    global _bg_cache
    if _bg_cache is not None:
        return _bg_cache.copy()
    im = Image.new("RGB", (W, H), (0, 0, 0))
    # subtle vignette via a small blur, then paste
    vig = Image.new("RGB", (W // 8, H // 8), (0, 0, 0))
    pv = vig.load()
    cw, ch = vig.size[0] / 2, vig.size[1] * 0.44
    for y in range(vig.size[1]):
        for x in range(vig.size[0]):
            d = math.hypot((x - cw) / vig.size[0], (y - ch) / vig.size[1])
            v = int(max(0, 22 - d * 36))
            pv[x, y] = (v, v, int(v * 1.1))
    vig = vig.resize((W, H), Image.LANCZOS)
    im = ImageChops.add(im, vig)
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    step = 80
    for y in range(0, H, step):
        g.line([(0, y), (W, y)], fill=(255, 255, 255, 12), width=1)
    for x in range(0, W, step):
        g.line([(x, 0), (x, H)], fill=(255, 255, 255, 12), width=1)
    for y in range(0, H, step):
        for x in range(0, W, step):
            g.ellipse((x - 1, y - 1, x + 2, y + 2), fill=(255, 255, 255, 22))
    im = Image.alpha_composite(im.convert("RGBA"), grid).convert("RGB")
    _bg_cache = im
    return im.copy()


def glow_sprite(radius: int, col, alpha: int = 140) -> Image.Image:
    radius = max(8, int(radius))
    key = (radius, col, alpha)
    if key in _glow_cache:
        return _glow_cache[key]
    side = int(radius * 2.8)
    layer = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    m = side / 2
    d.ellipse((m - radius, m - radius, m + radius, m + radius), fill=with_alpha(col, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=radius * 0.4))
    _glow_cache[key] = layer
    return layer


def paste_glow(base: Image.Image, cx: float, cy: float, radius: int, col, alpha: int = 140, scale: float = 1.0):
    if scale <= 0.02:
        return
    spr = glow_sprite(int(radius * scale), col, int(alpha * clamp01(scale)))
    x = int(cx - spr.size[0] / 2)
    y = int(cy - spr.size[1] / 2)
    if base.mode != "RGBA":
        raise ValueError("paste_glow expects RGBA")
    base.alpha_composite(spr, (x, y))


def rounded_rect(draw, box, radius, fill=None, outline=None, width=3):
    x0, y0, x1, y1 = box
    r = max(0, min(radius, (x1 - x0) / 2, (y1 - y0) / 2))
    if fill is not None:
        draw.rounded_rectangle(box, radius=r, fill=fill)
    if outline is not None:
        draw.rounded_rectangle(box, radius=r, outline=outline, width=width)


def hex_points(cx, cy, r, rot=-math.pi / 2):
    return [
        (cx + r * math.cos(rot + 2 * math.pi * i / 6), cy + r * math.sin(rot + 2 * math.pi * i / 6))
        for i in range(6)
    ]


def draw_badge(draw, cx, cy, r, kind, col, scale=1.0):
    """Small geometric badge: circle, squircle, hex, pill, diamond."""
    r = r * scale
    if r < 2:
        return
    ring = mix(col, PALETTE["white"], 0.35)
    if kind == "hex":
        draw.polygon(hex_points(cx, cy, r + 3), outline=ring)
        draw.polygon(hex_points(cx, cy, r), fill=col)
        draw.polygon(hex_points(cx, cy, r * 0.42), fill=PALETTE["dark"])
    elif kind == "diamond":
        pts = [
            (cx, cy - r - 2),
            (cx + r + 2, cy),
            (cx, cy + r + 2),
            (cx - r - 2, cy),
        ]
        draw.polygon(pts, outline=ring)
        draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=col)
        ir = r * 0.38
        draw.polygon([(cx, cy - ir), (cx + ir, cy), (cx, cy + ir), (cx - ir, cy)], fill=PALETTE["dark"])
    elif kind == "pill":
        box = (cx - r * 1.15, cy - r * 0.7, cx + r * 1.15, cy + r * 0.7)
        rounded_rect(draw, (box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3), r * 0.7, outline=ring, width=3)
        rounded_rect(draw, box, r * 0.62, fill=col)
        irx, iry = r * 0.38, r * 0.26
        rounded_rect(draw, (cx - irx, cy - iry, cx + irx, cy + iry), iry, fill=PALETTE["dark"])
    elif kind == "circle":
        draw.ellipse((cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3), outline=ring, width=3)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
        ir = r * 0.42
        draw.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), fill=PALETTE["dark"])
    else:  # squircle
        box = (cx - r, cy - r, cx + r, cy + r)
        rounded_rect(draw, (box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3), r * 0.45, outline=ring, width=3)
        rounded_rect(draw, box, r * 0.38, fill=col)
        ir = r * 0.38
        rounded_rect(draw, (cx - ir, cy - ir, cx + ir, cy + ir), ir * 0.4, fill=PALETTE["dark"])


def draw_arrow(draw, p1, p2, col, width=5, progress=1.0, head=True):
    progress = clamp01(progress)
    if progress <= 0.02:
        return
    x1, y1 = p1
    x2, y2 = p2
    xe = x1 + (x2 - x1) * progress
    ye = y1 + (y2 - y1) * progress
    glow = mix(col, PALETTE["white"], 0.35)
    draw.line((x1, y1, xe, ye), fill=with_alpha(col, 220) if len(col) == 4 else col, width=width + 6)
    draw.line((x1, y1, xe, ye), fill=glow, width=width)
    if head and progress > 0.55:
        ang = math.atan2(y2 - y1, x2 - x1)
        s = 16 + width
        left = (xe - s * math.cos(ang - 0.45), ye - s * math.sin(ang - 0.45))
        right = (xe - s * math.cos(ang + 0.45), ye - s * math.sin(ang + 0.45))
        tip = (xe + 6 * math.cos(ang), ye + 6 * math.sin(ang))
        draw.polygon([tip, left, right], fill=glow)


def packet_pos(p1, p2, t):
    return (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)


def draw_packet(draw, xy, col, w=54, h=36, scale=1.0):
    if scale <= 0.05:
        return
    x, y = xy
    w, h = w * scale, h * scale
    rounded_rect(
        draw,
        (x - w / 2, y - h / 2, x + w / 2, y + h / 2),
        8,
        fill=PALETTE["dark"],
        outline=col,
        width=3,
    )
    # tiny color bar, no letters
    rounded_rect(
        draw,
        (x - w / 2 + 6, y - h / 2 + 5, x + w / 2 - 6, y - h / 2 + 11),
        3,
        fill=col,
    )


def draw_check(draw, cx, cy, size, col, progress=1.0):
    """Rounded box that fills, then a check mark draws."""
    s = size / 2
    box = (cx - s, cy - s, cx + s, cy + s)
    rounded_rect(draw, box, 10, fill=PALETTE["dark"], outline=col, width=4)
    if progress <= 0:
        return
    fill_p = clamp01(progress / 0.45)
    if fill_p > 0:
        inner = (cx - s + 5, cy - s + 5, cx + s - 5, cy + s - 5)
        # simulate fill with a smaller rect growing
        mid_y = inner[3] - (inner[3] - inner[1]) * fill_p
        if fill_p >= 1:
            rounded_rect(draw, inner, 6, fill=col)
        else:
            # clip-like: draw full then we just fill from bottom
            rounded_rect(draw, (inner[0], mid_y, inner[2], inner[3]), 6, fill=col)
    mark = clamp01((progress - 0.4) / 0.6)
    if mark > 0:
        # check path: left dip to right tip
        p1 = (cx - s * 0.36, cy + s * 0.02)
        p2 = (cx - s * 0.06, cy + s * 0.32)
        p3 = (cx + s * 0.40, cy - s * 0.30)
        # two segments, first 35% then 65%
        white = PALETTE["white"]
        if mark < 0.35:
            t = mark / 0.35
            xe = p1[0] + (p2[0] - p1[0]) * t
            ye = p1[1] + (p2[1] - p1[1]) * t
            draw.line((p1, (xe, ye)), fill=white, width=6)
        else:
            draw.line((p1, p2), fill=white, width=6)
            t = (mark - 0.35) / 0.65
            xe = p2[0] + (p3[0] - p2[0]) * t
            ye = p2[1] + (p3[1] - p2[1]) * t
            draw.line((p2, (xe, ye)), fill=white, width=6)


def apply_opacity(im: Image.Image, a: float) -> Image.Image:
    a = clamp01(a)
    if a >= 0.999:
        return im
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    r, g, b, al = im.split()
    al = al.point(lambda p: int(p * a))
    im.putalpha(al)
    return im


def scale_around(im: Image.Image, scale: float, cx: int, cy: int, canvas_size=None):
    """Scale a full-frame RGBA layer around (cx, cy)."""
    if abs(scale - 1) < 0.01:
        return im
    scale = max(0.01, scale)
    nw, nh = int(im.width * scale), int(im.height * scale)
    resized = im.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGBA", im.size if canvas_size is None else canvas_size, (0, 0, 0, 0))
    # the point (cx,cy) on original should stay at (cx,cy)
    x = int(cx - cx * scale)
    y = int(cy - cy * scale)
    out.alpha_composite(resized, (x, y))
    return out
