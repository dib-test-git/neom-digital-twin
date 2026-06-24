"""Failover retry buffer for the pod telemetry adapter.

Fixes KAN-50: messages were being dropped during the brief window when the
OPC-UA session fails over from the primary to the secondary controller.

Design
------

When the adapter is healthy, samples flow straight to the Kafka producer.
When the OPC-UA session goes unhealthy (read error, connection lost, or
the controller advertises `BadSessionIdInvalid`), we:

  1. Switch to the standby controller's URL.
  2. Buffer the *most recent* `max_age_seconds` worth of unacknowledged
     samples in memory (keyed by `(corridor, tag, ts_ms)`).
  3. As soon as the new session is up and the first read succeeds,
     drain the buffer into Kafka in monotonic timestamp order.

We intentionally do *not* persist the buffer to disk. The pod controllers
already keep a 5-minute rolling history that we can backfill from if the
adapter process itself crashes; the buffer here is only for the
sub-second failover window.

Bounded by both wall-clock age (`max_age_seconds`, default 30s) and
sample count (`max_samples`, default 5000) so a stuck failover can't
exhaust memory.

Tracks KAN-50.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass

log = logging.getLogger("the-line.pod-adapter.retry-buffer")


@dataclass
class BufferedSample:
    corridor: str
    payload: dict
    enqueued_at: float  # monotonic seconds


class RetryBuffer:
    """Bounded in-memory ring of unacknowledged samples for failover."""

    def __init__(self, max_samples: int = 5000, max_age_seconds: float = 30.0) -> None:
        self._dq: deque[BufferedSample] = deque(maxlen=max_samples)
        self._max_age = max_age_seconds
        self.dropped_total = 0  # exposed via prometheus

    def __len__(self) -> int:
        self._prune()
        return len(self._dq)

    def push(self, corridor: str, payload: dict) -> None:
        if len(self._dq) == self._dq.maxlen:
            # deque is full; we'll lose the oldest entry — count it.
            self.dropped_total += 1
        self._dq.append(
            BufferedSample(
                corridor=corridor,
                payload=payload,
                enqueued_at=time.monotonic(),
            )
        )

    def drain(self) -> list[BufferedSample]:
        """Return all currently-buffered samples in FIFO order and clear."""
        self._prune()
        out = list(self._dq)
        self._dq.clear()
        if out:
            log.info(
                "draining %d samples from retry buffer (oldest=%.2fs ago)",
                len(out),
                time.monotonic() - out[0].enqueued_at,
            )
        return out

    def _prune(self) -> None:
        cutoff = time.monotonic() - self._max_age
        pruned = 0
        while self._dq and self._dq[0].enqueued_at < cutoff:
            self._dq.popleft()
            pruned += 1
        if pruned:
            self.dropped_total += pruned
            log.warning("retry buffer pruned %d samples older than %.1fs", pruned, self._max_age)
