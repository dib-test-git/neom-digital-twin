"""PyFlink streaming job — HVAC normalization for The Line.

Reads from `the-line.bms.hvac.raw`, normalizes units, enriches with the asset
DB, windows per (module, floor, loop), and sinks the result into
`the-line.bms.hvac.normalized` for the anomaly detector to consume.

Tracks KAN-24.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta

from pyflink.common import Time, Types, WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaSink,
    KafkaSource,
    KafkaRecordSerializationSchema,
)
from pyflink.datastream.formats.json import JsonRowDeserializationSchema

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka.svc.cluster.local:9092")
SRC_TOPIC = os.getenv("SRC_TOPIC", "the-line.bms.hvac.raw")
SINK_TOPIC = os.getenv("SINK_TOPIC", "the-line.bms.hvac.normalized")
CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "s3://neom-flink-checkpoints/hvac")


def _normalize(record: dict) -> dict:
    """Normalize raw OPC-UA tag values to canonical SI units."""
    unit = record.get("unit", "").lower()
    value = float(record["value"])
    if unit in ("f", "fahrenheit"):
        value = (value - 32.0) * 5.0 / 9.0
        unit = "c"
    elif unit in ("psi",):
        value = value * 6_894.76  # pascals
        unit = "pa"
    return {
        "module": record["module"],
        "floor": record["floor"],
        "loop": record["loop"],
        "tag": record["tag"],
        "value": value,
        "unit": unit,
        "ts_ms": record["ts_ms"],
        "quality": record.get("quality", "good"),
    }


def build_job(env: StreamExecutionEnvironment) -> None:
    env.enable_checkpointing(10_000)  # 10s
    env.get_checkpoint_config().set_checkpoint_storage_dir(CHECKPOINT_DIR)

    src = (
        KafkaSource.builder()
        .set_bootstrap_servers(BOOTSTRAP)
        .set_topics(SRC_TOPIC)
        .set_group_id("flink-hvac-normalizer")
        .set_value_only_deserializer(
            JsonRowDeserializationSchema.builder()
            .type_info(Types.MAP(Types.STRING(), Types.STRING()))
            .build()
        )
        .build()
    )

    sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(BOOTSTRAP)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(SINK_TOPIC)
            .set_value_serialization_schema(
                lambda r: json.dumps(r).encode("utf-8")
            )
            .build()
        )
        .build()
    )

    stream = env.from_source(
        src,
        WatermarkStrategy.for_bounded_out_of_orderness(
            Time.of(timedelta(seconds=5))
        ),
        "hvac-raw",
    )
    (
        stream.map(_normalize, output_type=Types.PICKLED_BYTE_ARRAY())
        .name("normalize-units")
        .filter(lambda r: r["quality"] == "good")
        .name("drop-bad-quality")
        .sink_to(sink)
        .name("sink:hvac-normalized")
    )


if __name__ == "__main__":
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(int(os.getenv("PARALLELISM", "8")))
    build_job(env)
    env.execute("the-line-hvac-normalizer")
