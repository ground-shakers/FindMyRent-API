variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "app_name" {
  description = "Application name used for resource naming"
  type        = string
  default     = "findmyrent"
}

variable "domain_name" {
  description = "Domain name for the API (HTTPS via Let's Encrypt)"
  type        = string
  default     = "ground-shakers.xyz"
}

variable "instance_type" {
  description = "EC2 instance type for the combined app + Jenkins server"
  type        = string
  default     = "t3.medium"  # 2 vCPU, 4 GB RAM — enough for app + Jenkins
}

variable "ssh_key_name" {
  description = "Name of the AWS EC2 key pair for SSH access"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH into instances (your IP — or 0.0.0.0/0 if you rotate networks)"
  type        = string
  default     = "0.0.0.0/0"  # SSH key is the real gate; CIDR is defence-in-depth
}

variable "ami_id" {
  description = "AMI ID for Ubuntu 22.04 LTS in your region"
  type        = string
  default     = "ami-0c7217cdde317cfec"  # Ubuntu 22.04 LTS us-east-1
}

variable "mongodb_atlas_cidr" {
  description = "MongoDB Atlas cluster CIDR (for potential VPC peering — not used with IP whitelist)"
  type        = string
  default     = ""
}