"""Composite rendered cutaways over a talking-head video, keeping speaker audio."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from style import W, H, FPS

from edit import (
    prepare_timeline,
    timebase_from_spec,
    split_windows_from_scenes,
    crossfade_from_spec,
)


def _srt_window(src: Path, offset: float, duration: float, dest: Path):
    def parse(ts: str) -> float:
        h, m, rest = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest.replace(",", "."))

    def fmt(v: float) -> str:
        if v < 0:
            v = 0
        return "%02d:%02d:%02d,%03d" % (v // 3600, (v % 3600) // 60, int(v % 60), round((v % 1) * 1000) % 1000)

    blocks = Path(src).read_text().strip().split("\n\n")
    out, i = [], 1
    for b in blocks:
        lines = b.split("\n")
        if len(lines) < 3:
            continue
        a, c = [parse(x) for x in lines[1].split(" --> ")]
        a -= offset
        c -= offset
        if c <= 0 or a >= duration:
            continue
        text = "\n".join(lines[2:])
        out.append(f"{i}\n{fmt(max(a, 0))} --> {fmt(min(c, duration))}\n{text}\n")
        i += 1
    dest.write_text("\n".join(out) + "\n")




def _bind_timeline(spec: dict, scene_clips: list[tuple[dict, Path]], workdir: Path | None = None):
    """Apply edit.keep_ranges if present and return remapped clips on the edited clock."""
    tmp = Path(workdir or tempfile.mkdtemp(prefix="geo_broll_"))
    tmp.mkdir(parents=True, exist_ok=True)
    prepared = prepare_timeline(spec, tmp)
    by_id = {s.get("id"): s for s in prepared["scenes"]}
    has_edit = bool((spec.get("edit") or {}).get("keep_ranges") or (spec.get("edit") or {}).get("keep"))
    tb = timebase_from_spec(spec)
    clips = []
    for scene, clip in scene_clips:
        if has_edit and tb == "source":
            rem = by_id.get(scene.get("id"))
            if rem is None:
                continue
            clips.append((rem, clip))
        else:
            clips.append((scene, clip))
    return prepared, clips, tmp


def _source_args(prepared: dict) -> list[str]:
    args = []
    if prepared["offset"]:
        args += ["-ss", str(prepared["offset"])]
    args += ["-t", str(prepared["duration"]), "-i", str(prepared["video"])]
    return args


def _finish_layout(
    spec: dict,
    prepared: dict,
    split_comp: Path,
    output: Path,
    tmp: Path,
    duration: float,
    offset: float,
) -> Path:
    """Blend full-screen hook/close with split cutaways, then burn captions and music."""
    comp = spec.get("composite") or {}
    layout = (comp.get("layout") or "split").lower()
    captions = comp.get("captions")
    music = comp.get("music")
    music_fade = float(comp.get("music_fade_start") or max(0, duration - 1.5))
    if music_fade >= duration - 0.05:
        music_fade = max(0.0, duration - 1.2)
    edit = spec.get("edit") or {}
    # 0 is a valid value (hard cut / no fade); do not treat it as missing.
    def _opt_float(*vals, default=0.0):
        for v in vals:
            if v is not None:
                return float(v)
        return default

    video_fade_out = _opt_float(edit.get("video_fade_out"), comp.get("video_fade_out"), default=0.0)
    layout_fade = _opt_float(edit.get("layout_fade"), comp.get("layout_fade"), default=0.25)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    args = ["ffmpeg", "-y", "-hide_banner", "-v", "error"]
    args += _source_args(prepared)
    args += ["-i", str(split_comp)]
    k_music = None
    if music:
        k_music = 2
        args += ["-i", str(music)]

    fg = []
    if layout in ("auto", "mixed"):
        windows = split_windows_from_scenes(prepared["scenes"])
        fg.append(
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps={FPS},setpts=PTS-STARTPTS[full]"
        )
        if not windows:
            cur = "full"
        else:
            nwin = len(windows)
            fg.append(
                f"[1:v]fps={FPS},setsar=1,format=yuva420p,split={nwin}"
                + "".join(f"[sw{i}]" for i in range(nwin))
            )
            cur = "full"
            for i, (a, b) in enumerate(windows):
                durw = max(0.05, b - a)
                fade_in = min(layout_fade, durw / 4)
                # Do not dissolve the split back to full-screen at program end:
                # that double-exposes two framings of the speaker. The closing
                # fade-to-black is the exit.
                fade_out = min(layout_fade, durw / 4)
                if b >= duration - max(video_fade_out, 0.02) - 1e-3:
                    fade_out = 0.0
                fx = []
                if fade_in > 0.02:
                    fx.append(f"fade=t=in:st={a:.3f}:d={fade_in:.3f}:alpha=1")
                if fade_out > 0.02:
                    fade_out_st = max(a, b - fade_out)
                    fx.append(f"fade=t=out:st={fade_out_st:.3f}:d={fade_out:.3f}:alpha=1")
                if fx:
                    fg.append(f"[sw{i}]" + ",".join(fx) + f"[sf{i}]")
                else:
                    fg.append(f"[sw{i}]format=yuva420p[sf{i}]")
                fg.append(
                    f"[{cur}][sf{i}]overlay=0:0:eof_action=pass:"
                    f"enable='gte(t,{a})*lt(t,{b})'[lx{i}]"
                )
                cur = f"lx{i}"
    else:
        fg.append(f"[1:v]setsar=1,fps={FPS},setpts=PTS-STARTPTS[laid]")
        cur = "laid"

    if captions:
        cap_path = Path(captions)
        cap_off = float(comp.get("caption_offset", 0 if prepared.get("materialized") else offset))
        cap_dur = float(comp.get("caption_duration", duration))
        if cap_path.suffix.lower() == ".ass":
            use_path = cap_path
            force = ""
        else:
            use_path = tmp / "captions.srt"
            _srt_window(cap_path, cap_off, cap_dur, use_path)
            style = comp.get("caption_style") or "FontSize=14,Bold=1,Outline=2,MarginV=60"
            force = f":force_style='{style}'"
        cap_esc = str(use_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")
        fg.append(f"[{cur}]subtitles={cap_esc}{force}[cap]")
        cur = "cap"

    if video_fade_out and video_fade_out > 0:
        fade_st = max(0.0, duration - video_fade_out)
        fg.append(f"[{cur}]fade=t=out:st={fade_st:.3f}:d={video_fade_out:.3f},format=yuv420p[v]")
    else:
        fg.append(f"[{cur}]format=yuv420p[v]")
    vmap = "[v]"

    if music:
        fade_out_d = 1.5 if (duration - music_fade) >= 1.5 else max(0.25, duration - music_fade)
        audio = (
            f"[{k_music}:a]atrim=0:{duration},volume=-29.5dB,aformat=channel_layouts=stereo,"
            f"afade=t=in:d=0.5,afade=t=out:st={music_fade}:d={fade_out_d:.3f}[m];"
            f"[1:a]aformat=channel_layouts=stereo,asplit[va][sc];"
            f"[m][sc]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=300[md];"
            f"[va][md]amix=inputs=2:normalize=0:duration=first[amix]"
        )
        if video_fade_out and video_fade_out > 0:
            fade_st = max(0.0, duration - video_fade_out)
            audio += f";[amix]afade=t=out:st={fade_st:.3f}:d={video_fade_out:.3f}[a]"
        else:
            audio += ";[amix]anull[a]"
        fg.append(audio)
        amap = "[a]"
    elif video_fade_out and video_fade_out > 0:
        fade_st = max(0.0, duration - video_fade_out)
        fg.append(
            f"[1:a]aformat=channel_layouts=stereo,afade=t=out:st={fade_st:.3f}:d={video_fade_out:.3f}[a]"
        )
        amap = "[a]"
    else:
        amap = "1:a"

    args += [
        "-filter_complex", ";".join(fg),
        "-map", vmap, "-map", amap,
        "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-t", str(duration),
        str(output),
    ]
    subprocess.run(args, check=True)
    return output


def composite(spec: dict, scene_clips: list[tuple[dict, Path]], output: Path, workdir: Path | None = None) -> Path:
    """
    scene_clips: list of (scene, rendered_mp4_path)
    source path/offset/duration come from spec['source']
    optional spec['composite'] for zooms, PNG overlays, captions, music
    """
    layout = ((spec.get("composite") or {}).get("layout") or "full").lower()
    if layout in ("split", "auto", "mixed"):
        return composite_split(spec, scene_clips, output, workdir)

    prepared, scene_clips, workdir = _bind_timeline(spec, scene_clips, workdir)
    video = prepared["video"]
    offset = prepared["offset"]
    duration = prepared["duration"]

    comp = spec.get("composite") or {}
    zooms = [tuple(z) for z in (comp.get("zooms") or [])]
    overlays = comp.get("overlays") or []
    captions = comp.get("captions")
    music = comp.get("music")
    music_fade = float(comp.get("music_fade_start") or max(0, duration - 1.5))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Filter graph: source (scaled 1080x1920) + optional zooms + cutaways + overlays + captions + audio
    args = [
        "ffmpeg", "-y", "-hide_banner", "-v", "error",
        "-ss", str(offset), "-t", str(duration), "-i", str(video),
    ]
    # cutaway inputs
    for scene, clip in scene_clips:
        args += ["-i", str(clip)]
    k_music = None
    if music:
        k_music = 1 + len(scene_clips)
        args += ["-i", str(music)]

    nzoom = len(zooms)
    fg = [
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1,fps={FPS},setpts=PTS-STARTPTS,split={nzoom+1}[b0]"
        + "".join(f"[z{i}]" for i in range(nzoom))
    ]
    cur = "b0"
    n = 1
    for i, (a, b) in enumerate(zooms):
        fg.append(f"[z{i}]scale=1166:2074,crop={W}:{H}:(iw-{W})/2:ih-{H}[zz{i}]")
        fg.append(f"[{cur}][zz{i}]overlay=0:0:enable='gte(t,{a})*lt(t,{b})'[c{n}]")
        cur = f"c{n}"
        n += 1

    for i, (scene, clip) in enumerate(scene_clips, start=1):
        a = float(scene["start"])
        b = float(scene["end"])
        dur = b - a
        fade = min(0.16, dur / 4)
        fg.append(
            f"[{i}:v]scale={W}:{H},setsar=1,fps={FPS},format=rgba,"
            f"trim=0:{dur:.3f},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d={fade:.3f}:alpha=1,"
            f"fade=t=out:st={max(dur-fade,0.01):.3f}:d={fade:.3f}:alpha=1,"
            f"setpts=PTS+{a}/TB[br{i}]"
        )
        fg.append(
            f"[{cur}][br{i}]overlay=0:0:eof_action=pass:enable='gte(t,{a})*lt(t,{b})'[c{n}]"
        )
        cur = f"c{n}"
        n += 1

    # PNG overlays (callouts / emojis), optional
    # We'll add them as extra inputs after building the base filter... easier in a second stage
    # to keep the input index math simple. Do one-pass: append overlay inputs now if present.
    # Actually we already started args. If overlays exist, we need their inputs before -filter_complex.
    # We'll do a two-stage encode when overlays/captions/music are present, which is simpler.

    tmp = Path(workdir or tempfile.mkdtemp(prefix="geo_broll_"))
    tmp.mkdir(parents=True, exist_ok=True)
    base = tmp / "base.mp4"

    args += [
        "-filter_complex", ";".join(fg),
        "-map", f"[{cur}]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        str(base),
    ]
    subprocess.run(args, check=True)

    if not overlays and not captions and not music:
        subprocess.run(["mv", str(base), str(output)], check=True)
        return output

    # Stage 2: overlays, captions, music
    args = ["ffmpeg", "-y", "-hide_banner", "-v", "error", "-i", str(base)]
    input_index = 1
    if music:
        args += ["-i", str(music)]
        music_idx = input_index
        input_index += 1
    fg = []
    cur = "0:v"
    for ov in overlays:
        path = Path(ov["file"])
        a, b = float(ov["start"]), float(ov["end"])
        x, y = int(ov.get("x", 60)), int(ov.get("y", 1080))
        slide = bool(ov.get("slide", True))
        args += ["-loop", "1", "-t", str(duration), "-i", str(path)]
        fl = "format=rgba"
        fl += f",fade=in:st={a}:d=0.2:alpha=1,fade=out:st={b-0.15}:d=0.15:alpha=1"
        xx = f"'{x}-max(0,0.2-(t-{a}))*300'" if slide else str(x)
        k = input_index
        fg += [
            f"[{k}:v]{fl}[o{k}]",
            f"[{cur}][o{k}]overlay=x={xx}:y={y}:enable='gte(t,{a})*lt(t,{b})'[c{k}]",
        ]
        cur = f"c{k}"
        input_index += 1

    if captions:
        cap_path = Path(captions)
        cap_off = float(comp.get("caption_offset", offset))
        cap_dur = float(comp.get("caption_duration", duration))
        if cap_path.suffix.lower() == ".ass":
            use_path = cap_path
            force = ""
        else:
            use_path = tmp / "captions.srt"
            _srt_window(cap_path, cap_off, cap_dur, use_path)
            style = comp.get("caption_style") or "FontSize=14,Bold=1,Outline=2,MarginV=60"
            force = f":force_style='{style}'"
        # escape path for ffmpeg
        cap_esc = str(use_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")
        fg.append(f"[{cur}]subtitles={cap_esc}{force},format=yuv420p[v]")
        vmap = "[v]"
    else:
        fg.append(f"[{cur}]format=yuv420p[v]")
        vmap = "[v]"

    if music:
        fg.append(
            f"[{music_idx}:a]atrim=0:{duration},volume=-29.5dB,aformat=channel_layouts=stereo,"
            f"afade=t=in:d=0.5,afade=t=out:st={music_fade}:d=1.5[m];"
            f"[0:a]aformat=channel_layouts=stereo,asplit[va][sc];"
            f"[m][sc]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=300[md];"
            f"[va][md]amix=inputs=2:normalize=0:duration=first[a]"
        )
        amap = "[a]"
    else:
        amap = "0:a"

    args += [
        "-filter_complex", ";".join(fg),
        "-map", vmap, "-map", amap,
        "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-t", str(duration),
        str(output),
    ]
    subprocess.run(args, check=True)
    return output


def composite_split(spec: dict, scene_clips: list[tuple[dict, Path]], output: Path, workdir: Path | None = None) -> Path:
    """Split-screen composite: graphics in the top ~55%, talking head in the bottom ~45%.

    Speaker is cropped from the (autorotated) source so the face sits in the lower pane.
    Cutaway mp4s are assumed to have already been rendered with safe_bottom at the split
    so their top region is the graphic pane; only that region is overlaid.
    """
    from PIL import Image, ImageDraw, ImageFilter

    prepared, scene_clips, workdir = _bind_timeline(spec, scene_clips, workdir)
    video = prepared["video"]
    offset = prepared["offset"]
    duration = prepared["duration"]

    comp = spec.get("composite") or {}
    layout = (comp.get("layout") or "split").lower()
    split_y = int(comp.get("split_y") or 1056)
    crop_cfg = comp.get("speaker_crop") or {}
    crop_y = int(crop_cfg.get("y", 340))
    crop_h = int(crop_cfg.get("h", H - split_y))
    inset = int(comp.get("speaker_inset", 20))
    top_gap = int(comp.get("speaker_top_gap", 12))
    bot_gap = int(comp.get("speaker_bottom_gap", 20))
    captions = comp.get("captions")
    music = comp.get("music")
    music_fade = float(comp.get("music_fade_start") or max(0, duration - 1.5))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(workdir)
    tmp.mkdir(parents=True, exist_ok=True)

    # Assets: dark grid for the top pane, rounded mask for the speaker card
    try:
        import sys
        root = Path(__file__).resolve().parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import motion as mo
        grid = mo.canvas(0.0).convert("RGB")
    except Exception:
        grid = Image.new("RGB", (W, H), (0, 0, 0))
        g = ImageDraw.Draw(grid)
        for i in range(0, W, 80):
            g.line((i, 0, i, H), fill=(28, 30, 38))
        for j in range(0, H, 80):
            g.line((0, j, W, j), fill=(28, 30, 38))
    grid_path = tmp / "grid.png"
    grid.save(grid_path)

    inner_w = W - inset * 2
    inner_h = (H - split_y) - top_gap - bot_gap
    mask = Image.new("L", (inner_w, inner_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, inner_w - 1, inner_h - 1), 28, fill=255)
    # slight feather on the edge
    mask = mask.filter(ImageFilter.GaussianBlur(0.6))
    mask_path = tmp / "speaker_mask.png"
    mask.save(mask_path)

    # Stage 1: split base (grid + cropped/rounded speaker + divider)
    spk_x = inset
    spk_y = split_y + top_gap
    base = tmp / "base.mp4"
    # color + grid, then speaker with mask, then divider + a soft shadow under the split
    filter_base = (
        f"color=c=0x000000:s={W}x{H}:r={FPS}:d={duration:.3f}[black];"
        f"[1:v]scale={W}:{H},setsar=1,format=rgba[grid];"
        f"[black][grid]overlay=0:0[bg];"
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1,fps={FPS},"
        f"crop={W}:{crop_h}:0:{crop_y},"
        f"scale={inner_w}:{inner_h},format=rgba[spk];"
        f"[2:v]scale={inner_w}:{inner_h},format=gray[msk];"
        f"[spk][msk]alphamerge[spka];"
        f"[bg][spka]overlay={spk_x}:{spk_y}[seated];"
        # soft shadow just above the speaker / under the divider
        f"[seated]drawbox=x=0:y={split_y-10}:w={W}:h=12:color=0x000000@0.45:t=fill,"
        f"drawbox=x=0:y={split_y-2}:w={W}:h=3:color=0x1580FF@0.7:t=fill[base]"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-v", "error",
        "-ss", str(offset), "-t", str(duration), "-i", str(video),
        "-loop", "1", "-t", str(duration), "-i", str(grid_path),
        "-loop", "1", "-t", str(duration), "-i", str(mask_path),
        "-filter_complex", filter_base,
        "-map", "[base]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        str(base),
    ]
    subprocess.run(cmd, check=True)

    # Stage 2: overlay cutaway top panes (already rendered with safe_bottom ~ split)
    args = ["ffmpeg", "-y", "-hide_banner", "-v", "error", "-i", str(base)]
    fg = []
    for i, (scene, clip) in enumerate(scene_clips, start=1):
        args += ["-i", str(clip)]
        a = float(scene["start"])
        b = float(scene["end"])
        dur = b - a
        fade = min(0.16, dur / 4)
        # crop only the graphic pane, leave the divider visible
        pane_h = split_y - 4
        fg.append(
            f"[{i}:v]scale={W}:{H},setsar=1,fps={FPS},format=rgba,"
            f"crop={W}:{pane_h}:0:0,"
            f"trim=0:{dur:.3f},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d={fade:.3f}:alpha=1,"
            f"fade=t=out:st={max(dur-fade,0.01):.3f}:d={fade:.3f}:alpha=1,"
            f"setpts=PTS+{a}/TB[br{i}]"
        )
    cur = "0:v"
    n = 1
    for i, (scene, clip) in enumerate(scene_clips, start=1):
        a = float(scene["start"])
        b = float(scene["end"])
        fg.append(
            f"[{cur}][br{i}]overlay=0:0:eof_action=pass:enable='gte(t,{a})*lt(t,{b})'[c{n}]"
        )
        cur = f"c{n}"
        n += 1

    # redraw divider on top so cutaway edges never hide it
    fg.append(
        f"[{cur}]drawbox=x=0:y={split_y-2}:w={W}:h=3:color=0x1580FF@0.7:t=fill[lined]"
    )
    cur = "lined"

    # Intermediate: split layout with graphics and divider, source audio intact.
    split_comp = tmp / "split_comp.mp4"
    args += [
        "-filter_complex", ";".join(fg),
        "-map", f"[{cur}]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        str(split_comp),
    ]
    subprocess.run(args, check=True)

    return _finish_layout(spec, prepared, split_comp, output, tmp, duration, offset)
