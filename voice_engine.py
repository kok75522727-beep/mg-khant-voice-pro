import asyncio
import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import edge_tts
import requests

# ---------------------------------------------------------------------------
# Voice list: first two are the existing Myanmar Edge voices; the next eight
# are Azure multilingual voices. The names shown in the UI are labels only.
# ---------------------------------------------------------------------------

FEATURED_VOICES = [
    ("edge:my-MM-ThihaNeural", "+0Hz", "Thiha", "မြန်မာအသံ (Thiha)"),
    ("edge:my-MM-NilarNeural", "+0Hz", "Nilar", "မြန်မာအသံ (Nilar)"),
    ("azure:en-US-AvaMultilingualNeural", "+0Hz", "Ava", "Azure Multilingual"),
    ("azure:en-US-AndrewMultilingualNeural", "+0Hz", "Andrew", "Azure Multilingual"),
    ("azure:en-US-BrianMultilingualNeural", "+0Hz", "Brian", "Azure Multilingual"),
    ("azure:en-US-EmmaMultilingualNeural", "+0Hz", "Emma", "Azure Multilingual"),
    ("azure:fr-FR-VivienneMultilingualNeural", "+0Hz", "Vivienne", "Azure Multilingual"),
    ("azure:fr-FR-RemyMultilingualNeural", "+0Hz", "Remy", "Azure Multilingual"),
    ("azure:de-DE-SeraphinaMultilingualNeural", "+0Hz", "Seraphina", "Azure Multilingual"),
    ("azure:de-DE-FlorianMultilingualNeural", "+0Hz", "Florian", "Azure Multilingual"),
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


def split_subtitle_segments(text, max_chars=10):
    """Split text into exact 10-character chunks for CapCut subtitles."""
    clean_text = re.sub(r"\s+", "", str(text).replace("\r", "")).strip()
    if not clean_text:
        return ["အသံဖိုင်"]
    return [
        clean_text[i:i + max_chars]
        for i in range(0, len(clean_text), max_chars)
    ]


def _srt_time(seconds):
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_segmented_srt(text, output_path):
    """Write one short subtitle cue per sentence/line for CapCut import."""
    segments = split_subtitle_segments(text)
    current = 0.0
    cues = []
    for index, segment in enumerate(segments, 1):
        # Keep each 10-character cue separate for clean CapCut cuts.
        duration = 1.2
        start = current
        end = current + duration
        cues.append(
            f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{segment}\n"
        )
        current = end
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

    # Use sentence-based cues so the same SRT imports cleanly into CapCut.
    write_segmented_srt(text, sub_file)
    return output_file, sub_file


def generate_azure_tts(text, voice, rate="+0%", volume="+0%", pitch="+0Hz"):
    """Generate multilingual speech through Azure Speech REST TTS."""
    key = os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION")
    if not key or not region:
        raise RuntimeError(
            "Azure API key မတွေ့ပါ။ AZURE_SPEECH_KEY နှင့် AZURE_SPEECH_REGION ကို environment variable အဖြစ် ထည့်ပါ။"
        )

    # Azure SSML uses the same percentage/Hz notation used by the UI.
    escaped_text = html.escape(text)
    ssml = f'''<speak version="1.0" xml:lang="en-US">
  <voice name="{html.escape(voice)}">
    <prosody rate="{rate}" pitch="{pitch}" volume="{volume}">{escaped_text}</prosody>
  </voice>
</speak>'''

    endpoint = (
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    )
    response = requests.post(
        endpoint,
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-160kbitrate-mono-mp3",
            "User-Agent": "MgKhantVoiceSystem/1.0",
        },
        data=ssml.encode("utf-8"),
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Azure TTS error {response.status_code}: {response.text[:300]}")

    output_file = Path("output.mp3")
    sub_file = Path("output.srt")
    output_file.write_bytes(response.content)
    # REST synthesis does not return Edge-style WordBoundary events here,
    # so create a valid fallback subtitle cue for download.
    write_fallback_srt(text, sub_file)
    return output_file, sub_file


def run_tts_to_file(text, voice_id, pitch_offset, rate="+0%", suffix="output"):
    """Route Edge voices locally and Azure voices through the configured API."""
    if voice_id.startswith("azure:"):
        audio_path, sub_path = generate_azure_tts(
            text, voice_id.removeprefix("azure:"), rate=rate, pitch=pitch_offset
        )
    else:
        edge_voice = voice_id.removeprefix("edge:")
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            audio_path, sub_path = loop.run_until_complete(
                generate_edge_tts(text, edge_voice, rate=rate, pitch=pitch_offset)
            )
        finally:
            loop.close()

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

