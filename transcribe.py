"""Transcribe a video with word timestamps via faster-whisper."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _model(name: str = "small"):
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        venv = Path(__file__).resolve().parent / ".venv/bin/python"
        hint = (
            "faster-whisper is not installed in this Python.\n"
            f"Create the tool venv and retry:\n"
            f"  python3 -m venv {Path(__file__).resolve().parent / '.venv'}\n"
            f"  {Path(__file__).resolve().parent / '.venv/bin/pip'} install -r "
            f"{Path(__file__).resolve().parent / 'requirements.txt'}\n"
            f"  {venv} geo_broll.py transcribe VIDEO -o transcript.json"
        )
        raise SystemExit(hint) from e
    return WhisperModel(name, compute_type="int8")


def extract_wav(video: Path, wav: Path, offset: float = 0.0, duration: float | None = None):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if offset:
        cmd += ["-ss", str(offset)]
    cmd += ["-i", str(video)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += ["-ac", "1", "-ar", "16000", str(wav)]
    subprocess.run(cmd, check=True)


def transcribe(
    video: Path,
    out: Path | None = None,
    model_name: str = "small",
    offset: float = 0.0,
    duration: float | None = None,
    language: str | None = "en",
) -> dict:
    video = Path(video)
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "audio.wav"
        extract_wav(video, wav, offset=offset, duration=duration)
        model = _model(model_name)
        # Pass PCM directly. Some PyAV builds reject faster-whisper's decode_audio().
        import wave
        import numpy as np
        with wave.open(str(wav), "rb") as wf:
            audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        segs, info = model.transcribe(
            audio,
            language=language,
            word_timestamps=True,
            vad_filter=False,
        )
        segments = []
        for s in segs:
            words = []
            for w in s.words or []:
                words.append({
                    "w": (w.word or "").strip(),
                    "start": round(float(w.start) + offset, 3),
                    "end": round(float(w.end) + offset, 3),
                })
            segments.append({
                "start": round(float(s.start) + offset, 3),
                "end": round(float(s.end) + offset, 3),
                "text": (s.text or "").strip(),
                "words": words,
            })
        result = {
            "source": str(video),
            "offset": offset,
            "duration": duration,
            "language": getattr(info, "language", language),
            "language_probability": getattr(info, "language_probability", None),
            "model": model_name,
            "segments": segments,
            "full_text": " ".join(s["text"] for s in segments).strip(),
        }
    if out:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result
