"""File discovery and format detection.

Accepts single files, folders (recursive) and archives:

* `.fit`, `.tcx`, `.gpx` and their gzip versions (`.fit.gz`... as found in the
  Strava bulk export);
* `.zip`, including nested zips (Garmin "Export your data" archive contains zips
  of FIT files; the Garmin API returns a zip holding the original FIT file).
"""

from __future__ import annotations

import gzip
import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from cadence_tracker.models import ParsedActivity

MAX_MEMBER_BYTES = 80 * 1024 * 1024  # guard against zip bombs
SUPPORTED_SUFFIXES = (".fit", ".tcx", ".gpx", ".zip", ".gz")


@dataclass
class RawFile:
    name: str  # original name (with archive path when extracted)
    data: bytes  # decompressed content
    fmt: str  # 'fit' | 'tcx' | 'gpx'


def detect_format(name: str, data: bytes) -> str | None:
    """Detect FIT/TCX/GPX from content first, then from the file name."""
    if len(data) >= 12 and data[8:12] == b".FIT":
        return "fit"
    head = data[:2048].lstrip().lower()
    if head.startswith(b"<?xml") or head.startswith(b"<"):
        if b"trainingcenterdatabase" in head:
            return "tcx"
        if b"<gpx" in head:
            return "gpx"
    lower = name.lower()
    for fmt in ("fit", "tcx", "gpx"):
        if lower.endswith(f".{fmt}"):
            return fmt
    return None


def _expand(name: str, data: bytes, depth: int = 0) -> Iterator[RawFile]:
    lower = name.lower()
    if depth > 3:
        return
    if lower.endswith(".gz") or data[:2] == b"\x1f\x8b":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
                inner = gz.read(MAX_MEMBER_BYTES + 1)
        except OSError:
            return
        if len(inner) <= MAX_MEMBER_BYTES:
            yield from _expand(name[:-3] if lower.endswith(".gz") else name, inner, depth + 1)
        return
    if lower.endswith(".zip") or data[:4] == b"PK\x03\x04":
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return
        with archive:
            for info in archive.infolist():
                member = info.filename
                if info.is_dir() or "__MACOSX" in member or info.file_size > MAX_MEMBER_BYTES:
                    continue
                if not member.lower().endswith(SUPPORTED_SUFFIXES):
                    continue
                yield from _expand(f"{name}/{member}", archive.read(info), depth + 1)
        return
    fmt = detect_format(name, data)
    if fmt:
        yield RawFile(name=name, data=data, fmt=fmt)


def iter_raw_files(paths: list[Path]) -> Iterator[RawFile]:
    """Yield every activity file found in the given files/folders/archives."""
    for path in paths:
        path = Path(path).expanduser()
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.name.lower().endswith(SUPPORTED_SUFFIXES):
                    yield from _expand(str(child), child.read_bytes())
        elif path.is_file():
            yield from _expand(str(path), path.read_bytes())


def iter_raw_bytes(name: str, data: bytes) -> Iterator[RawFile]:
    """Same as iter_raw_files for in-memory uploads (UI) and API downloads."""
    yield from _expand(name, data)


def parse_raw(raw: RawFile, *, source: str | None = None, source_id: str | None = None) -> list[ParsedActivity]:
    from cadence_tracker.ingest.fit import parse_fit
    from cadence_tracker.ingest.xml_formats import parse_gpx, parse_tcx

    parser = {"fit": parse_fit, "tcx": parse_tcx, "gpx": parse_gpx}[raw.fmt]
    return parser(raw.data, source=source or f"{raw.fmt}_file", source_id=source_id)
