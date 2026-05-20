resource "aws_s3_bucket_lifecycle_configuration" "optimized_storage" {
  bucket = aws_s3_bucket.optimized_storage.id
  rule {
    id = "cold-to-ia"; status = "Enabled"
    filter { prefix = "cold/" }
    transition { days = var.cold_transition_days; storage_class = "STANDARD_IA" }
  }
  rule {
    id = "archive-to-glacier"; status = var.enable_glacier_transition ? "Enabled" : "Disabled"
    filter { prefix = "archive/" }
    transition { days = var.archive_transition_days; storage_class = "GLACIER" }
  }
  rule {
    id = "cleanup-uploads"; status = "Enabled"
    filter { prefix = "" }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}
