import asyncio
import edge_tts
import subprocess
import json
from pathlib import Path

# ============================================================
# 10 VOICE PRESETS
# ============================================================

FEATURED_VOICES = [
    {
        "id": "thiha",
        "voice": "my-MM-ThihaNeural",
        "name": "Thiha",
        "display": "စိုင်းစိုင်းခန့်လှိုင်း",
        "pitch": "+0Hz",
        "rate": "+0%",
        "volume": "+0%",
        "effect": "None",
    },
    {
        "id": "naytoe",
        "voice": "my-MM-ThihaNeural",
        "name": "NayToe",
        "display": "နေတိုး",
        "pitch": "-18Hz",
        "rate": "-5%",
        "volume": "+0%",
        "effect": "Deep",
    },
    {
        "id": "pyayti",
        "voice": "my-MM-ThihaNeural",
        "name": "PyayTiOo",
        "display": "ပြေတီဦး",
        "pitch": "+15Hz",
        "rate": "+3%",
        "volume": "+0%",
        "effect": "None",
    },
    {
        "id": "myintmyat",
        "voice": "my-MM-ThihaNeural",
        "name": "MyintMyat",
        "display": "မြင့်မြတ်",
        "pitch": "-30Hz",
        "rate": "-8%",
        "volume": "+0%",
        "effect": "Giant",
    },
    {
        "id": "lumin",
        "voice": "my-MM-ThihaNeural",
        "name": "LuMin",
        "display": "လူမင်း",
        "pitch": "+25Hz",
        "rate": "+6%",
        "volume": "+0%",
        "effect": "Radio",
    },
    {
        "id": "nilar",
        "voice": "my-MM-NilarNeural",
        "name": "Nilar",
        "display": "ဝတ်မှုံရွှေရည်",
        "pitch": "+0Hz",
        "rate": "+0%",
        "volume": "+0%",
        "effect": "None",
    },
    {
        "id": "phwayphway",
        "voice": "my-MM-NilarNeural",
        "name": "PhwayPhway",
        "display": "ဖွေးဖွေး",
        "pitch": "+12Hz",
        "rate": "+4%",
        "volume": "+0%",
        "effect": "Echo",
    },
    {
        "id": "eaindra",
        "voice": "my-MM-NilarNeural",
        "name": "Eaindra",
        "display": "အိန္ဒြာကျော်ဇင်",
        "pitch": "+20Hz",
        "rate": "+5%",
        "volume": "+0%",
        "effect": "None",
    },
    {
        "id": "paingphyo",
        "voice": "my-MM-NilarNeural",
        "name": "PaingPhyo",
        "display": "ပိုင်ဖြိုးသု",
        "pitch": "-20Hz",
        "rate": "-5%",
        "volume": "+0%",
        "effect": "Deep",
    },
    {
        "id": "khaingthin",
        "voice": "my-MM-NilarNeural",
        "name": "KhaingThin",
        "display": "ခိုင်သင်းကြည်",
        "pitch": "+28Hz",
        "rate": "+7%",
        "volume": "+0%",
        "effect": "Radio",
    },
]


# ============================================================
# AUDIO EFFECTS
# ============================================================

EFFECTS = {
    "None": "",

    # Pitch / character
    "Deep":
        "asetrate=44100*0.82,aresample=44100,atempo=1.2195",

    "High":
        "asetrate=44100*1.18,aresample=44100,atempo=0.8475",

    # Voice character
    "Giant":
        "asetrate=44100*0.75,aresample=44100,atempo=1.3333,"
        "aecho=0.8:0.85:30:0.35",

    "Echo":
        "aecho=0.8:0.88:700:0.25",

    "Radio":
        "highpass=f=500,lowpass=f=3200",

    "Robot":
        "aformat=sample_fmts=s16:sample_rates=44100,"
        "aecho=0.8:0.88:40:0.25",

    "Underwater":
        "lowpass=f=650,aecho=0.8:0.7:100:0.25",

    "Warm":
        "lowpass=f=6500,acompressor=threshold=-18dB:ratio=2",

    "Studio":
        "highpass=f=80,lowpass=f=12000,"
        "acompressor=threshold=-18dB:ratio=2"
}


# ============================================================
# USAGE
# ============================================================

USAGE_FILE = Path("usage_stats.json")


