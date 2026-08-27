import html
import os
import re
import tempfile
import wave
from pathlib import Path

import requests
import streamlit as st


APP_TITLE = "မြန်မာစာ အသံပြောင်းစက်"
MAX_TEXT_CHARS = 10_000
CHUNK_SIZE = 2_400
SAMPLE_RATE = 24_000
SAMPLE_WIDTH = 2
CHANNELS = 1

# UI တွင် မြန်မာနာမည်ပဲ ပြပြီး Azure voice ID ကို နောက်ကွယ်မှာသာ သုံးသည်။
VOICE_CARDS = [
    ("နီလာ", "my-MM-NilarNeural"),
    ("အေမိဆန်", "en-US-AvaMultilingualNeural"),
    ("သင့်ဇာ", "en-US-EmmaMultilingualNeural"),
    ("စုမြတ်", "de-DE-SeraphinaMultilingualNeural"),
    ("ကြယ်စင်", "fr-FR-VivienneMultilingualNeural"),
    ("လမင်း", "zh-CN-XiaoxiaoMultilingualNeural"),
    ("သီဟ", "my-MM-ThihaNeural"),
    ("နေထူးနိုင်", "en-US-AndrewMultilingualNeural"),
    ("နေမျိုးအောင်", "en-US-BrianMultilingualNeural"),
    ("ကောင်ကောင်", "de-DE-FlorianMultilingualNeural"),
    ("အောင်ခန့်ပိုင်", "fr-FR-RemyMultilingualNeural"),
    ("နေတိုး", "it-IT-GiuseppeMultilingualNeural"),
]
VOICE_MAP = dict(VOICE_CARDS)


def read_secret(name: str, section: str = "azure_speech") -> str:
    """Read either top-level or nested Streamlit Secrets, then environment variables."""
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    try:
        nested = st.secrets.get(section, {})
        if hasattr(nested, "get"):
            value = nested.get(name.lower().replace("azure_speech_", ""), "")
            if value:
                return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, "").strip()


def azure_settings() -> tuple[str, str, str]:
    key = read_secret("AZURE_SPEECH_KEY")
    region = read_secret("AZURE_SPEECH_REGION") or "southeastasia"
    configured_endpoint = read_secret("AZURE_SPEECH_ENDPOINT")
    # api.cognitive.microsoft.com is not the regional TTS endpoint. Ignore it
    # and construct the documented regional TTS endpoint from the region.
    if configured_endpoint and ("tts.speech.microsoft.com" in configured_endpoint or "cognitiveservices.azure.com" in configured_endpoint):
        endpoint = configured_endpoint.rstrip("/")
    else:
        endpoint = f"https://{region}.tts.speech.microsoft.com"
    return key, region.lower(), endpoint


def voice_locale(voice_id: str) -> str:
    parts = str(voice_id).split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else "my-MM"


def split_text(text: str, limit: int = CHUNK_SIZE) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    pieces = [part.strip() for part in re.split(r"(?<=[။!?])\s+", cleaned) if part.strip()]
    chunks: list[str] = []
    current = ""
    for piece in pieces or [cleaned]:
        while len(piece) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(piece[:limit])
            piece = piece[limit:]
        candidate = f"{current} {piece}".strip()
        if current and len(candidate) > limit:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def make_ssml(text: str, voice_id: str, rate_percent: int, pitch_hz: int) -> str:
    safe_text = html.escape(text, quote=False)
    locale = voice_locale(voice_id)
    rate = f"{rate_percent:+d}%" if rate_percent else "0%"
    pitch = f"{pitch_hz:+d}Hz" if pitch_hz else "0Hz"
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{locale}">'
        f'<voice name="{html.escape(voice_id, quote=True)}">'
        f'<prosody rate="{rate}" pitch="{pitch}">{safe_text}</prosody>'
        "</voice></speak>"
    )


def request_audio(chunk: str, voice_id: str, key: str, endpoint: str, rate_percent: int, pitch_hz: int) -> bytes:
    url = f"{endpoint.rstrip('/')}/cognitiveservices/v1"
    response = requests.post(
        url,
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "raw-24khz-16bit-mono-pcm",
            "User-Agent": "azure-myanmar-tts-streamlit",
        },
        data=make_ssml(chunk, voice_id, rate_percent, pitch_hz).encode("utf-8"),
        timeout=(10, 90),
    )
    if not response.ok:
        detail = (response.text or "").strip()
        if len(detail) > 500:
            detail = detail[:500]
        raise RuntimeError(f"Azure Speech TTS error {response.status_code}: {detail or 'Azure က error detail မပြန်ပါ'}")
    audio = bytes(response.content or b"")
    if len(audio) < 480:
        raise RuntimeError("Azure က ပြန်ပေးသော အသံ data မပြည့်စုံပါ။")
    return audio


