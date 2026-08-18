import asyncio
import base64
import json
import os
import re
import wave
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

try:
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None

# ---------------------------------------------------------------------------
# ElevenLabs voices shown in the UI.
# ---------------------------------------------------------------------------

FEATURED_VOICES = [
    ("eleven:EabUFUUnrDFWvAeigfZl", "+0Hz", "စိုင်းစိုင်း", "စိုင်းစိုင်း"),
]

EFFECTS = {
    "None": "",
    "Chipmunk (High Pitch)": "asetrate=44100*1.5,atempo=1/1.5",
    "Deep (Low Pitch)": "asetrate=44100*0.7,atempo=1/0.7",
    "Robot": "aformat=sample_fmts=s16:sample_rates=44100,aecho=0.8:0.88:6:0.4",
    "Echo": "aecho=0.8:0.9:1000:0.3",
    "Giant": "asetrate=44100*0.6,atempo=1/0.6,aecho=0.8:0.9:20:0.5",
    "Underwater": "lowpass=f=500",
    "Radio": "highpass=f=500,lowpass=f=3000",
}

USAGE_FILE = Path("usage_stats.json")


def split_subtitle_segments(text, max_chars=40):
    """Split Burmese into natural phrase-length lines for CapCut."""
    clean_text = re.sub(r"\s+", " ", str(text).replace("\r", "")).strip()
    if not clean_text:
        return ["အသံဖိုင်"]

    sentences = re.split(r"(?<=[။!?！？])\s*|\n+", clean_text)
    segments = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars + 1)
        # Prefer a nearby space so Burmese words and phrases stay readable;
        # only hard-split when there is no safe boundary.
            if cut < 5:
                cut = max_chars
            segments.append(sentence[:cut].strip())
            sentence = sentence[cut:].lstrip()
        if sentence:
            segments.append(sentence)
    return segments or [clean_text]


def _srt_time(seconds):
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def get_audio_duration(audio_path):
    """Return the exact duration for MP3 or WAV audio."""
    path = Path(audio_path)
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav_file:
                return wav_file.getnframes() / float(wav_file.getframerate())
        except Exception:
            return None
    if MP3 is None:
        return None
    try:
        return float(MP3(str(path)).info.length)
    except Exception:
        return None


def split_tts_chunks(text, max_chars=420):
    """Split long text into safe TTS requests while preserving reading order."""
    clean_text = re.sub(r"\s+", " ", str(text).replace("\r", "")).strip()
    if not clean_text:
        return ["အသံဖိုင်"]
    chunks = []
    remaining = clean_text
    punctuation = "။!?！？,၊;:"
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        cut = max((window.rfind(mark) for mark in punctuation), default=-1)
        if cut < max_chars // 2:
            cut = window.rfind(" ")
        if cut < max_chars // 2:
            cut = max_chars
        else:
            cut += 1
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _strip_id3(mp3_bytes):
    """Remove an ID3v2 header so MP3 chunks can be joined as one stream."""
    if not mp3_bytes.startswith(b"ID3") or len(mp3_bytes) < 10:
        return mp3_bytes
    size_bytes = mp3_bytes[6:10]
    size = ((size_bytes[0] & 0x7F) << 21) | ((size_bytes[1] & 0x7F) << 14) | ((size_bytes[2] & 0x7F) << 7) | (size_bytes[3] & 0x7F)
    return mp3_bytes[10 + size:]


def write_segmented_srt(text, output_path, duration_seconds=None):
    """Write 15-character cues spanning exactly the audio duration."""
    segments = split_subtitle_segments(text)
    if not segments:
        segments = ["အသံဖိုင်"]
    total_duration = float(duration_seconds or (len(segments) * 1.6))
    cue_duration = total_duration / len(segments)
    cues = []
    for index, segment in enumerate(segments, 1):
        start = (index - 1) * cue_duration
        end = total_duration if index == len(segments) else index * cue_duration
        cues.append(
            f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{segment}\n"
        )
    Path(output_path).write_text("\n".join(cues), encoding="utf-8")


def write_fallback_srt(text, output_path, duration_seconds=30):
    """Backward-compatible wrapper that now writes segmented SRT cues."""
    write_segmented_srt(text, output_path)


def increment_usage():
    stats = {"count": 0}
    if USAGE_FILE.exists():
        try:
            with USAGE_FILE.open("r", encoding="utf-8") as f:
                stats = json.load(f)
        except (OSError, ValueError):
            pass
    stats["count"] = stats.get("count", 0) + 1
    with USAGE_FILE.open("w", encoding="utf-8") as f:
        json.dump(stats, f)


