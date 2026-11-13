"""Scene templates (v3). Each returns a 1080x1920 RGB frame at time t (seconds from scene start)."""
from __future__ import annotations

import math
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

import style as st
import motion as mo
import logos

W, H = st.W, st.H
PALETTE = st.PALETTE
CYCLE = st.CYCLE

TEMPLATES = (
    "network",
    "pipeline",
    "compare",
    "cards",
    "checklist",
    "emphasis",
    "counter",
    "donut",
    "progress",
    "gauge",
    "before_after",
    "chat_mockup",
    "profile_card",
    "icon_grid_highlight",
    "logo_card",
    "feature_grid_checks",
    "messy_to_clean",
    "doc_timeline",
    "bar_compare",
    "live_scan",
    "shield",
    "artifact_morph",
    "merge_toggle",
)


def _col(item, i=0, default=None):
    if isinstance(item, dict) and item.get("color"):
        return st.color(item["color"])
    return st.color(default) if default else st.cycle_color(i)


def _label(item, fallback=""):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("label") or item.get("title") or item.get("text") or fallback
    return fallback or str(item)


def _sub(item):
    if isinstance(item, dict):
        return item.get("sub") or item.get("subtitle") or item.get("caption") or ""
    return ""


def _items(scene, *keys):
    for k in keys:
        v = scene.get(k)
        if v:
            return list(v)
    return []


def _shape(item, i=0):
    if isinstance(item, dict) and item.get("shape"):
        return item["shape"]
    return ("squircle", "pill", "hex", "circle", "diamond")[i % 5]


def _logo_for(item, size, col=None):
    if not isinstance(item, dict):
        return logos.get_logo(_label(item), size, col=col, allow_badge=False)
    if item.get("logo") is False or item.get("badge_only"):
        return logos.text_badge(_label(item), size, col=col)
    name = item.get("logo") or item.get("brand")
    if name:
        return logos.get_logo(str(name), size, col=col, allow_badge=True)
    # auto from label only when it clearly matches a known brand
    lab = _label(item)
    if logos.looks_like_brand(lab):
        return logos.get_logo(lab, size, col=col, allow_badge=False)
    return None


def _content(t, title="", title_size=66, align="center"):
    im = mo.canvas(t)
    y = mo.title_block(im, title, t, 0.0, max_size=title_size, align=align)
    beats, bidx, tloc, dur = mo.beats_of(t if False else {"beats": None, "duration": 4}, t)  # placeholder, overwritten
    return im, y


def _safe():
    return mo.safe()


# ---------------------------------------------------------------------------
# Shared drawing pieces
# ---------------------------------------------------------------------------

def _post_thumb(w, h, col, variant=0):
    im = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bg = st.mix(col, mo.CARD_ELEV, 0.72)
    st.rounded_rect(d, (0, 0, w, h), 16, fill=bg)
    # decorative blobs
    blob = Image.new("RGBA", im.size, (0, 0, 0, 0))
    st.paste_glow(blob, 16 + (variant * 37) % (w - 20), h * 0.35, int(min(w, h) * 0.42), col, alpha=90)
    st.paste_glow(blob, w * 0.7, h * 0.2, int(min(w, h) * 0.28), st.mix(col, PALETTE["white"], 0.3), alpha=50)
    im.alpha_composite(blob)
    # fake caption bars (not text / not stats)
    d = ImageDraw.Draw(im)
    y = h - 46
    d.rounded_rectangle((14, y, 14 + int(w * 0.58), y + 10), 4, fill=(255, 255, 255, 50))
    d.rounded_rectangle((14, y + 16, 14 + int(w * 0.36), y + 24), 4, fill=(255, 255, 255, 28))
    return im


def _draw_label_block(layer, pad, box_w, box_h, title, subtitle, col, logo=None, number=None, shape="squircle", align_left=24):
    """Paint title/subtitle/logo/number inside an already-built soft_card layer."""
    d = ImageDraw.Draw(layer)
    compact = box_w < 340
    badge_r = 20 if compact else 26
    x0 = pad + align_left
    # left mark
    if number is not None:
        r = 22 if compact else 28
        cx, cy = pad + (34 if compact else 44), pad + box_h / 2
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
        nf = st.font(24 if compact else 28, 800)
        d.text((cx, cy + 1), str(number), font=nf, fill=PALETTE["white"], anchor="mm")
        x0 = pad + (64 if compact else 86)
    elif logo is not None:
        s = 36 if compact else 48
        ic = logo.resize((s, s), Image.LANCZOS).convert("RGBA")
        ly = pad + int((box_h - s) / 2)
        d.rounded_rectangle((pad + 14, ly - 4, pad + 14 + s + 8, ly + s + 4), 14, fill=st.mix(col, mo.CARD, 0.35))
        layer.alpha_composite(ic, (pad + 18, ly))
        x0 = pad + 14 + s + 16
    else:
        cx, cy = pad + (32 if compact else 44), pad + box_h / 2
        st.draw_badge(d, cx, cy, badge_r, shape, col, scale=1.0)
        x0 = pad + (62 if compact else 82)
    text_w = int(box_w - (x0 - pad) - 16)
    text_h = int(box_h - 20)
    max_lines = 3 if compact else 2
    if subtitle:
        tf, tlines, ts, th, tlh = st.fit_text(title, text_w, int(text_h * 0.62), mo.type_max(32 if compact else 46), min_size=18, weight=800, max_lines=max_lines)
        sf, slines, ss, sh, slh = st.fit_text(subtitle, text_w, int(text_h * 0.38), 20, min_size=14, weight=500, max_lines=2)
        block = th + 6 + sh
        top = pad + (box_h - block) / 2
        st.draw_lines(d, x0, top, tlines, tf, PALETTE["white"], tlh, align="left")
        st.draw_lines(d, x0, top + th + 6, slines, sf, PALETTE["gray"], slh, align="left")
    else:
        tf, tlines, ts, th, tlh = st.fit_text(title, text_w, text_h, mo.type_max(32 if compact else 46), min_size=18, weight=800, max_lines=max_lines)
        top = pad + (box_h - th) / 2
        st.draw_lines(d, x0, top, tlines, tf, PALETTE["white"], tlh, align="left")


def _pop_card(im, x, y, w, h, t, start, col, title, subtitle="", logo=None, number=None, shape="squircle",
              glow=True, accent=True, wipe=None, wipe_t=None):
    sc, op = mo.spring_pop(t, start, 0.52)
    if op <= 0:
        return
    layer, pad = mo.soft_card(
        int(w), int(h), radius=28,
        fill=mo.CARD,
        outline=st.mix(col, PALETTE["white"], 0.18),
        width=3,
        glow=col if glow else None,
        glow_a=70,
    )
    d = ImageDraw.Draw(layer)
    if accent:
        # colored left edge
        d.rounded_rectangle((pad, pad + 10, pad + 8, pad + h - 10), 4, fill=col)
    _draw_label_block(layer, pad, w, h, title, subtitle, col, logo=logo, number=number, shape=shape, align_left=22)
    if wipe is not None:
        prog = st.clamp01((t - (wipe_t if wipe_t is not None else start)) / 0.45)
        layer = mo.apply_wipe(layer, prog, direction=wipe)
    mo.paste_pop(im, layer, int(x - pad), int(y - pad), sc, op)


# ---------------------------------------------------------------------------
# network — org chart, staggered pop, optional outputs on beat 2
# ---------------------------------------------------------------------------


