"""Microsoft Azure Speech TTS engine for the Mg Khant Burmese app."""

import json
import os
import re
import tempfile
import wave
from html import escape
from pathlib import Path

import requests

AZURE_OUTPUT_FORMAT = "riff-24000hz-16bit-mono-pcm"
AZURE_SAMPLE_RATE = 24000
AZURE_TTS_CHUNK_CHARS = 4500
MAX_TEXT_CHARS = 10000
USAGE_FILE = Path("usage_stats.json")

# The first two are Burmese voices. The remaining voices are multilingual
# voices. Their provider IDs stay internal; only Burmese labels are returned
# to the UI.
VOICE_PROFILES = [
    {"id": "my-MM-NilarNeural", "name": "နီလာ", "label": "နီလာ"},
    {"id": "en-US-AvaMultilingualNeural", "name": "အေမိဆန်", "label": "အေမိဆန်"},
    {"id": "en-US-EmmaMultilingualNeural", "name": "သင့်ဇာ", "label": "သင့်ဇာ"},
    {"id": "de-DE-SeraphinaMultilingualNeural", "name": "စုမြတ်", "label": "စုမြတ်"},
    {"id": "fr-FR-VivienneMultilingualNeural", "name": "ကြယ်စင်", "label": "ကြယ်စင်"},
    {"id": "zh-CN-XiaoxiaoMultilingualNeural", "name": "လမင်း", "label": "လမင်း"},
    {"id": "my-MM-ThihaNeural", "name": "သီဟ", "label": "သီဟ"},
    {"id": "en-US-AndrewMultilingualNeural", "name": "နေထူးနိုင်", "label": "နေထူးနိုင်"},
    {"id": "en-US-BrianMultilingualNeural", "name": "နေမျိုးအောင်", "label": "နေမျိုးအောင်"},
    {"id": "de-DE-FlorianMultilingualNeural", "name": "ကောင်ကောင်", "label": "ကောင်ကောင်"},
    {"id": "fr-FR-RemyMultilingualNeural", "name": "အောင်ခန့်ပိုင်", "label": "အောင်ခန့်ပိုင်"},
    {"id": "it-IT-GiuseppeMultilingualNeural", "name": "နေတိုး", "label": "နေတိုး"},
]
FEATURED_VOICES = [(v["id"], 0, v["name"], v["label"]) for v in VOICE_PROFILES]


def _secret_or_env(api_key=None, region=None):
    key = str(api_key or os.getenv("AZURE_SPEECH_KEY") or os.getenv("MICROSOFT_SPEECH_KEY") or "").strip()
    area = str(region or os.getenv("AZURE_SPEECH_REGION") or os.getenv("MICROSOFT_SPEECH_REGION") or "").strip()
    return key, area


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


def split_tts_chunks(text, max_chars=AZURE_TTS_CHUNK_CHARS):
    clean = re.sub(r"\s+", " ", str(text).replace("\r", "")).strip()
    if not clean:
        return ["မင်္ဂလာပါ။"]
    result, remaining = [], clean
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


def get_google_voices(limit=12):
    """Compatibility name retained so existing app.py imports keep working."""
    return FEATURED_VOICES[:limit]


def get_voicemaker_voices(limit=12):
    return get_google_voices(limit)


