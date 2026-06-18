# services/pod-adapter

OPC-UA adapter for The Line's vertical-transit pods (high-speed cabins
running through Corridor A/B/C). Translates the pod controllers' OPC-UA
node space into Kafka events on `the-line.pods.telemetry`.

Tracks [KAN-27](https://dib-test1.atlassian.net/browse/KAN-27).

Active bug: [KAN-50](https://dib-test1.atlassian.net/browse/KAN-50) —
messages dropped after an OPC-UA failover; see the
`fix/pod-failover-buffer` branch.

## Tags surfaced

| Group | Examples |
| --- | --- |
| Motion | `pod.velocity_mps`, `pod.accel_mps2`, `pod.position_m` |
| Power  | `pod.bus_voltage`, `pod.motor_current_a` |
| Safety | `pod.door_state`, `pod.estop_active`, `pod.brake_temp_c` |
| Network | `pod.opcua.session_state`, `pod.opcua.last_seq` |

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python adapter.py --corridor C --opcua-url opc.tcp://pod-c.line.neom.local:4840
```

## Failover behaviour

When the active OPC-UA session times out the adapter falls back to the
secondary controller. Until KAN-50 lands, the small window during failover
can drop in-flight samples — `retry_buffer.py` (in progress) buffers
unacknowledged messages and re-emits them once the new session is up.