def render_network(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 64)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    center = scene.get("center") or {}
    nodes = _items(scene, "nodes", "children")
    outputs = _items(scene, "outputs")
    n = max(1, len(nodes))
    avail = BOTTOM - y0 - 4
    out_h = int(avail * 0.34) if outputs else 0
    rail = 28
    rest = avail - (out_h + (rail if outputs else 0))
    gap = 22
    c_h = max(130, int(rest * 0.40))
    ch_h = max(130, rest - c_h - gap)
    # if rounding leftover, give it to the output
    used = c_h + gap + ch_h + (rail + out_h if outputs else 0)
    if outputs:
        out_h += max(0, avail - used)
    c_w = SW
    cx = LEFT
    cy = y0
    ccol = _col(center, 0, "violet")
    _pop_card(
        im, cx, cy, c_w, c_h, t, 0.05, ccol,
        _label(center, "Team"), _sub(center),
        logo=_logo_for(center, 52, ccol),
        shape=_shape(center, 0),
        glow=True,
    )
    gapx = 16
    ch_w = int((SW - gapx * (n - 1)) / n) if n else SW
    ch_y = cy + c_h + gap
    # orthogonal connectors: down from parent, horizontal rail, down into each child
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    rail_y = cy + c_h + gap * 0.45
    mid_x = LEFT + SW / 2
    a = st.appear(t, 0.20, 0.28)
    if a > 0:
        col_rail = st.with_alpha(PALETTE["white"], int(140 * a))
        # parent stub
        ld.line((mid_x, cy + c_h - 2, mid_x, rail_y), fill=col_rail, width=4)
        xs = [LEFT + i * (ch_w + gapx) + ch_w / 2 for i in range(n)]
        if xs:
            ld.line((xs[0], rail_y, xs[-1], rail_y), fill=col_rail, width=4)
        for i, xmid in enumerate(xs):
            ac = st.appear(t, mo.stagger(0.22, i, 0.11), 0.28)
            if ac > 0:
                ld.line((xmid, rail_y, xmid, ch_y + 4), fill=st.with_alpha(_col(nodes[i], i + 1), int(200 * ac)), width=4)
    im.alpha_composite(lines)
    for i, node in enumerate(nodes):
        x = LEFT + i * (ch_w + gapx)
        col = _col(node, i + 1)
        _pop_card(
            im, x, ch_y, ch_w, ch_h, t, mo.stagger(0.28, i, 0.11), col,
            _label(node), _sub(node),
            logo=_logo_for(node, 44, col),
            shape=_shape(node, i + 1),
        )
    # beat 2: outputs row — if a single output, fill it with decorative post tiles
    if outputs and bidx >= 1:
        oy = ch_y + ch_h + rail
        oh = max(110, BOTTOM - oy - 4)
        m = len(outputs)
        if m == 1:
            out = outputs[0]
            col = _col(out, 0, "blue")
            start = beats[1] + 0.05
            sc, op = mo.spring_pop(t, start, 0.5)
            if op > 0:
                layer, pad = mo.soft_card(SW, oh, radius=28, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.18), width=3, glow=col, glow_a=70)
                d = ImageDraw.Draw(layer)
                d.rounded_rectangle((pad, pad + 10, pad + 8, pad + oh - 10), 4, fill=col)
                lab = _label(out, "Output")
                sub = _sub(out)
                tf, tlines, ts, th, tlh = st.fit_text(lab, SW - 48, 60, 34, min_size=20, weight=800, max_lines=1)
                st.draw_lines(d, pad + 24, pad + 14, tlines, tf, PALETTE["white"], tlh, align="left")
                header_h = th + (18 if not sub else 36)
                if sub and sub != lab:
                    d.text((pad + 24, pad + 14 + th + 2), sub, font=st.font(18, 600), fill=PALETTE["gray"], anchor="lt")
                gap_t = 12
                tw = int((SW - 40 - gap_t * 2) / 3)
                thb = max(60, oh - header_h - 20)
                tiles_left = pad + 20
                ty = pad + header_h
                for k in range(3):
                    thumb = _post_thumb(tw, thb, st.cycle_color(k), variant=k)
                    layer.alpha_composite(thumb, (tiles_left + k * (tw + gap_t), ty))
                # feeder line already implied by placement
                layer = mo.apply_wipe(layer, st.clamp01((t - start) / 0.4), "up")
                mo.paste_pop(im, layer, LEFT - pad, int(oy - pad), sc, op)
            # short stub from children mid down to the output
            lin = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dd = ImageDraw.Draw(lin)
            a = st.appear(t, beats[1], 0.28)
            if a > 0:
                dd.line((LEFT + SW / 2, ch_y + ch_h - 2, LEFT + SW / 2, oy + 4), fill=st.with_alpha(PALETTE["blue"], int(200 * a)), width=4)
            im.alpha_composite(lin)
        else:
            ow = int((SW - 14 * (m - 1)) / m) if m else SW
            mid = (LEFT + SW / 2, ch_y + ch_h - 2)
            lin = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dd = ImageDraw.Draw(lin)
            a = st.appear(t, beats[1], 0.3)
            st.draw_arrow(dd, mid, (LEFT + SW / 2, oy + 4), PALETTE["blue"], width=4, progress=a, head=True)
            im.alpha_composite(lin)
            for i, out in enumerate(outputs):
                x = LEFT + i * (ow + 14)
                col = _col(out, i, "blue")
                _pop_card(
                    im, x, oy, ow, oh, t, mo.stagger(beats[1] + 0.05, i, 0.1), col,
                    _label(out, "Output"), _sub(out),
                    logo=_logo_for(out, 44, col),
                    shape=_shape(out, i),
                    wipe="up",
                    wipe_t=beats[1] + i * 0.08,
                )
    return im.convert("RGB")


def render_pipeline(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 62)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    steps = _items(scene, "steps", "items", "nodes")
    n = max(1, len(steps))
    avail = BOTTOM - y0 - 8
    gap = 14
    h = int((avail - gap * (n - 1)) / n)
    cap = 420 if (BOTTOM - TOP) >= 1100 else 168
    h = max(100, min(cap, h))
    # if leftover, add it to the last card
    used = h * n + gap * (n - 1)
    extra_last = max(0, min(40, avail - used))
    # connecting arrows
    for i, step in enumerate(steps):
        y = y0 + i * (h + gap)
        hh = h + (extra_last if i == n - 1 else 0)
        col = _col(step, i)
        glow = (bidx >= 1 and i == n - 1)
        _pop_card(
            im, LEFT, y, SW, hh, t, mo.stagger(0.08, i, 0.16), col,
            _label(step), _sub(step),
            logo=_logo_for(step, 48, col),
            number=i + 1,
            shape=_shape(step, i),
            glow=True if glow else True,
        )
        if i < n - 1:
            a = st.appear(t, mo.stagger(0.22, i, 0.16), 0.28)
            if a > 0:
                # small chevron between cards
                mid_x = LEFT + SW / 2
                y1 = y + hh + 1
                d = ImageDraw.Draw(im)
                col2 = st.with_alpha(_col(steps[i + 1], i + 1), int(220 * a))
                d.polygon(
                    [(mid_x - 12, y1), (mid_x + 12, y1), (mid_x, y1 + gap - 2)],
                    fill=col2,
                )
    # traveling packet along the column on a loop after cards are in
    if t > 0.8 and n >= 2:
        cycle = 1.8
        u = ((t - 0.8) % cycle) / cycle
        # from first card center to last
        y_a = y0 + h / 2
        y_b = y0 + (n - 1) * (h + gap) + h / 2
        py = y_a + (y_b - y_a) * u
        plat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pd = ImageDraw.Draw(plat)
        st.draw_packet(pd, (LEFT + 28, py), st.cycle_color(int(t * 2)), scale=1.0)
        im.alpha_composite(plat)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# compare — two big cards, connector word (must be spoken)
# ---------------------------------------------------------------------------

def render_compare(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 62)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    left = scene.get("left") or {}
    right = scene.get("right") or {}
    connector = (scene.get("connector") or "").strip()
    avail = BOTTOM - y0 - 8
    gap = 20
    # stacked if we have a connector in the middle and limited width, but 9:16: side by side if short labels, else stacked.
    # Always two tall side-by-side cards with a connector badge overlapping the middle.
    cw = int((SW - gap) / 2)
    ch = avail
    for i, side, x in ((0, left, LEFT), (1, right, LEFT + cw + gap)):
        col = _col(side, i, "pink" if i == 0 else "amber")
        items = side.get("items") if isinstance(side, dict) else None
        sub = _sub(side)
        if items and not sub:
            sub = "  ·  ".join(_label(it) for it in items[:3])
        _pop_card(
            im, x, y0, cw, ch, t, mo.stagger(0.1, i, 0.16), col,
            _label(side), sub,
            logo=_logo_for(side, 52, col),
            shape=_shape(side, i),
        )
    if connector:
        sc, op = mo.spring_pop(t, 0.45, 0.4)
        if op > 0:
            f = st.font(28, 800)
            tw, _ = st.text_wh(f, connector)
            pw, ph = tw + 48, 56
            layer, pad = mo.soft_card(pw, ph, radius=28, fill=PALETTE["black"], outline=PALETTE["white"], width=3, glow=PALETTE["blue"], glow_a=60)
            d = ImageDraw.Draw(layer)
            d.text((pad + pw / 2, pad + ph / 2), connector, font=f, fill=PALETTE["white"], anchor="mm")
            mo.paste_pop(im, layer, int(W / 2 - pw / 2 - pad), int(y0 + ch / 2 - ph / 2 - pad), sc, op)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# cards — row/column of keyword cards; optional spoken value ticks
# ---------------------------------------------------------------------------

