################################################################################
# Kinesis Data Firehose — long-term archive of all telemetry to S3/Iceberg.
################################################################################

resource "aws_s3_bucket" "telemetry_archive" {
  bucket = "neom-the-line-telemetry-${terraform.workspace}"
}

resource "aws_s3_bucket_versioning" "telemetry_archive" {
  bucket = aws_s3_bucket.telemetry_archive.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_kinesis_firehose_delivery_stream" "hvac_normalized" {
  name        = "the-line-hvac-normalized-${terraform.workspace}"
  destination = "extended_s3"

  extended_s3_configuration {
    bucket_arn         = aws_s3_bucket.telemetry_archive.arn
    role_arn           = aws_iam_role.firehose.arn
    prefix             = "hvac_normalized/dt=!{timestamp:yyyy-MM-dd}/hr=!{timestamp:HH}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/"
    buffering_interval = 60
    buffering_size     = 64
    compression_format = "GZIP"

    data_format_conversion_configuration {
      input_format_configuration  { deserializer { open_x_json_ser_de {} } }
      output_format_configuration { serializer   { parquet_ser_de    {} } }
      schema_configuration {
        database_name = "the_line"
        table_name    = "hvac_normalized"
        role_arn      = aws_iam_role.firehose.arn
      }
    }
  }
}

resource "aws_iam_role" "firehose" {
  name = "the-line-firehose-${terraform.workspace}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "firehose.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}
