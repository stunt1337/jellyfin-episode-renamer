from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MediaTagOptions:
    include_resolution: bool = False
    resolution: str = ""
    include_hdr: bool = False
    hdr: str = ""
    include_video_codec: bool = False
    video_codec: str = ""
    include_audio: bool = False
    audio: str = ""
    include_custom: bool = False
    custom: str = ""


def build_media_tag_suffix(options: MediaTagOptions | None) -> str:
    if options is None:
        return ""

    tags = [
        options.resolution if options.include_resolution else "",
        options.hdr if options.include_hdr else "",
        options.video_codec if options.include_video_codec else "",
        options.audio if options.include_audio else "",
        options.custom if options.include_custom else "",
    ]
    clean_tags = [sanitize_tag(tag) for tag in tags if sanitize_tag(tag)]
    if not clean_tags:
        return ""
    return f" - {' '.join(clean_tags)}"


def append_media_tags(stem: str, options: MediaTagOptions | None) -> str:
    return f"{stem}{build_media_tag_suffix(options)}"


def sanitize_tag(value: str) -> str:
    tag = re.sub(r"[\\/:\0]", " ", value.strip())
    tag = re.sub(r"\s+", " ", tag).strip()
    return tag
