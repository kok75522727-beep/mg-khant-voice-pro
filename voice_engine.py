import json
import os
import re
import shutil
import tempfile
import wave
from pathlib import Path

import requests

try:
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None

# CAMB.AI public/custom voices are loaded dynamically from the account.
# The UI will show up to ten Burmese voices returned by /list-voices.
FEATURED_VOICES = []

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
CAMB_TTS_URL = "https://client.camb.ai/apis/tts-stream"
CAMB_VOICES_URL = "https://client.camb.ai/apis/list-voices"


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
            return None
    return None


def split_tts_chunks(text, max_chars=450):
    """Split text below CAMB.AI's 500-character plan limit with a safety margin."""
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


def _camb_headers(api_key):
    return {"x-api-key": api_key, "Content-Type": "application/json"}


def get_camb_voices(limit=10):
    """Return the confirmed CAMB voice directly; list-voices may omit custom IDs."""
    api_key = _secret_value("CAMB_API_KEY").strip()
    if not api_key:
        raise RuntimeError("CAMB_API_KEY ကို Streamlit Secrets ထဲ ထည့်ပါ။")
    # Confirmed by the user from CAMB Voice Library.
    return [("198651", "+0Hz", "စိုင်းစိုင်း", "စိုင်းစိုင်း")][:limit]


def _rate_to_float(rate):
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(rate or "0"))
    percent = float(match.group(0)) if match else 0.0
    return max(0.5, min(2.0, 1.0 + percent / 100.0))


def _append_wav_files(paths, output_path):
    with wave.open(str(output_path), "wb") as out:
        for index, path in enumerate(paths):
            with wave.open(str(path), "rb") as src:
                if index == 0:
                    out.setnchannels(src.getnchannels())
                    out.setsampwidth(src.getsampwidth())
                    out.setframerate(src.getframerate())
                elif (src.getnchannels(), src.getsampwidth(), src.getframerate()) != (out.getnchannels(), out.getsampwidth(), out.getframerate()):
                    raise RuntimeError("CAMB အသံအပိုင်းများ၏ audio format မတူပါ။")
                out.writeframes(src.readframes(src.getnframes()))


def generate_camb_tts(text, voice_id, rate="+0%", pitch="+0Hz"):
    """Generate Burmese WAV audio through CAMB.AI streaming TTS."""
    api_key = _secret_value("CAMB_API_KEY").strip()
    if not api_key:
        raise RuntimeError("CAMB_API_KEY ကို Streamlit Secrets ထဲ ထည့်ပါ။")
    language = (_secret_value("CAMB_LANGUAGE") or "my-mm").strip().lower()
    speech_model = (_secret_value("CAMB_SPEECH_MODEL") or "mars-8.1-flash-beta").strip()
    speaking_rate = _rate_to_float(rate)
    chunks = split_tts_chunks(text)
    output_file = Path("output.wav")
    sub_file = Path("output.srt")

    with tempfile.TemporaryDirectory(prefix="mgkhant_camb_") as temp_dir:
        temp_path = Path(temp_dir)
        chunk_files = []
        for index, chunk_text in enumerate(chunks):
            payload = {
                "text": chunk_text,
                "language": language,
                "voice_id": int(voice_id),
                "speech_model": speech_model,
                "output_configuration": {"format": "wav"},
                "voice_settings": {"speaking_rate": speaking_rate},
            }
            response = requests.post(
                CAMB_TTS_URL,
                headers=_camb_headers(api_key),
                json=payload,
                stream=True,
                timeout=180,
            )
            if not response.ok:
                raise RuntimeError(f"CAMB TTS error {response.status_code}: {response.text[:700]}")
            chunk_file = temp_path / f"chunk_{index:04d}.wav"
            with chunk_file.open("wb") as handle:
                for data in response.iter_content(chunk_size=8192):
                    if data:
                        handle.write(data)
            if chunk_file.stat().st_size < 100:
                raise RuntimeError(f"CAMB အသံအပိုင်း {index + 1} ဗလာဖြစ်နေပါသည်။")
            chunk_files.append(chunk_file)
        _append_wav_files(chunk_files, output_file)

    duration = get_audio_duration(output_file)
    if not duration or duration <= 0:
        raise RuntimeError("CAMB audio duration မရပါ။")
    write_segmented_srt(text, sub_file, duration)
    return output_file, sub_file


def run_tts_to_file(text, voice_id, pitch_offset, rate="+0%", suffix="output", api_key=None):
    audio_path, sub_path = generate_camb_tts(text, voice_id, rate=rate, pitch=pitch_offset)
    final_audio = Path(f"output_{suffix}{audio_path.suffix}")
    final_srt = Path(f"output_{suffix}.srt")
    shutil.copyfile(audio_path, final_audio)
    shutil.copyfile(sub_path, final_srt)
    increment_usage()
    return final_audio, final_srt


def change_tempo(input_path, tempo):
    # CAMB controls speaking rate at generation time; retain this helper for compatibility.
    return Path(input_path)


def apply_effects(input_path, effect_name, tempo=1.0):
    return Path(input_path)


__all__ = [
    "FEATURED_VOICES",
    "EFFECTS",
    "get_camb_voices",
    "generate_camb_tts",
    "change_tempo",
    "get_usage_count",
    "run_tts_to_file",
    "apply_effects",
    ]
    
