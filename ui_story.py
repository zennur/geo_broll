"""Rich UI-storytelling templates for geo_broll (v4).

These are reusable, spec-driven scenes that look like product UI rather than
sparse typographic cards:

  live_scan       — QA runner window, scanner beam, pass/fail ticks
  shield          — bugs stream from a codebase toward a Users device, then a shield traps them
  artifact_morph  — a bug ticket unfolds and morphs into a pull-request card
  merge_toggle    — reviewer toggle, approval stamp, branch merge

Labels come from the scene spec. Defaults are generic QA-runner chrome
(module names, branch pills, stylized snippets) and must not introduce
spoken statistics or third-party brand marks. Grok Bot is always a text badge.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import style as st
import motion as mo

PALETTE = st.PALETTE
BLUE = PALETTE["blue"]
ORANGE = PALETTE["orange"]
PINK = PALETTE["pink"]
AMBER = PALETTE["amber"]
TEAL = PALETTE["teal"]
VIOLET = PALETTE["violet"]
WHITE = PALETTE["white"]
GRAY = PALETTE["gray"]
MUTED = PALETTE["muted"]

# Poster surfaces
SURF = (17, 19, 24)       # #111318
SURF2 = (22, 25, 34)      # #161922
SURF3 = (28, 32, 42)
SURF4 = (10, 12, 16)
FAIL = (255, 58, 96)

_FONTS = Path(__file__).resolve().parent / "fonts"
JETBRAINS = next(
    (
        str(p)
        for p in (
            _FONTS / "JetBrainsMono" / "JetBrainsMono-VariableFont_wght.ttf",
        )
        if p.is_file()
    ),
    None,
)
PLEX = next(
    (
        str(p)
        for p in (
            _FONTS / "LiberationMono" / "LiberationMono-Regular.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"),
        )
        if p.is_file()
    ),
    None,
)
PLEX_BOLD = next(
    (
        str(p)
        for p in (
            _FONTS / "LiberationMono" / "LiberationMono-Bold.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"),
        )
        if p.is_file()
    ),
    PLEX,
)

_mono_cache: dict[tuple, ImageFont.FreeTypeFont] = {}


def mono(size: int, weight: int = 500) -> ImageFont.FreeTypeFont:
    size = max(10, int(size))
    key = (size, int(weight))
    f = _mono_cache.get(key)
    if f is None:
        try:
            if not JETBRAINS:
                raise FileNotFoundError("bundled JetBrains Mono not found")
            f = ImageFont.truetype(JETBRAINS, size)
            try:
                f.set_variation_by_axes([float(weight)])
            except Exception:
                pass
        except Exception:
            path = (PLEX_BOLD if weight >= 600 else PLEX) or str(
                Path(__file__).resolve().parent / "fonts" / "LiberationSans" / "LiberationSans-Regular.ttf"
            )
            f = ImageFont.truetype(path, size)
        _mono_cache[key] = f
    return f


TEMPLATES = ("live_scan", "shield", "artifact_morph", "merge_toggle")


def _beats(scene, t):
    return mo.beats_of(scene, t)


def _items(scene, *keys):
    for k in keys:
        v = scene.get(k)
        if v:
            return list(v)
    return []


def _lab(item, fallback=""):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("label") or item.get("title") or item.get("text") or fallback
    return fallback or str(item)


def _sub(item, fallback=""):
    if isinstance(item, dict):
        return item.get("sub") or item.get("subtitle") or item.get("endpoint") or fallback
    return fallback


def _col(item, default="blue"):
    if isinstance(item, dict) and item.get("color"):
        return st.color(item["color"])
    return st.color(default)


def _pill(d, box, fill, text, font, text_col=WHITE, radius=None):
    x0, y0, x1, y1 = [int(v) for v in box]
    h = max(2, y1 - y0)
    r = radius if radius is not None else h // 2
    st.rounded_rect(d, (x0, y0, x1, y1), r, fill=fill)
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), text, font=font, fill=text_col, anchor="mm")


def _traffic_lights(d, x, y, r=7, gap=22):
    for i, col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        cx = x + i * gap
        d.ellipse((cx - r, y - r, cx + r, y + r), fill=col)


def _gb_badge(layer, x, y, size, col=BLUE):
    """Draw a Grok Bot initials tile at top-left (x, y). Returns right edge."""
    d = ImageDraw.Draw(layer)
    s = int(size)
    st.rounded_rect(d, (x, y, x + s, y + s), int(s * 0.28), fill=col)
    d.text((x + s / 2, y + s / 2 + 1), "GB", font=st.font(int(s * 0.42), 800), fill=WHITE, anchor="mm")
    return x + s


def _syntax_bars(d, x, y, widths, colors, h=10, gap=8, max_w=400):
    """Stylized code/endpoint bars (no numerals)."""
    cy = y
    for w, col in zip(widths, colors):
        ww = int(max_w * w)
        st.rounded_rect(d, (x, cy, x + ww, cy + h), h // 2, fill=col)
        cy += h + gap
    return cy


def _code_line(d, x, y, chunks, size=18, weight=500):
    """chunks: list of (text, color). Returns next y."""
    f = mono(size, weight)
    cx = x
    # measure height
    _, th = st.text_wh(f, "Ag")
    for txt, col in chunks:
        d.text((cx, y), txt, font=f, fill=col, anchor="lm")
        tw, _ = st.text_wh(f, txt)
        cx += tw
    return y + int(th * 1.55)


def _window_shell(w, h, title, t, start=0.0, accent=BLUE, live=False, subtitle=""):
    """Return (layer, pad, content_box) for a mac-style dark app window."""
    sc, op = mo.spring_pop(t, start, 0.55)
    layer, pad = mo.soft_card(
        int(w), int(h), radius=36, fill=SURF,
        outline=st.mix(accent, WHITE, 0.22), width=3,
        glow=accent, glow_a=70,
    )
    d = ImageDraw.Draw(layer)
    bar_h = 92
    # title bar
    st.rounded_rect(d, (pad, pad, pad + w, pad + bar_h), 30, fill=SURF2)
    d.rectangle((pad, pad + bar_h - 28, pad + w, pad + bar_h), fill=SURF2)
    # hairline
    d.rectangle((pad, pad + bar_h, pad + w, pad + bar_h + 2), fill=st.mix(accent, SURF, 0.55))
    _traffic_lights(d, pad + 28, pad + bar_h / 2, r=8, gap=26)
    badge_s = 48
    bx = pad + 28 + 3 * 26 + 18
    by = pad + (bar_h - badge_s) // 2
    _gb_badge(layer, bx, by, badge_s, accent)
    title_x = bx + badge_s + 16
    d.text((title_x, pad + bar_h / 2 - (14 if subtitle else 0)), title,
           font=st.font(32, 800), fill=WHITE, anchor="lm")
    if subtitle:
        d.text((title_x, pad + bar_h / 2 + 20), subtitle,
               font=st.font(18, 600), fill=st.mix(WHITE, GRAY, 0.25), anchor="lm")
    if live:
        lf = st.font(16, 800)
        tw, _ = st.text_wh(lf, "LIVE")
        _pill(d, (pad + w - 28 - tw - 36, pad + (bar_h - 32) / 2, pad + w - 28, pad + (bar_h + 32) / 2),
              TEAL, "LIVE", lf, WHITE)
        # pulse dot
        pulse = 0.55 + 0.45 * math.sin(t * 7.0)
        cx = pad + w - 28 - tw - 36 - 16
        cy = pad + bar_h / 2
        rr = int(5 + 2 * pulse)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=st.with_alpha(TEAL, int(200 * pulse + 55)))
    content = (pad, pad + bar_h + 2, pad + w, pad + h)
    return layer, pad, content, sc, op


# ---------------------------------------------------------------------------
# live_scan
# ---------------------------------------------------------------------------

_DEFAULT_MODULES = [
    {"label": "Auth Flow", "sub": "POST /session", "color": "teal", "snippet": "await signIn(user)"},
    {"label": "Checkout", "sub": "POST /checkout", "color": "blue", "snippet": "expect(cart).ok()"},
    {"label": "API Endpoints", "sub": "GET /v1/items", "color": "violet", "snippet": "request('/v1/items')"},
]


def render_live_scan(scene, t):
    im = mo.canvas(t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = mo.safe()
    beats, bidx, tloc, dur = _beats(scene, t)
    b1 = beats[0] if beats else 0.0
    b2 = beats[1] if len(beats) > 1 else 2.0
    b3 = beats[2] if len(beats) > 2 else 3.8

    title = scene.get("title") or scene.get("window_title") or "Grok Bot · QA Runner"
    kicker = scene.get("kicker") or "QA Testing"
    modules = _items(scene, "modules", "rows", "items") or list(_DEFAULT_MODULES)
    fail_at = int(scene.get("fail_index", 1))  # Checkout by default
    fail_at = max(0, min(fail_at, len(modules) - 1))

    # Window fills the safe band
    win_w, win_h = SW, BOTTOM - TOP - 8
    layer, pad, content, sc, op = _window_shell(
        win_w, win_h, title, t, start=0.0, accent=BLUE, live=True, subtitle="Software development"
    )
    d = ImageDraw.Draw(layer)
    cx0, cy0, cx1, cy1 = content
    inner_w = cx1 - cx0
    inner_h = cy1 - cy0

    # Status strip
    strip_h = 64
    st.rounded_rect(d, (cx0, cy0, cx1, cy0 + strip_h), 0, fill=SURF4)
    status_txt = "Scanning modules…"
    status_col = TEAL
    if t >= b2:
        status_txt = "Issue flagged"
        status_col = FAIL
    if t >= b3:
        status_txt = "Issue flagged"
        status_col = FAIL
    # live dots
    for i in range(3):
        dx = cx0 + 28 + i * 18
        on = 0.35 + 0.65 * max(0, math.sin(t * 6 - i * 0.9))
        col = status_col if t >= b2 and i == fail_at % 3 else TEAL
        d.ellipse((dx - 5, cy0 + strip_h / 2 - 5, dx + 5, cy0 + strip_h / 2 + 5),
                  fill=st.with_alpha(col, int(80 + 175 * on)))
    d.text((cx0 + 90, cy0 + strip_h / 2), status_txt, font=st.font(26, 800), fill=WHITE, anchor="lm")

    # Footer arrives on beat 3; until then the rows fill the window.
    footer_h = 168
    reserved = 0
    if t >= b3:
        reserved = int(footer_h * st.ease_out_cubic(st.clamp01((t - b3) / 0.35)))
    rows_top = cy0 + strip_h + 16
    rows_bot = cy1 - 12 - reserved
    n = len(modules)
    gap = 14
    row_h = int((rows_bot - rows_top - gap * (n - 1)) / max(n, 1))
    row_h = max(150, row_h)

    # Scanner beam (beat 1, continues faintly)
    scan_span = max(0.8, b2 - 0.15)
    scan_p = st.clamp01((t - 0.15) / scan_span)
    if t < b3 + 0.4:
        beam_y = rows_top + scan_p * (rows_bot - rows_top)
        beam = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        st.paste_glow(beam, pad + win_w / 2, beam_y, 220, TEAL if t < b2 else BLUE, alpha=90 if t < b2 else 40)
        bd = ImageDraw.Draw(beam)
        bd.rectangle((cx0 + 8, int(beam_y - 3), cx1 - 8, int(beam_y + 3)), fill=st.with_alpha(TEAL, 200 if t < b2 else 80))
        # soft vertical fade band
        bd.rectangle((cx0 + 8, int(beam_y - 18), cx1 - 8, int(beam_y + 18)), fill=st.with_alpha(TEAL, 40))
        layer.alpha_composite(beam)

    # Tick timings: first rows pass after b2, fail row slightly later
    pass_times = []
    k = 0
    for i in range(n):
        if i == fail_at:
            pass_times.append(b2 + 0.55)
        else:
            pass_times.append(b2 + k * 0.28)
            k += 1

    for i, mod in enumerate(modules):
        y = rows_top + i * (row_h + gap)
        col = _col(mod, default=st.CYCLE[i % 6])
        label = _lab(mod, f"Module {i+1}")
        sub = _sub(mod, "")
        snippet = mod.get("snippet") if isinstance(mod, dict) else ""
        tick_t = pass_times[i]
        failed = i == fail_at and t >= tick_t
        passed = i != fail_at and t >= tick_t
        # row background
        fill = SURF2
        outline = st.mix(col, SURF, 0.45)
        if failed:
            pulse = 0.5 + 0.5 * math.sin((t - tick_t) * 6.5)
            fill = st.mix(FAIL, SURF, 0.82 + 0.08 * pulse)
            outline = FAIL
            st.paste_glow(layer, cx0 + inner_w / 2, y + row_h / 2, int(row_h * 0.7), FAIL, alpha=int(50 + 40 * pulse))
        elif passed:
            outline = TEAL
            fill = st.mix(TEAL, SURF2, 0.88)
        st.rounded_rect(d, (cx0 + 16, y, cx1 - 16, y + row_h), 24, fill=fill)
        st.rounded_rect(d, (cx0 + 16, y, cx1 - 16, y + row_h), 24, outline=outline, width=3)
        # left accent
        d.rounded_rectangle((cx0 + 16, y + 16, cx0 + 24, y + row_h - 16), 4, fill=FAIL if failed else (TEAL if passed else col))

        # module index tile
        tile = 56
        tx, ty = cx0 + 40, y + (row_h - tile) // 2
        st.rounded_rect(d, (tx, ty, tx + tile, ty + tile), 16, fill=st.mix(FAIL if failed else col, SURF, 0.25))
        d.text((tx + tile / 2, ty + tile / 2), str(i + 1), font=st.font(28, 800), fill=WHITE, anchor="mm")

        text_x = tx + tile + 20
        d.text((text_x, y + row_h * 0.28), label, font=st.font(36, 800), fill=WHITE, anchor="lm")
        if sub:
            # endpoint pill
            ef = mono(16, 600)
            etw, eth = st.text_wh(ef, sub)
            _pill(d, (text_x, y + row_h * 0.28 + 22, text_x + etw + 24, y + row_h * 0.28 + 22 + 28),
                  SURF4, sub, ef, st.mix(col, WHITE, 0.55), radius=8)
        if snippet:
            d.text((text_x, y + row_h * 0.76), snippet, font=mono(20, 500), fill=st.mix(WHITE, MUTED, 0.35), anchor="lm")

        # mini syntax bars on the mid-right of the row (behind the status mark)
        bar_x = text_x + 420 if inner_w > 800 else text_x + 300
        if bar_x < cx1 - 160:
            _syntax_bars(
                d, bar_x, y + row_h * 0.38,
                widths=(0.55, 0.38, 0.47),
                colors=(st.with_alpha(col, 160), st.with_alpha(WHITE, 50), st.with_alpha(VIOLET, 140)),
                h=9, gap=8, max_w=min(200, cx1 - 150 - bar_x),
            )

        # status mark on the right
        mx, my = cx1 - 70, y + row_h / 2
        mark_r = 28
        if t < tick_t:
            # pending ring
            d.ellipse((mx - mark_r, my - mark_r, mx + mark_r, my + mark_r), outline=MUTED, width=3)
        elif passed:
            pop = mo.spring(t - tick_t, omega=16, zeta=0.58)
            rr = int(mark_r * min(1.15, max(0.2, pop)))
            d.ellipse((mx - rr, my - rr, mx + rr, my + rr), fill=TEAL)
            # check
            fchk = st.font(int(32 * min(1, pop)), 800)
            d.text((mx, my + 1), "✓", font=fchk, fill=WHITE, anchor="mm")
        else:
            pop = mo.spring(t - tick_t, omega=16, zeta=0.55)
            rr = int(mark_r * min(1.15, max(0.2, pop)))
            d.ellipse((mx - rr, my - rr, mx + rr, my + rr), fill=FAIL)
            d.text((mx, my + 1), "✕", font=st.font(int(32 * min(1, pop)), 800), fill=WHITE, anchor="mm")

    # Beat 3 footer summary
    if t >= b3 - 0.02:
        sc3, op3 = mo.spring_pop(t, b3, 0.5)
        fy = cy1 - footer_h
        footer = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        fd = ImageDraw.Draw(footer)
        st.rounded_rect(fd, (cx0 + 16, fy, cx1 - 16, cy1 - 16), 24, fill=SURF3)
        st.rounded_rect(fd, (cx0 + 16, fy, cx1 - 16, cy1 - 16), 24, outline=AMBER, width=3)
        st.paste_glow(footer, pad + win_w / 2, fy + footer_h / 2, 200, AMBER, alpha=50)
        # badge
        bf = st.font(28, 800)
        badge = scene.get("summary") or "QA Testing · Active"
        btw, _ = st.text_wh(bf, badge)
        _pill(fd, (cx0 + 36, fy + 22, cx0 + 36 + btw + 40, fy + 70), AMBER, badge, bf, WHITE)
        # detail lines
        details = scene.get("details")
        if not details:
            details = []
            for i, mod in enumerate(modules):
                name = _lab(mod)
                if i == fail_at:
                    details.append((name, "Needs review", FAIL))
                else:
                    details.append((name, "Passed", TEAL))
        dx = cx0 + 36
        dy = fy + 88
        df = st.font(20, 700)
        for name, state, scol in details:
            fd.ellipse((dx, dy + 6, dx + 12, dy + 18), fill=scol)
            fd.text((dx + 20, dy + 12), f"{name}  ·  {state}", font=df, fill=WHITE, anchor="lm")
            dx += 300
            if dx > cx1 - 260:
                dx = cx0 + 36
                dy += 32
        # pop the footer
        # (already drawn on footer layer)
        footer = st.apply_opacity(footer, op3) if op3 < 0.999 else footer
        if abs(sc3 - 1) > 0.01:
            # scale around footer center
            pass
        layer.alpha_composite(footer)

    mo.paste_pop(im, layer, LEFT - pad, TOP + 4 - pad, sc, op)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# shield
# ---------------------------------------------------------------------------

_DEFAULT_CODE = [
    [("def ", VIOLET), ("scan", BLUE), ("(suite):", GRAY)],
    [("    ", WHITE), ("for ", VIOLET), ("case ", WHITE), ("in ", VIOLET), ("suite:", GRAY)],
    [("        ", WHITE), ("run", BLUE), ("(case)", GRAY)],
    [("        ", WHITE), ("if ", VIOLET), ("failed:", PINK)],
    [("            ", WHITE), ("capture", BLUE), ("(bug)", PINK)],
    [("    ", WHITE), ("report", BLUE), ("(suite)", GRAY)],
    [("assert ", VIOLET), ("user", WHITE), (".safe", TEAL)],
    [("queue ", GRAY), ("+= ", WHITE), ("findings", AMBER)],
    [("# before users see it", MUTED)],
    [("flush", BLUE), ("(quarantine)", AMBER)],
]


def _phone_mock(w, h, t, safe=False):
    """A tall dark mobile screen with a Users skeleton UI. Returns RGBA image."""
    im = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # device chrome
    st.rounded_rect(d, (0, 0, w, h), 42, fill=(8, 10, 14))
    st.rounded_rect(d, (0, 0, w, h), 42, outline=TEAL if safe else st.mix(BLUE, WHITE, 0.25), width=4)
    # screen
    inset = 10
    st.rounded_rect(d, (inset, inset, w - inset, h - inset), 34, fill=SURF)
    # status bar
    d.text((28, 28), "9:41", font=st.font(14, 700), fill=GRAY, anchor="lt")
    d.rounded_rectangle((w / 2 - 28, 20, w / 2 + 28, 28), 4, fill=(40, 44, 52))
    # header
    d.text((w / 2, 70), "Users", font=st.font(32, 800), fill=WHITE, anchor="mt")
    # status chip
    chip = "Safe" if safe else "Live"
    chip_col = TEAL if safe else BLUE
    cf = st.font(16, 800)
    tw, _ = st.text_wh(cf, chip)
    _pill(d, (w / 2 - (tw + 36) / 2, 112, w / 2 + (tw + 36) / 2, 144),
          st.mix(chip_col, SURF, 0.35), chip, cf, chip_col)
    if safe:
        # green wash
        wash = Image.new("RGBA", im.size, (0, 0, 0, 0))
        st.paste_glow(wash, w / 2, h * 0.45, int(w * 0.7), TEAL, alpha=80)
        im.alpha_composite(wash)
        d = ImageDraw.Draw(im)
    # feed cards
    cy = 168
    for i in range(3):
        st.rounded_rect(d, (22, cy, w - 22, cy + 150), 18, fill=SURF2)
        # avatar
        d.ellipse((36, cy + 18, 72, cy + 54), fill=st.mix(TEAL if safe else BLUE, SURF, 0.4))
        st.rounded_rect(d, (86, cy + 24, 86 + int((w - 140) * 0.62), cy + 36), 4, fill=(255, 255, 255, 50))
        st.rounded_rect(d, (86, cy + 44, 86 + int((w - 140) * 0.38), cy + 54), 4, fill=(255, 255, 255, 28))
        # body bars
        st.rounded_rect(d, (36, cy + 74, w - 36, cy + 86), 4, fill=(255, 255, 255, 28))
        st.rounded_rect(d, (36, cy + 96, w - 80, cy + 108), 4, fill=(255, 255, 255, 18))
        if safe:
            # tiny teal check on the card
            d.ellipse((w - 62, cy + 18, w - 34, cy + 46), fill=TEAL)
            d.text((w - 48, cy + 32), "✓", font=st.font(16, 800), fill=WHITE, anchor="mm")
        cy += 162
    # bottom nav
    nav_y = h - 58
    for i, cx in enumerate((w * 0.25, w * 0.5, w * 0.75)):
        r = 6 if i != 1 else 8
        d.ellipse((cx - r, nav_y - r, cx + r, nav_y + r), fill=TEAL if (safe and i == 1) else MUTED)
    return im


def _bug_icon(size, col=FAIL):
    s = int(size)
    im = Image.new("RGBA", (s + 16, s + 16), (0, 0, 0, 0))
    st.paste_glow(im, (s + 16) / 2, (s + 16) / 2, int(s * 0.7), col, alpha=120)
    d = ImageDraw.Draw(im)
    cx, cy, r = (s + 16) / 2, (s + 16) / 2, s * 0.32
    # body
    d.ellipse((cx - r, cy - r * 0.9, cx + r, cy + r * 0.9), fill=col)
    # head
    d.ellipse((cx - r * 0.55, cy - r * 1.25, cx + r * 0.55, cy - r * 0.35), fill=col)
    # antennae
    d.line((cx - 3, cy - r * 1.1, cx - r * 0.7, cy - r * 1.55), fill=col, width=2)
    d.line((cx + 3, cy - r * 1.1, cx + r * 0.7, cy - r * 1.55), fill=col, width=2)
    # legs
    for dx in (-1, 1):
        d.line((cx + dx * r * 0.8, cy - r * 0.15, cx + dx * r * 1.25, cy - r * 0.45), fill=col, width=2)
        d.line((cx + dx * r * 0.85, cy + r * 0.15, cx + dx * r * 1.3, cy + r * 0.15), fill=col, width=2)
        d.line((cx + dx * r * 0.8, cy + r * 0.45, cx + dx * r * 1.2, cy + r * 0.75), fill=col, width=2)
    return im


def render_shield(scene, t):
    im = mo.canvas(t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = mo.safe()
    beats, bidx, tloc, dur = _beats(scene, t)
    b1 = beats[0] if beats else 0.0
    b2 = beats[1] if len(beats) > 1 else 2.2
    title = scene.get("title") or "Before my users"
    y0 = mo.title_block(im, title, t, 0.0, max_size=64)

    avail_h = BOTTOM - y0 - 8
    # Layout: IDE left (full height), phone right, shield in the gap.
    # Caught tray slides up over the bottom of the IDE on beat 2.
    catch_h = 128
    phone_w = 360
    ide_w = int(SW - phone_w - 88)
    ide_h = avail_h
    phone_h = min(ide_h, 1040)
    ide_x, ide_y = LEFT, y0
    phone_x = RIGHT - phone_w
    phone_y = y0 + max(0, (ide_h - phone_h) // 2)
    shield_x = ide_x + ide_w + 20
    shield_w = 48

    # --- IDE window ---
    ide_layer, ipad, content, isc, iop = _window_shell(
        ide_w, ide_h, scene.get("ide_title") or "Codebase", t, start=0.0,
        accent=PINK, live=False, subtitle="QA scan"
    )
    d = ImageDraw.Draw(ide_layer)
    cx0, cy0, cx1, cy1 = content
    # gutter + code
    d.rectangle((cx0, cy0, cx0 + 52, cy1), fill=SURF4)
    code = scene.get("code_lines") or _DEFAULT_CODE
    ly = cy0 + 18
    ln = 1
    while ly < cy1 - 28:
        line = code[(ln - 1) % len(code)]
        d.text((cx0 + 26, ly), f"{ln:02d}", font=mono(15, 500), fill=MUTED, anchor="mm")
        if isinstance(line, str):
            line = [(line, GRAY)]
        _code_line(d, cx0 + 64, ly, line, size=17, weight=500)
        ly += 34
        ln += 1
    mo.paste_pop(im, ide_layer, ide_x - ipad, ide_y - ipad, isc, iop)

    shielded = t >= b2

    # --- Phone ---
    scp, opp = mo.spring_pop(t, 0.12, 0.6)
    phone = _phone_mock(phone_w, phone_h, t, safe=shielded)
    # label already inside; extra "Users" / "Safe" badge above if needed — already in mock
    if shielded:
        # extra Safe glow behind the device
        st.paste_glow(im, phone_x + phone_w / 2, phone_y + phone_h / 2, 280, TEAL, alpha=70)
    mo.paste_pop(im, phone, phone_x, phone_y, scp, opp)

    # --- Caught tray (under/over the IDE bottom) then bugs land on it ---
    if shielded:
        scc, opc = mo.spring_pop(t, b2 + 0.12, 0.4)
        tray_w, tray_h = ide_w - 28, catch_h - 8
        tray, tpad = mo.soft_card(
            tray_w, tray_h, radius=24, fill=st.mix(FAIL, SURF, 0.55),
            outline=FAIL, width=3, glow=FAIL, glow_a=50,
        )
        td = ImageDraw.Draw(tray)
        lab = scene.get("caught_label") or "Caught"
        td.text((tpad + 22, tpad + 16), lab, font=st.font(24, 800), fill=WHITE, anchor="lt")
        # inset from the IDE bottom and sides so the tray has breathing room
        mo.paste_pop(im, tray, int(ide_x + 14 - tpad), int(ide_y + ide_h - tray_h - 16 - tpad), scc, opc)

    # --- Bugs ---
    nbugs = int(scene.get("bugs", 8))
    bug_img = _bug_icon(36, FAIL)
    catch_origin_x = shield_x - 10
    catch_origin_y = BOTTOM - 70
    for i in range(nbugs):
        launch = 0.18 + i * 0.13
        # path from IDE (right edge, staggered y) toward phone
        sx = ide_x + ide_w - 8
        sy = ide_y + 160 + (i % 6) * 110 + (i % 3) * 16
        # impact point on the phone's left edge
        tx = phone_x + 8
        ty = phone_y + 180 + (i % 5) * 90
        # quarantine slot — inside the Caught tray overlaid on the IDE bottom
        qx = ide_x + 110 + (i % 4) * 78
        qy = ide_y + ide_h - catch_h + 58 + (i // 4) * 36

        if t < launch:
            continue
        travel = 1.15
        if not shielded or (t < b2):
            p = st.ease_out_cubic(st.clamp01((t - launch) / travel))
            # slight sine wobble
            x = sx + (tx - sx) * p
            y = sy + (ty - sy) * p + 10 * math.sin((t - launch) * 6 + i)
        else:
            # position at shield time, then bounce to quarantine
            p_hit = st.ease_out_cubic(st.clamp01((b2 - launch) / travel))
            hx = sx + (tx - sx) * p_hit
            hy = sy + (ty - sy) * p_hit
            # clamp at shield
            hx = min(hx, shield_x - 6)
            bp = st.ease_out_cubic(st.clamp01((t - b2) / 0.55))
            # overshoot bounce
            bounce = math.sin(bp * math.pi) * 18
            x = hx + (qx - hx) * bp
            y = hy + (qy - hy) * bp - bounce
        mo.paste_pop(im, bug_img, int(x - bug_img.size[0] / 2), int(y - bug_img.size[1] / 2), 1.0, 1.0)

    # --- Shield barrier ---
    if shielded:
        scs, ops = mo.spring_pop(t, b2, 0.45)
        sh_h = ide_h - 8
        sh_layer, shpad = mo.soft_card(
            shield_w, sh_h, radius=20, fill=st.mix(TEAL, SURF, 0.25),
            outline=TEAL, width=3, glow=BLUE, glow_a=140,
        )
        sd = ImageDraw.Draw(sh_layer)
        # inner blade
        sd.rounded_rectangle((shpad + 14, shpad + 16, shpad + shield_w - 14, shpad + sh_h - 16), 10, fill=TEAL)
        # chevron marks
        for k in range(6):
            yy = shpad + 40 + k * (sh_h - 80) / 5
            sd.polygon([(shpad + 8, yy), (shpad + shield_w / 2, yy + 10), (shpad + 8, yy + 20)], fill=BLUE)
        mo.paste_pop(im, sh_layer, int(shield_x - shpad), int(y0 + 10 - shpad), scs, ops)


    return im.convert("RGB")


# ---------------------------------------------------------------------------
# artifact_morph
# ---------------------------------------------------------------------------

def _ticket_card(w, h, scene):
    layer, pad = mo.soft_card(
        w, h, radius=36, fill=SURF, outline=st.mix(AMBER, WHITE, 0.25),
        width=3, glow=AMBER, glow_a=90,
    )
    d = ImageDraw.Draw(layer)
    # header band
    st.rounded_rect(d, (pad, pad, pad + w, pad + 120), 30, fill=st.mix(AMBER, SURF, 0.55))
    d.rectangle((pad, pad + 80, pad + w, pad + 120), fill=st.mix(AMBER, SURF, 0.55))
    # BUG tag
    tf = st.font(22, 800)
    _pill(d, (pad + 28, pad + 28, pad + 28 + 86, pad + 68), AMBER, "BUG", tf, (20, 16, 8))
    # severity dot
    d.ellipse((pad + 128, pad + 36, pad + 156, pad + 64), fill=FAIL)
    d.text((pad + 168, pad + 50), scene.get("severity") or "Issue", font=st.font(22, 700), fill=WHITE, anchor="lm")
    # title
    d.text((pad + 32, pad + 160), scene.get("ticket_title") or "Bug Ticket",
           font=st.font(56, 800), fill=WHITE, anchor="lt")
    d.text((pad + 32, pad + 230), scene.get("ticket_sub") or "Flagged in QA scan",
           font=st.font(26, 600), fill=GRAY, anchor="lt")

    # stack-trace panel fills down to the footer
    fy = pad + h - 100
    panel_y = pad + 280
    st.rounded_rect(d, (pad + 28, panel_y, pad + w - 28, fy - 20), 20, fill=SURF4)
    d.text((pad + 48, panel_y + 24), "stack trace", font=mono(18, 600), fill=MUTED, anchor="lt")
    traces = scene.get("stack") or [
        [("checkout.spec.ts", AMBER)],
        [("  › ", MUTED), ("describe('cart')", GRAY)],
        [("  › ", MUTED), ("expect(cart).toBeVisible()", WHITE)],
        [("  at ", MUTED), ("scan.runner", BLUE), ("  (qa)", MUTED)],
        [("  at ", MUTED), ("qa.tick()", TEAL)],
        [("", MUTED)],
        [("FAIL  Checkout", FAIL)],
        [("      cart was not visible", GRAY)],
        [("", MUTED)],
        [("# flagged before users", MUTED)],
        [("capture", BLUE), ("(result)", PINK)],
    ]
    body_top = panel_y + 64
    body_bot = fy - 36
    usable = []
    for line in traces:
        if isinstance(line, str):
            line = [(line, GRAY)]
        if line and line[0][0] == "":
            continue
        usable.append(line)
    # extra context lines if the panel is tall
    extras = [
        [("  at ", MUTED), ("runner.tick", BLUE)],
        [("# captured before users", MUTED)],
        [("queue.push", TEAL), ("(issue)", AMBER)],
        [("return ", VIOLET), ("status", WHITE)],
    ]
    ei = 0
    avail = max(40, body_bot - body_top)
    while avail / max(len(usable), 1) > 58 and ei < len(extras) * 2:
        usable.append(extras[ei % len(extras)])
        ei += 1
    line_h = avail / max(len(usable), 1)
    for i, line in enumerate(usable):
        ly = body_top + i * line_h
        if ly + 24 > body_bot:
            break
        _code_line(d, pad + 48, ly, line, size=24, weight=500)

    # footer pills
    # assignee
    who = scene.get("assignee") or "Grok Bot"
    af = st.font(22, 800)
    atw, _ = st.text_wh(af, who)
    # GB mini + pill
    _gb_badge(layer, pad + 32, fy, 48, BLUE)
    _pill(d, (pad + 92, fy + 6, pad + 92 + atw + 36, fy + 42), SURF3, who, af, WHITE)
    status = scene.get("ticket_status") or "Open"
    sf = st.font(22, 800)
    stw, _ = st.text_wh(sf, status)
    _pill(d, (pad + w - 32 - stw - 40, fy + 6, pad + w - 32, fy + 48), AMBER, status, sf, (20, 16, 8))
    return layer, pad


def _pr_card(w, h, scene, approved=False, merged=False, toggle=None, t=0.0, branch_band=0):
    """Pull request card. toggle is None or ('left'|'right', left_name, right_name, progress 0..1).
    branch_band reserves pixels above the footer for a merge-lines + Merged badge strip.
    """
    accent = VIOLET if not merged else TEAL
    layer, pad = mo.soft_card(
        w, h, radius=36, fill=SURF, outline=st.mix(accent, WHITE, 0.28),
        width=3, glow=accent, glow_a=90,
    )
    d = ImageDraw.Draw(layer)
    # header
    st.rounded_rect(d, (pad, pad, pad + w, pad + 120), 30, fill=st.mix(VIOLET, SURF, 0.5))
    d.rectangle((pad, pad + 80, pad + w, pad + 120), fill=st.mix(VIOLET, SURF, 0.5))
    tf = st.font(22, 800)
    _pill(d, (pad + 28, pad + 28, pad + 28 + 78, pad + 68), VIOLET, "PR", tf, WHITE)
    branch = scene.get("branch") or "fix/qa-issue  →  main"
    bf = mono(18, 600)
    btw, _ = st.text_wh(bf, branch)
    _pill(d, (pad + 120, pad + 32, pad + 120 + btw + 32, pad + 64), SURF4, branch, bf, st.mix(VIOLET, WHITE, 0.7), radius=10)

    d.text((pad + 32, pad + 150), scene.get("pr_title") or "Pull Request",
           font=st.font(52, 800), fill=WHITE, anchor="lt")

    body_top = pad + 230
    # optional reviewer toggle
    if toggle is not None:
        side, left_n, right_n, prog = toggle
        tw = w - 64
        th = 72
        tx, ty = pad + 32, body_top
        st.rounded_rect(d, (tx, ty, tx + tw, ty + th), 36, fill=SURF4)
        # sliding thumb
        half = tw / 2
        thumb_x = tx + prog * half
        thumb_col = TEAL if prog < 0.5 else BLUE
        st.rounded_rect(d, (thumb_x + 4, ty + 4, thumb_x + half - 4, ty + th - 4), 32, fill=thumb_col)
        d.text((tx + half / 2, ty + th / 2), left_n, font=st.font(26, 800),
               fill=WHITE if prog < 0.5 else GRAY, anchor="mm")
        d.text((tx + half * 1.5, ty + th / 2), right_n, font=st.font(26, 800),
               fill=WHITE if prog >= 0.5 else GRAY, anchor="mm")
        body_top = ty + th + 24

    # footer first so the diff can fill everything above it
    fy = pad + h - 120
    # diff panel fills remaining height (minus optional branch-merge band)
    panel_bot = fy - 16 - int(branch_band)
    st.rounded_rect(d, (pad + 28, body_top, pad + w - 28, panel_bot), 20, fill=SURF4)
    d.text((pad + 48, body_top + 18), "diff", font=mono(18, 600), fill=MUTED, anchor="lt")
    diffs = scene.get("diff") or [
        ("+", "if (retry) return next()"),
        ("-", "throw new Error()"),
        ("+", "await assertVisible(cart)"),
        (" ", "export function checkout()"),
        ("+", "return status.ok"),
        ("-", "cart.render(fallback)"),
        ("+", "cart.render(ready)"),
        (" ", "export default checkout"),
    ]
    diffs = list(diffs)
    extras = [
        (" ", "// qa runner hook"),
        ("+", "queue.flush()"),
        ("-", "cart.render(fallback)"),
        (" ", "module.exports = checkout"),
        ("+", "assertVisible(cart)"),
    ]
    start_y = body_top + 54
    avail = max(40, panel_bot - 16 - start_y)
    ei = 0
    while avail / max(len(diffs), 1) > 56 and ei < len(extras):
        cand = extras[ei]
        ei += 1
        if cand not in diffs:
            diffs.append(cand)
    n = len(diffs)
    line_h = avail / max(n, 1)
    ly = start_y
    for kind, txt in diffs:
        if ly + line_h - 8 > panel_bot:
            break
        if kind == "+":
            bg, col, prefix = st.mix(TEAL, SURF4, 0.7), TEAL, "+  "
        elif kind == "-":
            bg, col, prefix = st.mix(FAIL, SURF4, 0.7), FAIL, "−  "
        else:
            bg, col, prefix = None, GRAY, "   "
        row_h = line_h - 6
        if bg:
            d.rectangle((pad + 28, ly - 4, pad + w - 28, ly + row_h - 4), fill=bg)
        d.text((pad + 48, ly + (row_h - 8) / 2), prefix + txt, font=mono(22, 500), fill=col, anchor="lm")
        ly += line_h

    # footer: checks + merge button
    checks = scene.get("checks") or ["QA checks", "Build"]
    cx = pad + 32
    cf = st.font(18, 800)
    for c in checks:
        tw, _ = st.text_wh(cf, "✓  " + c)
        _pill(d, (cx, fy, cx + tw + 32, fy + 44), st.mix(TEAL, SURF, 0.3), "✓  " + c, cf, TEAL)
        cx += tw + 44

    # Footer Merge button only while the PR is still awaiting merge.
    # Once merged, the branch-band "Merged" badge is the single status — no duplicate button.
    if (scene.get("show_merge_button", False) or toggle is not None) and not merged:
        label = "Merge"
        mf = st.font(28, 800)
        mtw, _ = st.text_wh(mf, label)
        mw = mtw + 72
        mx1 = pad + w - 32
        _pill(d, (mx1 - mw, fy - 4, mx1, fy + 52), BLUE, label, mf, WHITE, radius=26)

    if approved:
        # stamp sits in the title row, clear of the diff and the toggle
        stamp = Image.new("RGBA", (280, 100), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        sd.rounded_rectangle((8, 12, 272, 88), 14, outline=TEAL, width=5)
        sd.text((140, 50), "Approved  ✓", font=st.font(30, 800), fill=TEAL, anchor="mm")
        stamp = stamp.rotate(10, expand=True, resample=Image.BICUBIC)
        sx = pad + w - stamp.size[0] - 16
        # sit on the header/title, clearly above the reviewer toggle
        sy = pad + 70
        layer.alpha_composite(stamp, (int(sx), int(sy)))

    return layer, pad


def render_artifact_morph(scene, t):
    im = mo.canvas(t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = mo.safe()
    beats, bidx, tloc, dur = _beats(scene, t)
    b2 = beats[1] if len(beats) > 1 else 2.1
    title = scene.get("title") or "Converts them"
    y0 = mo.title_block(im, title, t, 0.0, max_size=64)
    avail_h = BOTTOM - y0 - 8
    card_w, card_h = SW, avail_h

    show_pr = t >= b2
    if not show_pr:
        layer, pad = _ticket_card(card_w, card_h, scene)
        sc, op = mo.spring_pop(t, 0.0, 0.55)
        mo.paste_pop(im, layer, LEFT - pad, y0 - pad, sc, op)
    else:
        # morph: ticket fades/shrinks left, PR wipes in from the right with an arrow flash
        ticket, tpad = _ticket_card(card_w, card_h, scene)
        pr, ppad = _pr_card(card_w, card_h, scene, approved=False, merged=False, toggle=None, t=t)
        fade = st.clamp01((t - b2) / 0.32)
        # ticket slides left and fades quickly so footer pills don't linger on the PR
        mo.paste_pop(im, ticket, int(LEFT - tpad - 120 * fade), y0 - tpad, 1.0 - 0.08 * fade, max(0.0, 1.0 - fade * 1.15))
        pr = mo.apply_wipe(pr, fade, direction="left", softness=22)
        mo.paste_pop(im, pr, LEFT - ppad, y0 - ppad, 1.0, 1.0)
        # arrow flash in the first 0.4s of the morph
        if fade < 1:
            ax = LEFT + SW / 2
            ay = y0 + avail_h / 2
            flash = Image.new("RGBA", (st.W, st.H), (0, 0, 0, 0))
            st.paste_glow(flash, ax, ay, 160, VIOLET, alpha=int(90 * (1 - fade)))
            fd = ImageDraw.Draw(flash)
            # chevron
            s = 50
            fd.polygon([(ax - s, ay - s), (ax + s, ay), (ax - s, ay + s), (ax - s / 3, ay)], fill=st.with_alpha(VIOLET, int(220 * (1 - fade))))
            im.alpha_composite(flash)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# merge_toggle
# ---------------------------------------------------------------------------

def _branch_lines(im, x0, y0, x1, y1, x_meet, y_meet, progress, col_a, col_b, col_m):
    """Two strokes that travel toward a merge point, then one outgoing stroke."""
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    p = st.clamp01(progress)

    def lerp(a, b, u):
        return a + (b - a) * u

    # incoming A (left) and B (right) for first 0.55 of progress
    u = st.clamp01(p / 0.55)
    ax, ay = lerp(x0, x_meet, u), lerp(y0, y_meet, u)
    bx, by = lerp(x1, x_meet, u), lerp(y1, y_meet, u)
    d.line((x0, y0, ax, ay), fill=col_a, width=6)
    d.line((x1, y1, bx, by), fill=col_b, width=6)
    d.ellipse((x0 - 8, y0 - 8, x0 + 8, y0 + 8), fill=col_a)
    d.ellipse((x1 - 8, y1 - 8, x1 + 8, y1 + 8), fill=col_b)
    if p >= 0.55:
        d.ellipse((x_meet - 10, y_meet - 10, x_meet + 10, y_meet + 10), fill=col_m)
        v = st.clamp01((p - 0.55) / 0.45)
        mx, my = lerp(x_meet, x_meet, 1), lerp(y_meet, y_meet + 70, v)
        d.line((x_meet, y_meet, mx, my), fill=col_m, width=6)
        d.ellipse((mx - 8, my - 8, mx + 8, my + 8), fill=col_m)
    im.alpha_composite(overlay)
    return p


def render_merge_toggle(scene, t):
    im = mo.canvas(t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = mo.safe()
    beats, bidx, tloc, dur = _beats(scene, t)
    b2 = beats[1] if len(beats) > 1 else 2.5
    title = scene.get("title") or "Review and merge"
    y0 = mo.title_block(im, title, t, 0.0, max_size=64)
    avail_h = BOTTOM - y0 - 8
    card_w, card_h = SW, avail_h

    left_n = scene.get("left") or scene.get("reviewer_left") or "Reviewer"
    right_n = scene.get("right") or scene.get("reviewer_right") or "Grok Bot"
    if isinstance(left_n, dict):
        left_n = _lab(left_n, "Reviewer")
    if isinstance(right_n, dict):
        right_n = _lab(right_n, "Grok Bot")

    # toggle progress: 0 = left, 1 = right. Starts on the left reviewer, slides at beat 2.
    if t < b2:
        prog = 0.0
    else:
        prog = st.ease_in_out(st.clamp01((t - b2) / 0.45))

    approved = t >= b2 + 0.35
    merged = t >= b2 + 0.9

    scene = dict(scene)
    scene["show_merge_button"] = True
    band = 118  # reserved strip above the footer for branch lines + Merged badge
    layer, pad = _pr_card(
        card_w, card_h, scene,
        approved=approved, merged=merged,
        toggle=("right", left_n, right_n, prog),
        t=t,
        branch_band=band,
    )
    sc, op = mo.spring_pop(t, 0.0, 0.5)
    mo.paste_pop(im, layer, LEFT - pad, y0 - pad, sc, op)

    # Branch merge animation lives in the reserved band above the Merge button
    band_cy = y0 + avail_h - 120 - band / 2
    if t < b2 + 0.45:
        # waiting stubs so the reserved band is never an empty hole
        stub = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(stub)
        sd.ellipse((LEFT + 70 - 7, band_cy - 7, LEFT + 70 + 7, band_cy + 7), fill=TEAL)
        sd.ellipse((RIGHT - 70 - 7, band_cy - 7, RIGHT - 70 + 7, band_cy + 7), fill=BLUE)
        sd.line((LEFT + 80, band_cy, LEFT + SW / 2 - 40, band_cy), fill=st.with_alpha(TEAL, 80), width=4)
        sd.line((RIGHT - 80, band_cy, RIGHT - SW / 2 + 40, band_cy), fill=st.with_alpha(BLUE, 80), width=4)
        im.alpha_composite(stub)
    if t >= b2 + 0.45:
        p = st.clamp01((t - (b2 + 0.45)) / 0.7)
        _branch_lines(
            im,
            LEFT + 70, band_cy - 8,
            RIGHT - 70, band_cy - 8,
            LEFT + SW / 2, band_cy - 8,
            p, TEAL, BLUE, VIOLET,
        )
        if t >= b2 + 0.85:
            scb, opb = mo.spring_pop(t, b2 + 0.85, 0.45)
            lab = scene.get("merged_label") or "Merged"
            mf = st.font(30, 800)
            tw, _ = st.text_wh(mf, lab)
            bl, bpad = mo.soft_card(tw + 64, 52, radius=26, fill=TEAL, outline=WHITE, width=2, glow=TEAL, glow_a=90)
            bd = ImageDraw.Draw(bl)
            bd.text((bpad + (tw + 64) / 2, bpad + 26), lab, font=mf, fill=WHITE, anchor="mm")
            mo.paste_pop(
                im, bl,
                int(LEFT + (SW - tw - 64) / 2 - bpad),
                int(band_cy + 10 - bpad),
                scb, opb,
            )

    return im.convert("RGB")


RENDERERS = {
    "live_scan": render_live_scan,
    "shield": render_shield,
    "artifact_morph": render_artifact_morph,
    "merge_toggle": render_merge_toggle,
}
