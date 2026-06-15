################################################################################
# Kafka (Amazon MSK)
#
# Two clusters:
#   - "general"            — HVAC raw/normalized/alerts, pod telemetry
#   - "safety_critical"    — fire/life-safety, lift overrides (KAN-28)
#
# Safety-critical MUST live on its own cluster with 5x replication, dedicated
# brokers, and cross-AZ replication. Do not co-mingle topics.
################################################################################

resource "aws_msk_cluster" "general" {
  cluster_name           = "the-line-${terraform.workspace}-general"
  kafka_version          = "3.6.0"
  number_of_broker_nodes = 9

  broker_node_group_info {
    instance_type   = local.is_prod ? "kafka.m7g.xlarge" : "kafka.m7g.large"
    client_subnets  = aws_subnet.private[*].id
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = 1000
      }
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  open_monitoring {
    prometheus {
      jmx_exporter  { enabled_in_broker = true }
      node_exporter { enabled_in_broker = true }
    }
  }
}

# KAN-28: safety-critical cluster, isolated.
resource "aws_msk_cluster" "safety_critical" {
  cluster_name           = "the-line-${terraform.workspace}-safety"
  kafka_version          = "3.6.0"
  number_of_broker_nodes = 9

  broker_node_group_info {
    instance_type   = "kafka.m7g.2xlarge"
    client_subnets  = aws_subnet.private[*].id
    security_groups = [aws_security_group.msk_safety.id]

    storage_info {
      ebs_storage_info {
        volume_size = 2000
      }
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.safety.arn
    revision = aws_msk_configuration.safety.latest_revision
  }
}

resource "aws_msk_configuration" "safety" {
  name           = "the-line-safety-critical"
  kafka_versions = ["3.6.0"]

  server_properties = <<EOT
auto.create.topics.enable=false
default.replication.factor=5
min.insync.replicas=3
unclean.leader.election.enable=false
EOT
}

resource "aws_security_group" "msk"        { name = "msk-general-${terraform.workspace}"; vpc_id = aws_vpc.main.id }
resource "aws_security_group" "msk_safety" { name = "msk-safety-${terraform.workspace}";  vpc_id = aws_vpc.main.id }

output "msk_general_bootstrap"  { value = aws_msk_cluster.general.bootstrap_brokers_tls }
output "msk_safety_bootstrap"   { value = aws_msk_cluster.safety_critical.bootstrap_brokers_tls }
