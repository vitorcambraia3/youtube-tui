from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    channel: str = ""
    duration: float = 0.0
    webpage_url: str = field(default="")

    def __post_init__(self) -> None:
        if not self.webpage_url:
            object.__setattr__(self, "webpage_url", f"https://youtu.be/{self.id}")

    def __str__(self) -> str:
        dur = self.format_duration(self.duration)
        parts = [self.title]
        if self.channel:
            parts.append(f" — {self.channel}")
        if dur:
            parts.append(f" ({dur})")
        return "".join(parts)

    @staticmethod
    def format_duration(seconds: float) -> str:
        if not seconds or seconds < 0:
            return ""
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"