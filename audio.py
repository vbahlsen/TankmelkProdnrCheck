"""Avspilling av forhåndsinnspilte lydvarsler (cues).

Cue-filene genereres én gang per maskin av tools/generate_voice_cues.ps1 og ligger i
settings.VOICE_CUES_DIR. Denne modulen spiller dem av med justerbart volum, uten
eksterne avhengigheter (ren stdlib: winsound + wave + array), siden pydub/audioop
ikke fungerer på Python 3.13+ (audioop ble fjernet fra stdlib).

Volumjustering skjer ved å skalere PCM-samplene og skrive en volum-justert kopi til
en cache-mappe (én gang per unike (cue, volumnivå)-kombinasjon), som deretter spilles
av med winsound.PlaySound(..., SND_FILENAME | SND_ASYNC). Python sitt winsound-modul
tillater ikke SND_MEMORY sammen med SND_ASYNC ("Cannot play asynchronously from
memory"), så avspilling direkte fra minnet uten mellomlagring er ikke mulig.
"""

import array
import io
import os
import wave
import winsound

import settings

CUE_KEYS = [str(n) for n in range(1, 16)] + ["ikke_i_uttaksliste", "mottatt_duplikat"]

# Antatt lengde (ms) på én talt cue -- brukes til å sekvensere flere cue'er
# etter hverandre uten at et nytt PlaySound-kall kutter av det forrige.
CUE_CHAIN_GAP_MS = 900

_path_cache: dict[tuple[str, int], str] = {}


def _cue_source_path(cue_key: str) -> str:
    return os.path.join(settings.VOICE_CUES_DIR, f"{cue_key}.wav")


def _volume_bucket(volume: float) -> int:
    """Runder volum til nærmeste hele prosent for å begrense antall cache-filer."""
    return round(max(0.0, min(1.0, volume)) * 100)


def _render_with_gain(cue_key: str, gain: float) -> bytes | None:
    try:
        with wave.open(_cue_source_path(cue_key), "rb") as wf:
            params = wf.getparams()
            raw_frames = wf.readframes(wf.getnframes())
    except (FileNotFoundError, wave.Error):
        return None

    if params.sampwidth == 2 and gain != 1.0:
        samples = array.array("h")
        samples.frombytes(raw_frames)
        for i, sample in enumerate(samples):
            scaled = int(sample * gain)
            if scaled > 32767:
                scaled = 32767
            elif scaled < -32768:
                scaled = -32768
            samples[i] = scaled
        raw_frames = samples.tobytes()

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf_out:
        wf_out.setparams(params)
        wf_out.writeframes(raw_frames)
    return buf.getvalue()


def _cached_wav_path(cue_key: str, volume: float) -> str | None:
    bucket = _volume_bucket(volume)
    cache_key = (cue_key, bucket)
    if cache_key in _path_cache:
        return _path_cache[cache_key]

    out_path = os.path.join(settings.VOLUME_CACHE_DIR, f"{cue_key}_{bucket}.wav")
    if os.path.exists(out_path):
        _path_cache[cache_key] = out_path
        return out_path

    data = _render_with_gain(cue_key, bucket / 100.0)
    if data is None:
        return None

    os.makedirs(settings.VOLUME_CACHE_DIR, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data)
    _path_cache[cache_key] = out_path
    return out_path


def play_cue(cue_key: str, volume: float, purge: bool = True) -> bool:
    """Spiller av en cue asynkront. Returnerer False hvis lydfila mangler.

    purge=True (standard) stopper ev. lyd som fortsatt spilles fra en tidligere
    hendelse først -- "siste vinner", viktig for tallcue'er ved raske gjentatte
    skanninger. Sett purge=False når du bevisst spiller flere cue'er etter
    hverandre for samme hendelse (f.eks. sorteringsnummer + "Mottatt duplikat"),
    siden winsound bare kan spille én lyd om gangen og et nytt PlaySound-kall
    ellers ville kuttet av den forrige cue'en i samme sekvens."""
    path = _cached_wav_path(cue_key, volume)
    if path is None:
        return False

    if purge:
        winsound.PlaySound(None, winsound.SND_PURGE)
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    return True


def play_test(volume: float) -> None:
    """Brukes av innstillingsdialogen til å høre gjeldende volum."""
    play_cue("mottatt_duplikat", volume)


def missing_cue_files() -> list[str]:
    """Returnerer nøklene til cue'er hvis lydfil ikke finnes -- til varsling i UI."""
    missing = []
    for key in CUE_KEYS:
        try:
            with wave.open(_cue_source_path(key), "rb"):
                pass
        except (FileNotFoundError, wave.Error):
            missing.append(key)
    return missing