def get_usage_count():
    if USAGE_FILE.exists():
        try:
            with USAGE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f).get("count", 0)
        except (OSError, ValueError):
            return 0
    return 0


def _secret_value(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def generate_elevenlabs_tts(text, voice_id, rate="+0%", pitch="+0Hz"):
    """Generate ElevenLabs MP3 audio in safe chunks and create duration-matched SRT."""
    api_key = (_secret_value("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY ကို Streamlit Secrets ထဲ ထည့်ပါ။")
    eleven_voice_id = voice_id.removeprefix("eleven:")
    chunks = split_tts_chunks(text, max_chars=900)
    chunk_files = []
    output_file = Path("output.mp3")
    sub_file = Path("output.srt")
    with tempfile.TemporaryDirectory(prefix="mgkhant_eleven_") as temp_dir:
        temp_path = Path(temp_dir)
        for index, chunk_text in enumerate(chunks):
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice_id}",
                headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
                params={"output_format": "mp3_44100_128"},
                json={
                    "text": chunk_text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.0,
                        "use_speaker_boost": True,
                    },
                },
                timeout=90,
            )
            if not response.ok:
                raise RuntimeError(f"ElevenLabs TTS error {response.status_code}: {response.text[:500]}")
            chunk_file = temp_path / f"chunk_{index:04d}.mp3"
            chunk_file.write_bytes(response.content)
            if chunk_file.stat().st_size < 100:
                raise RuntimeError(f"ElevenLabs audio chunk {index + 1} ဗလာဖြစ်နေပါသည်။")
            chunk_files.append(chunk_file)

        manifest = temp_path / "concat.txt"
        manifest.write_text("".join(f"file '{path.as_posix()}'\n" for path in chunk_files), encoding="utf-8")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c:a", "libmp3lame", "-q:a", "2", str(output_file)],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ffmpeg မတွေ့ပါ။ Streamlit Cloud repository ထဲမှာ packages.txt ဖိုင်နဲ့ ffmpeg ထည့်ပါ။") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"ElevenLabs MP3 ပေါင်းရာတွင် အမှား: {detail}") from exc

    duration = get_audio_duration(output_file)
    if not duration or duration <= 0:
        raise RuntimeError("ElevenLabs audio duration မရပါ။")
    write_segmented_srt(text, sub_file, duration)
    return output_file, sub_file


def run_tts_to_file(text, voice_id, pitch_offset, rate="+0%", suffix="output", api_key=None):
    """Route the selected ElevenLabs voice."""
    if voice_id.startswith("eleven:"):
        audio_path, sub_path = generate_elevenlabs_tts(text, voice_id, rate=rate, pitch=pitch_offset)
    else:
        raise RuntimeError("မသိသော ElevenLabs voice ID ဖြစ်ပါသည်။")

    final_audio = Path(f"output_{suffix}{audio_path.suffix}")
    final_srt = Path(f"output_{suffix}.srt")
    shutil.copyfile(audio_path, final_audio)
    shutil.copyfile(sub_path, final_srt)
    increment_usage()
    return final_audio, final_srt


# ---------------------------------------------------------------------------
# Audio effects logic
# ---------------------------------------------------------------------------


def apply_effects(input_path, effect_name, tempo=1.0):
    input_path = Path(input_path)
    output_path = input_path.parent / f"effect_{input_path.name}"
    filter_str = EFFECTS.get(effect_name, "")

    if tempo != 1.0:
        filter_str = f"{filter_str},atempo={tempo}" if filter_str else f"atempo={tempo}"

    command = ["ffmpeg", "-y", "-i", str(input_path)]
    if filter_str:
        command += ["-af", filter_str]
    command += [str(output_path)]
    subprocess.run(command, check=True, capture_output=True)
    return output_path


def change_tempo(input_path, tempo):
    input_path = Path(input_path)
    output_path = input_path.parent / f"tempo_{input_path.name}"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-af", f"atempo={tempo}", str(output_path)],
        check=True,
        capture_output=True,
    )
    return output_path


__all__ = [
    "FEATURED_VOICES",
    "EFFECTS",
    "generate_elevenlabs_tts",
    "change_tempo",
    "get_usage_count",
    "run_tts_to_file",
    "apply_effects",
]


