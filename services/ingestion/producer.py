"""Per-module BMS producer.

Pulls HVAC tags from a module's OPC-UA gateway and publishes them to the
`the-line.bms.hvac.raw` Kafka topic. Designed to run one instance per
module, supervised by the edge node-pool.

KAN-24 — initial coverage is Modules 1-4. Extending to Modules 5+ is tracked
under follow-ups; see services/ingestion/README.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
from dataclasses import dataclass

from asyncua import Client
from confluent_kafka import Producer

log = logging.getLogger("the-line.ingestion.producer")

DEFAULT_TOPIC = "the-line.bms.hvac.raw"


@dataclass
class TagSpec:
    module: int
    floor: int
    loop: str
    node_id: str
    unit: str


def _load_tag_map(module: int) -> list[TagSpec]:
    # In real life this comes from the asset DB; stub here for Modules 1-4.
    if module not in (1, 2, 3, 4):
        raise ValueError(f"module {module} not yet onboarded (KAN-24)")
    tags: list[TagSpec] = []
    for floor in range(1, 121):  # 120 floors per module (stub)
        for loop in ("supply", "return"):
            tags.append(
                TagSpec(
                    module=module,
                    floor=floor,
                    loop=loop,
                    node_id=f"ns=4;s=Module{module}.F{floor:03d}.{loop}.temp",
                    unit="c",
                )
            )
    return tags


def _delivery(err, msg):
    if err is not None:
        log.error("kafka delivery failed: %s", err)
    else:
        log.debug("delivered %s[%d]@%d", msg.topic(), msg.partition(), msg.offset())


async def run(module: int, opcua_url: str, bootstrap: str, topic: str) -> None:
    producer = Producer(
        {
            "bootstrap.servers": bootstrap,
            "linger.ms": 20,
            "compression.type": "lz4",
            "enable.idempotence": True,
            "acks": "all",
            "client.id": f"module-{module:02d}-bms",
        }
    )
    tag_map = _load_tag_map(module)
    log.info("module=%d tags=%d connecting to %s", module, len(tag_map), opcua_url)

    async with Client(url=opcua_url) as client:
        nodes = [client.get_node(t.node_id) for t in tag_map]
        while True:
            values = await client.read_values(nodes)
            for spec, raw in zip(tag_map, values):
                payload = {
                    "module": spec.module,
                    "floor": spec.floor,
                    "loop": spec.loop,
                    "tag": spec.node_id,
                    "value": float(raw.Value.Value) if hasattr(raw, "Value") else float(raw),
                    "unit": spec.unit,
                    "quality": "good",
                    "ts_ms": int(asyncio.get_event_loop().time() * 1000),
                }
                producer.produce(
                    topic,
                    key=f"m{spec.module:02d}-f{spec.floor:03d}".encode(),
                    value=json.dumps(payload).encode("utf-8"),
                    on_delivery=_delivery,
                )
            producer.poll(0)
            await asyncio.sleep(1.0)  # 1 Hz sample rate (KAN-24 baseline)


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, loop.stop)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", type=int, required=True)
    ap.add_argument(
        "--opcua-url",
        default="opc.tcp://edge-gw.module-{module}.line.neom.local:4840",
    )
    ap.add_argument("--bootstrap", default="kafka.svc.cluster.local:9092")
    ap.add_argument("--topic", default=DEFAULT_TOPIC)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    url = args.opcua_url.format(module=args.module)
    loop = asyncio.new_event_loop()
    _install_signal_handlers(loop)
    try:
        loop.run_until_complete(run(args.module, url, args.bootstrap, args.topic))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
