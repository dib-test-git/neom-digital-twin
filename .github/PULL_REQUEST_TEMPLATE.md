<!--
Thanks for the PR. The Line is safety-critical infrastructure — please be
thorough. CI must be green and CODEOWNERS must approve before merge.
-->

## Summary

<!-- One or two sentences: what does this change and why? -->

## Jira

<!-- e.g. KAN-24, KAN-49 -->
Refs:

## Type of change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would change existing behavior)
- [ ] Infrastructure / IaC change
- [ ] Documentation only
- [ ] Touches a **safety-critical** stream or runbook (requires extra reviewer)

## Test plan

<!-- How was this validated? Include commands, replay traces, screenshots. -->

- [ ] Unit tests added/updated
- [ ] Integration tests pass against local Kafka/Flink
- [ ] Replayed against module trace `traces/module-XX-YYYYMMDD.parquet`
- [ ] Operator console smoke-tested at >=200 floors

## Risk / rollout

- Blast radius:
- Rollback plan:
- Feature flag:

## Reviewer checklist

- [ ] CODEOWNERS approval present
- [ ] No new dependencies pulled in without security review
- [ ] Metrics + log lines added for new code paths
- [ ] Runbook updated if alerting changed
