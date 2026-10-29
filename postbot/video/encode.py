"""FFmpeg helpers: stream raw frames into an H.264 MP4 (no intermediate PNGs)."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("video")


def ffmpeg_exe() -> str:
    """System ffmpeg if present, otherwise the static binary bundled with imageio-ffmpeg (Windows/CI)."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("FFmpeg not found. Install it, or `pip install imageio-ffmpeg`.") from exc


class Encoder:
    def __init__(self, out: Path, w: int, h: int, fps: int, audio: Path | None = None, crf: int = 20):
        cmd = [ffmpeg_exe(), "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
        if audio:
            cmd += ["-i", str(audio)]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
                "-movflags", "+faststart"]
        if audio:
            cmd += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
        cmd.append(str(out))
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, frame) -> None:
        self.proc.stdin.write(frame.tobytes())

    def close(self) -> None:
        self.proc.stdin.close()
        err = self.proc.stderr.read().decode(errors="replace")
        if self.proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {err[-400:]}")


def probe_duration(path: Path) -> float:
    """Duration of an encoded file in seconds (reads ffmpeg's header output)."""
    res = subprocess.run([ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True)
    for line in res.stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hms = line.split(",")[0].split()[1]
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0
