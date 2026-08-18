"""Google AI Studio Gemini TTS engine for the Mg Khant AI Burmese app."""

import base64
import json
import os
import re
import tempfile
import wave
from pathlib import Path

import requests

GOOGLE_TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"
GOOGLE_TTS_MODEL = "gemini-2.5-flash-preview-tts"
GOOGLE_TTS_SAMPLE_RATE = 24000
GOOGLE_TTS_CHUNK_CHARS = 2800
USAGE_FILE = Path("usage_stats.json")

# The API uses one selected prebuilt voice per request. The Burmese names are
# local labels; the style instructions make the ten choices audibly distinct.
VOICE_PROFILES = [
    {"id": "Kore", "pitch": 0, "name": "ရွှေနေ", "label": "ရွှေနေ — တည်ငြိမ်အမျိုးသား"},
    {"id": "Puck", "pitch": 2, "name": "သီဟ", "label": "သီဟ — တက်ကြွအမျိုးသား"},
    {"id": "Charon", "pitch": -3, "name": "မင်းခန့်", "label": "မင်းခန့် — နက်ရှိုင်းအမျိုးသား"},
    {"id": "Fenrir", "pitch": -5, "name": "နေတိုး", "label": "နေတိုး — အားကောင်းအမျိုးသား"},
    {"id": "Aoede", "pitch": 4, "name": "နီလာ", "label": "နီလာ — နူးညံ့အမျိုးသမီး"},
    {"id": "Leda", "pitch": 2, "name": "မေသဇင်", "label": "မေသဇင် — ရှင်းလင်းအမျိုးသမီး"},
    {"id": "Zephyr", "pitch": 5, "name": "သွန်းဝတီ", "label": "သွန်းဝတီ — ချိုသာအမျိုးသမီး"},
    {"id": "Kore", "pitch": 7, "name": "ကြယ်စင်", "label": "ကြယ်စင် — မြန်ဆန်တက်ကြွ"},
    {"id": "Puck", "pitch": 8, "name": "ဟာသလေး", "label": "ဟာသလေး — ပျော်စရာဟာသအသံ"},
    {"id": "Charon", "pitch": 1, "name": "သတင်းဖတ်သူ", "label": "သတင်းဖတ်သူ — ပရော်ဖက်ရှင်နယ်"},
]
FEATURED_VOICES = [(v["id"], v["pitch"], v["name"], v["label"]) for v in VOICE_PROFILES]

PROFILE_STYLES = {
    ("Kore", 0): "Use a calm, balanced Burmese male delivery with natural pauses.",
    ("Puck", 2): "Use an energetic Burmese male delivery with bright emphasis.",
    ("Charon", -3): "Use a deep, serious Burmese male delivery with measured pauses.",
    ("Fenrir", -5): "Use a strong, confident Burmese male delivery with firm emphasis.",
    ("Aoede", 4): "Use a gentle, warm Burmese female delivery with a soft tone.",
    ("Leda", 2): "Use a clear, polished Burmese female delivery suitable for explanations.",
    ("Zephyr", 5): "Use a cheerful, friendly Burmese female delivery with a bright tone.",
    ("Kore", 7): "Use a quick, lively Burmese delivery while keeping pronunciation clear.",
    ("Puck", 8): "Use playful comic timing, expressive reactions, and a light humorous Burmese tone.",
    ("Charon", 1): "Use a precise, authoritative Burmese news-reader delivery.",
}

EFFECTS = {
    "None": "",
    "ဟာသပုံစံ": "Speak with playful comic timing and a light, humorous tone.",
    "သတင်းဖတ်ပုံစံ": "Speak clearly and professionally like a Burmese news reader.",
    "ဇာတ်လမ်းပြောပုံစံ": "Speak warmly and expressively like a storyteller.",
}


def split_subtitle_segments(text, max_chars=40):
    clean = re.sub(r"\s+", " ", str(text).replace("\r", "")).strip()
    if not clean:
        return ["အသံဖိုင်"]
    sentences = re.split(r"(?<=[။!?！？])\s*|\n+", clean)
    segments = []
    for sentence in sentences:
        sentence = sentence.strip()
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars + 1)
            if cut < 5:
                cut = max_chars
            segments.append(sentence[:cut].strip())
            sentence = sentence[cut:].lstrip()
        if sentence:
            segments.append(sentence)
    return segments or [clean]


