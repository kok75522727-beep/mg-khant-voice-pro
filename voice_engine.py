"""VoiceMaker.in Burmese TTS engine for the Mg Khant AI Streamlit app."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from urllib.parse import urljoin

import requests

try:
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None

VOICE_MAKER_TTS_URL = "https://developer.voicemaker.in/api/v1/voice/convert"
VOICE_MAKER_VOICE_ID = "ai3-my-MM-Khine"
VOICE_MAKER_LANGUAGE = "my-MM"
VOICE_MAKER_ENGINE = "neural"
VOICE_MAKER_CHUNK_CHARS = 4000

FEATURED_VOICES = [(VOICE_MAKER_VOICE_ID, "+0Hz", "စိုင်းစိုင်း", "စိုင်းစိုင်း")]

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
    path = Path(audio_path)
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav_file:
                return wav_file.getnframes() / float(wav_file.getframerate())
        except Exception:
            return None
    if MP3 is not None:
        try:
            return float(MP3(str(path)).info.length)
        except Exception:
            pass
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def split_tts_chunks(text, max_chars=VOICE_MAKER_CHUNK_CHARS):
    """Split long Burmese text at punctuation or spaces before the API call."""
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


def write_segmented_srt(text, output_path, duration_seconds=None):
    segments = split_subtitle_segments(text)
    total_duration = float(duration_seconds or (len(segments) * 1.6))
    cue_duration = total_duration / len(segments)
    cues = []
    for index, segment in enumerate(segments, 1):
        start = (index - 1) * cue_duration
        end = total_duration if index == len(segments) else index * cue_duration
        cues.append(f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{segment}\n")
    Path(output_path).write_text("\n".join(cues), encoding="utf-8")


def write_fallback_srt(text, output_path, duration_seconds=30):
    write_segmented_srt(text, output_path, duration_seconds)


def increment_usage():
    stats = {"count": 0}
    if USAGE_FILE.exists():
        try:
            stats = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    stats["count"] = stats.get("count", 0) + 1
    USAGE_FILE.write_text(json.dumps(stats), encoding="utf-8")


def get_usage_count():
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text(encoding="utf-8")).get("count", 0)
        except (OSError, ValueError):
            return 0
    return 0


def _secret_value(name):
    value = os.getenv(name)
    if value:
        return str(value)
    try:
        import streamlit as st
        return str(st.secrets.get(name, ""))
    except Exception:
        return ""


def get_voicemaker_voices(limit=10):
    """Return the configured Burmese VoiceMaker voice."""
    api_key = _secret_value("VOICEMAKER_API_KEY").strip()
    if not api_key:
        raise RuntimeError("VOICEMAKER_API_KEY ကို Streamlit Secrets ထဲ ထည့်ပါ။")
    return FEATURED_VOICES[:limit]


def _as_api_number(value, default=0):
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value or ""))
    return int(float(match.group(0))) if match else default


def _speed_to_master_speed(rate):
    return max(-100, min(100, _as_api_number(rate, 0)))


def _pitch_to_master_pitch(pitch):
    return max(-100, min(100, _as_api_number(pitch, 0)))


def _append_mp3_files(paths, output_path):
    """Concatenate MP3 chunks with ffmpeg's concat demuxer using safe paths."""
    concat_file = Path(output_path).with_suffix(".concat.txt")
    try:
        lines = []
        for path in paths:
            safe_path = Path(path).resolve().as_posix().replace("'", "'\\''")
            lines.append(f"file '{safe_path}'")
        concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
             "-safe", "0", "-i", str(concat_file), "-c", "copy", str(output_path)],
            check=True, capture_output=True, text=True, timeout=300,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg မတွေ့ပါ။ Streamlit deployment environment တွင် ffmpeg ထည့်ပါ။") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"MP3 အပိုင်းများပေါင်းရာတွင် အမှား: {exc.stderr[-1000:]}") from exc
    finally:
        try:
            concat_file.unlink()
        except OSError:
            pass