def render_cards(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 62)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    cards = _items(scene, "cards", "items", "nodes")
    n = max(1, len(cards))
    avail = BOTTOM - y0 - 8
    # vertical stack fills the frame better for 2–4 cards
    gap = 16
    h = int((avail - gap * (n - 1)) / n)
    h = max(110, min(200, h))
    for i, card in enumerate(cards):
        y = y0 + i * (h + gap)
        col = _col(card, i)
        value = None
        suffix = ""
        if isinstance(card, dict) and card.get("value") is not None:
            # only tick a number the spec provided (must be spoken)
            begin = float(card.get("from", 0))
            end = float(card["value"])
            suffix = str(card.get("suffix") or "")
            decimals = card.get("decimals")
            cur = mo.count_value(t, mo.stagger(0.35, i, 0.12), 1.15, begin, end)
            value = mo.format_number(cur, suffix, decimals=decimals)
        sub = _sub(card)
        if value:
            # put the ticking number as the title, label as subtitle if no sub
            lab = _label(card)
            ttl = value
            sub = sub or lab
        else:
            ttl = _label(card)
        _pop_card(
            im, LEFT, y, SW, h, t, mo.stagger(0.08, i, 0.13), col,
            ttl, sub,
            logo=_logo_for(card, 48, col),
            shape=_shape(card, i),
        )
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# checklist — rows tick off in sequence; beat 2 can stamp remaining
# ---------------------------------------------------------------------------

def render_checklist(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 62)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    items = _items(scene, "items", "steps", "cards")
    n = max(1, len(items))
    avail = BOTTOM - y0 - 8
    gap = 16
    h = int((avail - gap * (n - 1)) / n)
    h = max(108, min(170, h))
    for i, item in enumerate(items):
        y = y0 + i * (h + gap)
        col = _col(item, i)
        start = mo.stagger(0.08, i, 0.16)
        sc, op = mo.spring_pop(t, start, 0.5)
        if op <= 0:
            continue
        layer, pad = mo.soft_card(SW, h, radius=28, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.18), width=3, glow=col, glow_a=60)
        d = ImageDraw.Draw(layer)
        # check box on the left
        check_start = start + 0.28
        # on beat 2, accelerate remaining checks
        if bidx >= 1:
            check_start = min(check_start, beats[1] + i * 0.1)
        prog = st.clamp01((t - check_start) / 0.4)
        st.draw_check(d, pad + 48, pad + h / 2, 56, col, progress=prog)
        logo = _logo_for(item, 40, col)
        text_x = pad + 90
        text_w = SW - 110
        tf, tlines, ts, th, tlh = st.fit_text(_label(item), text_w, h - 24, 36, min_size=20, weight=800, max_lines=2)
        sub = _sub(item)
        if sub:
            sf, slines, ss, sh, slh = st.fit_text(sub, text_w, 36, 22, min_size=16, weight=500, max_lines=1)
            block = th + 6 + sh
            top = pad + (h - block) / 2
            st.draw_lines(d, text_x, top, tlines, tf, PALETTE["white"], tlh, align="left")
            st.draw_lines(d, text_x, top + th + 6, slines, sf, PALETTE["gray"], slh, align="left")
        else:
            top = pad + (h - th) / 2
            st.draw_lines(d, text_x, top, tlines, tf, PALETTE["white"], tlh, align="left")
        mo.paste_pop(im, layer, LEFT - pad, int(y - pad), sc, op)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# emphasis — giant phrase, word-by-word, support chips, spring
# ---------------------------------------------------------------------------

def render_emphasis(scene, t):
    im = mo.canvas(t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    phrase = scene.get("phrase") or scene.get("title") or scene.get("label") or ""
    col = st.color(scene.get("color") or "violet")
    support = _items(scene, "support", "chips", "items")
    # plate
    avail = BOTTOM - TOP - 20
    plate_h = int(avail * (0.52 if support else 0.62))
    plate_h = max(280, min(plate_h, avail - (100 if support else 20)))
    plate_w = SW
    px, py = LEFT, TOP + 10 + (avail - plate_h - (90 if support else 0)) // 3
    sc, op = mo.spring_pop(t, 0.05, 0.5)
    if op > 0:
        layer, pad = mo.soft_card(plate_w, plate_h, radius=36, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.22), width=3, glow=col, glow_a=90)
        mo.paste_pop(im, layer, px - pad, py - pad, sc, op)
    # words
    f, lines, size, total, line_h = st.fit_text(phrase, plate_w - 48, plate_h - 40, mo.type_max(86), min_size=40, weight=800, max_lines=3)
    words = phrase.split()
    # layout full phrase, reveal word by word
    dlayer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(dlayer)
    word_i = 0
    y = py + (plate_h - total) / 2
    for line in lines:
        lw, _ = st.text_wh(f, line)
        x = W / 2 - lw / 2
        parts = line.split(" ")
        for part in parts:
            a = st.appear(t, 0.22 + word_i * 0.14, 0.22)
            if a > 0:
                rise = int((1 - a) * 16)
                fill = st.with_alpha(PALETTE["white"], int(255 * min(1, a * 1.15)))
                d.text((x, y + rise), part, font=f, fill=fill, anchor="lt")
            pw, _ = st.text_wh(f, part)
            sw, _ = st.text_wh(f, " ")
            x += pw + sw
            word_i += 1
        y += line_h
    im.alpha_composite(dlayer)
    # support chips
    if support:
        yy = py + plate_h + 28
        fchip = st.font(24, 700)
        widths = []
        for s in support:
            lab = _label(s)
            tw, _ = st.text_wh(fchip, lab)
            widths.append(tw + 70)
        gap = 16
        total_w = sum(widths) + gap * (len(widths) - 1)
        x = W / 2 - total_w / 2
        # wrap if needed
        if total_w > SW:
            x = LEFT
        for i, s in enumerate(support):
            sc, op = mo.spring_pop(t, 0.9 + i * 0.12, 0.4)
            if op <= 0:
                x += widths[i] + gap
                continue
            ccol = _col(s, i, "blue")
            cw, ch = widths[i], 58
            layer, pad = mo.soft_card(cw, ch, radius=20, fill=mo.CARD, outline=ccol, width=3, glow=ccol, glow_a=50)
            d = ImageDraw.Draw(layer)
            st.draw_badge(d, pad + 26, pad + ch / 2, 14, _shape(s, i), ccol)
            d.text((pad + 48, pad + ch / 2), _label(s), font=fchip, fill=PALETTE["white"], anchor="lm")
            mo.paste_pop(im, layer, int(x - pad), int(yy - pad), sc, op)
            x += cw + gap
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# counter — large ticking number (only if the spec provides spoken values)
# ---------------------------------------------------------------------------

def render_counter(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or scene.get("label") or ""
    y0 = mo.title_block(im, title, t, 0.0, 56)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    col = st.color(scene.get("color") or "blue")
    begin = float(scene.get("from", 0))
    end = float(scene.get("value") if scene.get("value") is not None else scene.get("to") or 0)
    suffix = str(scene.get("suffix") or "")
    decimals = scene.get("decimals")
    caption = scene.get("caption") or scene.get("sub") or ""
    # optional secondary caption on beat 2
    caption2 = scene.get("caption2") or ""
    cur = mo.count_value(t, 0.25, min(1.6, max(0.9, dur * 0.45)), begin, end)
    text = mo.format_number(cur, suffix, decimals=decimals)
    avail = BOTTOM - y0 - 8
    card_h = avail
    sc, op = mo.spring_pop(t, 0.08, 0.55)
    layer, pad = mo.soft_card(SW, card_h, radius=36, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.2), width=3, glow=col, glow_a=100)
    d = ImageDraw.Draw(layer)
    # big number
    f = st.font(140, 800)
    # shrink to fit
    while st.text_wh(f, text)[0] > SW - 60:
        f = st.font(max(48, f.size - 8), 800)
    d.text((pad + SW / 2, pad + card_h * 0.46), text, font=f, fill=PALETTE["white"], anchor="mm")
    cap = caption2 if (bidx >= 1 and caption2) else caption
    if cap:
        cf, clines, cs, ch, clh = st.fit_text(cap, SW - 80, 100, 36, min_size=22, weight=600, max_lines=2)
        st.draw_lines(d, pad + SW / 2, pad + card_h * 0.46 + 90, clines, cf, PALETTE["gray"], clh, align="center")
    mo.paste_pop(im, layer, LEFT - pad, y0 - pad, sc, op)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# donut / progress
# ---------------------------------------------------------------------------

