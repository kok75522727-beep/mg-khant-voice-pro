import asyncio
import edge_tts
import subprocess
import json
from pathlib import Path


# ============================================================
# FEATURED VOICES
# Format:
# (edge_voice, pitch, name, display_name)
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
# VOICE EXTRA SETTINGS
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
        "effect": "Radio"
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
        "effect": "None"
    },

    "PaingPhyo": {
        "rate": "-5%",
        "effect": "Deep"
    },

    "KhaingThin": {
        "rate": "+7%",
        "effect": "Radio"
    }
}


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

    "Radio":
        "highpass=f=500,"
        "lowpass=f=3200",

    "Echo":
        "aecho=0.8:0.88:700:0.25",

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

            pass

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
# FIND VOICE
# ============================================================

def get_voice_info(voice_name):

    for (
        voice_id,
        pitch,
        name,
        label
    ) in FEATURED_VOICES:

        if name == voice_name:
            return (
                voice_id,
                pitch,
                name,
                label
            )

    return None


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

    loop = asyncio.new_event_loop()

    try:

        asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            coro
        )

    finally:

        loop.close()

        asyncio.set_event_loop(None)


# ============================================================
# APPLY EFFECTS
# ============================================================

def apply_effects(
    input_path,
    effect_name="None",
    tempo=1.0
):

    input_path = Path(
        input_path
    )

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

    subprocess.run(
        command,
        check=True,
        capture_output=True
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

    output_path = (
        input_path.parent /
        f"tempo_{input_path.stem}.mp3"
    )

    tempo = float(tempo)

    if tempo < 0.5:
        tempo = 0.5

    if tempo > 2.0:
        tempo = 2.0

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
# MAIN TTS FUNCTION
# ============================================================

def run_tts_to_file(
    text,
    voice_id,
    pitch_offset="+0Hz",
    rate="+0%",
    suffix="output"
):

    # --------------------------------------------
    # Find selected voice
    # --------------------------------------------

    selected = None

    for (
        voice,
        default_pitch,
        name,
        label
    ) in FEATURED_VOICES:

        if name == voice_id:

            selected = (
                voice,
                default_pitch,
                name,
                label
            )

            break

    if selected is None:

        raise ValueError(
            f"Voice not found: {voice_id}"
        )

    (
        voice,
        default_pitch,
        name,
        label
    ) = selected


    # --------------------------------------------
    # Voice settings
    # --------------------------------------------

    settings = VOICE_SETTINGS.get(
        name,
        {
            "rate": "+0%",
            "effect": "None"
        }
    )

    # If app provides default values,
    # use preset values for distinction.
    actual_pitch = (
        default_pitch
        if pitch_offset == "+0Hz"
        else pitch_offset
    )

    actual_rate = (
        settings["rate"]
        if rate == "+0%"
        else rate
    )


    # --------------------------------------------
    # Temporary files
    # --------------------------------------------

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
    # Generate Edge TTS
    # --------------------------------------------

    run_async(
        generate_tts(
            text=text,
            voice=voice,
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


    # --------------------------------------------
    # Apply effect
    # --------------------------------------------

    processed_audio = apply_effects(
        input_path=raw_audio,
        effect_name=settings["effect"],
        tempo=1.0
    )


    # --------------------------------------------
    # Rename final audio
    # --------------------------------------------

    if final_audio.exists():

        final_audio.unlink()

    processed_audio.replace(
        final_audio
    )


    # --------------------------------------------
    # SRT
    # --------------------------------------------

    if raw_srt.exists():

        if final_srt.exists():
            final_srt.unlink()

        raw_srt.replace(
            final_srt
        )


    # --------------------------------------------
    # Cleanup
    # --------------------------------------------

    if raw_audio.exists():

        try:
            raw_audio.unlink()
        except Exception:
            pass


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

    # Optional tempo adjustment
    if tempo != 1.0:

        tempo_audio = change_tempo(
            audio,
            tempo
        )

        if audio.exists():

            audio.unlink()

        tempo_audio.replace(
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