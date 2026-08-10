import asyncio
import edge_tts
import os
import subprocess
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Voice Lists with 10 Celebrity Names
# ---------------------------------------------------------------------------

FEATURED_VOICES = [
    ('my-MM-ThihaNeural', '+0Hz', 'Thiha', 'စိုင်းစိုင်းခန့်လှိုင်း'),
    ('my-MM-ThihaNeural', '-5Hz', 'NayToe', 'နေတိုး'),
    ('my-MM-ThihaNeural', '+5Hz', 'PyayTiOo', 'ပြေတီဦး'),
    ('my-MM-ThihaNeural', '-10Hz', 'MyintMyat', 'မြင့်မြတ်'),
    ('my-MM-ThihaNeural', '+10Hz', 'LuMin', 'လူမင်း'),
    ('my-MM-NilarNeural', '+0Hz', 'Nilar', 'ဝတ်မှုံရွှေရည်'),
    ('my-MM-NilarNeural', '-5Hz', 'PhwayPhway', 'ဖွေးဖွေး'),
    ('my-MM-NilarNeural', '+5Hz', 'Eaindra', 'အိန္ဒြာကျော်ဇင်'),
    ('my-MM-NilarNeural', '-10Hz', 'PaingPhyo', 'ပိုင်ဖြိုးသု'),
    ('my-MM-NilarNeural', '+10Hz', 'KhaingThin', 'ခိုင်သင်းကြည်')
]

EFFECTS = {
    "None": "",
    "Chipmunk (High Pitch)": "asetrate=44100*1.5,atempo=1/1.5",
    "Deep (Low Pitch)": "asetrate=44100*0.7,atempo=1/0.7",
    "Male Voice": "pitch=0.8",
    "Female Voice": "pitch=1.2",
    "Robot": "aformat=sample_fmts=s16:sample_rates=44100,aecho=0.8:0.88:6:0.4",
    "Echo": "aecho=0.8:0.9:1000:0.3",
    "Giant": "pitch=0.5,aecho=0.8:0.9:20:0.5",
    "Underwater": "lowpass=f=500",
    "Radio": "highpass=f=500,lowpass=f=3000"
}

# ---------------------------------------------------------------------------
# Usage Tracking (Hidden from Users, Admin Only)
# ---------------------------------------------------------------------------

USAGE_FILE = Path("usage_stats.json")

def increment_usage():
    stats = {"count": 0}
    if USAGE_FILE.exists():
        try:
            with open(USAGE_FILE, "r") as f:
                stats = json.load(f)
        except:
            pass
    stats["count"] = stats.get("count", 0) + 1
    with open(USAGE_FILE, "w") as f:
        json.dump(stats, f)

def get_usage_count():
    if USAGE_FILE.exists():
        try:
            with open(USAGE_FILE, "r") as f:
                stats = json.load(f)
                return stats.get("count", 0)
        except:
            return 0
    return 0

# ---------------------------------------------------------------------------
# TTS Logic with SRT Generation
# ---------------------------------------------------------------------------

async def generate_tts(text, voice, rate="+0%", volume="+0%", pitch="+0%"):
    """Generate TTS audio and SRT subtitles using edge_tts."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
    output_file = "output.mp3"
    sub_file = "output.srt"
    
    # Generate audio with subtitle data
    submaker = edge_tts.SubMaker()
    with open(output_file, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
    
    # Save SRT file
    with open(sub_file, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())
    
    return Path(output_file), Path(sub_file)

def run_tts_to_file(text, voice_id, pitch_offset, rate="+0%", suffix="output"):
    """Run TTS and save to file with SRT support."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        audio_path, sub_path = loop.run_until_complete(
            generate_tts(text, voice_id, rate=rate, pitch=pitch_offset)
        )
        final_audio = Path(f"output_{suffix}.mp3")
        final_srt = Path(f"output_{suffix}.srt")
        
        if audio_path.exists():
            audio_path.replace(final_audio)
        if sub_path.exists():
            sub_path.replace(final_srt)
        
        increment_usage()
        return final_audio, final_srt
    finally:
        loop.close()

# ---------------------------------------------------------------------------
# Audio Effects Logic
# ---------------------------------------------------------------------------

def apply_effects(input_path, effect_name, tempo=1.0):
    """Apply audio effects using ffmpeg."""
    input_path = Path(input_path)
    output_path = input_path.parent / f"effect_{input_path.name}"
    filter_str = EFFECTS.get(effect_name, "")
    
    if tempo != 1.0:
        if filter_str:
            filter_str += f",atempo={tempo}"
        else:
            filter_str = f"atempo={tempo}"
    
    if not filter_str:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(input_path), str(output_path)],
            check=True,
            capture_output=True
        )
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(input_path), "-af", filter_str, str(output_path)],
            check=True,
            capture_output=True
        )
    
    return output_path

def change_tempo(input_path, tempo):
    """Change audio tempo using ffmpeg."""
    input_path = Path(input_path)
    output_path = input_path.parent / f"tempo_{input_path.name}"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-af", f"atempo={tempo}", str(output_path)],
        check=True,
        capture_output=True
    )
    return output_path
    
