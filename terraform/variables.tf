variable "aws_region" {
  description = "AWS region"; type = string; default = "us-east-1"
}
variable "bucket_name" {
  description = "S3 bucket name"; type = string; default = "egress-optimized-storage"
}
variable "environment" {
  description = "Environment"; type = string; default = "dev"
}
variable "enable_glacier_transition" {
  description = "Enable Glacier"; type = bool; default = true
}
variable "cold_transition_days" {
  description = "Days to IA"; type = number; default = 30
}
variable "archive_transition_days" {
  description = "Days to Glacier"; type = number; default = 90
}
