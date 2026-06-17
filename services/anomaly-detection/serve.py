"""Online scoring service. Consumes normalized HVAC stream, emits alerts."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal

from confluent_kafka import Consumer, Producer

from features import build_features
from model import HvacAnomalyModel

log = logging.getLogger("the-line.anomaly.serve")


def _make_consumer(bootstrap: str) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": "anomaly-scorer",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }
    )


def _make_producer(bootstrap: str) -> Producer:
    return Producer(
        {
            "bootstrap.servers": bootstrap,
            "enable.idempotence": True,
            "compression.type": "lz4",
        }
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="local path or s3:// URI")
    ap.add_argument(
        "--src-topic", default="the-line.bms.hvac.normalized"
    )
    ap.add_argument("--alerts-topic", default="the-line.bms.hvac.alerts")
    ap.add_argument(
        "--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)

    model = HvacAnomalyModel.load(args.model)
    consumer = _make_consumer(args.bootstrap)
    producer = _make_producer(args.bootstrap)
    consumer.subscribe([args.src_topic])

    running = True

    def _stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while running:
        msg = consumer.poll(0.5)
        if msg is None or msg.error():
            continue
        record = json.loads(msg.value())
        # In production we keep a rolling window per (module, floor, loop)
        # in a state store; here we just delegate to the model row-wise.
        feats = build_features(_row_to_frame(record)).iloc[-1].to_dict()
        result = model.score_one({**record, **feats})
        if result.is_anomaly:
            producer.produce(
                args.alerts_topic,
                key=msg.key(),
                value=json.dumps(
                    {
                        **record,
                        "score": result.score,
                        "threshold": result.threshold,
                    }
                ).encode(),
            )
        consumer.commit(msg, asynchronous=True)

    consumer.close()
    producer.flush(5)


def _row_to_frame(record: dict):
    import pandas as pd

    return pd.DataFrame([{**record, "ts": record.get("ts_ms")}])


if __name__ == "__main__":
    main()