def _merge_wav_files(paths, output_path):
    with wave.open(str(output_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(AZURE_SAMPLE_RATE)
        for path in paths:
            with wave.open(str(path), "rb") as part:
                if part.getnchannels() != 1 or part.getsampwidth() != 2 or part.getframerate() != AZURE_SAMPLE_RATE:
                    raise RuntimeError("အသံအပိုင်းများ၏ audio format မတူပါ။")
                out.writeframes(part.readframes(part.getnframes()))


def _speed_percent(rate):
    try:
        value = float(rate)
    except (TypeError, ValueError):
        value = 1.0
    return int(round((value - 1.0) * 100))


def _normalize_region(region):
    value = str(region or "").strip().lower().rstrip("/")
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    for suffix in (".tts.speech.microsoft.com", ".cognitiveservices.azure.com"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value.strip("/ ")


def _azure_endpoint(region, endpoint=None):
    custom = str(endpoint or "").strip().rstrip("/")
    if custom:
        if not custom.startswith(("https://", "http://")):
            custom = "https://" + custom
        if custom.endswith("/cognitiveservices/v1"):
            return custom
        return custom + "/cognitiveservices/v1"
    return f"https://{_normalize_region(region)}.tts.speech.microsoft.com/cognitiveservices/v1"


def generate_google_tts(text, voice_id="my-MM-NilarNeural", rate=1.0, pitch=0, api_key=None, region=None, endpoint=None, style=""):
    """Compatibility name retained; implementation now uses Azure Speech TTS."""
    text = str(text or "").strip()
    if len(text) > MAX_TEXT_CHARS:
        raise RuntimeError(f"စာလုံးရေ {MAX_TEXT_CHARS:,} ထက် မကျော်ရပါ။ လက်ရှိ {len(text):,} လုံးရှိပါသည်။")
    key, area = _secret_or_env(api_key, region)
    area = _normalize_region(area)
    if not key:
        raise RuntimeError("Azure Speech Key ကို Streamlit Secrets ထဲမှာ ထည့်ပါ။")
    if not area:
        raise RuntimeError("Azure Speech Region ကို Streamlit Secrets ထဲမှာ ထည့်ပါ။")

    chunks = split_tts_chunks(text)
    output_file, srt_file = Path("output.wav"), Path("output.srt")
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml; charset=utf-8",
        "Accept": "audio/wav",
        "X-Microsoft-OutputFormat": AZURE_OUTPUT_FORMAT,
        "User-Agent": "MgKhant-Burmese-TTS",
    }
    voice_name = voice_id or "my-MM-NilarNeural"
    rate_value = _speed_percent(rate)
    pitch_hz = int(pitch or 0)
    rate_text = f"{rate_value:+d}%" if rate_value else "0%"
    pitch_text = f"{pitch_hz:+d}Hz" if pitch_hz else "0Hz"
    voice_locale = "-".join(voice_name.split("-")[:2]) if "-" in voice_name else "my-MM"

    with tempfile.TemporaryDirectory(prefix="mgkhant_azure_") as temp_dir:
        chunk_files = []
        for index, chunk in enumerate(chunks):
            ssml = (
                '<?xml version="1.0" encoding="utf-8"?>'
                '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
                f'xml:lang="{escape(voice_locale)}">'
                f'<voice name="{escape(voice_name)}"><prosody rate="{rate_text}" pitch="{pitch_text}">'
                f'{escape(chunk)}</prosody></voice></speak>'
            )
            response = requests.post(_azure_endpoint(area, endpoint), headers=headers, data=ssml.encode("utf-8"), timeout=180)
            if response.status_code >= 400:
                detail = response.text.strip()[:1200]
                if not detail:
                    detail = f"response headers: {dict(response.headers)}"
                if response.status_code in {401, 403}:
                    raise RuntimeError("Azure Speech Key သို့မဟုတ် Region မမှန်ပါ။")
                if response.status_code == 429:
                    raise RuntimeError(f"AZURE_QUOTA_EXCEEDED: Azure Speech quota ပြည့်သွားပါပြီ။ {detail}")
                raise RuntimeError(
                    f"Azure Speech TTS error {response.status_code}: {detail} "
                    f"(region={area}, voice={voice_name})"
                )
            chunk_file = Path(temp_dir) / f"chunk_{index:04d}.wav"
            chunk_file.write_bytes(response.content)
            chunk_files.append(chunk_file)
        _merge_wav_files(chunk_files, output_file)

    duration = get_audio_duration(output_file)
    if not duration or duration <= 0:
        raise RuntimeError("Azure audio duration မရပါ။")
    write_segmented_srt(text, srt_file, duration)
    return output_file, srt_file


def run_tts_to_file(text, voice_id, pitch_offset=0, rate=1.0, suffix="output", api_key=None, region=None, endpoint=None, style=""):
    audio, srt = generate_google_tts(text, voice_id=voice_id, rate=rate, pitch=pitch_offset, api_key=api_key, region=region, endpoint=endpoint, style=style)
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
    "FEATURED_VOICES", "get_google_voices", "get_voicemaker_voices", "generate_google_tts",
    "run_tts_to_file", "change_tempo", "get_usage_count", "apply_effects", "MAX_TEXT_CHARS",
]
