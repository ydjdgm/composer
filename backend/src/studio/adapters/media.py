"""Bounded validation of untrusted audio, separate from musical analysis."""

import json
import math
import queue
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path


class MediaError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _run_bounded(
    args: list[str],
    *,
    max_bytes: int,
    deadline: float,
    cancelled: Callable[[], bool],
    capture: bool = False,
) -> tuple[int, bytes]:
    """Drain stdout concurrently so timeout and cancellation also work on Windows."""
    if cancelled():
        raise MediaError("cancelled", "Audio validation was cancelled.")
    try:
        process = subprocess.Popen(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as exc:
        raise MediaError("provider_unavailable", "FFmpeg and ffprobe must be installed.", True) from exc
    except OSError as exc:
        raise MediaError("provider_unavailable", "The media validator could not start.", True) from exc

    chunks: queue.Queue[bytes | Exception | None] = queue.Queue(maxsize=4)
    stopped = threading.Event()

    def enqueue(value: bytes | Exception | None) -> None:
        while not stopped.is_set():
            try:
                chunks.put(value, timeout=0.1)
                return
            except queue.Full:
                continue

    def read_stdout() -> None:
        assert process.stdout is not None
        try:
            while not stopped.is_set():
                chunk = process.stdout.read(64 * 1024)
                if not chunk:
                    break
                enqueue(chunk)
        except Exception as exc:
            enqueue(exc)
        finally:
            enqueue(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    total = 0
    output = bytearray()
    try:
        eof = False
        while not eof or process.poll() is None:
            if cancelled():
                raise MediaError("cancelled", "Audio validation was cancelled.")
            if time.monotonic() >= deadline:
                raise MediaError("validation_timeout", "Audio validation exceeded the time limit.")
            try:
                chunk = chunks.get(timeout=0.1)
            except queue.Empty:
                continue
            if chunk is None:
                eof = True
            elif isinstance(chunk, Exception):
                raise MediaError("invalid_audio", "Audio could not be decoded.") from chunk
            else:
                total += len(chunk)
                if total > max_bytes:
                    raise MediaError("media_limit_exceeded", "Audio exceeds the validation limits.")
                if capture:
                    output.extend(chunk)
        if process.returncode != 0:
            raise MediaError("invalid_audio", "Audio is damaged or does not match its file format.")
        return total, bytes(output)
    finally:
        stopped.set()
        if process.poll() is None:
            process.kill()
        process.wait()
        reader.join(timeout=2)
        if process.stdout is not None:
            process.stdout.close()


def validate_audio(
    path: Path,
    extension: str,
    *,
    ffprobe: str = "ffprobe",
    ffmpeg: str = "ffmpeg",
    max_duration: float = 600,
    timeout: float = 60,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict:
    demuxer = extension.lower().lstrip(".")
    if demuxer not in {"wav", "mp3", "flac"}:
        raise MediaError("unsupported_media", "Only WAV, MP3, and FLAC audio are supported.")
    if not math.isfinite(max_duration) or max_duration <= 0 or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Media duration and timeout limits must be positive and finite")
    deadline = time.monotonic() + timeout
    source = str(path.resolve())
    input_options = [
        "-protocol_whitelist", "file", "-format_whitelist", "wav,mp3,flac",
        "-probesize", "1048576", "-analyzeduration", "5000000", "-f", demuxer,
    ]
    _, raw = _run_bounded(
        [ffprobe, "-v", "error", *input_options, "-select_streams", "a",
         "-show_entries", "stream=sample_rate,channels:format=format_name,duration",
         "-of", "json", source],
        max_bytes=64 * 1024, deadline=deadline, cancelled=cancelled, capture=True,
    )
    try:
        metadata = json.loads(raw)
        streams = metadata["streams"]
        if len(streams) != 1 or metadata["format"]["format_name"] != demuxer:
            raise ValueError("Expected a single audio stream")
        sample_rate = int(streams[0]["sample_rate"])
        channels = int(streams[0]["channels"])
        if not 8000 <= sample_rate <= 192000 or not 1 <= channels <= 8:
            raise ValueError("Unsupported sample rate or channels")
        declared_duration = metadata["format"].get("duration")
        if declared_duration not in (None, "N/A"):
            duration = float(declared_duration)
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("Invalid duration")
            if duration > max_duration:
                raise MediaError("media_limit_exceeded", "Audio exceeds the duration limit.")
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise MediaError("invalid_audio", "Audio metadata is invalid or unsupported.") from exc

    # Decode the entire source: a truncated preview would conceal corruption or
    # a forged duration. PCM count is bounded independently of container metadata.
    bytes_per_frame = channels * 2
    decoded_bytes, _ = _run_bounded(
        [ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-xerror",
         "-err_detect", "explode", *input_options, "-i", source,
         "-map", "0:a:0", "-vn", "-sn", "-dn", "-threads", "1",
         "-ar", str(sample_rate), "-ac", str(channels),
         "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"],
        max_bytes=int(max_duration * sample_rate) * bytes_per_frame,
        deadline=deadline, cancelled=cancelled,
    )
    if decoded_bytes == 0 or decoded_bytes % bytes_per_frame:
        raise MediaError("invalid_audio", "Audio contains no complete decoded frames.")
    frame_count = decoded_bytes // bytes_per_frame
    return {
        "duration_seconds": frame_count / sample_rate,
        "sample_rate": sample_rate,
        "channels": channels,
        "frame_count": frame_count,
        "format": demuxer,
    }
