# infrastructure/terraform/main.tf
#
# Root module entry point for FindMyRent infrastructure.
#
# Resources are organised across dedicated files:
#   backend.tf          — S3 remote state + provider config
#   variables.tf        — Input variables
#   vpc.tf              — VPC, subnets, IGW, route tables
#   security_groups.tf  — Firewall rules
#   ec2_combined.tf     — EC2 instance + Elastic IP
#   outputs.tf          — Output values
#
# No resources are defined in this file.