def render_donut(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 60)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    col = st.color(scene.get("color") or "blue")
    # progress 0-1, or percent 0-100 if the speaker said a percent
    if scene.get("percent") is not None:
        target = float(scene["percent"]) / 100.0
        show = scene.get("suffix")
        if show is None:
            show = "%"
        label_mode = "percent"
        begin_p = float(scene.get("from", 0)) / 100.0
    else:
        target = float(scene.get("value") if scene.get("value") is not None else scene.get("progress") or 0)
        if target > 1:
            target = target / 100.0
            label_mode = "percent"
            show = scene.get("suffix", "%")
            begin_p = float(scene.get("from", 0))
            if begin_p > 1:
                begin_p /= 100.0
        else:
            label_mode = "frac"
            show = scene.get("suffix") or ""
            begin_p = float(scene.get("from", 0))
    caption = scene.get("caption") or scene.get("sub") or scene.get("label") or ""
    p = mo.count_value(t, 0.25, 1.3, begin_p, target)
    avail = BOTTOM - y0 - 8
    sc, op = mo.spring_pop(t, 0.06, 0.5)
    layer, pad = mo.soft_card(SW, avail, radius=36, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.18), width=3, glow=col, glow_a=80)
    # donut centered in the upper 2/3
    cx = pad + SW / 2
    cy = pad + avail * 0.42
    r = int(min(SW, avail) * 0.32)
    mo.draw_donut(layer, cx, cy, r, max(22, int(r * 0.22)), p, col)
    d = ImageDraw.Draw(layer)
    if label_mode == "percent":
        txt = f"{int(round(p * 100))}{show if show is not None else '%'}"
    else:
        txt = mo.format_number(p, show or "")
    nf = st.font(72, 800)
    while st.text_wh(nf, txt)[0] > r * 1.4:
        nf = st.font(max(28, nf.size - 6), 800)
    d.text((cx, cy), txt, font=nf, fill=PALETTE["white"], anchor="mm")
    if caption:
        cf, clines, cs, ch, clh = st.fit_text(caption, SW - 80, 90, 34, min_size=20, weight=600, max_lines=2)
        st.draw_lines(d, cx, pad + avail * 0.78, clines, cf, PALETTE["gray"], clh, align="center")
    # beat 2: optional highlight caption
    cap2 = scene.get("caption2")
    if bidx >= 1 and cap2:
        cf, clines, cs, ch, clh = st.fit_text(cap2, SW - 80, 70, 30, min_size=18, weight=600, max_lines=2)
        st.draw_lines(d, cx, pad + avail * 0.90, clines, cf, col, clh, align="center")
    mo.paste_pop(im, layer, LEFT - pad, y0 - pad, sc, op)
    return im.convert("RGB")


def render_progress(scene, t):
    return render_donut(scene, t)


# ---------------------------------------------------------------------------
# gauge — needle swings; labels must come from the spec / transcript
# ---------------------------------------------------------------------------

def render_gauge(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 60)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    left_lab = scene.get("left") or scene.get("left_label") or ""
    right_lab = scene.get("right") or scene.get("right_label") or ""
    if isinstance(left_lab, dict):
        left_col = _col(left_lab, 0, "blue")
        left_lab = _label(left_lab)
    else:
        left_col = st.color(scene.get("left_color") or "blue")
    if isinstance(right_lab, dict):
        right_col = _col(right_lab, 1, "pink")
        right_lab = _label(right_lab)
    else:
        right_col = st.color(scene.get("right_color") or "pink")
    target = float(scene.get("value") if scene.get("value") is not None else 0.5)
    if target > 1:
        target = target / 100.0
    begin = float(scene.get("from", 0))
    if begin > 1:
        begin /= 100.0
    # beat 2 can snap the needle to `value2` if provided
    if bidx >= 1 and scene.get("value2") is not None:
        v2 = float(scene["value2"])
        if v2 > 1:
            v2 /= 100.0
        p = mo.count_value(t, beats[1], 0.8, target, v2)
    else:
        p = mo.count_value(t, 0.3, 1.2, begin, target)
    col = st.color(scene.get("color") or "blue")
    avail = BOTTOM - y0 - 8
    sc, op = mo.spring_pop(t, 0.06, 0.5)
    layer, pad = mo.soft_card(SW, avail, radius=36, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.16), width=3, glow=col, glow_a=70)
    cx = pad + SW / 2
    cy = pad + avail * 0.58
    r = int(min(SW * 0.38, avail * 0.42))
    mo.draw_gauge(layer, cx, cy, r, p, left_col, right_col)
    d = ImageDraw.Draw(layer)
    lf = st.font(24, 700)
    if left_lab:
        d.text((pad + 40, pad + avail - 36), left_lab, font=lf, fill=left_col, anchor="lm")
    if right_lab:
        d.text((pad + SW - 40, pad + avail - 36), right_lab, font=lf, fill=right_col, anchor="rm")
    cap = scene.get("caption") or scene.get("sub") or ""
    if cap:
        cf, clines, cs, ch, clh = st.fit_text(cap, SW - 80, 80, 32, min_size=18, weight=700, max_lines=2)
        st.draw_lines(d, cx, pad + 28, clines, cf, PALETTE["white"], clh, align="center")
    mo.paste_pop(im, layer, LEFT - pad, y0 - pad, sc, op)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# before_after — two text cards; beat 2 wipes to After
# ---------------------------------------------------------------------------

def render_before_after(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 56)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    before = scene.get("before") or {}
    after = scene.get("after") or {}
    if isinstance(before, str):
        before = {"text": before}
    if isinstance(after, str):
        after = {"text": after}
    b_label = before.get("kicker") or before.get("label") or "Before"
    a_label = after.get("kicker") or after.get("label") or "After"
    b_text = before.get("text") or before.get("body") or _label(before)
    a_text = after.get("text") or after.get("body") or _label(after)
    b_col = _col(before, 0, "pink")
    a_col = _col(after, 1, "teal")
    highlights = before.get("highlights") or before.get("marks") or []
    avail = BOTTOM - y0 - 8
    show_after = bidx >= 1
    body = a_text if show_after else b_text
    kicker = a_label if show_after else b_label
    col = a_col if show_after else b_col
    start = beats[1] if show_after else 0.08
    sc, op = mo.spring_pop(t, start if show_after else 0.08, 0.5)
    layer, pad = mo.soft_card(SW, avail, radius=32, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.2), width=3, glow=col, glow_a=70)
    d = ImageDraw.Draw(layer)
    # kicker pill
    kf = st.font(22, 800)
    tw, _ = st.text_wh(kf, kicker)
    st.rounded_rect(d, (pad + 24, pad + 22, pad + 24 + tw + 28, pad + 62), 16, fill=col)
    d.text((pad + 24 + (tw + 28) / 2, pad + 42), kicker, font=kf, fill=PALETTE["white"], anchor="mm")
    # body
    bf, blines, bs, bh, blh = st.fit_text(body, SW - 72, avail - 120, 36, min_size=20, weight=650, max_lines=8)
    top = pad + 86
    # before: draw highlight backgrounds for marked phrases
    if (not show_after) and highlights:
        # naive: if a line contains a highlight word, tint the line
        for i, ln in enumerate(blines):
            if any(h.lower() in ln.lower() for h in highlights if h):
                d.rounded_rectangle((pad + 28, top + i * blh - 2, pad + SW - 28, top + i * blh + blh - 6), 8, fill=st.with_alpha(b_col, 50))
    st.draw_lines(d, pad + 36, top, blines, bf, PALETTE["white"] if show_after else st.mix(PALETTE["white"], b_col, 0.12), blh, align="left")
    if show_after:
        # check in the corner
        st.draw_check(d, pad + SW - 50, pad + 44, 44, a_col, progress=st.clamp01((t - beats[1]) / 0.4))
        layer = mo.apply_wipe(layer, st.clamp01((t - beats[1]) / 0.4), "left")
    mo.paste_pop(im, layer, LEFT - pad, y0 - pad, sc, op)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# chat_mockup — message bubbles + typing; messages from the spec only
# ---------------------------------------------------------------------------

