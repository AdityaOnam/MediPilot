"""
Simulated clock — mirrors mock.ts:109-111 semantics exactly.

sim_now() = sim_base + (real_now - sim_epoch) * speed

set_speed() freezes the current sim time, then re-anchors so
advancing the speed doesn't jump the clock.
"""

from __future__ import annotations

import datetime
import time


class SimClock:
    def __init__(self) -> None:
        now = time.time()
        self._sim_base: float = now
        self._sim_epoch: float = now
        self._speed: float = 1.0

    @property
    def speed(self) -> float:
        return self._speed

    def sim_now(self) -> datetime.datetime:
        real_now = time.time()
        sim_ts = self._sim_base + (real_now - self._sim_epoch) * self._speed
        return datetime.datetime.fromtimestamp(sim_ts, tz=datetime.timezone.utc)

    def sim_now_iso(self) -> str:
        return self.sim_now().isoformat()

    def real_now_iso(self) -> str:
        return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    def set_speed(self, speed: float) -> None:
        now_real = time.time()
        self._sim_base = self._sim_base + (now_real - self._sim_epoch) * self._speed
        self._sim_epoch = now_real
        self._speed = max(0.0, speed)
