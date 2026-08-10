import asyncio
import edge_tts
import subprocess
import json
import shutil
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
# EFFECTS
# ============================================================

EFFECTS = {
    "None": "",

    "Deep":
        "asetrate=44100*0.82,"
        "aresample=44100,"
        "atempo=1.2195",

    "High":
        "asetrate=44100*1.18,"
        "aresample=44100,"
        "atempo=0.8475",

    "Giant":
        "asetrate=44100*0.75,"
        "aresample=44100,"
        "atempo=1.3333,"
        "aecho=0.8:0.85:30:0.35",

    "Echo":
        "aecho=0.8:0.88:700:0.25",

    "Radio":
        "highpass=f=500,"
        "lowpass=f=3200",

    "Robot":
        "aformat=sample_fmts=s16:sample_rates=44100,"
        "aecho=0.8:0.88:40:0.25",

    "Underwater":
        "lowpass=f=650,"
        "aecho=0.8:0.7:100:0.25",

    "Warm":
        "lowpass=f=6500,"
        "acompressor=threshold=-18dB:ratio=2",

    "Studio":
        "highpass=f=80,"
        "lowpass=f=12000,"
        "acompressor=threshold=-18dB:ratio=2",
}


# ============================================================
# USAGE
# ============================================================

USAGE_FILE = Path("usage_stats.json")


def increment_usage():
    stats = {"count": 0}

    if USAGE_FILE.exists():
        try:
            with open(
                USAGE_FILE,
                "r",
                encoding="utf-8"
            ) as f:
                stats = json.load(f)
        except Exception:
            stats = {"count": 0}

    stats["count"] = stats.get("count", 0) + 1

    try:
        with open(
            USAGE_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                stats,
                f,
                ensure_ascii=False,
                indent=2
            )
    except Exception:
        pass


def get_usage_count():
    if not USAGE_FILE.exists():
        return 0

    try:
        with open(
            USAGE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            stats = json.load(f)

        return stats.get("count", 0)

    except Exception:
        return 0


# ============================================================
# FIND VOICE
# ============================================================

def get_voice_by_id(voice_id):

    for voice in FEATURED_VOICES:

        if voice["id"] == voice_id:
            return voice

    return None


# ============================================================
# ASYNC EDGE TTS
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

    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch
    )

    submaker = edge_tts.SubMaker()

    with open(
        output_file,
        "wb"
    ) as audio_file:

        async for chunk in communicate.stream():

            if chunk["type"] == "audio":

                audio_file.write(
                    chunk["data"]
                )

            elif chunk["type"] == "WordBoundary":

                submaker.feed(chunk)

    with open(
        sub_file,
        "w",
        encoding="utf-8"
    ) as subtitle_file:

        subtitle_file.write(
            submaker.get_srt()
        )

    return (
        Path(output_file),
        Path(sub_file)
    )


# ============================================================
# RUN EDGE TTS
# ============================================================

def _run_async(coro):

    loop = asyncio.new_event_loop()

    try:

        asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)

    finally:

        loop.close()

        asyncio.set_event_loop(None)


# ============================================================
# APPLY AUDIO EFFECT
# ============================================================

def apply_effects(
    input_path,
    effect_name="None",
    tempo=1.0,
    output_name=None
):

    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {input_path}"
        )

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpeg is not installed or not available."
        )

    if output_name:

        output_path = (
            input_path.parent /
            output_name
        )

    else:

        output_path = (
            input_path.parent /
            f"effect_{input_path.stem}.mp3"
        )

    filter_str = EFFECTS.get(
        effect_name,
        ""
    )

    # Add tempo
    if tempo != 1.0:

        tempo_filter = (
            f"atempo={float(tempo)}"
        )

        if filter_str:

            filter_str += (
                "," + tempo_filter
            )

        else:

            filter_str = tempo_filter

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
    ]

    if filter_str:

        command.extend([
            "-af",
            filter_str
        ])

    command.extend([
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(output_path)
    ])

    try:

        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )

    except subprocess.CalledProcessError as e:

        error_message = (
            e.stderr
            if e.stderr
            else "Unknown FFmpeg error."
        )

        raise RuntimeError(
            f"FFmpeg audio processing failed:\n"
            f"{error_message}"
        )

    return output_path


# ============================================================
# CHANGE TEMPO
# ============================================================