def render_chat_mockup(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 56)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    messages = _items(scene, "messages", "items", "bubbles")
    header = scene.get("header") or scene.get("name") or ""
    col = st.color(scene.get("color") or "blue")
    avail = BOTTOM - y0 - 8
    sc, op = mo.spring_pop(t, 0.06, 0.5)
    layer, pad = mo.soft_card(SW, avail, radius=36, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.16), width=3, glow=col, glow_a=55)
    d = ImageDraw.Draw(layer)
    # header bar
    st.rounded_rect(d, (pad, pad, pad + SW, pad + 78), 24, fill=mo.CARD_ELEV)
    # cover bottom corners of header
    d.rectangle((pad, pad + 50, pad + SW, pad + 78), fill=mo.CARD_ELEV)
    if header:
        hf, hlines, hs, hh, hlh = st.fit_text(header, SW - 120, 48, 28, min_size=18, weight=800, max_lines=1)
        logo = logos.get_logo(header, 40, col=col, allow_badge=True) if header else None
        if logo:
            layer.alpha_composite(logo.resize((40, 40), Image.LANCZOS).convert("RGBA"), (pad + 22, pad + 20))
            st.draw_lines(d, pad + 74, pad + (78 - hh) / 2, hlines, hf, PALETTE["white"], hlh, align="left")
        else:
            st.draw_lines(d, pad + 28, pad + (78 - hh) / 2, hlines, hf, PALETTE["white"], hlh, align="left")
    # bubbles
    y = pad + 96
    for i, msg in enumerate(messages):
        if isinstance(msg, str):
            msg = {"text": msg, "side": "left" if i % 2 == 0 else "right"}
        text = msg.get("text") or msg.get("label") or _label(msg)
        side = (msg.get("side") or ("left" if i % 2 == 0 else "right")).lower()
        mcol = _col(msg, i, "blue" if side == "right" else "dark")
        start = mo.stagger(0.25, i, 0.28)
        a = st.appear(t, start, 0.3)
        if a <= 0 or y > pad + avail - 90:
            continue
        ff, flines, fs, fh, flh = st.fit_text(text, int(SW * 0.7), 160, 26, min_size=18, weight=600, max_lines=4)
        bw = min(int(SW * 0.78), max((st.text_wh(ff, ln)[0] for ln in flines), default=40) + 36)
        bh = fh + 28
        if side == "right":
            bx = pad + SW - 18 - bw
            fill = mcol
            tcol = PALETTE["white"]
        else:
            bx = pad + 18
            fill = mo.CARD_ELEV
            tcol = PALETTE["white"]
        # appear with slight rise
        rise = int((1 - a) * 12)
        st.rounded_rect(d, (bx, y + rise, bx + bw, y + rise + bh), 20, fill=st.with_alpha(fill if side == "right" else mo.CARD_ELEV, int(255 * a)))
        st.draw_lines(d, bx + 18, y + rise + 14, flines, ff, st.with_alpha(tcol, int(255 * a)), flh, align="left")
        y += bh + 12
    # typing dots on last beat or after last message
    type_at = beats[1] if len(beats) > 1 else 0.9
    if t >= type_at and y < pad + avail - 50:
        dots_y = y + 18
        bx, by, bw, bh = pad + 18, dots_y, 90, 44
        st.rounded_rect(d, (bx, by, bx + bw, by + bh), 18, fill=mo.CARD_ELEV)
        for k in range(3):
            phase = (t * 4 + k * 0.4) % 1.0
            aa = int(80 + 140 * abs(math.sin(phase * math.pi)))
            dx = bx + 22 + k * 22
            dy = by + bh / 2
            d.ellipse((dx - 6, dy - 6, dx + 6, dy + 6), fill=st.with_alpha(PALETTE["gray"], aa))
    # input bar on beat 2
    if bidx >= 1:
        prompt = scene.get("input") or scene.get("placeholder") or ""
        bar_h = 56
        by = pad + avail - bar_h - 16
        st.rounded_rect(d, (pad + 16, by, pad + SW - 16, by + bar_h), 28, fill=mo.CARD_ELEV, outline=col, width=2)
        # send pip
        d.ellipse((pad + SW - 66, by + 8, pad + SW - 26, by + 48), fill=col)
        d.polygon([(pad + SW - 54, by + 20), (pad + SW - 54, by + 36), (pad + SW - 34, by + 28)], fill=PALETTE["white"])
        if prompt:
            # type the input characters
            typed = st.clamp01((t - beats[1]) / 0.8)
            nch = max(0, int(len(prompt) * typed))
            shown = prompt[:nch] + ("|" if int(t * 2) % 2 == 0 and nch < len(prompt) else "")
            d.text((pad + 32, by + bar_h / 2), shown, font=st.font(22, 600), fill=PALETTE["white"], anchor="lm")
    mo.paste_pop(im, layer, LEFT - pad, y0 - pad, sc, op)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# profile_card — avatar (initials or logo) + name + role, optional spoken stat
# ---------------------------------------------------------------------------

def render_profile_card(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 56)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    profiles = _items(scene, "profiles", "cards", "items", "people")
    if not profiles:
        # single profile from top-level fields
        profiles = [scene]
    n = len(profiles)
    avail = BOTTOM - y0 - 8
    gap = 16
    h = int((avail - gap * (n - 1)) / n) if n else avail
    h = max(120, min(220, h))
    for i, p in enumerate(profiles):
        y = y0 + i * (h + gap)
        col = _col(p, i)
        name = p.get("name") or _label(p)
        role = p.get("role") or p.get("sub") or p.get("subtitle") or ""
        kicker = p.get("kicker") or p.get("number") or ""  # e.g. "#1" only if spoken
        start = mo.stagger(0.08, i, 0.14)
        sc, op = mo.spring_pop(t, start, 0.5)
        if op <= 0:
            continue
        layer, pad = mo.soft_card(SW, h, radius=30, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.18), width=3, glow=col, glow_a=70)
        d = ImageDraw.Draw(layer)
        # colored header strip
        st.rounded_rect(d, (pad, pad, pad + SW, pad + 28), 24, fill=col)
        d.rectangle((pad, pad + 16, pad + SW, pad + 28), fill=col)
        # avatar
        av = 86
        ax, ay = pad + 28, pad + (h - av) / 2 + 6
        d.ellipse((ax, ay, ax + av, ay + av), fill=st.mix(col, mo.CARD, 0.2), outline=col, width=3)
        logo = _logo_for(p, 56, col)
        if logo:
            layer.alpha_composite(logo.resize((56, 56), Image.LANCZOS).convert("RGBA"), (int(ax + 15), int(ay + 15)))
        else:
            ini = mo.initials(name)
            d.text((ax + av / 2, ay + av / 2), ini, font=st.font(32, 800), fill=PALETTE["white"], anchor="mm")
        tx = ax + av + 22
        tf, tlines, ts, th, tlh = st.fit_text(name, SW - (tx - pad) - 90, 80, 36, min_size=20, weight=800, max_lines=2)
        st.draw_lines(d, tx, pad + (h - th - (26 if role else 0)) / 2, tlines, tf, PALETTE["white"], tlh, align="left")
        if role:
            d.text((tx, pad + (h - th - 26) / 2 + th + 8), role, font=st.font(22, 600), fill=PALETTE["gray"], anchor="lt")
        if kicker:
            d.text((pad + SW - 28, pad + h / 2), str(kicker), font=st.font(36, 800), fill=col, anchor="rm")
        # optional spoken value ticks on beat 2
        if isinstance(p, dict) and p.get("value") is not None and bidx >= 1:
            cur = mo.count_value(t, beats[1], 0.9, float(p.get("from", 0)), float(p["value"]))
            txt = mo.format_number(cur, str(p.get("suffix") or ""), decimals=p.get("decimals"))
            d.text((pad + SW - 28, pad + h / 2), txt, font=st.font(36, 800), fill=col, anchor="rm")
        mo.paste_pop(im, layer, LEFT - pad, int(y - pad), sc, op)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# icon_grid_highlight — grid of icons; one highlighted on beat 2
# also used for relative bars (no numeric labels) via item['bar']
# ---------------------------------------------------------------------------

