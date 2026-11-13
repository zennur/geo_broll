"""Motion, cards, charts, and background helpers for geo_broll v3."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter, ImageChops

import style as st

# Dark card fills (poster-like)
CARD = (17, 17, 17)
CARD_ELEV = (26, 26, 28)
CARD_ALT = (14, 16, 22)


def spring(t: float, omega: float = 14.0, zeta: float = 0.62) -> float:
    """Underdamped spring from 0 to 1, with overshoot. t is elapsed/duration (>=0)."""
    t = max(0.0, float(t))
    if t == 0:
        return 0.0
    if zeta >= 0.999:
        return 1.0 - math.exp(-omega * t)
    wd = omega * math.sqrt(max(1e-6, 1.0 - zeta * zeta))
    return 1.0 - math.exp(-zeta * omega * t) * (
        math.cos(wd * t) + (zeta * omega / wd) * math.sin(wd * t)
    )


def spring_pop(t: float, start: float = 0.0, dur: float = 0.55):
    """Return (scale, opacity). Scale overshoots then settles at 1; opacity eases in faster."""
    if t < start:
        return 0.0, 0.0
    u = (t - start) / max(dur, 0.001)
    op = st.ease_out_cubic(st.clamp01(u / 0.42))
    sc = spring(min(u, 3.0) * 1.05, omega=13.5, zeta=0.62)
    sc = max(0.0, sc)
    return sc, op


def appear_back(t, start, dur=0.45):
    return st.appear(t, start, dur, "back")


def stagger(base: float, i: int, gap: float = 0.12) -> float:
    return base + i * gap


def scene_duration(scene: dict, default: float = 4.0) -> float:
    if scene.get("duration"):
        return float(scene["duration"])
    if scene.get("start") is not None and scene.get("end") is not None:
        return max(0.5, float(scene["end"]) - float(scene["start"]))
    return default


def beats_of(scene: dict, t: float, min_for_two: float = 3.0):
    """Return (beat_times, current_index, t_since_beat, duration)."""
    dur = scene_duration(scene)
    raw = scene.get("beats")
    if raw is None:
        if dur >= min_for_two:
            raw = [0.0, min(2.4, max(1.45, dur * 0.48))]
        else:
            raw = [0.0]
    times = [float(b) for b in raw]
    if not times:
        times = [0.0]
    idx = 0
    for i, b in enumerate(times):
        if t >= b:
            idx = i
    return times, idx, t - times[idx], dur


def safe():
    return st.SAFE_TOP, st.SAFE_BOTTOM, st.SAFE_LEFT, st.SAFE_RIGHT, st.SAFE_W, st.SAFE_H


def type_max(base: int) -> int:
    """Bump type when the safe band is taller than the cramped overlay layout (~630px)."""
    _t, _b, _l, _r, _w, sh = safe()
    if sh >= 1100:
        return int(round(base * 1.22))
    if sh >= 800:
        return int(round(base * 1.1))
    return int(base)


_grid_tile = None
_static_rgb = None


def _static_base() -> Image.Image:
    global _static_rgb
    if _static_rgb is None:
        # use the original static bg (no motion)
        _static_rgb = st.make_background()
    return _static_rgb


def _moving_grid_sheet() -> Image.Image:
    global _grid_tile
    if _grid_tile is not None:
        return _grid_tile
    step = 80
    sheet = Image.new("RGBA", (st.W + step, st.H + step), (0, 0, 0, 0))
    g = ImageDraw.Draw(sheet)
    for y in range(0, sheet.size[1], step):
        g.line([(0, y), (sheet.size[0], y)], fill=(255, 255, 255, 16), width=1)
    for x in range(0, sheet.size[0], step):
        g.line([(x, 0), (x, sheet.size[1])], fill=(255, 255, 255, 16), width=1)
    for y in range(0, sheet.size[1], step):
        for x in range(0, sheet.size[0], step):
            g.ellipse((x - 1, y - 1, x + 2, y + 2), fill=(255, 255, 255, 26))
    _grid_tile = sheet
    return sheet


def canvas(t: float = 0.0) -> Image.Image:
    """Full-frame RGBA background with a drifting grid and slow color glows."""
    im = _static_base().convert("RGBA")
    step = 80
    ox = int((t * 14) % step)
    oy = int((t * 9) % step)
    sheet = _moving_grid_sheet()
    grid = sheet.crop((step - ox, step - oy, step - ox + st.W, step - oy + st.H))
    # the static bg already has a grid; keep this one slightly stronger so motion reads
    im.alpha_composite(grid)
    # drifting glows so the frame is never frozen
    st.paste_glow(
        im,
        220 + 90 * math.sin(t * 0.45),
        380 + 50 * math.cos(t * 0.33),
        240,
        st.PALETTE["blue"],
        alpha=36,
    )
    st.paste_glow(
        im,
        860 + 70 * math.cos(t * 0.28),
        620 + 60 * math.sin(t * 0.37),
        260,
        st.PALETTE["violet"],
        alpha=28,
    )
    st.paste_glow(
        im,
        540 + 40 * math.sin(t * 0.22),
        200 + 20 * math.cos(t * 0.4),
        180,
        st.PALETTE["pink"],
        alpha=18,
    )
    return im


def soft_card(
    w: int,
    h: int,
    radius: int = 28,
    fill=CARD,
    outline=None,
    width: int = 3,
    glow=None,
    glow_a: int = 80,
    shadow: bool = True,
) -> tuple[Image.Image, int]:
    """Rounded card with soft drop shadow and optional colored glow. Returns (layer, pad)."""
    w, h = int(w), int(h)
    pad = 30
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle((pad + 3, pad + 10, pad + w + 3, pad + h + 14), radius, fill=(0, 0, 0, 170))
        sh = sh.filter(ImageFilter.GaussianBlur(11))
        layer.alpha_composite(sh)
    if glow is not None:
        st.paste_glow(layer, pad + w / 2, pad + h / 2, int(min(w, h) * 0.48), glow, alpha=glow_a)
    d = ImageDraw.Draw(layer)
    box = (pad, pad, pad + w, pad + h)
    st.rounded_rect(d, box, radius, fill=fill)
    if outline is not None:
        st.rounded_rect(d, box, radius, outline=outline, width=width)
    return layer, pad


def apply_wipe(im: Image.Image, progress: float, direction: str = "left", softness: int = 18) -> Image.Image:
    """Reveal an RGBA layer with a soft mask wipe. direction: left, right, up, down, circle."""
    p = st.ease_out_cubic(st.clamp01(progress))
    if p >= 0.999:
        return im
    if p <= 0.01:
        out = im.copy()
        out.putalpha(0)
        return out
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    if direction == "left":
        d.rectangle((0, 0, int(w * p), h), fill=255)
    elif direction == "right":
        d.rectangle((int(w * (1 - p)), 0, w, h), fill=255)
    elif direction == "up":
        d.rectangle((0, int(h * (1 - p)), w, h), fill=255)
    elif direction == "down":
        d.rectangle((0, 0, w, int(h * p)), fill=255)
    else:
        r = int(math.hypot(w, h) * 0.6 * p)
        cx, cy = w // 2, h // 2
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    if softness:
        mask = mask.filter(ImageFilter.GaussianBlur(softness))
    out = im.copy()
    if out.mode != "RGBA":
        out = out.convert("RGBA")
    r, g, b, a = out.split()
    a = ImageChops.multiply(a, mask)
    out.putalpha(a)
    return out


def paste_pop(dest: Image.Image, layer: Image.Image, x: int, y: int, scale: float, opacity: float):
    """Paste layer at top-left (x,y) of the *unscaled* image, scaling about its center."""
    if opacity <= 0.02 or scale <= 0.02:
        return
    w, h = layer.size
    src = layer
    if abs(scale - 1.0) > 0.008:
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        src = layer.resize((nw, nh), Image.LANCZOS)
        x = int(x - (nw - w) / 2)
        y = int(y - (nh - h) / 2)
    if opacity < 0.999:
        src = st.apply_opacity(src, opacity)
    dest.alpha_composite(src, (int(x), int(y)))


def count_value(t: float, start: float, dur: float, begin: float, end: float) -> float:
    p = st.ease_out_cubic(st.clamp01((t - start) / max(dur, 0.001)))
    return begin + (end - begin) * p


def format_number(n: float, suffix: str = "", decimals: int | None = None) -> str:
    suffix = suffix or ""
    if decimals is not None:
        txt = f"{n:.{decimals}f}"
    else:
        # integer unless the endpoints clearly want a decimal
        if abs(n - round(n)) < 0.05:
            txt = f"{int(round(n))}"
        else:
            txt = f"{n:.1f}"
    return f"{txt}{suffix}"


def draw_donut(layer: Image.Image, cx, cy, radius, thickness, progress, col, track=(42, 44, 52)):
    d = ImageDraw.Draw(layer)
    bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
    # track
    d.arc(bbox, start=0, end=360, fill=track, width=int(thickness))
    prog = st.clamp01(progress)
    if prog > 0.002:
        # start at 12 o'clock
        d.arc(bbox, start=-90, end=-90 + 360 * prog, fill=col, width=int(thickness))
        # end cap
        ang = math.radians(-90 + 360 * prog)
        ex = cx + radius * math.cos(ang)
        ey = cy + radius * math.sin(ang)
        cap = max(2, int(thickness * 0.5))
        d.ellipse((ex - cap, ey - cap, ex + cap, ey + cap), fill=col)


def draw_gauge(layer: Image.Image, cx, cy, radius, value, left_col, right_col, needle_col=(255, 255, 255)):
    """Semicircle gauge, value 0..1 maps left (180deg) to right (0deg)."""
    d = ImageDraw.Draw(layer)
    thick = max(14, int(radius * 0.22))
    bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
    # left half of arc (180 to 90) left_col, right half (90 to 0) right_col — drawn as two arcs
    d.arc(bbox, start=180, end=270, fill=left_col, width=thick)
    d.arc(bbox, start=270, end=360, fill=right_col, width=thick)
    # needle
    v = st.clamp01(value)
    ang = math.radians(180 - 180 * v)
    nx = cx + (radius - thick * 0.15) * math.cos(ang)
    ny = cy - (radius - thick * 0.15) * math.sin(ang)
    # slightly thicker stem
    d.line((cx, cy, nx, ny), fill=needle_col, width=6)
    hub = max(8, int(radius * 0.1))
    d.ellipse((cx - hub, cy - hub, cx + hub, cy + hub), fill=needle_col)
    d.ellipse((cx - hub * 0.45, cy - hub * 0.45, cx + hub * 0.45, cy + hub * 0.45), fill=CARD)


def draw_bar(d: ImageDraw.ImageDraw, box, fill, track=(40, 42, 50), radius=10, progress=1.0):
    x0, y0, x1, y1 = [int(v) for v in box]
    st.rounded_rect(d, (x0, y0, x1, y1), radius, fill=track)
    p = st.clamp01(progress)
    if p <= 0.01:
        return
    # vertical bar grows upward
    top = int(y1 - (y1 - y0) * p)
    if y1 - top >= 4:
        st.rounded_rect(d, (x0, top, x1, y1), radius, fill=fill)


def draw_hbar(d: ImageDraw.ImageDraw, box, fill, track=(40, 42, 50), radius=8, progress=1.0):
    x0, y0, x1, y1 = [int(v) for v in box]
    st.rounded_rect(d, (x0, y0, x1, y1), radius, fill=track)
    p = st.clamp01(progress)
    if p <= 0.01:
        return
    right = int(x0 + (x1 - x0) * p)
    if right - x0 >= 4:
        st.rounded_rect(d, (x0, y0, right, y1), radius, fill=fill)


def check_badge(draw, cx, cy, size, col, progress=1.0):
    """Filled circle + check, for stamping onto cards."""
    st.draw_check(draw, cx, cy, size, col, progress=progress)


def title_block(im: Image.Image, text: str, t: float, start: float = 0.0, max_size: int = 68, align: str = "center"):
    """Draw a large title in the safe area. Returns the y just below the title (or SAFE_TOP if none)."""
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = safe()
    if not text:
        return TOP + 4
    sc, op = spring_pop(t, start, 0.45)
    if op <= 0:
        return TOP + 4
    max_size = type_max(max_size)
    min_sz = 40 if (BOTTOM - TOP) >= 1100 else 34
    f, lines, size, total, line_h = st.fit_text(
        text, SW - 16, 240, max_size, min_size=min_sz, weight=800, max_lines=2
    )
    rise = int((1 - min(1, sc)) * 18)
    top = TOP + 6 + rise
    layer = Image.new("RGBA", (st.W, st.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = st.with_alpha(st.PALETTE["white"], int(255 * op))
    x = st.W // 2 if align == "center" else LEFT
    st.draw_lines(d, x, top, lines, f, col, line_h, align=align)
    im.alpha_composite(layer)
    return TOP + 6 + total + 22


def kicker_pill(im, text, t, start, x, y, col, logo=None):
    """Small colored pill, left at (x,y) top-left of visual (not including shadow pad)."""
    if not text:
        return 0
    sc, op = spring_pop(t, start, 0.4)
    if op <= 0:
        return 0
    f = st.font(22, 700)
    tw, th = st.text_wh(f, text)
    h = 44
    w = tw + 36 + (36 if logo is not None else 0)
    layer, pad = soft_card(int(w), h, radius=22, fill=st.mix(col, CARD, 0.15), outline=col, width=2, glow=col, glow_a=50, shadow=False)
    d = ImageDraw.Draw(layer)
    tx = pad + 18
    if logo is not None:
        ic = logo.resize((26, 26), Image.LANCZOS)
        if ic.mode != "RGBA":
            ic = ic.convert("RGBA")
        layer.alpha_composite(ic, (pad + 12, pad + (h - 26) // 2))
        tx = pad + 44
    d.text((tx, pad + h / 2), text, font=f, fill=st.PALETTE["white"], anchor="lm")
    paste_pop(im, layer, int(x - pad), int(y - pad), sc, op)
    return w


def initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p and p[0].isalnum()]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()