def change_tempo(
    input_path,
    tempo
):

    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {input_path}"
        )

    tempo = float(tempo)

    if tempo <= 0:
        raise ValueError(
            "Tempo must be greater than 0."
        )

    # FFmpeg atempo supports 0.5 - 2.0
    if tempo < 0.5:
        tempo = 0.5

    if tempo > 2.0:
        tempo = 2.0

    output_path = (
        input_path.parent /
        f"tempo_{input_path.name}"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-filter:a",
            f"atempo={tempo}",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(output_path)
        ],
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

    selected = get_voice_by_id(
        voice_id
    )

    if selected is None:

        raise ValueError(
            f"Unknown voice ID: {voice_id}"
        )

    safe_suffix = str(
        suffix
    ).replace(
        " ",
        "_"
    )

    raw_audio = Path(
        f"raw_{safe_suffix}.mp3"
    )

    raw_srt = Path(
        f"raw_{safe_suffix}.srt"
    )

    final_audio = Path(
        f"output_{safe_suffix}.mp3"
    )

    final_srt = Path(
        f"output_{safe_suffix}.srt"
    )

    # ----------------------------------------
    # Generate TTS
    # ----------------------------------------

    _run_async(
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

    # ----------------------------------------
    # Apply voice effect
    # ----------------------------------------

    processed_audio = apply_effects(
        input_path=raw_audio,
        effect_name=selected["effect"],
        tempo=tempo,
        output_name=final_audio.name
    )

    # ----------------------------------------
    # Move SRT
    # ----------------------------------------

    if raw_srt.exists():

        if final_srt.exists():
            final_srt.unlink()

        raw_srt.replace(
            final_srt
        )

    # ----------------------------------------
    # Delete temporary audio
    # ----------------------------------------

    if raw_audio.exists():

        try:
            raw_audio.unlink()
        except Exception:
            pass

    increment_usage()

    return (
        processed_audio,
        final_srt
    )


# ============================================================
# COMPATIBILITY FUNCTION
# ============================================================

def run_tts_to_file(
    text,
    voice_id,
    pitch_offset=None,
    rate="+0%",
    suffix="output",
    tempo=1.0,
    volume="+0%"
):
    """
    Compatible with older app.py calls.

    The selected voice preset controls
    its own pitch/rate/effect.
    """

    selected = get_voice_by_id(
        voice_id
    )

    if selected is None:

        raise ValueError(
            f"Unknown voice ID: {voice_id}"
        )

    # If old app sends a custom pitch,
    # use it. Otherwise use preset pitch.
    pitch = (
        pitch_offset
        if pitch_offset is not None
        else selected["pitch"]
    )

    # If old app sends custom rate,
    # use it. Otherwise use preset rate.
    actual_rate = (
        rate
        if rate != "+0%"
        else selected["rate"]
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

    _run_async(
        generate_tts(
            text=text,
            voice=selected["voice"],
            rate=actual_rate,
            volume=volume,
            pitch=pitch,
            output_file=str(raw_audio),
            sub_file=str(raw_srt)
        )
    )

    processed = apply_effects(
        input_path=raw_audio,
        effect_name=selected["effect"],
        tempo=tempo,
        output_name=final_audio.name
    )

    if raw_srt.exists():

        if final_srt.exists():
            final_srt.unlink()

        raw_srt.replace(
            final_srt
        )

    if raw_audio.exists():

        try:
            raw_audio.unlink()
        except Exception:
            pass

    increment_usage()

    return (
        processed,
        final_srt
    )


# ============================================================
# VOICE LIST FOR STREAMLIT
# ============================================================

def get_voice_list():

    return [
        {
            "id": voice["id"],
            "name": voice["name"],
            "display": voice["display"],
            "voice": voice["voice"],
            "pitch": voice["pitch"],
            "rate": voice["rate"],
            "effect": voice["effect"],
        }
        for voice in FEATURED_VOICES
    ]


# ============================================================
# GET VOICE NAMES
# ============================================================

def get_voice_names():

    return [
        voice["name"]
        for voice in FEATURED_VOICES
    ]


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_text = """
    မင်္ဂလာပါ။
    ဒါကတော့ Mg Khant AI Studio ရဲ့
    မြန်မာ AI အသံစမ်းသပ်မှု ဖြစ်ပါတယ်။
    """

    try:

        audio, srt = run_tts_to_file(
            text=test_text,
            voice_id="naytoe",
            suffix="test"
        )

        print(
            "Audio:",
            audio
        )

        print(
            "SRT:",
            srt
        )

    except Exception as e:

        print(
            "ERROR:",
            e
        )