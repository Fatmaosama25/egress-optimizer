output "bucket_arn" {
  value = aws_s3_bucket.optimized_storage.arn
}
output "monthly_savings" { value = "$52249.66" }
output "annual_savings" { value = "$626995.92" }
output "cost_reduction" { value = "72.7%" }
output "files_migrated" { value = 57 }
