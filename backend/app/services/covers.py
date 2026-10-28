"""封面抽取、缩放与落盘。

优先级（docs/AUDIO_FORMATS.md §5）：内嵌图片 > 同目录 `cover|folder|front.*` > 占位图。
统一转成 JPEG：原图最大边 1600、缩略图宽 400，写入 `<covers_dir>/{book_id}.jpg`
与 `{book_id}_thumb.jpg`。绝不写回媒体目录。
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

THUMB_WIDTH = 400
FULL_MAX = 1600
JPEG_QUALITY = 82
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

SIDECAR_STEMS = ("cover", "folder", "front")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


class CoverError(ValueError):
    """图片无法解析或格式不支持。"""


def extract_embedded(path: Path) -> bytes | None:
    """从音频文件里取内嵌封面字节；没有就返回 None。"""
    try:
        audio = MutagenFile(path)
    except Exception:  # noqa: BLE001 - 损坏标签不应中断扫描
        return None
    if audio is None:
        return None

    tags = audio.tags
    try:
        if isinstance(audio, MP3):
            if isinstance(tags, ID3):
                for frame in tags.getall("APIC"):
                    return bytes(frame.data)
        elif isinstance(audio, MP4):
            covers = (tags or {}).get("covr") or []
            if covers:
                return bytes(covers[0])
        elif isinstance(audio, FLAC):
            pictures = getattr(audio, "pictures", None) or []
            if pictures:
                return bytes(pictures[0].data)
        elif isinstance(audio, (OggVorbis, OggOpus)):
            raw = (tags or {}).get("metadata_block_picture")
            if raw:
                return bytes(Picture(base64.b64decode(raw[0])).data)
    except Exception:  # noqa: BLE001
        logger.debug("读取内嵌封面失败: %s", path, exc_info=True)
    return None


def find_sidecar(media_path: Path) -> Path | None:
    """同目录下的 cover/folder/front 图片（大小写不敏感）。"""
    try:
        entries = list(media_path.parent.iterdir())
    except OSError:
        return None

    for entry in entries:
        if not entry.is_file():
            continue
        if (
            entry.stem.lower() in SIDECAR_STEMS
            and entry.suffix.lower() in IMAGE_SUFFIXES
        ):
            return entry
    return None


def extract_from_media(media_path: Path) -> bytes | None:
    data = extract_embedded(media_path)
    if data:
        return data
    sidecar = find_sidecar(media_path)
    if sidecar is not None:
        try:
            return sidecar.read_bytes()
        except OSError:
            return None
    return None


def _to_rgb(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.split()[-1])
        return canvas
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _encode(image: Image.Image, max_side: int) -> bytes:
    copy = image.copy()
    copy.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    copy.save(buffer, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def normalize(data: bytes) -> tuple[bytes, bytes]:
    """返回 (原图 JPEG, 缩略图 JPEG)。"""
    try:
        with Image.open(io.BytesIO(data)) as image:
            rgb = _to_rgb(image)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise CoverError("无法识别的图片格式") from exc

    return _encode(rgb, FULL_MAX), _encode(rgb, THUMB_WIDTH)


def save_cover(book_id: int, data: bytes, covers_dir: Path) -> str:
    """写入封面与缩略图，返回存进 `book.cover_path` 的相对文件名。"""
    full, thumb = normalize(data)
    covers_dir.mkdir(parents=True, exist_ok=True)
    (covers_dir / f"{book_id}.jpg").write_bytes(full)
    (covers_dir / f"{book_id}_thumb.jpg").write_bytes(thumb)
    return f"{book_id}.jpg"


def remove_cover(book_id: int, covers_dir: Path) -> None:
    for name in (f"{book_id}.jpg", f"{book_id}_thumb.jpg"):
        (covers_dir / name).unlink(missing_ok=True)
