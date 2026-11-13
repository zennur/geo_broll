#!/usr/bin/env python3
"""geo_broll — generic geometric motion-graphics B-roll from a video + scene spec.

Commands:
  transcribe VIDEO -o transcript.json
  edit SPEC.json -o trimmed.mp4
  render SPEC.json -o DIR
  preview SPEC.json -o DIR
  composite SPEC.json -o OUT.mp4
  run SPEC.json -o OUT.mp4
  contact SPEC.json --video OUT.mp4 -o contact.jpg
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def apply_spec_style(spec: dict):
    style = spec.get("style") or {}
    if not style:
        return
    from style import apply_insets, apply_palette
    apply_insets(
        safe_top=style.get("safe_top"),
        safe_bottom=style.get("safe_bottom"),
        safe_left=style.get("safe_left"),
        safe_right=style.get("safe_right"),
    )
    if style.get("palette"):
        apply_palette(style["palette"])


def _resolve_path(value, base: Path, must_exist: bool = True) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    for cand in (Path.cwd() / path, base / path):
        if cand.exists():
            return str(cand.resolve())
    if must_exist:
        return str(path)
    return str((base / path).resolve())


def load_spec(path: Path) -> dict:
    spec = json.loads(Path(path).read_text())
    if "scenes" not in spec:
        raise SystemExit(f"{path} has no 'scenes' list")
    # resolve relative paths against the spec file and CWD
    base = Path(path).parent
    src = spec.get("source") or {}
    if src.get("path"):
        src["path"] = _resolve_path(src["path"], base, must_exist=True)
        spec["source"] = src
    comp = spec.get("composite") or {}
    for key in ("captions", "music"):
        if comp.get(key):
            comp[key] = _resolve_path(comp[key], base, must_exist=True)
    if comp:
        spec["composite"] = comp
    if spec.get("output") and not Path(spec["output"]).is_absolute():
        spec["output"] = str((base / spec["output"]).resolve())
    return spec


def cmd_transcribe(args):
    from transcribe import transcribe
    result = transcribe(
        Path(args.video),
        out=Path(args.output) if args.output else None,
        model_name=args.model,
        offset=args.offset,
        duration=args.duration,
        language=args.language,
    )
    if not args.output:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(f"wrote {args.output}  ({len(result['segments'])} segments)")



def cmd_edit(args):
    from edit import materialize_from_spec, keep_ranges_from_spec, crossfade_from_spec, edited_duration
    spec = load_spec(Path(args.spec))
    dest = Path(args.output or spec.get("output") or "edited_source.mp4")
    ranges = keep_ranges_from_spec(spec)
    cf = crossfade_from_spec(spec)
    dur = edited_duration(ranges, cf)
    print(f"keep_ranges={ranges}  crossfade={cf:.3f}s  edited duration={dur:.3f}s")
    materialize_from_spec(spec, dest)
    print(f"wrote {dest}")


def cmd_render(args):
    from render import render_scene_mp4, preview_frames, scene_duration
    spec = load_spec(Path(args.spec))
    apply_spec_style(spec)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    for i, scene in enumerate(spec["scenes"], 1):
        sid = scene.get("id") or f"s{i}_{scene.get('template','scene')}"
        dest = out / f"{sid}.mp4"
        print(f"rendering {sid} ({scene_duration(scene):.2f}s, {scene.get('template')}) -> {dest}")
        render_scene_mp4(scene, dest)
        if args.preview:
            preview_frames(scene, out / "preview")
    print("done")


def cmd_preview(args):
    from render import preview_frames
    spec = load_spec(Path(args.spec))
    apply_spec_style(spec)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    for i, scene in enumerate(spec["scenes"], 1):
        scene = dict(scene)
        scene.setdefault("id", scene.get("id") or f"s{i}_{scene.get('template','scene')}")
        paths = preview_frames(scene, out)
        for p in paths:
            print(p)


def _scene_clips(spec, clip_dir: Path):
    clips = []
    for i, scene in enumerate(spec["scenes"], 1):
        sid = scene.get("id") or f"s{i}_{scene.get('template','scene')}"
        path = clip_dir / f"{sid}.mp4"
        if not path.exists():
            raise SystemExit(f"missing rendered clip {path}; run `render` first or use `run`")
        clips.append((scene, path))
    return clips


def cmd_composite(args):
    from composite import composite
    spec = load_spec(Path(args.spec))
    clips = _scene_clips(spec, Path(args.clips))
    dest = Path(args.output or spec.get("output") or "out.mp4")
    print(f"compositing {len(clips)} cutaways -> {dest}")
    composite(spec, clips, dest)
    print(f"wrote {dest}")


def cmd_run(args):
    from render import render_scene_mp4, scene_duration
    from composite import composite
    spec = load_spec(Path(args.spec))
    apply_spec_style(spec)
    dest = Path(args.output or spec.get("output") or "out.mp4")
    clip_dir = Path(args.clips or (ROOT / "out" / dest.stem))
    clip_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, scene in enumerate(spec["scenes"], 1):
        sid = scene.get("id") or f"s{i}_{scene.get('template','scene')}"
        path = clip_dir / f"{sid}.mp4"
        print(f"rendering {sid} ({scene_duration(scene):.2f}s, {scene.get('template')})")
        render_scene_mp4(scene, path)
        clips.append((scene, path))
    print(f"compositing -> {dest}")
    composite(spec, clips, dest)
    print(f"wrote {dest}")


def cmd_contact(args):
    from contact import write_contact_sheet
    spec = load_spec(Path(args.spec))
    video = Path(args.video or spec.get("output") or "")
    if not video or not video.exists():
        raise SystemExit("pass --video path to the composited mp4 (or set spec.output)")
    dest = Path(args.output or (video.parent / f"{video.stem}_contact.jpg"))
    write_contact_sheet(spec, video, dest)
    print(f"wrote {dest}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transcribe", help="Transcribe a video with word timestamps")
    t.add_argument("video")
    t.add_argument("-o", "--output", help="JSON path (default: stdout)")
    t.add_argument("--model", default="small")
    t.add_argument("--offset", type=float, default=0.0)
    t.add_argument("--duration", type=float, default=None)
    t.add_argument("--language", default="en")
    t.set_defaults(func=cmd_transcribe)

    e = sub.add_parser("edit", help="Write a trimmed talking-head from edit.keep_ranges")
    e.add_argument("spec")
    e.add_argument("-o", "--output", help="trimmed mp4 path")
    e.set_defaults(func=cmd_edit)

    r = sub.add_parser("render", help="Render each scene in a spec to an mp4 folder")
    r.add_argument("spec")
    r.add_argument("-o", "--output", required=True, help="output folder for scene mp4s")
    r.add_argument("--preview", action="store_true")
    r.set_defaults(func=cmd_render)

    pr = sub.add_parser("preview", help="Write a few stills per scene (no video encode)")
    pr.add_argument("spec")
    pr.add_argument("-o", "--output", required=True)
    pr.set_defaults(func=cmd_preview)

    c = sub.add_parser("composite", help="Lay already-rendered scenes over the source video")
    c.add_argument("spec")
    c.add_argument("-o", "--output")
    c.add_argument("--clips", required=True, help="folder produced by `render`")
    c.set_defaults(func=cmd_composite)

    u = sub.add_parser("run", help="Render all scenes and composite in one step")
    u.add_argument("spec")
    u.add_argument("-o", "--output")
    u.add_argument("--clips", help="folder for intermediate scene mp4s")
    u.set_defaults(func=cmd_run)

    ct = sub.add_parser("contact", help="Build a contact-sheet JPEG from a finished render")
    ct.add_argument("spec")
    ct.add_argument("--video", help="composited mp4 (default: spec.output)")
    ct.add_argument("-o", "--output", help="JPEG path")
    ct.set_defaults(func=cmd_contact)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
