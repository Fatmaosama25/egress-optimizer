output "bucket_arn" {
  value = aws_s3_bucket.optimized_storage.arn
}
output "monthly_savings" { value = "$6772.77" }
output "annual_savings" { value = "$81273.24" }
output "cost_reduction" { value = "65.6%" }
output "files_migrated" { value = 21 }
