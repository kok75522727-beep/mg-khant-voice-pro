import asyncio
import edge_tts
import subprocess
import json
import os
import tempfile
from pathlib import Path


# ============================================================
# VOICE LIST
# IMPORTANT:
# app.py expects:
# (voice_id, pitch, name, label)
# ============================================================

FEATURED_VOICES = [
    (
        "my-MM-ThihaNeural",
        "+0Hz",
        "Thiha",
        "စိုင်းစိုင်းခန့်လှိုင်း"
    ),
    (
        "my-MM-ThihaNeural",
        "-18Hz",
        "NayToe",
        "နေတိုး"
    ),
    (
        "my-MM-ThihaNeural",
        "+15Hz",
        "PyayTiOo",
        "ပြေတီဦး"
    ),
    (
        "my-MM-ThihaNeural",
        "-30Hz",
        "MyintMyat",
        "မြင့်မြတ်"
    ),
    (
        "my-MM-ThihaNeural",
        "+25Hz",
        "LuMin",
        "လူမင်း"
    ),

    (
        "my-MM-NilarNeural",
        "+0Hz",
        "Nilar",
        "ဝတ်မှုံရွှေရည်"
    ),
    (
        "my-MM-NilarNeural",
        "+12Hz",
        "PhwayPhway",
        "ဖွေးဖွေး"
    ),
    (
        "my-MM-NilarNeural",
        "+20Hz",
        "Eaindra",
        "အိန္ဒြာကျော်ဇင်"
    ),
    (
        "my-MM-NilarNeural",
        "-20Hz",
        "PaingPhyo",
        "ပိုင်ဖြိုးသု"
    ),
    (
        "my-MM-NilarNeural",
        "+28Hz",
        "KhaingThin",
        "ခိုင်သင်းကြည်"
    ),
]


# ============================================================
# VOICE PRESETS
# ============================================================

VOICE_SETTINGS = {

    "Thiha": {
        "rate": "+0%",
        "effect": "None"
    },

    "NayToe": {
        "rate": "-5%",
        "effect": "Deep"
    },

    "PyayTiOo": {
        "rate": "+3%",
        "effect": "None"
    },

    "MyintMyat": {
        "rate": "-8%",
        "effect": "Giant"
    },

    "LuMin": {
        "rate": "+6%",
        "effect": "Warm"
    },

    "Nilar": {
        "rate": "+0%",
        "effect": "None"
    },

    "PhwayPhway": {
        "rate": "+4%",
        "effect": "High"
    },

    "Eaindra": {
        "rate": "+5%",
        "effect": "Studio"
    },

    "PaingPhyo": {
        "rate": "-5%",
        "effect": "Warm"
    },

    "KhaingThin": {
        "rate": "+7%",
        "effect": "Studio"
    },
}


# ============================================================
# EFFECTS
# ============================================================

EFFECTS = {

    "None": "",

    # Lower / deeper character
    "Deep":
        "asetrate=44100*0.82,"
        "aresample=44100,"
        "atempo=1.219512",

    # Higher character
    "High":
        "asetrate=44100*1.18,"
        "aresample=44100,"
        "atempo=0.847458",

    # Large / heavy character
    "Giant":
        "asetrate=44100*0.75,"
        "aresample=44100,"
        "atempo=1.333333,"
        "aecho=0.8:0.85:35:0.30",

    # Warm voice
    "Warm":
        "lowpass=f=7500,"
        "acompressor=threshold=-18dB:ratio=2.2",

    # Clean studio
    "Studio":
        "highpass=f=80,"
        "lowpass=f=12000,"
        "acompressor=threshold=-18dB:ratio=2",

    # Radio
    "Radio":
        "highpass=f=500,"
        "lowpass=f=3200",

    # Echo
    "Echo":
        "aecho=0.8:0.88:700:0.25",

    # Robot
    "Robot":
        "aformat=sample_fmts=s16:sample_rates=44100,"
        "aecho=0.8:0.88:40:0.25",

    # Underwater
    "Underwater":
        "lowpass=f=650,"
        "aecho=0.8:0.7:100:0.25",
}


# ============================================================
# USAGE
# ============================================================

USAGE_FILE = Path("usage_stats.json")