def _srt_time(seconds):
    millis = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(millis, 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def get_audio_duration(path):
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return None


def split_tts_chunks(text, max_chars=GOOGLE_TTS_CHUNK_CHARS):
    clean = re.sub(r"\s+", " ", str(text).replace("\r", "")).strip()
    if not clean:
        return ["မင်္ဂလာပါ။"]
    result = []
    remaining = clean
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
        result.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        result.append(remaining)
    return result


def write_segmented_srt(text, output_path, duration_seconds=None):
    segments = split_subtitle_segments(text)
    duration = float(duration_seconds or len(segments) * 1.6)
    each = duration / len(segments)
    cues = []
    for i, segment in enumerate(segments, 1):
        start = (i - 1) * each
        end = duration if i == len(segments) else i * each
        cues.append(f"{i}\n{_srt_time(start)} --> {_srt_time(end)}\n{segment}\n")
    Path(output_path).write_text("\n".join(cues), encoding="utf-8")


def increment_usage():
    stats = {"count": 0}
    try:
        if USAGE_FILE.exists():
            stats = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    stats["count"] = int(stats.get("count", 0)) + 1
    USAGE_FILE.write_text(json.dumps(stats), encoding="utf-8")


def get_usage_count():
    try:
        return int(json.loads(USAGE_FILE.read_text(encoding="utf-8")).get("count", 0)) if USAGE_FILE.exists() else 0
    except (OSError, ValueError):
        return 0


def get_google_voices(limit=10):
    return FEATURED_VOICES[:limit]


def get_voicemaker_voices(limit=10):
    """Compatibility name for app versions that still import this symbol."""
    return get_google_voices(limit)


def _pcm_to_wav(pcm_bytes, output_path, sample_rate=GOOGLE_TTS_SAMPLE_RATE):
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def _merge_wav_files(paths, output_path):
    with wave.open(str(output_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(GOOGLE_TTS_SAMPLE_RATE)
        for path in paths:
            with wave.open(str(path), "rb") as part:
                if part.getnchannels() != 1 or part.getsampwidth() != 2 or part.getframerate() != GOOGLE_TTS_SAMPLE_RATE:
                    raise RuntimeError("Google အသံအပိုင်းများ၏ audio format မတူပါ။")
                out.writeframes(part.readframes(part.getnframes()))


def _extract_inline_audio(payload):
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        parts = (candidate.get("content") or {}).get("parts") or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return inline
    return None


def _gemini_key(api_key):
    return str(api_key or "").strip()


def _speed_instruction(rate):
    try:
        rate_num = float(rate)
    except (TypeError, ValueError):
        rate_num = 1.0
    if rate_num < 0.85:
        return "Speak slowly and clearly."
    if rate_num > 1.25:
        return "Speak briskly but keep every Burmese word clear."
    return "Speak at a natural, steady pace."


def generate_google_tts(text, voice_id="Kore", rate=1.0, pitch=0, api_key=None, style=""):
    key = _gemini_key(api_key)
    style = style or PROFILE_STYLES.get((voice_id, int(pitch)), "Speak naturally and clearly in Burmese.")
    if not key:
        raise RuntimeError("Google AI Studio API key ထည့်ပါ။")
    chunks = split_tts_chunks(text)
    output_file = Path("output.wav")
    srt_file = Path("output.srt")
    headers = {"Content-Type": "application/json"}

    with tempfile.TemporaryDirectory(prefix="mgkhant_google_") as temp_dir:
        chunk_files = []
        for index, chunk in enumerate(chunks):
            prompt = (
                "Speak the following Burmese Myanmar text exactly as written. "
                "Do not translate it, do not add words, and do not explain anything. "
                f"{_speed_instruction(rate)} {style} Text: {chunk}"
            ).strip()
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_id}},
                        "languageCode": "my-MM",
                    },
                },
            }
            response = requests.post(f"{GOOGLE_TTS_URL}?key={key}", headers=headers, json=body, timeout=180)
            if response.status_code >= 400:
                detail = response.text[:1200]
                if response.status_code == 429 or "quota" in detail.lower() or "exceeded" in detail.lower():
                    raise RuntimeError(f"GOOGLE_QUOTA_EXCEEDED: Google AI Studio quota ပြည့်သွားပါပြီ။ {detail}")
                raise RuntimeError(f"Google Gemini TTS error {response.status_code}: {detail}")
            try:
                payload = response.json()
            except ValueError as exc:
                raise RuntimeError("Google AI Studio response JSON မဟုတ်ပါ။") from exc
            inline = _extract_inline_audio(payload)
            if not inline:
                raise RuntimeError(f"Google AI Studio audio response မရပါ: {json.dumps(payload, ensure_ascii=False)[:1000]}")
            try:
                pcm = base64.b64decode(inline["data"])
            except Exception as exc:
                raise RuntimeError("Google AI Studio audio data ကို decode မလုပ်နိုင်ပါ။") from exc
            chunk_file = Path(temp_dir) / f"chunk_{index:04d}.wav"
            _pcm_to_wav(pcm, chunk_file)
            chunk_files.append(chunk_file)
        _merge_wav_files(chunk_files, output_file)

    duration = get_audio_duration(output_file)
    if not duration or duration <= 0:
        raise RuntimeError("Google audio duration မရပါ။")
    write_segmented_srt(text, srt_file, duration)
    return output_file, srt_file


def run_tts_to_file(text, voice_id, pitch_offset, rate=1.0, suffix="output", api_key=None, style=""):
    audio, srt = generate_google_tts(text, voice_id=voice_id, rate=rate, pitch=pitch_offset, api_key=api_key, style=style)
    final_audio = Path(f"output_{suffix}.wav")
    final_srt = Path(f"output_{suffix}.srt")
    final_audio.write_bytes(audio.read_bytes())
    final_srt.write_text(srt.read_text(encoding="utf-8"), encoding="utf-8")
    increment_usage()
    return final_audio, final_srt


def change_tempo(input_path, tempo):
    return Path(input_path)


def apply_effects(input_path, effect_name, tempo=1.0):
    return Path(input_path)


__all__ = [
    "FEATURED_VOICES", "EFFECTS", "PROFILE_STYLES", "get_google_voices", "get_voicemaker_voices",
    "generate_google_tts", "run_tts_to_file", "change_tempo", "get_usage_count",
    "apply_effects",
]