def render_icon_grid_highlight(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 62)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    items = _items(scene, "items", "cards", "icons")
    n = max(1, len(items))
    highlight = scene.get("highlight")
    if highlight is None:
        # first item marked highlight, else last
        highlight = next((i for i, it in enumerate(items) if isinstance(it, dict) and it.get("highlight")), n - 1)
    highlight = int(highlight)
    avail = BOTTOM - y0 - 8
    has_bars = any(isinstance(it, dict) and it.get("bar") is not None for it in items)
    # layout: 1 row if n<=3, else 2 rows
    cols = n if n <= 3 else math.ceil(n / 2)
    rows = 1 if n <= 3 else 2
    gap = 16
    cw = int((SW - gap * (cols - 1)) / cols)
    ch = int((avail - gap * (rows - 1)) / rows)
    for i, item in enumerate(items):
        r, c = divmod(i, cols) if rows > 1 else (0, i)
        # if last row has fewer, we still left-align
        x = LEFT + c * (cw + gap)
        y = y0 + r * (ch + gap)
        col = _col(item, i)
        start = mo.stagger(0.08, i, 0.1)
        is_hi = (i == highlight)
        # scale boost on beat 2 for the highlighted cell
        sc, op = mo.spring_pop(t, start, 0.5)
        if op <= 0:
            continue
        glow_a = 110 if (is_hi and bidx >= 1) else 60
        outline = col if (is_hi and bidx >= 1) else st.mix(col, PALETTE["white"], 0.16)
        layer, pad = mo.soft_card(cw, ch, radius=28, fill=mo.CARD, outline=outline, width=4 if (is_hi and bidx >= 1) else 3, glow=col, glow_a=glow_a)
        d = ImageDraw.Draw(layer)
        logo = _logo_for(item, 72, col)
        lab = _label(item)
        if has_bars:
            ic_y = pad + 18
        else:
            # vertically center the icon + label cluster in tall cells
            tf0, tlines0, ts0, th0, tlh0 = st.fit_text(lab, cw - 24, 120, mo.type_max(32), min_size=18, weight=800, max_lines=3)
            cluster = 64 + 24 + th0 + (30 if _sub(item) else 0)
            ic_y = pad + max(18, int((ch - cluster) / 2))
        if logo:
            ic = logo.resize((64, 64), Image.LANCZOS).convert("RGBA")
            layer.alpha_composite(ic, (pad + (cw - 64) // 2, ic_y))
        else:
            st.draw_badge(d, pad + cw / 2, ic_y + 32, 36, _shape(item, i), col)
        if has_bars:
            bar_v = float(item.get("bar") or 0) if isinstance(item, dict) else 0
            if bar_v > 1:
                bar_v = 1.0
            grow = mo.count_value(t, start + 0.25, 1.0, 0.0, bar_v)
            if bidx >= 1 and is_hi:
                # a little extra presence, still no number
                grow = mo.count_value(t, start + 0.25, 1.0, 0.0, bar_v)
            bar_top = pad + 96
            bar_bot = pad + ch - 70
            mo.draw_bar(d, (pad + 28, bar_top, pad + cw - 28, bar_bot), col, progress=grow)
            tf, tlines, ts, th, tlh = st.fit_text(lab, cw - 20, 56, 26, min_size=16, weight=800, max_lines=2)
            st.draw_lines(d, pad + cw / 2, pad + ch - 58, tlines, tf, PALETTE["white"], tlh, align="center")
        else:
            tf, tlines, ts, th, tlh = st.fit_text(lab, cw - 24, 90, 28, min_size=16, weight=800, max_lines=3)
            st.draw_lines(d, pad + cw / 2, ic_y + 80, tlines, tf, PALETTE["white"], tlh, align="center")
            sub = _sub(item)
            if sub:
                d.text((pad + cw / 2, pad + ch - 28), sub, font=st.font(18, 600), fill=PALETTE["gray"], anchor="ms")
        # dim non-highlighted slightly on beat 2
        if bidx >= 1 and not is_hi:
            op *= 0.55
        elif bidx >= 1 and is_hi:
            sc *= 1.04
        mo.paste_pop(im, layer, int(x - pad), int(y - pad), sc, op)
    return im.convert("RGB")


def render_bar_compare(scene, t):
    # convenience alias: force bar mode if items lack bar by assigning even steps? NO — never invent values.
    # If no bar is provided, use even visual heights only when highlight is set, as a metaphor:
    # unhighlighted 0.45 / 0.6, highlighted 1.0 — this is a relative "more" graphic, not a labeled stat.
    items = _items(scene, "items", "cards")
    hi = scene.get("highlight")
    if hi is None:
        hi = next((i for i, it in enumerate(items) if isinstance(it, dict) and it.get("highlight")), len(items) - 1)
    new_items = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            it = {"label": str(it)}
        it = dict(it)
        if it.get("bar") is None:
            it["bar"] = 1.0 if i == int(hi) else (0.62 if i == (int(hi) - 1) % max(1, len(items)) else 0.42)
        new_items.append(it)
    scene = dict(scene)
    scene["items"] = new_items
    scene["highlight"] = hi
    return render_icon_grid_highlight(scene, t)


# ---------------------------------------------------------------------------
# logo_card — hero brand/tool card (logo or text badge)
# ---------------------------------------------------------------------------


def render_logo_card(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 56)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    name = scene.get("name") or scene.get("brand") or scene.get("label") or ""
    sub = scene.get("sub") or scene.get("subtitle") or scene.get("caption") or ""
    kicker = scene.get("kicker") or scene.get("number") or ""
    col = st.color(scene.get("color") or "blue")
    avail = BOTTOM - y0 - 8
    sc, op = mo.spring_pop(t, 0.06, 0.55)
    layer, pad = mo.soft_card(SW, avail, radius=36, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.2), width=3, glow=col, glow_a=90)
    d = ImageDraw.Draw(layer)
    is_brand = logos.looks_like_brand(scene.get("logo") or name)
    # colored header band
    band_h = 130
    st.rounded_rect(d, (pad, pad, pad + SW, pad + band_h), 30, fill=col)
    d.rectangle((pad, pad + band_h - 40, pad + SW, pad + band_h), fill=col)
    if kicker:
        d.text((pad + SW - 36, pad + band_h / 2), str(kicker), font=st.font(mo.type_max(56), 800), fill=PALETTE["white"], anchor="rm")

    # hero mark — vertically center the lockup in the card body
    mark = 200 if (BOTTOM - TOP) >= 1100 else 148
    logo = logos.get_logo(scene.get("logo") or name, 160, col=col, allow_badge=True)
    nf, nlines, ns, nh, nlh = st.fit_text(name, SW - 80, 180, mo.type_max(78), min_size=36, weight=800, max_lines=2)
    sub_h = 0
    if sub:
        _sf, _sl, _ss, sub_h, _slh = st.fit_text(sub, SW - 80, 100, mo.type_max(36), min_size=22, weight=600, max_lines=2)
        sub_h = sub_h + 18
    lockup = mark + 36 + nh + sub_h
    body_top = pad + band_h
    body_h = (pad + avail) - body_top
    ty = int(body_top + max(24, (body_h - lockup) / 2))
    tx = pad + (SW - mark) // 2
    if is_brand:
        d.rounded_rectangle((tx, ty, tx + mark, ty + mark), 36, fill=PALETTE["white"])
        if logo:
            ic = logo.resize((int(mark * 0.68), int(mark * 0.68)), Image.LANCZOS).convert("RGBA")
            r, g, b, a = ic.split()
            ic = Image.merge("RGBA", (r.point(lambda p: 20), g.point(lambda p: 20), b.point(lambda p: 20), a))
            layer.alpha_composite(ic, (tx + int(mark * 0.16), ty + int(mark * 0.16)))
    else:
        d.rounded_rectangle((tx, ty, tx + mark, ty + mark), 40, fill=col)
        ini = mo.initials(name)
        d.text((tx + mark / 2, ty + mark / 2), ini, font=st.font(int(mark * 0.42), 800), fill=PALETTE["white"], anchor="mm")

    name_top = ty + mark + 36
    nf, nlines, ns, nh, nlh = st.fit_text(name, SW - 80, 180, mo.type_max(78), min_size=36, weight=800, max_lines=2)
    st.draw_lines(d, pad + SW / 2, name_top, nlines, nf, PALETTE["white"], nlh, align="center")
    # subtitle appears on beat 2 if a second beat exists, else immediately after the name
    show_sub_at = beats[1] if (len(beats) > 1 and sub) else 0.35
    if sub and t >= show_sub_at - 0.05:
        sf, slines, ss, sh, slh = st.fit_text(sub, SW - 80, 100, mo.type_max(36), min_size=22, weight=600, max_lines=2)
        st.draw_lines(d, pad + SW / 2, name_top + nh + 18, slines, sf, PALETTE["gray"], slh, align="center")
    # optional extra badge only if it is not the same as the subtitle
    cap2 = scene.get("caption2") or scene.get("badge")
    if cap2 and sub and cap2.strip().lower() == sub.strip().lower():
        cap2 = ""
    if bidx >= 1 and cap2:
        cf = st.font(mo.type_max(24), 800)
        tw, _ = st.text_wh(cf, cap2)
        bx = pad + (SW - (tw + 48)) / 2
        by = pad + avail - 90
        st.rounded_rect(d, (bx, by, bx + tw + 48, by + 56), 28, fill=col)
        d.text((bx + (tw + 48) / 2, by + 28), cap2, font=cf, fill=PALETTE["white"], anchor="mm")
    mo.paste_pop(im, layer, LEFT - pad, y0 - pad, sc, op)
    return im.convert("RGB")


def render_feature_grid_checks(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 60)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    kicker = scene.get("kicker") or ""
    if kicker:
        kcol = st.color(scene.get("kicker_color") or "teal")
        mo.kicker_pill(im, kicker, t, 0.05, LEFT, y0, kcol, logo=_logo_for({"label": kicker, "logo": scene.get("kicker_logo")}, 26, kcol))
        y0 += 58
    items = _items(scene, "items", "cards", "features")
    n = max(1, len(items))
    cols = 2 if n > 2 else n
    rows = math.ceil(n / cols)
    avail = BOTTOM - y0 - 8
    gap = 28 if n > 2 else 16
    cw = int((SW - gap * (cols - 1)) / cols)
    ch = int((avail - gap * (rows - 1)) / rows)
    # connecting chevrons between cells appear on beat 2
    centers = []
    for i, item in enumerate(items):
        r, c = divmod(i, cols)
        x = LEFT + c * (cw + gap)
        y = y0 + r * (ch + gap)
        centers.append((x + cw / 2, y + ch / 2))
        col = _col(item, i)
        start = mo.stagger(0.08, i, 0.11)
        sc, op = mo.spring_pop(t, start, 0.5)
        if op <= 0:
            continue
        layer, pad = mo.soft_card(cw, ch, radius=28, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.16), width=3, glow=col, glow_a=55)
        # abstract post thumb in the top portion
        thumb_h = int(ch * 0.48)
        thumb = _post_thumb(cw - 24, thumb_h, col, variant=i)
        layer.alpha_composite(thumb, (pad + 12, pad + 12))
        d = ImageDraw.Draw(layer)
        lab = _label(item)
        tf, tlines, ts, th, tlh = st.fit_text(lab, cw - 28, ch - thumb_h - 20, 28, min_size=16, weight=800, max_lines=2)
        st.draw_lines(d, pad + 16, pad + thumb_h + 22, tlines, tf, PALETTE["white"], tlh, align="left")
        # check circle top-right, fills on beat 2 (or staggered after pop)
        check_at = (beats[1] + i * 0.14) if len(beats) > 1 else start + 0.45
        prog = st.clamp01((t - check_at) / 0.35)
        st.draw_check(d, pad + cw - 36, pad + 36, 44, col, progress=prog)
        mo.paste_pop(im, layer, int(x - pad), int(y - pad), sc, op)
    # small chevrons in the gaps between neighbors (not through the cards)
    if bidx >= 1 and n >= 2:
        lin = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lin)
        a = st.appear(t, beats[1], 0.35)
        if a > 0:
            def chevron(x, y, dx, dy, col):
                # small filled arrow in the gap
                cola = st.with_alpha(col, int(230 * a))
                if dx:  # horizontal
                    ld.ellipse((x - 14, y - 14, x + 14, y + 14), fill=cola)
                    ld.polygon([(x - 5 * dx, y - 6), (x - 5 * dx, y + 6), (x + 7 * dx, y)], fill=PALETTE["white"])
                else:
                    ld.ellipse((x - 14, y - 14, x + 14, y + 14), fill=cola)
                    ld.polygon([(x - 6, y - 5 * dy), (x + 6, y - 5 * dy), (x, y + 7 * dy)], fill=PALETTE["white"])
            # between horizontal neighbors
            for i, item in enumerate(items):
                r, c = divmod(i, cols)
                if c < cols - 1 and (i + 1) < n and (i + 1) // cols == r:
                    x = LEFT + (c + 1) * (cw + gap) - gap / 2
                    y = y0 + r * (ch + gap) + ch / 2
                    chevron(x, y, 1, 0, st.cycle_color(i))
            # between vertical neighbors
            for i, item in enumerate(items):
                r, c = divmod(i, cols)
                below = i + cols
                if below < n:
                    x = LEFT + c * (cw + gap) + cw / 2
                    y = y0 + (r + 1) * (ch + gap) - gap / 2
                    chevron(x, y, 0, 1, st.cycle_color(i + 1))
        im.alpha_composite(lin)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# messy_to_clean — scattered pieces on beat 1 snap into a tidy card on beat 2