def increment_usage():

    stats = {
        "count": 0
    }

    if USAGE_FILE.exists():

        try:

            with open(
                USAGE_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                stats = json.load(f)

        except Exception:

            stats = {
                "count": 0
            }

    stats["count"] = (
        stats.get("count", 0) + 1
    )

    try:

        with open(
            USAGE_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                stats,
                f,
                ensure_ascii=False
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

        return stats.get(
            "count",
            0
        )

    except Exception:

        return 0


# ============================================================
# FIND PRESET
# ============================================================

def find_voice(voice_id):

    if not voice_id:
        return None

    voice_id = str(
        voice_id
    ).strip()

    # ----------------------------------------
    # Exact preset name
    # ----------------------------------------

    for (
        edge_voice,
        pitch,
        name,
        label
    ) in FEATURED_VOICES:

        if voice_id.lower() == name.lower():

            return {
                "voice": edge_voice,
                "pitch": pitch,
                "name": name,
                "label": label
            }

    # ----------------------------------------
    # Exact Edge voice ID
    #
    # If app sends:
    # my-MM-ThihaNeural
    #
    # choose Thiha preset
    # ----------------------------------------

    for (
        edge_voice,
        pitch,
        name,
        label
    ) in FEATURED_VOICES:

        if voice_id.lower() == edge_voice.lower():

            return {
                "voice": edge_voice,
                "pitch": pitch,
                "name": name,
                "label": label
            }

    # ----------------------------------------
    # Display label
    # ----------------------------------------

    for (
        edge_voice,
        pitch,
        name,
        label
    ) in FEATURED_VOICES:

        if voice_id == label:

            return {
                "voice": edge_voice,
                "pitch": pitch,
                "name": name,
                "label": label
            }

    return None


# ============================================================
# ASYNC TTS
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

        raise ValueError(
            "Text cannot be empty."
        )

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
# ASYNC RUNNER
# ============================================================

def run_async(coro):

    try:

        return asyncio.run(coro)

    except RuntimeError:

        loop = asyncio.new_event_loop()

        try:

            return loop.run_until_complete(
                coro
            )

        finally:

            loop.close()


# ============================================================
# FFMPEG CHECK
# ============================================================

def check_ffmpeg():

    try:

        subprocess.run(
            [
                "ffmpeg",
                "-version"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        return True

    except Exception:

        return False


# ============================================================
# APPLY EFFECT
# ============================================================

def apply_effects(
    input_path,
    effect_name="None",
    tempo=1.0,
    output_name=None
):

    input_path = Path(
        input_path
    )

    if not input_path.exists():

        raise FileNotFoundError(
            f"Audio file not found: {input_path}"
        )

    if not check_ffmpeg():

        raise RuntimeError(
            "FFmpeg is not installed."
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

    # ----------------------------------------
    # Tempo
    # ----------------------------------------

    if tempo is not None:

        try:

            tempo = float(
                tempo
            )

        except Exception:

            tempo = 1.0

        if tempo != 1.0:

            # FFmpeg atempo safe range
            if tempo < 0.5:
                tempo = 0.5

            if tempo > 2.0:
                tempo = 2.0

            tempo_filter = (
                f"atempo={tempo}"
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
        str(input_path)
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

        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )

    except subprocess.CalledProcessError as error:

        message = (
            error.stderr
            if error.stderr
            else "Unknown FFmpeg error."
        )

        raise RuntimeError(
            "FFmpeg processing failed:\n"
            + message
        )

    return output_path


# ============================================================
# CHANGE TEMPO
# ============================================================

def change_tempo(
    input_path,
    tempo
):

    input_path = Path(
        input_path
    )

    if not input_path.exists():

        raise FileNotFoundError(
            f"Audio file not found: {input_path}"
        )

    try:

        tempo = float(
            tempo
        )

    except Exception:

        tempo = 1.0

    if tempo < 0.5:
        tempo = 0.5

    if tempo > 2.0:
        tempo = 2.0

    output_path = (
        input_path.parent /
        f"tempo_{input_path.stem}.mp3"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-af",
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
# MAIN FUNCTION
# ============================================================

def run_tts_to_file(
    text,
    voice_id,
    pitch_offset="+0Hz",
    rate="+0%",
    suffix="output"
):

    # ----------------------------------------
    # Find selected voice
    # ----------------------------------------

    selected = find_voice(
        voice_id
    )

    if selected is None:

        raise ValueError(
            f"Voice not found: {voice_id}"
        )

    edge_voice = selected["voice"]
    preset_pitch = selected["pitch"]
    name = selected["name"]

    # ----------------------------------------
    # Preset settings
    # ----------------------------------------

    settings = VOICE_SETTINGS.get(
        name,
        {
            "rate": "+0%",
            "effect": "None"
        }
    )

    preset_rate = settings[
        "rate"
    ]

    effect_name = settings[
        "effect"
    ]

    # ----------------------------------------
    # Pitch
    # ----------------------------------------

    if (
        pitch_offset is None
        or
        pitch_offset == "+0Hz"
    ):

        actual_pitch = preset_pitch

    else:

        actual_pitch = pitch_offset

    # ----------------------------------------
    # Rate
    # ----------------------------------------

    if (
        rate is None
        or
        rate == "+0%"
    ):

        actual_rate = preset_rate

    else:

        actual_rate = rate

    # ----------------------------------------
    # Unique temporary files
    # ----------------------------------------

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
    # Remove old files
    # ----------------------------------------

    for file in [
        raw_audio,
        raw_srt,
        final_audio,
        final_srt
    ]:

        try:

            if file.exists():
                file.unlink()

        except Exception:

            pass

    # ----------------------------------------
    # Generate TTS
    # ----------------------------------------

    run_async(
        generate_tts(
            text=text,
            voice=edge_voice,
            rate=actual_rate,
            volume="+0%",
            pitch=actual_pitch,
            output_file=str(
                raw_audio
            ),
            sub_file=str(
                raw_srt
            )
        )
    )

    # ----------------------------------------
    # Apply effect
    # ----------------------------------------

    processed = apply_effects(
        input_path=raw_audio,
        effect_name=effect_name,
        tempo=1.0,
        output_name=final_audio.name
    )

    # ----------------------------------------
    # SRT
    # ----------------------------------------

    if raw_srt.exists():

        raw_srt.replace(
            final_srt
        )

    # ----------------------------------------
    # Delete raw audio
    # ----------------------------------------

    if raw_audio.exists():

        try:

            raw_audio.unlink()

        except Exception:

            pass

    # ----------------------------------------
    # Usage
    # ----------------------------------------

    increment_usage()

    return (
        final_audio,
        final_srt
    )


# ============================================================
# ALIAS
# ============================================================

def generate_voice(
    text,
    voice_id,
    tempo=1.0,
    suffix="voice"
):

    audio, srt = run_tts_to_file(
        text=text,
        voice_id=voice_id,
        pitch_offset="+0Hz",
        rate="+0%",
        suffix=suffix
    )

    if tempo != 1.0:

        changed = change_tempo(
            audio,
            tempo
        )

        try:

            audio.unlink()

        except Exception:

            pass

        changed.replace(
            audio
        )

    return (
        audio,
        srt
    )


# ============================================================
# VOICE LIST
# ============================================================

def get_voice_list():

    return [
        {
            "id": name,
            "name": name,
            "display": label,
            "voice": voice,
            "pitch": pitch
        }

        for (
            voice,
            pitch,
            name,
            label
        ) in FEATURED_VOICES
    ]


# ============================================================
# GET VOICE NAMES
# ============================================================

def get_voice_names():

    return [
        name

        for (
            voice,
            pitch,
            name,
            label
        ) in FEATURED_VOICES
    ]


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_text = """
မင်္ဂလာပါ။ ဒါကတော့ Mg Khant AI Studio
မြန်မာ AI Voice Generator ရဲ့ စမ်းသပ်အသံဖြစ်ပါတယ်။
"""

    try:

        audio, srt = run_tts_to_file(
            text=test_text,
            voice_id="my-MM-ThihaNeural",
            suffix="test"
        )

        print(
            "SUCCESS"
        )

        print(
            "Audio:",
            audio
        )

        print(
            "SRT:",
            srt
        )

    except Exception as error:

        print(
            "ERROR:",
            error
        )