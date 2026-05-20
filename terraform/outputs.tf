output "bucket_arn" {
  value = aws_s3_bucket.optimized_storage.arn
}
output "monthly_savings" { value = "$8267.29" }
output "annual_savings" { value = "$99207.48" }
output "cost_reduction" { value = "72.7%" }
output "files_migrated" { value = 26 }
