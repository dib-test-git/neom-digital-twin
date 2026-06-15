# infra/

Terraform for the cloud side of the digital-twin platform. Deployed into
two NEOM AWS accounts (prod-edge / prod-cloud) per the safety-critical
split described in [docs/architecture.md](../docs/architecture.md).

## Modules

| File | What |
| --- | --- |
| `main.tf` | Provider config, backend, root composition |
| `kafka.tf` | MSK clusters — one general-purpose, one for safety-critical (KAN-28) |
| `kinesis.tf` | Kinesis Data Firehose for long-term archive to S3/Iceberg |
| `iam.tf` | Roles for Flink, anomaly-detection, pod-adapter |
| `network.tf` | VPC + multi-AZ subnets, transit-gateway attachments |
| `flink/` | EMR-on-EKS Flink cluster + submitter script |

## Common ops

```bash
terraform init
terraform workspace select prod-cloud
terraform plan -out tf.plan
terraform apply tf.plan
```

Apply is gated by CODEOWNERS in `.github/CODEOWNERS` — any change touching
`/infra/` requires sign-off from **@neom-platform-data** AND
**@neom-cityops-leads** because the BMS/safety streams flow through here.
