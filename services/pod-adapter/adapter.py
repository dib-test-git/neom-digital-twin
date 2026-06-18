"""Vertical-transit pod telemetry adapter.

One adapter instance per corridor (A/B/C). Subscribes to the pod
controller's OPC-UA node space and republishes events to Kafka.

KAN-27.
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
    opcua_url: str
    bootstrap: str
    topic: str = "the-line.pods.telemetry"
    sample_hz: float = 10.0


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

    log.info("connecting corridor=%s url=%s", cfg.corridor, cfg.opcua_url)
    async with Client(url=cfg.opcua_url) as client:
        nodes = {t: client.get_node(f"ns=5;s={t}") for t in POD_TAGS}
        period = 1.0 / cfg.sample_hz
        while True:
            try:
                values = await client.read_values(list(nodes.values()))
            except (ua.UaError, ConnectionError) as exc:
                log.warning("opcua read failed: %s — failing over", exc)
                await asyncio.sleep(0.5)
                continue
            payload = {"corridor": cfg.corridor, **dict(zip(POD_TAGS, values))}
            producer.produce(
                cfg.topic,
                key=cfg.corridor.encode(),
                value=json.dumps(payload, default=str).encode(),
            )
            producer.poll(0)
            await asyncio.sleep(period)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corridor", required=True, choices=["A", "B", "C"])
    ap.add_argument("--opcua-url", required=True)
    ap.add_argument(
        "--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    )
    ap.add_argument("--sample-hz", type=float, default=10.0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)

    cfg = AdapterConfig(
        corridor=args.corridor,
        opcua_url=args.opcua_url,
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
