import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import edge_tts
import requests

try:
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None

# ---------------------------------------------------------------------------
# Voice list: first two are the existing Myanmar Edge voices; the next eight
# are ElevenLabs voice slots. The names shown in the UI are labels only.
# ---------------------------------------------------------------------------

FEATURED_VOICES = [
    ("edge:my-MM-ThihaNeural", "+0Hz", "Thiha", "မြန်မာအသံ (Thiha)"),
    ("edge:my-MM-NilarNeural", "+0Hz", "Nilar", "မြန်မာအသံ (Nilar)"),
    ("eleven:1", "+0Hz", "ကိုဇင်မင်း", "မင်းသား Voice 1"),
    ("eleven:2", "+0Hz", "ကိုထက်အောင်", "မင်းသား Voice 2"),
    ("eleven:3", "+0Hz", "ကိုရဲမင်း", "မင်းသား Voice 3"),
    ("eleven:4", "+0Hz", "ကိုသီဟ", "မင်းသား Voice 4"),
    ("eleven:5", "+0Hz", "မေသက်", "မင်းသမီး Voice 1"),
    ("eleven:6", "+0Hz", "သဇင်", "မင်းသမီး Voice 2"),
    ("eleven:7", "+0Hz", "နွယ်နွယ်", "မင်းသမီး Voice 3"),
    ("eleven:8", "+0Hz", "အိမ့်ချစ်", "မင်းသမီး Voice 4"),
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
    """Return the exact MP3 duration when mutagen is installed."""
    if MP3 is None:
        return None
    try:
        return float(MP3(str(audio_path)).info.length)
    except Exception:
        return None


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


async def generate_edge_tts(text, voice, rate="+0%", volume="+0%", pitch="+0Hz"):
    """Generate audio and SRT using the existing Edge TTS Myanmar voices."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
    output_file = Path("output.mp3")
    sub_file = Path("output.srt")
    submaker = edge_tts.SubMaker()

    with output_file.open("wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    # Use the real MP3 duration so the final SRT timestamp matches the audio.
    write_segmented_srt(text, sub_file, get_audio_duration(output_file))
    return output_file, sub_file


def _secret_value(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def generate_elevenlabs_tts(text, slot, rate="+0%", volume="+0%", pitch="+0Hz"):
    """Generate one of the eight configured ElevenLabs voices."""
    api_key = _secret_value("ELEVENLABS_API_KEY")
    slot_number = slot.rsplit(":", 1)[-1]
    voice_id = _secret_value(f"ELEVENLABS_VOICE_ID_{slot_number}")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY ကို Streamlit Secrets ထဲ ထည့်ပါ။")
    if not voice_id:
        raise RuntimeError(f"ELEVENLABS_VOICE_ID_{slot_number} မတွေ့ပါ။ ElevenLabs voice ID ထည့်ပါ။")

    try:
        rate_value = float(str(rate).replace("%", "").replace("+", ""))
    except ValueError:
        rate_value = 0.0
    speed = max(0.7, min(1.2, 1.0 + rate_value / 100.0))
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
                "speed": speed,
            },
        },
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(f"ElevenLabs TTS error {response.status_code}: {response.text[:300]}")

    output_file = Path("output.mp3")
    sub_file = Path("output.srt")
    output_file.write_bytes(response.content)
    write_segmented_srt(text, sub_file, get_audio_duration(output_file))
    return output_file, sub_file


def run_tts_to_file(text, voice_id, pitch_offset, rate="+0%", suffix="output"):
    """Route the two Edge voices and eight ElevenLabs voices only."""
    if voice_id.startswith("eleven:"):
        audio_path, sub_path = generate_elevenlabs_tts(
            text, voice_id, rate=rate, pitch=pitch_offset
        )
    elif voice_id.startswith("edge:"):
        edge_voice = voice_id.removeprefix("edge:")
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            audio_path, sub_path = loop.run_until_complete(
                generate_edge_tts(text, edge_voice, rate=rate, pitch=pitch_offset)
            )
        finally:
            loop.close()
    else:
        raise RuntimeError("မသိသော voice ID ဖြစ်ပါသည်။ Edge သို့မဟုတ် ElevenLabs voice ကို ရွေးပါ။")

    final_audio = Path(f"output_{suffix}.mp3")
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
    "change_tempo",
    "get_usage_count",
    "run_tts_to_file",
    "apply_effects",
]

