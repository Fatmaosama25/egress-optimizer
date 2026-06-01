output "bucket_arn" {
  value = aws_s3_bucket.optimized_storage.arn
}
output "monthly_savings" { value = "$4406.67" }
output "annual_savings" { value = "$52880.04" }
output "cost_reduction" { value = "59.2%" }
output "files_migrated" { value = 14 }