def pcm_to_wav(pcm: bytes) -> bytes:
    output = tempfile.SpooledTemporaryFile()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    output.seek(0)
    return output.read()


def srt_time(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds_value, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_value:02d},{millis:03d}"


def make_srt(chunks: list[str], audio_segments: list[bytes]) -> str:
    lines: list[str] = []
    cursor = 0.0
    for index, (chunk, audio) in enumerate(zip(chunks, audio_segments), start=1):
        duration = max(0.1, len(audio) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS))
        lines.extend([
            str(index),
            f"{srt_time(cursor)} --> {srt_time(cursor + duration)}",
            chunk,
            "",
        ])
        cursor += duration
    return "\n".join(lines)


def synthesize(text: str, voice_id: str, rate_percent: int, pitch_hz: int) -> tuple[bytes, str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        raise ValueError("အသံပြောင်းရန် စာသားထည့်ပါ။")
    if len(cleaned) > MAX_TEXT_CHARS:
        raise ValueError(f"စာလုံးရေ {MAX_TEXT_CHARS:,} ထက် မကျော်ရပါ။ လက်ရှိ {len(cleaned):,} လုံးရှိပါတယ်။")
    key, _region, endpoint = azure_settings()
    if not key:
        raise RuntimeError("AZURE_SPEECH_KEY ကို Streamlit Secrets ထဲ ထည့်ပါ။")
    chunks = split_text(cleaned)
    segments = [request_audio(chunk, voice_id, key, endpoint, rate_percent, pitch_hz) for chunk in chunks]
    return b"".join(segments), make_srt(chunks, segments)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🎙️", layout="centered")
    st.title("🎙️ မြန်မာစာ အသံပြောင်းစက်")
    st.caption("Azure Speech API သက်သက်ဖြင့် စာသားကို အသံပြောင်းပါ။")

    with st.expander("အသုံးပြုရန်လိုအပ်သော Secrets", expanded=False):
        st.code('AZURE_SPEECH_KEY = "သင့် Azure Speech Key"\nAZURE_SPEECH_REGION = "southeastasia"', language="toml")
        st.caption("Endpoint ကို မထည့်လည်းရပါသည်။ Region မှန်ကန်ပါက TTS endpoint ကို အလိုအလျောက်တည်ဆောက်ပါမည်။")

    text = st.text_area("အသံပြောင်းမည့်စာ", height=240, max_chars=MAX_TEXT_CHARS, placeholder="မြန်မာစာကို ဒီမှာ ထည့်ပါ…")
    st.caption(f"{len(text):,} / {MAX_TEXT_CHARS:,} စာလုံး")

    selected_name = st.selectbox("အသံရွေးရန်", [name for name, _voice in VOICE_CARDS])
    selected_voice = VOICE_MAP[selected_name]
    rate = st.slider("အသံမြန်နှုန်း", -40, 40, 0, 5, format="%d%%")
    pitch = st.slider("အသံအနိမ့်အမြင့်", -10, 10, 0, 1, format="%dHz")

    if st.button("အသံဖန်တီးမည်", type="primary", use_container_width=True):
        try:
            with st.spinner("အသံဖန်တီးနေပါသည်…"):
                pcm, srt = synthesize(text, selected_voice, rate, pitch)
            wav_data = pcm_to_wav(pcm)
            st.success("အသံဖန်တီးပြီးပါပြီ။")
            st.audio(wav_data, format="audio/wav")
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button("WAV ဒေါင်းရန်", wav_data, "myanmar_voice.wav", "audio/wav", use_container_width=True)
            with col_b:
                st.download_button("SRT ဒေါင်းရန်", srt.encode("utf-8"), "myanmar_voice.srt", "text/plain", use_container_width=True)
        except Exception as exc:
            st.error(f"အမှားအယွင်း ဖြစ်ပေါ်သည်: {exc}")


if __name__ == "__main__":
    main()