# ---------------------------------------------------------------------------


def render_messy_to_clean(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 60)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    items = _items(scene, "items", "pieces", "swatches")
    clean_label = scene.get("clean_label") or ""
    # avoid a duplicate heading when the scene title already says the same thing
    if clean_label and title and clean_label.strip().lower() == title.strip().lower():
        clean_label = ""
    col = st.color(scene.get("color") or "blue")
    avail = BOTTOM - y0 - 4
    snap_t = beats[1] if len(beats) > 1 else dur * 0.48
    p = st.clamp01((t - snap_t) / 0.7)
    p = mo.spring(p * 1.1, omega=12, zeta=0.7) if t >= snap_t else 0.0

    # tidy card fades in as pieces land
    sc_c, op_c = mo.spring_pop(t, snap_t, 0.55)
    inner_top = 20
    if op_c > 0.05:
        card, pad = mo.soft_card(SW, avail, radius=34, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.2), width=3, glow=col, glow_a=80)
        d = ImageDraw.Draw(card)
        if clean_label:
            hf, hlines, hs, hh, hlh = st.fit_text(clean_label, SW - 64, 80, 40, min_size=22, weight=800, max_lines=2)
            st.draw_lines(d, pad + 32, pad + 24, hlines, hf, PALETTE["white"], hlh, align="left")
            inner_top = 24 + hh + 16
        mo.paste_pop(im, card, LEFT - pad, y0 - pad, max(0.92, sc_c), op_c * 0.95)

    swatches = [it for it in items if not isinstance(it, dict) or (it.get("type") or "swatch") == "swatch"]
    types = [it for it in items if isinstance(it, dict) and it.get("type") in ("type", "text", "specimen", "label")]
    if not swatches and not types:
        swatches = items

    n_sw = max(1, len(swatches))
    # destinations fill the tidy card: swatch row ~38%, type row the rest
    pad_in = 22
    sw_y = y0 + inner_top
    sw_h = max(100, int((avail - inner_top - 20) * 0.38))
    sw_w = int((SW - pad_in * 2 - 12 * (n_sw - 1)) / n_sw)
    sw_x0 = LEFT + pad_in
    type_y = sw_y + sw_h + 18
    type_h = max(120, (y0 + avail) - type_y - 18)

    JITTER = [
        (-80, 50, -11), (90, -30, 9), (-40, 70, -7), (60, 40, 8),
        (-100, -20, 6), (40, 80, -9), (110, 20, 5), (-50, -40, 10),
    ]

    def _lerp(a, b, u):
        return a + (b - a) * u

    def _clamp_pos(x, y, w, h):
        x = max(LEFT, min(x, RIGHT - w))
        y = max(y0, min(y, BOTTOM - h))
        return x, y

    for i, it in enumerate(swatches):
        col_i = _col(it, i)
        dest_x = sw_x0 + i * (sw_w + 12)
        dest_y = sw_y
        jx, jy, jrot = JITTER[i % len(JITTER)]
        mx, my = _clamp_pos(dest_x + jx, dest_y + jy + 30, sw_w, sw_h)
        u = p
        x = _lerp(mx, dest_x, u)
        y = _lerp(my, dest_y, u)
        rot = _lerp(jrot, 0, u)
        start = mo.stagger(0.08, i, 0.09)
        sc, op = mo.spring_pop(t, start, 0.45)
        if op <= 0:
            continue
        layer, pad = mo.soft_card(sw_w, sw_h, radius=20, fill=mo.CARD_ELEV, outline=col_i, width=2, glow=col_i, glow_a=40, shadow=True)
        d = ImageDraw.Draw(layer)
        # color chip fills most of the cell
        inset = 10
        st.rounded_rect(d, (pad + inset, pad + inset, pad + sw_w - inset, pad + sw_h - inset), 14, fill=col_i)
        lab = _label(it) or ""
        if lab:
            tf, tlines, ts, th, tlh = st.fit_text(lab, sw_w - 16, 36, 18, min_size=12, weight=700, max_lines=1)
            # name sits on the color chip in white
            st.draw_lines(d, pad + sw_w / 2, pad + sw_h - inset - th - 4, tlines, tf, PALETTE["white"], tlh, align="center")
        if abs(rot) > 0.4:
            layer = layer.rotate(rot, resample=Image.BICUBIC, expand=True)
            mo.paste_pop(im, layer, int(x - layer.size[0] / 2 + sw_w / 2), int(y - layer.size[1] / 2 + sw_h / 2), sc, op)
        else:
            mo.paste_pop(im, layer, int(x - pad), int(y - pad), sc, op)

    specs = types
    if specs:
        m = len(specs)
        tw = int((SW - pad_in * 2 - 16 * (m - 1)) / m)
        for i, it in enumerate(specs):
            col_i = _col(it, i + 3, "blue")
            dest_x = LEFT + pad_in + i * (tw + 16)
            dest_y = type_y
            jx, jy, jrot = JITTER[(i + 4) % len(JITTER)]
            mx, my = _clamp_pos(dest_x + jx * 0.7, dest_y + jy * 0.5, tw, type_h)
            u = p
            x = _lerp(mx, dest_x, u)
            y = _lerp(my, dest_y, u)
            rot = _lerp(jrot * 0.8, 0, u)
            start = mo.stagger(0.16, i, 0.1)
            sc, op = mo.spring_pop(t, start, 0.45)
            if op <= 0:
                continue
            layer, pad = mo.soft_card(tw, type_h, radius=22, fill=mo.CARD, outline=st.mix(col_i, PALETTE["white"], 0.15), width=2, glow=PALETTE["blue"], glow_a=35)
            d = ImageDraw.Draw(layer)
            lab = _label(it) or "Aa"
            d.text((pad + tw / 2, pad + type_h * 0.42), lab, font=st.font(min(84, int(type_h * 0.42)), 800), fill=PALETTE["white"], anchor="mm")
            sub = _sub(it)
            if sub:
                d.text((pad + tw / 2, pad + type_h * 0.78), sub, font=st.font(22, 600), fill=PALETTE["gray"], anchor="mm")
            if abs(rot) > 0.4:
                layer = layer.rotate(rot, resample=Image.BICUBIC, expand=True)
                mo.paste_pop(im, layer, int(x - layer.size[0] / 2 + tw / 2), int(y - layer.size[1] / 2 + type_h / 2), sc, op)
            else:
                mo.paste_pop(im, layer, int(x - pad), int(y - pad), sc, op)
    return im.convert("RGB")


