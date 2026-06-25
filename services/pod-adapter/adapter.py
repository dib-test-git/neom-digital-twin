"""Vertical-transit pod telemetry adapter.

One adapter instance per corridor (A/B/C). Subscribes to the pod
controller's OPC-UA node space and republishes events to Kafka.

KAN-27 — base adapter.
KAN-50 — failover retry buffer integration (see retry_buffer.py).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
from dataclasses import dataclass

from asyncua import Client, ua
from confluent_kafka import Producer

from retry_buffer import RetryBuffer

log = logging.getLogger("the-line.pod-adapter")

POD_TAGS: list[str] = [
    "pod.velocity_mps",
    "pod.accel_mps2",
    "pod.position_m",
    "pod.bus_voltage",
    "pod.motor_current_a",
    "pod.door_state",
    "pod.estop_active",
    "pod.brake_temp_c",
]


@dataclass
class AdapterConfig:
    corridor: str
    primary_url: str
    standby_url: str
    bootstrap: str
    topic: str = "the-line.pods.telemetry"
    sample_hz: float = 10.0


def _publish(producer: Producer, topic: str, corridor: str, payload: dict) -> None:
    producer.produce(
        topic,
        key=corridor.encode(),
        value=json.dumps(payload, default=str).encode(),
    )


async def run(cfg: AdapterConfig) -> None:
    producer = Producer(
        {
            "bootstrap.servers": cfg.bootstrap,
            "linger.ms": 5,
            "compression.type": "lz4",
            "enable.idempotence": True,
            "acks": "all",
            "client.id": f"pod-adapter-{cfg.corridor.lower()}",
        }
    )

    buffer = RetryBuffer(max_samples=5000, max_age_seconds=30.0)
    url = cfg.primary_url
    period = 1.0 / cfg.sample_hz

    while True:
        log.info("connecting corridor=%s url=%s", cfg.corridor, url)
        try:
            async with Client(url=url) as client:
                nodes = {t: client.get_node(f"ns=5;s={t}") for t in POD_TAGS}

                # Drain any samples accumulated during the failover window.
                for buffered in buffer.drain():
                    _publish(producer, cfg.topic, buffered.corridor, buffered.payload)

                while True:
                    try:
                        values = await client.read_values(list(nodes.values()))
                    except (ua.UaError, ConnectionError) as exc:
                        log.warning("opcua read failed on %s: %s — failing over", url, exc)
                        break
                    payload = {"corridor": cfg.corridor, **dict(zip(POD_TAGS, values))}
                    try:
                        _publish(producer, cfg.topic, cfg.corridor, payload)
                        producer.poll(0)
                    except BufferError:
                        # Producer queue full — buffer locally and retry next tick.
                        buffer.push(cfg.corridor, payload)
                    await asyncio.sleep(period)
        except Exception as exc:  # pragma: no cover — top-level safety net
            log.error("adapter session error: %s", exc, exc_info=True)

        # Failover: swap URLs and try again after a short backoff.
        url = cfg.standby_url if url == cfg.primary_url else cfg.primary_url
        log.info("failing over to %s (buffered=%d)", url, len(buffer))
        await asyncio.sleep(0.5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corridor", required=True, choices=["A", "B", "C"])
    ap.add_argument("--primary-url", required=True)
    ap.add_argument("--standby-url", required=True)
    ap.add_argument(
        "--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    )
    ap.add_argument("--sample-hz", type=float, default=10.0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)

    cfg = AdapterConfig(
        corridor=args.corridor,
        primary_url=args.primary_url,
        standby_url=args.standby_url,
        bootstrap=args.bootstrap,
        sample_hz=args.sample_hz,
    )
    loop = asyncio.new_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, loop.stop)
    try:
        loop.run_until_complete(run(cfg))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
