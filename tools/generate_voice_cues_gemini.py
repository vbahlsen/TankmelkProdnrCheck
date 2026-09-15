"""Genererer de 17 faste lydvarslene ("1".."15", "ikke_i_uttaksliste",
"mottatt_duplikat") som .wav-filer med Gemini sin tale-generering (Google AI
Studio), som alternativ til tools/generate_voice_cues.ps1 for maskiner der en
norsk Windows-stemme ikke kan installeres (f.eks. pga. virksomhetspolicy).

Krever en API-nøkkel fra https://aistudio.google.com/apikey satt som
miljøvariabel GEMINI_API_KEY.

Kjøres én gang per maskin (eller på nytt for å bytte stemme/kvalitet). Filene
lagres i samme mappe som den lokale PowerShell-varianten bruker, så appen
plukker dem opp uendret: %APPDATA%\\TankmelkScanner\\voice_cues\\<key>.wav
"""

import base64
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import settings  # noqa: E402

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODEL = "gemini-3.1-flash-tts-preview"
VOICE = os.environ.get("GEMINI_TTS_VOICE", "Kore")

CUES = {
    "1": "en",
    "2": "to",
    "3": "tre",
    "4": "fire",
    "5": "fem",
    "6": "seks",
    "7": "sju",
    "8": "åtte",
    "9": "ni",
    "10": "ti",
    "11": "elleve",
    "12": "tolv",
    "13": "tretten",
    "14": "fjorten",
    "15": "femten",
    "ikke_i_uttaksliste": "Ikke i uttaksliste",
    "mottatt_duplikat": "Mottatt duplikat",
}


RETRY_SECONDS_RE = re.compile(r"retry in ([\d.]+)s")


def _call_api(api_key: str, prompt: str) -> bytes:
    body = {
        "model": MODEL,
        "input": prompt,
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": VOICE}]},
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def synthesize(api_key: str, text: str, max_retries: int = 4) -> tuple[bytes, int, int]:
    # Korte, bare ord (f.eks. "seks", "ni") blir noen ganger feilaktig blokkert av
    # Geminis innholdsfilter når de sendes helt uten kontekst -- en fullstendig
    # setning rundt ordet unngår som regel den falske positive treffen.
    prompt = f"Si dette rolig og tydelig på norsk: {text}."

    for attempt in range(max_retries + 1):
        try:
            raw = _call_api(api_key, prompt)
            break
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", "replace")
            if e.code == 429 and attempt < max_retries:
                match = RETRY_SECONDS_RE.search(error_body)
                wait = float(match.group(1)) + 2 if match else 30
                print(f" (rate limited, venter {wait:.0f}s...)", end="", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"Gemini API-feil {e.code}: {error_body}") from e
    else:
        raise RuntimeError("Ga opp etter for mange forsøk (rate limit).")

    parsed = json.loads(raw)
    content = parsed["steps"][0]["content"][0]
    pcm_bytes = base64.b64decode(content["data"])
    sample_rate = content.get("sample_rate", 24000)
    channels = content.get("channels", 1)
    return pcm_bytes, sample_rate, channels


def save_wav(path: str, pcm_bytes: bytes, sample_rate: int, channels: int) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit (audio/l16)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("FEIL: miljøvariabelen GEMINI_API_KEY er ikke satt.")
        sys.exit(1)

    os.makedirs(settings.VOICE_CUES_DIR, exist_ok=True)
    print(f"Genererer lydvarsler til: {settings.VOICE_CUES_DIR}")
    print(f"Modell: {MODEL}, stemme: {VOICE}")

    for key, text in CUES.items():
        out_path = os.path.join(settings.VOICE_CUES_DIR, f"{key}.wav")
        print(f"  -> {key}.wav  ('{text}')", end="", flush=True)
        try:
            pcm, rate, channels = synthesize(api_key, text)
            save_wav(out_path, pcm, rate, channels)
            print(f"  OK ({len(pcm)} bytes, {rate} Hz)")
        except Exception as e:
            print(f"  FEILET: {e}")
        time.sleep(1.2)  # skånsomt mot rate limits (fri prøvekonto: 10 forespørsler/min)

    # Fjern evt. mellomlagrede volum-justerte kopier av de GAMLE (engelske) filene,
    # slik at audio.py ikke fortsetter å spille av dem i stedet for de nye.
    if os.path.isdir(settings.VOLUME_CACHE_DIR):
        shutil.rmtree(settings.VOLUME_CACHE_DIR)
        print(f"Tømte volum-cache: {settings.VOLUME_CACHE_DIR}")

    print("Ferdig.")


if __name__ == "__main__":
    main()
