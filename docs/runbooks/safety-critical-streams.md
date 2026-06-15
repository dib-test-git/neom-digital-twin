# Runbook — safety-critical stream interruption

> **Severity:** P1 by default. Page CityOps on first symptom.
> Tracks [KAN-28](https://dib-test1.atlassian.net/browse/KAN-28).

## When to use this runbook

You are paged because one of:

- Producer lag on a `the-line.safety.*` topic exceeded the SLO (>5s for
  60s sustained).
- The `safety_critical` MSK cluster has < 3 in-sync replicas on any
  partition.
- A fire-life or lift-override consumer has stopped committing offsets.

## On-call rotation

- **Primary** — @neom-cityops-leads (PagerDuty: `cityops-primary`)
- **Secondary** — @neom-platform-data
- Escalation after 15 min → CityOps Director

## Step 1 — confirm scope

```bash
# Are we losing replicas?
kafka-topics --bootstrap-server $SAFETY_BOOTSTRAP \
  --describe --under-replicated-partitions

# Producer lag per partition
kafka-consumer-groups --bootstrap-server $SAFETY_BOOTSTRAP \
  --group safety-archiver --describe
```

If `under-replicated-partitions` is empty AND consumer lag is normal, this
is a false page — verify alerting and close.

## Step 2 — fail consumers over

Safety-critical consumers run active/standby in two AZs. If the active
side is the affected one:

```bash
kubectl --context neom-prod-cloud -n safety \
  rollout restart deployment/safety-archiver-az-b
kubectl --context neom-prod-cloud -n safety \
  scale deployment/safety-archiver-az-a --replicas=0
```

Wait for the standby to catch up (lag → 0) before declaring recovered.

## Step 3 — broker failure

If brokers are down:

1. Do **not** restart the whole cluster. Identify the failed broker IDs
   from CloudWatch.
2. If quorum is preserved (≥ 5 of 9), simply replace the failed nodes via
   the standard MSK replace-broker runbook.
3. If quorum is lost — escalate immediately. Re-mirror from the archive
   cluster is a multi-hour operation; the city will run on local pod
   safety overrides in the meantime.

## Step 4 — post-incident

- File an incident issue in this repo with the `incident` and
  `safety-critical` labels.
- Link the Jira ticket created in CityOps' rotation.
- Schedule a blameless review within 5 working days.

## Related

- [docs/architecture.md §4](../architecture.md) — isolation model
- `infra/kafka.tf` — `aws_msk_cluster.safety_critical`