def _download_audio(audio_url, target_path, api_key):
    if not audio_url:
        raise RuntimeError("VoiceMaker response ထဲမှာ audio path မတွေ့ပါ။")
    absolute_url = urljoin(VOICE_MAKER_TTS_URL, str(audio_url))
    response = requests.get(absolute_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=180)
    if not response.ok:
        raise RuntimeError(f"VoiceMaker audio download error {response.status_code}: {response.text[:700]}")
    target_path.write_bytes(response.content)
    if target_path.stat().st_size < 100:
        raise RuntimeError("VoiceMaker အသံအပိုင်း ဗလာဖြစ်နေပါသည်။")


def generate_voicemaker_tts(text, voice_id=VOICE_MAKER_VOICE_ID, rate="+0%", pitch="+0Hz"):
    """Generate Burmese MP3 audio through VoiceMaker and create an SRT file."""
    api_key = _secret_value("VOICEMAKER_API_KEY").strip()
    if not api_key:
        raise RuntimeError("VOICEMAKER_API_KEY ကို Streamlit Secrets ထဲ ထည့်ပါ။")
    voice_id = voice_id or VOICE_MAKER_VOICE_ID
    chunks = split_tts_chunks(text)
    output_file = Path("output.mp3")
    sub_file = Path("output.srt")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    with tempfile.TemporaryDirectory(prefix="mgkhant_voicemaker_") as temp_dir:
        temp_path = Path(temp_dir)
        chunk_files = []
        for index, chunk_text in enumerate(chunks):
            payload = {
                "Engine": VOICE_MAKER_ENGINE,
                "VoiceId": voice_id,
                "LanguageCode": VOICE_MAKER_LANGUAGE,
                "Text": chunk_text,
                "OutputFormat": "mp3",
                "SampleRate": "48000",
                "MasterVolume": "0",
                "MasterSpeed": str(_speed_to_master_speed(rate)),
                "MasterPitch": str(_pitch_to_master_pitch(pitch)),
            }
            response = requests.post(VOICE_MAKER_TTS_URL, headers=headers, json=payload, timeout=180)
            if not response.ok:
                raise RuntimeError(f"VoiceMaker TTS error {response.status_code}: {response.text[:1000]}")
            try:
                result = response.json()
            except ValueError as exc:
                raise RuntimeError(f"VoiceMaker response JSON မဟုတ်ပါ: {response.text[:500]}") from exc
            if not result.get("success", False):
                raise RuntimeError(f"VoiceMaker TTS မအောင်မြင်ပါ: {json.dumps(result, ensure_ascii=False)[:1000]}")
            chunk_file = temp_path / f"chunk_{index:04d}.mp3"
            _download_audio(result.get("path"), chunk_file, api_key)
            chunk_files.append(chunk_file)
        _append_mp3_files(chunk_files, output_file)

    duration = get_audio_duration(output_file)
    if not duration or duration <= 0:
        raise RuntimeError("VoiceMaker audio duration မရပါ။")
    write_segmented_srt(text, sub_file, duration)
    return output_file, sub_file


def run_tts_to_file(text, voice_id, pitch_offset, rate="+0%", suffix="output", api_key=None):
    audio_path, sub_path = generate_voicemaker_tts(text, voice_id, rate=rate, pitch=pitch_offset)
    final_audio = Path(f"output_{suffix}{audio_path.suffix}")
    final_srt = Path(f"output_{suffix}.srt")
    shutil.copyfile(audio_path, final_audio)
    shutil.copyfile(sub_path, final_srt)
    increment_usage()
    return final_audio, final_srt


def change_tempo(input_path, tempo):
    return Path(input_path)


def apply_effects(input_path, effect_name, tempo=1.0):
    return Path(input_path)


__all__ = [
    "FEATURED_VOICES",
    "EFFECTS",
    "get_voicemaker_voices",
    "generate_voicemaker_tts",
    "change_tempo",
    "get_usage_count",
    "run_tts_to_file",
    "apply_effects",
    ]
                                 