def render_doc_timeline(scene, t):
    im = mo.canvas(t)
    title = scene.get("title") or ""
    y0 = mo.title_block(im, title, t, 0.0, 58)
    beats, bidx, tloc, dur = mo.beats_of(scene, t)
    TOP, BOTTOM, LEFT, RIGHT, SW, SH = _safe()
    lines = _items(scene, "lines", "items", "instructions")
    doc_title = scene.get("doc_title") or "Instructions"
    timeline_label = scene.get("timeline_label") or scene.get("caption") or ""
    col = st.color(scene.get("color") or "pink")
    avail = BOTTOM - y0 - 8
    # split: doc on top, timeline below (timeline reserved even before beat 2 so layout doesn't jump)
    gap = 18
    tl_h = min(220, max(150, int(avail * 0.38)))
    doc_h = avail - tl_h - gap
    # document card
    sc, op = mo.spring_pop(t, 0.06, 0.5)
    if op > 0:
        layer, pad = mo.soft_card(SW, doc_h, radius=30, fill=mo.CARD, outline=st.mix(col, PALETTE["white"], 0.16), width=3, glow=col, glow_a=60)
        d = ImageDraw.Draw(layer)
        # window chrome
        d.ellipse((pad + 20, pad + 18, pad + 36, pad + 34), fill=(255, 80, 80, 255))
        d.ellipse((pad + 44, pad + 18, pad + 60, pad + 34), fill=(255, 180, 40, 255))
        d.ellipse((pad + 68, pad + 18, pad + 84, pad + 34), fill=(60, 200, 110, 255))
        d.text((pad + 100, pad + 26), doc_title, font=st.font(22, 700), fill=PALETTE["gray"], anchor="lm")
        n = max(1, len(lines))
        row_top = pad + 56
        row_h = max(52, int((doc_h - 64) / n))
        for i, line in enumerate(lines):
            yy = row_top + i * row_h
            lcol = _col(line, i, "teal")
            lab = _label(line)
            start = mo.stagger(0.22, i, 0.16)
            a = st.appear(t, start, 0.25)
            if a <= 0:
                continue
            # line plate
            st.rounded_rect(d, (pad + 16, yy, pad + SW - 16, yy + row_h - 8), 14, fill=st.with_alpha(mo.CARD_ELEV, int(230 * a)))
            prog = st.clamp01((t - (start + 0.15)) / 0.35)
            st.draw_check(d, pad + 48, yy + (row_h - 8) / 2, 36, lcol, progress=prog)
            tf, tlines, ts, th, tlh = st.fit_text(lab, SW - 110, row_h - 16, 28, min_size=16, weight=700, max_lines=2)
            st.draw_lines(d, pad + 76, yy + ((row_h - 8) - th) / 2, tlines, tf, st.with_alpha(PALETTE["white"], int(255 * a)), tlh, align="left")
        mo.paste_pop(im, layer, LEFT - pad, y0 - pad, sc, op)

    # timeline on beat 2 (or slightly earlier if only one beat)
    tl_at = beats[1] if len(beats) > 1 else 0.9
    sc2, op2 = mo.spring_pop(t, tl_at, 0.5)
    if op2 > 0:
        ty = y0 + doc_h + gap
        layer, pad = mo.soft_card(SW, tl_h, radius=26, fill=mo.CARD, outline=st.mix(PALETTE["amber"], PALETTE["white"], 0.16), width=3, glow=PALETTE["amber"], glow_a=55)
        d = ImageDraw.Draw(layer)
        if timeline_label:
            d.text((pad + 24, pad + 22), timeline_label, font=st.font(24, 800), fill=PALETTE["white"], anchor="lm")
        # track
        track_y = pad + (58 if timeline_label else 28)
        track_h = tl_h - (track_y - pad) - 24
        st.rounded_rect(d, (pad + 18, track_y, pad + SW - 18, track_y + track_h), 12, fill=mo.CARD_ELEV)
        # clip blocks (structural, unlabeled durations — not stats)
        nclips = max(3, min(5, len(lines) or 3))
        cols = [st.cycle_color(i) for i in range(nclips)]
        widths = [0.22, 0.18, 0.28, 0.16, 0.16][:nclips]
        # normalize
        s = sum(widths)
        widths = [w / s for w in widths]
        grow = st.clamp01((t - tl_at) / 0.7)
        x = pad + 26
        inner_w = SW - 52
        for i, (wfrac, ccol) in enumerate(zip(widths, cols)):
            cw = int(inner_w * wfrac * grow) - 8
            if cw > 8:
                st.rounded_rect(
                    d,
                    (x, track_y + 10, x + cw, track_y + track_h - 10),
                    8,
                    fill=st.mix(ccol, mo.CARD, 0.15),
                    outline=ccol,
                    width=2,
                )
            x += max(cw, 0) + 8
        # playhead
        ph = st.clamp01((t - tl_at - 0.2) / max(0.8, dur - tl_at))
        px = pad + 26 + int((SW - 52) * ph)
        d.rectangle((px, track_y + 2, px + 4, track_y + track_h - 2), fill=PALETTE["white"])
        d.polygon([(px - 8, track_y - 4), (px + 12, track_y - 4), (px + 2, track_y + 10)], fill=PALETTE["white"])
        layer = mo.apply_wipe(layer, st.clamp01((t - tl_at) / 0.4), "left")
        mo.paste_pop(im, layer, LEFT - pad, ty - pad, sc2, op2)
    return im.convert("RGB")


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

RENDERERS = {
    "network": render_network,
    "pipeline": render_pipeline,
    "compare": render_compare,
    "cards": render_cards,
    "checklist": render_checklist,
    "emphasis": render_emphasis,
    "counter": render_counter,
    "donut": render_donut,
    "progress": render_progress,
    "gauge": render_gauge,
    "before_after": render_before_after,
    "chat_mockup": render_chat_mockup,
    "profile_card": render_profile_card,
    "icon_grid_highlight": render_icon_grid_highlight,
    "logo_card": render_logo_card,
    "feature_grid_checks": render_feature_grid_checks,
    "messy_to_clean": render_messy_to_clean,
    "doc_timeline": render_doc_timeline,
    "bar_compare": render_bar_compare,
}

# v4 rich UI-storytelling templates
from ui_story import RENDERERS as _UI_RENDERERS
RENDERERS.update(_UI_RENDERERS)


def render_frame(scene: dict, t: float) -> Image.Image:
    kind = (scene.get("template") or scene.get("type") or "emphasis").lower().strip()
    if kind not in RENDERERS:
        raise ValueError(f"Unknown template {kind!r}. Choose one of: {', '.join(TEMPLATES)}")
    return RENDERERS[kind](scene, t)
