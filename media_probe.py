from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from media_tags import MediaTagOptions


class MediaProbeError(RuntimeError):
    pass


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def probe_media_tags(path: Path) -> MediaTagOptions:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise MediaProbeError("ffprobe was not found in PATH.")

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format:stream",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() or error.stdout.strip() or str(error)
        raise MediaProbeError(f"ffprobe failed for {path.name}: {details}") from error

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise MediaProbeError(f"ffprobe returned invalid JSON for {path.name}.") from error

    return tags_from_ffprobe_data(data)


def tags_from_ffprobe_data(data: dict[str, Any]) -> MediaTagOptions:
    streams = [stream for stream in data.get("streams", []) if isinstance(stream, dict)]
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]

    resolution = detect_resolution(video)
    hdr = detect_hdr(video)
    video_codec = detect_video_codec(video)
    audio = detect_best_audio(audio_streams)

    return MediaTagOptions(
        include_resolution=bool(resolution),
        resolution=resolution,
        include_hdr=bool(hdr),
        hdr=hdr,
        include_video_codec=bool(video_codec),
        video_codec=video_codec,
        include_audio=bool(audio),
        audio=audio,
    )


def detect_resolution(video: dict[str, Any]) -> str:
    height = int(video.get("height") or 0)
    if height >= 2000:
        return "2160p"
    if height >= 1000:
        return "1080p"
    if height >= 700:
        return "720p"
    if height >= 560:
        return "576p"
    if height >= 460:
        return "480p"
    return ""


def detect_video_codec(video: dict[str, Any]) -> str:
    codec = str(video.get("codec_name") or "").lower()
    codec_map = {
        "hevc": "HEVC",
        "h265": "HEVC",
        "h264": "H264",
        "av1": "AV1",
        "mpeg2video": "MPEG2",
        "vc1": "VC1",
    }
    return codec_map.get(codec, codec.upper())


def detect_hdr(video: dict[str, Any]) -> str:
    text = json.dumps(video, sort_keys=True).lower()
    has_dolby_vision = any(token in text for token in ("dolby vision", "dovi", "dvhe", "dvh1"))
    has_hdr10_plus = any(token in text for token in ("hdr10+", "smpte st 2094", "dynamic_hdr_plus"))

    transfer = str(video.get("color_transfer") or "").lower()
    has_hdr = transfer in {"smpte2084", "arib-std-b67"} or any(
        token in text for token in ("smpte2084", "bt2020", "hdr10")
    )

    if has_dolby_vision and has_hdr:
        return "DV HDR"
    if has_dolby_vision:
        return "DV"
    if has_hdr10_plus:
        return "HDR10+"
    if has_hdr:
        return "HDR"
    return ""


def detect_best_audio(audio_streams: list[dict[str, Any]]) -> str:
    best = ""
    best_score = -1
    for stream in audio_streams:
        audio = detect_audio_codec(stream)
        score = audio_score(audio)
        if score > best_score:
            best = audio
            best_score = score
    return best


def detect_audio_codec(stream: dict[str, Any]) -> str:
    codec = str(stream.get("codec_name") or "").lower()
    profile = str(stream.get("profile") or "").lower()
    tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
    title = str(tags.get("title") or "").lower()
    text = json.dumps(stream, sort_keys=True).lower()

    if codec == "truehd":
        if "atmos" in text:
            return "TrueHD Atmos"
        return "TrueHD"
    if codec == "dts":
        if "dts:x" in text or "dts-x" in text:
            return "DTS:X"
        if "ma" in title or "master audio" in text or "dts-hd ma" in text or "dts hd ma" in text:
            return "DTS-HD MA"
        return "DTS"
    if codec == "eac3":
        return "EAC3"
    if codec == "ac3":
        return "AC3"
    if codec == "aac":
        return "AAC"
    if codec == "flac":
        return "FLAC"
    if profile:
        return profile.upper()
    return codec.upper()


def audio_score(audio: str) -> int:
    ranking = {
        "TrueHD Atmos": 90,
        "DTS:X": 85,
        "TrueHD": 80,
        "DTS-HD MA": 75,
        "FLAC": 70,
        "DTS": 60,
        "EAC3": 50,
        "AC3": 40,
        "AAC": 30,
    }
    return ranking.get(audio, 0)