def increment_usage():
    stats = {"count": 0}

    if USAGE_FILE.exists():
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except Exception:
            pass

    stats["count"] = stats.get("count", 0) + 1

    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f)


def get_usage_count():
    if USAGE_FILE.exists():
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("count", 0)
        except Exception:
            return 0

    return 0


# ============================================================
# EDGE TTS
# ============================================================

async def generate_tts(
    text,
    voice,
    rate="+0%",
    volume="+0%",
    pitch="+0%",
    output_file="output.mp3",
    sub_file="output.srt"
):
    """
    Generate MP3 + SRT
    """

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch
    )

    submaker = edge_tts.SubMaker()

    with open(output_file, "wb") as audio:
        async for chunk in communicate.stream():

            if chunk["type"] == "audio":
                audio.write(chunk["data"])

            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    with open(sub_file, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())

    return Path(output_file), Path(sub_file)


# ============================================================
# APPLY EFFECT
# ============================================================

def apply_effects(
    input_path,
    effect_name="None",
    tempo=1.0,
    output_name=None
):

    input_path = Path(input_path)

    if output_name:
        output_path = input_path.parent / output_name
    else:
        output_path = input_path.parent / (
            f"effect_{input_path.stem}.mp3"
        )

    filter_str = EFFECTS.get(effect_name, "")

    # Tempo
    if tempo != 1.0:

        if filter_str:
            filter_str += f",atempo={tempo}"
        else:
            filter_str = f"atempo={tempo}"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path)
    ]

    if filter_str:
        command += [
            "-af",
            filter_str
        ]

    command += [
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(output_path)
    ]

    subprocess.run(
        command,
        check=True,
        capture_output=True
    )

    return output_path


# ============================================================
# GENERATE VOICE
# ============================================================

def generate_voice(
    text,
    voice_id,
    tempo=1.0,
    suffix="voice"
):

    selected = None

    for voice in FEATURED_VOICES:
        if voice["id"] == voice_id:
            selected = voice
            break

    if selected is None:
        raise ValueError(
            f"Unknown voice: {voice_id}"
        )

    raw_audio = Path(
        f"raw_{suffix}.mp3"
    )

    raw_srt = Path(
        f"raw_{suffix}.srt"
    )

    final_audio = Path(
        f"output_{suffix}.mp3"
    )

    final_srt = Path(
        f"output_{suffix}.srt"
    )

    # --------------------------------------------
    # EDGE TTS
    # --------------------------------------------

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:

        loop.run_until_complete(
            generate_tts(
                text=text,
                voice=selected["voice"],
                rate=selected["rate"],
                volume=selected["volume"],
                pitch=selected["pitch"],
                output_file=str(raw_audio),
                sub_file=str(raw_srt)
            )
        )

    finally:
        loop.close()

    # --------------------------------------------
    # EFFECT
    # --------------------------------------------

    processed = apply_effects(
        raw_audio,
        selected["effect"],
        tempo=tempo,
        output_name=final_audio.name
    )

    # --------------------------------------------
    # SRT
    # --------------------------------------------

    if raw_srt.exists():

        raw_srt.replace(final_srt)

    # --------------------------------------------
    # CLEAN TEMP FILE
    # --------------------------------------------

    if raw_audio.exists():
        raw_audio.unlink()

    increment_usage()

    return processed, final_srt


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def run_tts_to_file(
    text,
    voice_id,
    tempo=1.0,
    suffix="output"
):

    return generate_voice(
        text=text,
        voice_id=voice_id,
        tempo=tempo,
        suffix=suffix
    )


# ============================================================
# LIST VOICES
# ============================================================

def get_voice_list():

    return [
        {
            "id": v["id"],
            "name": v["name"],
            "display": v["display"]
        }
        for v in FEATURED_VOICES
    ]


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    text = """
    မင်္ဂလာပါ။ ဒီအသံကတော့ မြန်မာဘာသာစကား
    AI Voice Generator ကနေ ဖန်တီးထားတဲ့ အသံဖြစ်ပါတယ်။
    """

    audio, srt = run_tts_to_file(
        text=text,
        voice_id="naytoe",
        tempo=1.0,
        suffix="test"
    )

    print("Audio:", audio)
    print("SRT:", srt)