# Terraform & Jenkins Integration Guide

> **Context:** FindMyRent API is a FastAPI application currently using **GitHub Actions** for CI/CD,
> deployed to an **AWS EC2** instance as a **Docker container**, backed by **MongoDB Atlas** (cloud-hosted)
> and **Redis** (local). This guide integrates **Terraform** (infrastructure-as-code) and **Jenkins** (self-hosted CI/CD)
> into that existing workflow.
>
> **Cost-saving design:** Jenkins runs **on the same EC2 instance** as the application, eliminating the
> need for a separate server. MongoDB is hosted on **MongoDB Atlas**, so no database runs on EC2.
>
> **Security design:** Jenkins is **never exposed to the public internet**. Port 8080 is closed in the
> security group; you access the Jenkins UI via an **SSH tunnel**. GitHub webhooks reach Jenkins through
> an **nginx reverse proxy** on port 443 (`/github-webhook/`). The API is served over **HTTPS** on
> `ground-shakers.xyz` using Let's Encrypt.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Why Terraform + Jenkins](#2-why-terraform--jenkins)
3. [Prerequisites](#3-prerequisites)
4. [Phase 1 — Terraform: Provision Infrastructure](#4-phase-1--terraform-provision-infrastructure)
   - [Directory Structure](#41-directory-structure)
   - [S3 Backend (Remote State)](#42-s3-backend--dynamodb-state-lock)
   - [Variables](#43-variables)
   - [VPC & Networking](#44-vpc--networking)
   - [Security Groups](#45-security-groups)
   - [EC2: Combined App + Jenkins Server](#46-ec2-combined-app--jenkins-server)
   - [Deploy Script](#461-deploy-script)
   - [Dockerfile](#462-dockerfile)
   - [Outputs](#47-outputs)
   - [Running Terraform](#48-running-terraform)
   - [Initial Server Setup](#49-initial-server-setup-one-time-after-first-apply)
5. [Phase 2 — DNS & HTTPS Setup](#5-phase-2--dns--https-setup)
   - [DNS Configuration](#51-dns-configuration)
   - [Nginx & Let's Encrypt](#52-nginx--lets-encrypt)
   - [Verify HTTPS](#53-verify-https)
6. [Phase 3 — Jenkins: CI/CD Pipeline](#6-phase-3--jenkins-cicd-pipeline)
   - [Accessing Jenkins via SSH Tunnel](#61-accessing-jenkins-via-ssh-tunnel)
   - [Initial Jenkins Setup](#62-initial-jenkins-setup)
   - [Required Jenkins Plugins](#63-required-jenkins-plugins)
   - [Configure Credentials in Jenkins](#64-configure-credentials-in-jenkins)
   - [Configure SMTP for Email Notifications](#65-configure-smtp-for-email-notifications)
   - [Jenkinsfile](#66-jenkinsfile)
   - [Multibranch Pipeline Setup](#67-multibranch-pipeline-setup)
7. [Phase 4 — GitHub Integration](#7-phase-4--github-integration)
   - [GitHub Webhook to Jenkins (via nginx)](#71-github-webhook-to-jenkins-via-nginx)
   - [Updated GitHub Actions (Optional Bridge)](#72-updated-github-actions-optional-bridge)
8. [Secrets Management](#8-secrets-management)
9. [MongoDB Atlas Configuration](#9-mongodb-atlas-configuration)
10. [Rollback Strategy](#10-rollback-strategy)
11. [Resource Sizing & Monitoring](#11-resource-sizing--monitoring)
12. [Full Workflow Diagram](#12-full-workflow-diagram)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Architecture Overview

### Current State

```
Developer → GitHub → GitHub Actions → SSH → EC2 (Docker container)
                                              │
                                              └─→ MongoDB Atlas (cloud)
```

### Target State with Terraform + Jenkins

```
Developer → GitHub
              │
              ├─ Webhook (HTTPS :443) ──► nginx ──► Jenkins (localhost:8080)
              │                                          │
              │                                 ┌────────┴────────┐
              │                             Test & Lint        Build
              │                                 │
              │                            Deploy locally
              │                            (same server)
              │
              └── Terraform ──────► Provision/Update Infrastructure
                  (local or CI)         │
                                   S3 State Backend

Developer ── SSH tunnel (:8080) ──► Jenkins UI (localhost:8080)
```

### Infrastructure Topology (After Terraform)

```
AWS Region (e.g. us-east-1)
└── VPC (10.0.0.0/16)
    └── Public Subnet (10.0.1.0/24)
        └── EC2: Combined Server
             ├── nginx (:443 — HTTPS, :80 — redirect)
             │   ├── ground-shakers.xyz  → proxy to Docker container :8000
             │   └── /github-webhook/    → proxy to Jenkins :8080
             ├── Docker: findmyrent-api (:8000 — via host network)
             ├── Jenkins (:8080 — localhost only, NOT exposed)
             ├── Redis (:6379 — localhost only)
             └──→ MongoDB Atlas (external, cloud-hosted)
```

### Why a Single Server?

Running Jenkins and the application on the same EC2 instance is a practical choice for a solo-developer project:

- **Cost:** Eliminates a second EC2 instance (~$15–30/month saved for a t3.medium).
- **Simplicity:** No SSH-based remote deployments; Jenkins deploys locally via shell commands.
- **Trade-off:** During CI builds (tests, linting), Jenkins will consume CPU/RAM that the app also uses. For a low-traffic API this is acceptable. If traffic grows significantly, split them onto separate instances later.
- **Mitigation:** Schedule heavy builds during off-peak hours, or use Jenkins' "Quiet Period" and "Throttle Concurrent Builds" to limit resource contention.

### Why MongoDB Atlas (Not Self-Hosted)?

- **Zero EC2 overhead:** No MongoDB process competing for server resources; no backup/patching burden.
- **Built-in HA:** Atlas provides replica sets, automated backups, and point-in-time restore out of the box.
- **Free tier available:** Atlas M0 (512 MB) is free forever — sufficient for development and early pilots.
- **Network security:** Atlas supports IP whitelisting and VPC peering. For this guide, the EC2 Elastic IP is whitelisted in Atlas.

### Why SSH Tunnel for Jenkins (Not Port 8080)?

- **No public exposure:** Port 8080 is completely closed in the security group. Jenkins is only reachable on `localhost:8080`.
- **IP-agnostic:** Your public IP can change (different networks, hotspots) — SSH tunnel works regardless as long as you have your SSH key.
- **Encrypted:** All Jenkins traffic travels through the SSH tunnel; no unencrypted HTTP on the wire.
- **GitHub webhooks:** Reach Jenkins via nginx on port 443 (`/github-webhook/` path), so they work without exposing port 8080.

---

## 2. Why Terraform + Jenkins

| Concern | GitHub Actions | Terraform + Jenkins |
|---|---|---|
| Infrastructure changes | Manual / CLI | Version-controlled, reproducible |
| Pipeline visibility | GitHub UI only | Jenkins dashboard, build history |
| Self-hosted runners | Extra cost | Jenkins on your own EC2 |
| Secrets management | GitHub Secrets | Jenkins Credentials Store |
| Parallelism | Limited free tier | Configurable |
| EC2 provisioning | Manual | `terraform apply` |
| Rollback | `git reset` + redeploy | Parameterised build trigger |

---

## 3. Prerequisites

| Tool | Version | Install |
|---|---|---|
| Terraform | >= 1.6 | <https://developer.hashicorp.com/terraform/install> |
| AWS CLI | v2 | `pip install awscli` or binary |
| AWS account | — | IAM user with EC2, VPC, S3, DynamoDB permissions |
| An SSH key pair | — | `ssh-keygen -t ed25519 -f ~/.ssh/findmyrent` |
| MongoDB Atlas account | — | <https://www.mongodb.com/atlas> (free tier works) |
| Domain | — | `ground-shakers.xyz` with DNS access |
| Jenkins | LTS | Installed via Terraform user-data (below) |

Configure AWS CLI:

```bash
aws configure
# AWS Access Key ID: <your key>
# AWS Secret Access Key: <your secret>
# Default region: us-east-1
# Default output format: json
```

---

## 4. Phase 1 — Terraform: Provision Infrastructure

### 4.1 Directory Structure

Add the following to the root of `FindMyRent/`:

```
FindMyRent/
├── Dockerfile                   # Docker image definition for the API
├── infrastructure/
│   ├── terraform/
│   │   ├── main.tf              # Root module entry point
│   │   ├── variables.tf         # Input variables
│   │   ├── outputs.tf           # Output values
│   │   ├── backend.tf           # S3 remote state config
│   │   ├── vpc.tf               # VPC, subnets, IGW, route tables
│   │   ├── security_groups.tf   # Firewall rules
│   │   ├── ec2_combined.tf      # Combined app + Jenkins EC2
│   │   └── user_data/
│   │       └── combined_server.sh  # Bootstrap: Docker + Jenkins + Redis + nginx
│   └── scripts/
│       └── deploy.sh            # Called by Jenkins to build & deploy Docker container
├── Jenkinsfile                  # Jenkins pipeline definition
└── .github/workflows/main.yml   # (kept as optional fallback)
```

> **Note:** No separate `ec2_jenkins.tf` — everything runs on one instance.

**`infrastructure/terraform/main.tf`**

```hcl
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
# No resources are defined in this file. Terraform loads all .tf
# files in this directory automatically.
```

---

### 4.2 S3 Backend + DynamoDB State Lock

**Create these AWS resources once manually (bootstrapping).**

> **Windows note:** The AWS CLI on Windows CMD/PowerShell handles JSON quoting differently
> from Linux/macOS. The steps below use the `file://` approach which works reliably on
> **all platforms** (Windows CMD, PowerShell, Linux, macOS). Each step tells you exactly
> what file to create and what command to run.

Follow these steps **in order** from your terminal. All commands assume you're running
from the same directory where you create the JSON files.

---

**Step 1 — Choose a working directory**

Open your terminal (CMD or PowerShell on Windows) and navigate to a folder where you'll
create temporary JSON files. Your project root works fine:

```cmd
cd C:\path\to\FindMyRent
```

---

**Step 2 — Create the S3 bucket**

No JSON file needed for this one. Run:

```cmd
aws s3api create-bucket --bucket findmyrent-terraform-state --region us-east-1
```

---

**Step 3 — Enable versioning on the bucket**

Create a file called `versioning.json` in your current directory with this content:

```json
{
  "Status": "Enabled"
}
```

On Windows CMD you can create it with:

```cmd
echo {"Status": "Enabled"} > versioning.json
```

Then run:

```cmd
aws s3api put-bucket-versioning --bucket findmyrent-terraform-state --versioning-configuration file://versioning.json
```

---

**Step 4 — Enable server-side encryption**

Create a file called `encryption.json` in your current directory with this content:

```json
{
  "Rules": [
    {
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }
  ]
}
```

On Windows CMD you can create it with:

```cmd
echo {"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]} > encryption.json
```

Then run:

```cmd
aws s3api put-bucket-encryption --bucket findmyrent-terraform-state --server-side-encryption-configuration file://encryption.json
```

---

**Step 5 — Create the DynamoDB state lock table**

Create a file called `dynamodb-attrs.json` in your current directory with this content:

```json
[
  {
    "AttributeName": "LockID",
    "AttributeType": "S"
  }
]
```

On Windows CMD:

```cmd
echo [{"AttributeName": "LockID", "AttributeType": "S"}] > dynamodb-attrs.json
```

Create a second file called `dynamodb-schema.json` with this content:

```json
[
  {
    "AttributeName": "LockID",
    "KeyType": "HASH"
  }
]
```

On Windows CMD:

```cmd
echo [{"AttributeName": "LockID", "KeyType": "HASH"}] > dynamodb-schema.json
```

Then run:

```cmd
aws dynamodb create-table --table-name findmyrent-terraform-locks --attribute-definitions file://dynamodb-attrs.json --key-schema file://dynamodb-schema.json --billing-mode PAY_PER_REQUEST --region us-east-1
```

---

**Step 6 — Clean up temporary files**

The JSON files were only needed for bootstrapping. Delete them:

```cmd
del versioning.json encryption.json dynamodb-attrs.json dynamodb-schema.json
```

(On Linux/macOS: `rm versioning.json encryption.json dynamodb-attrs.json dynamodb-schema.json`)

---

**Verify everything was created:**

```cmd
aws s3api head-bucket --bucket findmyrent-terraform-state
aws dynamodb describe-table --table-name findmyrent-terraform-locks --query "Table.TableStatus"
```

The first command should return no output (success). The second should return `"ACTIVE"`.

**`infrastructure/terraform/backend.tf`**

```hcl
terraform {
  backend "s3" {
    bucket         = "findmyrent-terraform-state"
    key            = "findmyrent/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "findmyrent-terraform-locks"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  required_version = ">= 1.6.0"
}

provider "aws" {
  region = var.aws_region
}
```

---

### 4.3 Variables

**`infrastructure/terraform/variables.tf`**

```hcl
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
```

Create `infrastructure/terraform/terraform.tfvars` **(do not commit this file)**:

```hcl
aws_region   = "us-east-1"
environment  = "production"
ssh_key_name = "findmyrent-key"  # Must match your AWS key pair name
domain_name  = "ground-shakers.xyz"
```

Add to `.gitignore`:

```
infrastructure/terraform/terraform.tfvars
infrastructure/terraform/.terraform/
infrastructure/terraform/*.tfstate
infrastructure/terraform/*.tfstate.backup
infrastructure/terraform/tfplan
infrastructure/terraform/tfplan-destroy
```

---

### 4.4 VPC & Networking

**`infrastructure/terraform/vpc.tf`**

```hcl
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.app_name}-vpc"
    Environment = var.environment
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.app_name}-igw"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.app_name}-public-subnet"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.app_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}
```

> **No private subnet needed.** MongoDB runs on Atlas (external), so there's no database instance to isolate in a private subnet.

---

### 4.5 Security Groups

**`infrastructure/terraform/security_groups.tf`**

```hcl
# Combined App + Jenkins Security Group
resource "aws_security_group" "combined" {
  name        = "${var.app_name}-combined-sg"
  description = "Security group for FindMyRent API + Jenkins (single server)"
  vpc_id      = aws_vpc.main.id

  # HTTPS from anywhere (API traffic + GitHub webhooks)
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP from anywhere (Let's Encrypt validation + redirect to HTTPS)
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH — used for admin access AND Jenkins UI via SSH tunnel
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # ──────────────────────────────────────────────────────────
  # NO port 8080 ingress rule.
  # Jenkins is localhost-only; accessed via SSH tunnel.
  # GitHub webhooks reach Jenkins via nginx on port 443.
  # ──────────────────────────────────────────────────────────

  # All outbound (needed for: Atlas connection, apt, pip, git, Let's Encrypt, etc.)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.app_name}-combined-sg"
  }
}
```

> **Key security decisions:**
>
> - **Port 8080 is NOT open.** Jenkins listens on `localhost:8080` only. You access it via SSH tunnel; GitHub webhooks reach it through nginx on 443.
> - **Port 8000 is NOT open.** The Docker container binds to `127.0.0.1:8000` (via `--network host`); nginx reverse-proxies it on 443.
> - **Port 80 is open** for Let's Encrypt HTTP-01 challenge validation and HTTP→HTTPS redirect.
> - **Port 22** is the only admin port. The SSH key is the primary authentication gate.

---

### 4.6 EC2: Combined App + Jenkins Server

**`infrastructure/terraform/user_data/combined_server.sh`**

```bash
#!/bin/bash
set -e

# ============================================================
# Update system
# ============================================================
apt-get update -y
apt-get upgrade -y

# ============================================================
# Install Docker
# ============================================================
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

systemctl enable docker
systemctl start docker

# ============================================================
# Install Python 3.13 (needed by Jenkins for test/lint stages)
# ============================================================
apt-get install -y software-properties-common
add-apt-repository ppa:deadsnakes/ppa -y
apt-get update -y
apt-get install -y python3.13 python3.13-venv python3.13-dev python3-pip

# ============================================================
# Install Redis (local caching only — MongoDB is on Atlas)
# ============================================================
apt-get install -y redis-server
systemctl enable redis-server
systemctl start redis-server

# ============================================================
# Install git, nginx, curl, certbot
# ============================================================
apt-get install -y git nginx curl certbot python3-certbot-nginx

# ============================================================
# Install Java (required for Jenkins)
# ============================================================
apt-get install -y fontconfig openjdk-21-jdk

# ============================================================
# Install Jenkins
# NOTE: The jenkins.io-2023.key file does NOT match the key
# Jenkins actually signs their repo with (7198F4B714ABFC68).
# We fetch the real key from Ubuntu's keyserver and convert it
# to the binary format apt expects.
# ============================================================
apt-get install -y gnupg

# Step 1: Import the actual signing key into a temporary keyring
apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 7198F4B714ABFC68

# Step 2: Export it to the file that signed-by will reference
apt-key export 14ABFC68 | gpg --dearmor -o /usr/share/keyrings/jenkins-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.gpg] \
  https://pkg.jenkins.io/debian binary/" | \
  tee /etc/apt/sources.list.d/jenkins.list > /dev/null

apt-get update -y
apt-get install -y jenkins

# ============================================================
# Lock Jenkins to localhost only (no public access)
# ============================================================
sed -i 's/^HTTP_HOST=.*/HTTP_HOST=127.0.0.1/' /etc/default/jenkins 2>/dev/null || true

# For Jenkins installed via systemd override:
mkdir -p /etc/systemd/system/jenkins.service.d
cat > /etc/systemd/system/jenkins.service.d/override.conf <<'EOF'
[Service]
Environment="JENKINS_LISTEN_ADDRESS=127.0.0.1"
EOF

systemctl daemon-reload
systemctl enable jenkins
systemctl start jenkins

# ============================================================
# Create app directory and .env location
# ============================================================
useradd -m -s /bin/bash ubuntu || true
mkdir -p /home/ubuntu/FindMyRent-API
chown -R ubuntu:ubuntu /home/ubuntu/FindMyRent-API

# Make /home/ubuntu traversable by the jenkins user (needed for deploy.sh)
chmod 755 /home/ubuntu

# ============================================================
# Add jenkins and ubuntu users to docker group
# Jenkins also needs to be in the ubuntu group for deploy access
# ============================================================
usermod -aG docker jenkins
usermod -aG docker ubuntu
usermod -aG ubuntu jenkins

# Allow jenkins to manage Docker containers without sudo
cat > /etc/sudoers.d/jenkins-deploy <<'EOF'
jenkins ALL=(ALL) NOPASSWD: /usr/bin/docker *
EOF

# ============================================================
# Configure nginx — write directly into 'default' site config
# IMPORTANT: We overwrite the default config rather than
# creating a separate file, because certbot --nginx modifies
# the config it finds. Writing to a separate file causes
# certbot to modify 'default' instead, leaving the proxy
# rules missing and webhooks/API returning 404.
# ============================================================
cat > /etc/nginx/sites-available/default <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ground-shakers.xyz;

    # Let's Encrypt validation
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # API reverse proxy (HTTP — will be upgraded to HTTPS by certbot)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # GitHub webhook → Jenkins (proxied locally)
    location /github-webhook/ {
        proxy_pass http://127.0.0.1:8080/github-webhook/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

nginx -t && systemctl reload nginx

echo "Combined server bootstrap complete"
echo "Jenkins initial admin password:"
cat /var/lib/jenkins/secrets/initialAdminPassword 2>/dev/null || echo "(not yet available — check after Jenkins starts)"
echo ""
echo "NEXT STEPS:"
echo "  1. Point ground-shakers.xyz DNS A record to this server's Elastic IP"
echo "  2. Run: sudo certbot --nginx -d ground-shakers.xyz"
echo "  3. Access Jenkins via: ssh -L 8080:localhost:8080 ubuntu@<SERVER_IP>"
```

**`infrastructure/terraform/ec2_combined.tf`**

```hcl
resource "aws_instance" "combined" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.ssh_key_name
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.combined.id]

  user_data = file("${path.module}/user_data/combined_server.sh")

  root_block_device {
    volume_size = 30   # Extra space for Jenkins build artifacts + app
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name        = "${var.app_name}-combined-server"
    Environment = var.environment
    Role        = "app+jenkins"
  }
}

resource "aws_eip" "combined" {
  instance = aws_instance.combined.id
  domain   = "vpc"

  tags = {
    Name = "${var.app_name}-eip"
  }
}
```

### 4.6.1 Deploy Script

**`infrastructure/scripts/deploy.sh`**

This script builds a Docker image from the latest code and replaces the running container. It can also be run manually over SSH for ad-hoc deployments outside of the pipeline.

```bash
#!/bin/bash
# infrastructure/scripts/deploy.sh
# Called by Jenkins (Deploy stage) or manually via SSH.
# Usage: ./infrastructure/scripts/deploy.sh [git-commit-sha]
set -e

APP_DIR="/home/ubuntu/FindMyRent-API"
CONTAINER_NAME="findmyrent-api"
IMAGE_NAME="findmyrent-api"
ENV_FILE="/home/ubuntu/.env"
HEALTH_URL="http://localhost:8000/health"
FALLBACK_URL="http://localhost:8000/"

# Use provided commit SHA or default to latest master
COMMIT="${1:-latest}"

echo "==> Pulling latest code..."
cd "$APP_DIR"
git fetch origin master
git reset --hard origin/master

echo "==> Building Docker image (tag: ${COMMIT})..."
docker build -t "${IMAGE_NAME}:${COMMIT}" .
docker tag "${IMAGE_NAME}:${COMMIT}" "${IMAGE_NAME}:latest"

echo "==> Stopping old container..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

echo "==> Starting new container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --env-file "$ENV_FILE" \
    --network host \
    "${IMAGE_NAME}:latest"

echo "==> Waiting for container to stabilise..."
sleep 5

echo "==> Health check..."
curl -sf "$HEALTH_URL" \
    || curl -sf "$FALLBACK_URL" \
    || (echo "Health check failed! Rolling back..." && \
        docker stop "$CONTAINER_NAME" && \
        docker rm "$CONTAINER_NAME" && \
        echo "Container stopped. Check logs: docker logs ${CONTAINER_NAME}" && \
        exit 1)

echo "==> Pruning old images..."
docker image prune -f

echo "==> Deployment successful!"
echo "==> Live at: https://ground-shakers.xyz"
```

Make it executable in the repo:

```bash
chmod +x infrastructure/scripts/deploy.sh
git add infrastructure/scripts/deploy.sh
git commit -m "Add Docker deploy script"
```

> **Two ways to use this script:**
>
> 1. **Via Jenkins:** The Jenkinsfile's Deploy stage calls `sh './infrastructure/scripts/deploy.sh'` — one clean line.
> 2. **Manually:** SSH into the server and run `./infrastructure/scripts/deploy.sh` if you ever need to deploy without Jenkins (e.g. Jenkins is down, or a quick hotfix).

> **Note:** `--network host` is used so the container can reach Redis on `localhost:6379` and is reachable by nginx on `localhost:8000`. The Atlas connection goes outbound over the internet regardless.

---

### 4.6.2 Dockerfile

**`Dockerfile`** (in the project root):

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (cached layer — only rebuilds when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# Bind to 127.0.0.1 — only nginx (on the same host) can reach the API
CMD ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "2"]
```

> **Why `--host 127.0.0.1`?** With `--network host`, the container shares the host's network stack.
> Binding to `127.0.0.1` means the API is only reachable from the same machine (i.e. nginx).
> External traffic arrives via nginx on port 443 (HTTPS).

---

### 4.7 Outputs

**`infrastructure/terraform/outputs.tf`**

```hcl
output "server_public_ip" {
  description = "Public IP of the combined app + Jenkins server"
  value       = aws_eip.combined.public_ip
}

output "dns_instructions" {
  description = "DNS setup instructions"
  value       = "Point A record for ${var.domain_name} to ${aws_eip.combined.public_ip}"
}

output "app_url" {
  description = "FindMyRent API URL (after HTTPS setup)"
  value       = "https://${var.domain_name}"
}

output "jenkins_tunnel_command" {
  description = "SSH tunnel command to access Jenkins UI"
  value       = "ssh -i ~/.ssh/findmyrent -L 8080:localhost:8080 ubuntu@${aws_eip.combined.public_ip}"
}

output "jenkins_url" {
  description = "Jenkins URL (only accessible via SSH tunnel)"
  value       = "http://localhost:8080  (requires SSH tunnel — see jenkins_tunnel_command)"
}

output "ssh_command" {
  description = "SSH command to connect to server"
  value       = "ssh -i ~/.ssh/findmyrent ubuntu@${aws_eip.combined.public_ip}"
}

output "atlas_whitelist_ip" {
  description = "Add this IP to MongoDB Atlas Network Access whitelist"
  value       = aws_eip.combined.public_ip
}
```

---

### 4.8 Running Terraform

```bash
cd infrastructure/terraform

# Initialise (downloads providers, connects to S3 backend)
terraform init

# Preview what will be created and save the plan to a file
terraform plan -var-file="terraform.tfvars" -out="tfplan"

# Apply the saved plan (guarantees exactly what was previewed gets applied)
terraform apply "tfplan"

# After apply, note the outputs:
terraform output

# IMPORTANT: Copy the atlas_whitelist_ip value and add it
# to MongoDB Atlas → Network Access → IP Access List
```

> **Why `-out="tfplan"`?** Without it, `terraform plan` only prints to screen, and a
> subsequent `terraform apply` re-calculates the plan from scratch — which could differ
> if anything changed in between (e.g. a new provider version, a resource modified outside
> Terraform). Saving the plan to a file and passing it to `apply` guarantees you get
> exactly the changes you reviewed.
>
> The `tfplan` file is binary and environment-specific — do not commit it. Add it to `.gitignore`:
>
> ```
> infrastructure/terraform/tfplan
> ```

**To destroy all infrastructure:**

```bash
terraform plan -var-file="terraform.tfvars" -destroy -out="tfplan-destroy"
terraform apply "tfplan-destroy"
```

---

### 4.9 Initial Server Setup (One-Time, After First Apply)

After `terraform apply` completes and the EC2 instance is running, SSH in and perform these
one-time setup steps. The user-data script installs all software, but it cannot clone your
private repo or create your `.env` file — those require your credentials.

**Step 1 — SSH into the server:**

```bash
# Use the SSH command from terraform output
ssh -i ~/.ssh/findmyrent ubuntu@<SERVER_IP>
```

**Step 2 — Wait for user-data to finish (first boot only):**

```bash
# Check if cloud-init has completed
cloud-init status
# Should say: "status: done"

# If it says "status: running", wait and check again in a minute.
# You can watch the log live:
tail -f /var/log/cloud-init-output.log
```

**Step 3 — Clone the repository:**

```bash
# Clone your repo into the deploy directory
git clone https://github.com/ground-shakers/FindMyRent-API.git /home/ubuntu/FindMyRent-API
```

> If your repo is private, you'll need to authenticate. Options:
>
> - Use an HTTPS URL with a GitHub PAT: `git clone https://<PAT>@github.com/ground-shakers/FindMyRent-API.git /home/ubuntu/FindMyRent-API`
> - Or set up an SSH key for the `ubuntu` user and use the SSH URL.

**Step 4 — Create the `.env` file:**

```bash
nano /home/ubuntu/.env
```

Paste your environment variables:

```bash
# MongoDB Atlas
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/findmyrent?retryWrites=true&w=majority

# Redis (local — accessible via localhost because of --network host)
REDIS_URL=redis://localhost:6379

# Application secrets
SECRET_KEY=<your-secret-key>
# ... other env vars your app needs
```

Save and exit (`Ctrl+X`, `Y`, `Enter` in nano).

**Step 5 — Verify Docker is running:**

```bash
docker --version
# Should show: Docker version 2x.x.x

sudo systemctl status docker
# Should show: active (running)
```

**Step 6 — Verify Jenkins is running:**

```bash
sudo systemctl status jenkins
# Should show: active (running)

sudo ss -tlnp | grep 8080
# Should show: 127.0.0.1:8080
```

> After these steps, the server is ready for Jenkins to deploy to. The first successful
> Jenkins build will run `deploy.sh`, which builds the Docker image from the cloned repo,
> starts the container, and makes the API live at `https://ground-shakers.xyz`.

---

## 5. Phase 2 — DNS & HTTPS Setup

This phase must happen **after** `terraform apply` (you need the Elastic IP) and **before** Jenkins setup (so the webhook URL is ready).

### 5.1 DNS Configuration

1. Get your server's Elastic IP:

   ```bash
   terraform output server_public_ip
   ```

2. Go to your DNS provider for `ground-shakers.xyz` and create an **A record**:

   | Type | Name | Value | TTL |
   |---|---|---|---|
   | A | `@` (or `ground-shakers.xyz`) | `<Elastic IP from step 1>` | 300 |

3. Wait for DNS propagation (usually 1–5 minutes with a low TTL):

   ```bash
   # Verify DNS is pointing correctly
   dig ground-shakers.xyz +short
   # Should return your Elastic IP
   ```

### 5.2 Nginx & Let's Encrypt

SSH into the server and run Certbot to obtain a free TLS certificate:

```bash
ssh -i ~/.ssh/findmyrent ubuntu@<SERVER_IP>

# Run certbot — it will auto-modify the nginx config for HTTPS
sudo certbot --nginx -d ground-shakers.xyz \
  --non-interactive \
  --agree-tos \
  --email dev@ground-shakers.xyz \
  --redirect
```

Certbot will:

- Obtain a Let's Encrypt certificate for `ground-shakers.xyz`.
- Modify `/etc/nginx/sites-available/default` to add a `listen 443 ssl` block with certificate paths.
- Add an automatic HTTP→HTTPS redirect on port 80.
- Set up auto-renewal via a systemd timer (certificates renew automatically every ~60 days).

> **Why we use the `default` config file:** Certbot's `--nginx` plugin scans for `server_name`
> directives in nginx configs. If you write proxy rules in a separate file (e.g. `findmyrent`)
> but certbot modifies `default`, your proxy rules are lost and the API / webhooks return 404.
> Writing everything into `default` ensures certbot modifies the file that already has the
> proxy rules.

After certbot runs, the nginx config will look approximately like this (certbot modifies it automatically):

```nginx
# /etc/nginx/sites-available/default (after certbot)
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ground-shakers.xyz;

    # Certbot adds: redirect to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name ground-shakers.xyz;

    # Certbot adds these certificate paths
    ssl_certificate /etc/letsencrypt/live/ground-shakers.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ground-shakers.xyz/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # API reverse proxy (preserved from original config)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # GitHub webhook → Jenkins (preserved from original config)
    location /github-webhook/ {
        proxy_pass http://127.0.0.1:8080/github-webhook/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

> **Verify certbot auto-renewal is set up:**
>
> ```bash
> sudo systemctl list-timers | grep certbot
> # Should show: certbot.timer — runs twice daily
>
> # Test renewal (dry run):
> sudo certbot renew --dry-run
> ```

### 5.3 Verify HTTPS

```bash
# From your local machine:
curl -I https://ground-shakers.xyz
# Should return: HTTP/2 200 (or the health check response)

# Verify HTTP redirects to HTTPS:
curl -I http://ground-shakers.xyz
# Should return: HTTP/1.1 301 Moved Permanently → https://ground-shakers.xyz
```

---

## 6. Phase 3 — Jenkins: CI/CD Pipeline

### 6.1 Accessing Jenkins via SSH Tunnel

Jenkins is **not accessible from the internet**. Port 8080 is closed and Jenkins only listens on `127.0.0.1`. To access the Jenkins web UI, open an SSH tunnel:

```bash
# Open the tunnel (keep this terminal open while using Jenkins)
ssh -i ~/.ssh/findmyrent -L 8080:localhost:8080 ubuntu@<SERVER_IP>
```

Then open **<http://localhost:8080>** in your browser. All Jenkins traffic flows encrypted through the SSH tunnel.

**Convenience aliases** — add to your `~/.bashrc` or `~/.zshrc`:

```bash
alias fmr-ssh="ssh -i ~/.ssh/findmyrent ubuntu@<SERVER_IP>"
alias fmr-jenkins="ssh -i ~/.ssh/findmyrent -L 8080:localhost:8080 ubuntu@<SERVER_IP>"
```

> **Why this works regardless of your IP:** The SSH tunnel connects from your machine through port 22 to the server. Your public IP doesn't matter — only your SSH private key authenticates you. Switch networks, use coffee-shop Wi-Fi, tether from your phone — it all works the same.

---

### 6.2 Initial Jenkins Setup

After `terraform apply`, Jenkins is auto-installed via `user_data`. Get the initial admin password:

```bash
# Open the SSH tunnel
ssh -i ~/.ssh/findmyrent -L 8080:localhost:8080 ubuntu@<SERVER_IP>

# In that same SSH session, get the password:
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

1. Open **<http://localhost:8080>** in your browser (tunnel must be active)
2. Enter the initial admin password
3. Choose **"Install suggested plugins"**
4. Create your admin user
5. Set Jenkins URL to **`http://localhost:8080`**

> **Important:** Set the Jenkins URL to `http://localhost:8080` (not the server's public IP). Jenkins will never be accessed via a public URL.

---

### 6.3 Required Jenkins Plugins

Install these via **Manage Jenkins → Plugins → Available plugins**:

| Plugin | Purpose |
|---|---|
| **Pipeline** | Declarative pipeline support (`Jenkinsfile`) |
| **Git** | GitHub repository checkout |
| **GitHub Integration** | Webhook trigger from GitHub |
| **Credentials Binding** | Bind secrets to environment variables |
| **Email Extension** | Email notifications (matches GitHub Actions emails) |
| **AnsiColor** | Colourised console output |
| **Blue Ocean** | Modern pipeline UI (optional but recommended) |
| **Workspace Cleanup** | Clean workspace before builds |

> **Note:** `SSH Agent` plugin is **not required** — Jenkins deploys locally, not over SSH.

---

### 6.4 Configure Credentials in Jenkins

Go to **Manage Jenkins → Credentials → System → Global credentials → Add Credential**:

| ID | Type | Value | Used For |
|---|---|---|---|
| `github-pat` | Username with password | GitHub username + Personal Access Token | Repo checkout + branch scanning |
| `mongodb-atlas-uri` | Secret text | `mongodb+srv://user:pass@cluster.mongodb.net/findmyrent` | Test stage (if tests need DB) |
| `mail-to` | Secret text | Your recipient email | Email notifications |
| `mail-from` | Secret text | `dev@ground-shakers.xyz` | Email sender |
| `github-webhook-secret` | Secret text | Random string (same as webhook config) | Webhook validation |

> **Note:** SMTP credentials (`mail-username`, `mail-password`) are configured globally in Jenkins
> (see [Section 6.5](#65-configure-smtp-for-email-notifications)), not as pipeline credentials.
> The `to` and `from` fields use `env.MAIL_TO` and `env.MAIL_FROM` in the Jenkinsfile —
> `withCredentials` sets them as environment variables, and `env.VARIABLE` reads them without
> Groovy GString interpolation (avoiding the secret exposure warning).

---

### 6.5 Configure SMTP for Email Notifications

The `emailext` plugin does **not** support `smtpHost` or `smtpPort` as inline parameters in the Jenkinsfile — SMTP must be configured globally in Jenkins settings.

1. Open Jenkins via SSH tunnel (`http://localhost:8080`)
2. Go to **Manage Jenkins → System**
3. Scroll down to **Extended E-mail Notification** and configure:
   - **SMTP server:** `smtp-relay.brevo.com`
   - **SMTP port:** `587`
   - **Credentials:** click **Add** → select **Jenkins**, then:
     - Kind: **Username with password**
     - Username: `985dc4001@smtp-brevo.com` (your Brevo SMTP login)
     - Password: your Brevo SMTP password
     - ID: `brevo-smtp`
   - Select the `brevo-smtp` credential from the dropdown
   - **Use TLS:** tick the checkbox
4. Optionally scroll to **Default Recipients** and enter your email
5. Click **Save**

> **Why not in the Jenkinsfile?** Jenkins' `emailext` step reads SMTP settings from the global
> config. Passing `smtpHost` or `smtpPort` in the Jenkinsfile causes a compilation error:
> `Invalid parameter "smtpHost"`. The Jenkinsfile only specifies `to`, `from`, `subject`, and `body`.

---

### 6.6 Jenkinsfile

**File to create/update:** `Jenkinsfile` (in the root of `FindMyRent/`)

Create `Jenkinsfile` in the root of `FindMyRent/`:

```groovy
pipeline {
    agent any

    options {
        ansiColor('xterm')
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    environment {
        PYTHON_VERSION  = '3.13'
        APP_NAME        = 'FindMyRent-API'
        APP_DIR         = '/home/ubuntu/FindMyRent-API'
        CONTAINER_NAME  = 'findmyrent-api'
        APP_URL         = 'https://ground-shakers.xyz'
    }

    stages {

        // ─────────────────────────────────────────────────
        // STAGE 1: Checkout
        // ─────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                cleanWs()
                checkout scm
                echo "Branch: ${env.BRANCH_NAME} | Commit: ${env.GIT_COMMIT[0..7]}"
            }
        }

        // ─────────────────────────────────────────────────
        // STAGE 2: Install Dependencies
        // ─────────────────────────────────────────────────
        stage('Install Dependencies') {
            steps {
                sh '''
                    python3.13 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install pytest pytest-cov pytest-asyncio httpx flake8
                '''
            }
        }

        // ─────────────────────────────────────────────────
        // STAGE 3: Lint
        // ─────────────────────────────────────────────────
        stage('Lint') {
            steps {
                sh '''
                    . venv/bin/activate
                    echo "Running critical linting checks..."
                    flake8 . --exclude=venv --count --select=E9,F63,F7,F82 --show-source --statistics

                    echo "Running style checks (non-blocking)..."
                    flake8 . --exclude=venv --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
                '''
            }
        }

        // ─────────────────────────────────────────────────
        // STAGE 4: Tests
        // ─────────────────────────────────────────────────
        stage('Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    pytest tests/ -v \
                        --cov=. \
                        --cov-report=xml \
                        --cov-report=html \
                        --cov-fail-under=0 \
                        --junit-xml=test-results.xml
                '''
            }
            post {
                always {
                    junit 'test-results.xml'
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
            }
        }

        // ─────────────────────────────────────────────────
        // STAGE 5: Deploy  (master branch only)
        // LOCAL deployment — no SSH needed
        // ─────────────────────────────────────────────────
        stage('Deploy') {
            when {
                branch 'master'
            }
            steps {
                sh 'chmod +x ./infrastructure/scripts/deploy.sh'
                sh './infrastructure/scripts/deploy.sh'
            }
        }

    } // end stages

    // ─────────────────────────────────────────────────
    // POST: Notifications
    // MAIL_TO and MAIL_FROM are set in the environment
    // block or read via withCredentials + env.VARIABLE
    // ─────────────────────────────────────────────────
    post {
        success {
            script {
                if (env.BRANCH_NAME == 'master') {
                    withCredentials([
                        string(credentialsId: 'mail-to',   variable: 'MAIL_TO'),
                        string(credentialsId: 'mail-from', variable: 'MAIL_FROM')
                    ]) {
                        emailext(
                            subject: "✅ Deployment Successful — ${env.APP_NAME} #${env.BUILD_NUMBER}",
                            to: env.MAIL_TO,
                            from: env.MAIL_FROM,
                            body: """
Deployment completed successfully!

Application : ${env.APP_NAME}
Branch      : ${env.BRANCH_NAME}
Commit      : ${env.GIT_COMMIT}
Build #     : ${env.BUILD_NUMBER}
App URL     : https://ground-shakers.xyz

Jenkins build: ${env.BUILD_URL}
                            """.stripIndent()
                        )
                    }
                }
            }
        }

        failure {
            withCredentials([
                string(credentialsId: 'mail-to',   variable: 'MAIL_TO'),
                string(credentialsId: 'mail-from', variable: 'MAIL_FROM')
            ]) {
                emailext(
                    subject: "❌ Build Failed — ${env.APP_NAME} #${env.BUILD_NUMBER}",
                    to: env.MAIL_TO,
                    from: env.MAIL_FROM,
                    body: """
Build or deployment FAILED.

Application : ${env.APP_NAME}
Branch      : ${env.BRANCH_NAME}
Commit      : ${env.GIT_COMMIT}
Build #     : ${env.BUILD_NUMBER}
Stage       : ${env.FAILED_STAGE ?: 'Unknown'}

Check console output: ${env.BUILD_URL}console
                    """.stripIndent()
                )
            }
        }

        always {
            cleanWs()
        }
    }
}
```

> **Key design:** The Deploy stage calls `deploy.sh` which builds a Docker image, stops the old container, and starts a new one. No systemd service is involved — Docker's `--restart unless-stopped` policy handles automatic restarts. The script can also be run manually via SSH for ad-hoc deployments.

---

### 6.7 Multibranch Pipeline Setup

#### Step 1 — Create a GitHub Personal Access Token

Jenkins needs a token to clone your repo and scan for branches.

1. Go to <https://github.com/settings/tokens> (GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic))
2. Click **Generate new token (classic)**
3. Configure:
   - **Note:** `jenkins-findmyrent`
   - **Expiration:** 90 days (you'll rotate it after — set a calendar reminder)
   - **Scopes:** tick `repo` (full control of private repositories) and `admin:repo_hook` (allows Jenkins to manage webhooks)
4. Click **Generate token**
5. **Copy the token immediately** — GitHub will never show it again

#### Step 2 — Add the token as a Jenkins credential

If you haven't already added this in [Section 6.4](#64-configure-credentials-in-jenkins):

1. Open Jenkins via SSH tunnel (`http://localhost:8080`)
2. Go to **Manage Jenkins → Credentials → System → Global credentials → Add Credentials**
3. Configure:
   - **Kind:** Username with password
   - **Username:** your GitHub username (e.g. `noble-dev`)
   - **Password:** paste the PAT you just generated
   - **ID:** `github-pat`
   - **Description:** `GitHub PAT for FindMyRent`
4. Click **Create**

#### Step 3 — Create the Multibranch Pipeline

1. Go to **Jenkins Dashboard → New Item** (via SSH tunnel at <http://localhost:8080>)
2. Name it `FindMyRent-API`, select **Multibranch Pipeline**, click OK
3. Under **Branch Sources**, add a **GitHub** source:
   - **Repository HTTPS URL:** `https://github.com/<your-username>/FindMyRent`
   - **Credentials:** select `github-pat` from the dropdown
4. Under **Build Configuration**:
   - Mode: `by Jenkinsfile`
   - Script Path: `Jenkinsfile`
5. Under **Scan Multibranch Pipeline Triggers**, enable **Periodically if not otherwise run**: `1 minute`
6. Click **Save** → Jenkins will scan the repo and create pipeline jobs for each branch that contains a `Jenkinsfile`

> **Token expiry:** When your PAT expires (after 90 days), Jenkins builds will start failing
> with authentication errors. Generate a new token on GitHub, then update the `github-pat`
> credential in Jenkins: **Manage Jenkins → Credentials → github-pat → Update → paste new token**.

---

## 7. Phase 4 — GitHub Integration

### 7.1 GitHub Webhook to Jenkins (via nginx)

The webhook reaches Jenkins through the nginx reverse proxy on port 443 — not through port 8080 directly.

1. In your GitHub repo, go to **Settings → Webhooks → Add webhook**
2. Configure:
   - **Payload URL:** `https://ground-shakers.xyz/github-webhook/`
   - **Content type:** `application/json`
   - **Secret:** (same value stored as `github-webhook-secret` credential in Jenkins)
   - **Events:** Select `Just the push event` and `Pull requests`
3. Click **Add webhook**
4. GitHub will send a test ping — check that it shows a green tick (200 response)

> **No extra Jenkins configuration needed.** For Multibranch Pipelines, Jenkins automatically
> responds to webhook pings and triggers a branch scan. The "GitHub hook trigger for GITScm
> polling" checkbox exists on regular Pipeline jobs but is not present on Multibranch Pipelines.
> The 1-minute polling you configured in [Section 6.7](#67-multibranch-pipeline-setup) acts as
> a fallback if a webhook ever fails to deliver.

> **How it works:**
>
> 1. GitHub sends a POST to `https://ground-shakers.xyz/github-webhook/`
> 2. nginx terminates TLS and proxies the request to `http://127.0.0.1:8080/github-webhook/`
> 3. Jenkins receives the webhook and triggers a branch scan
> 4. If the branch has a `Jenkinsfile`, the pipeline runs
>
> No public port 8080 is needed. The webhook uses the same HTTPS port (443) as the API.

---

### 7.2 Updated GitHub Actions (Optional Bridge)

You can keep GitHub Actions purely for PRs (lightweight checks) and let Jenkins handle deployments. Update `.github/workflows/main.yml`:

```yaml
name: PR Checks

on:
  pull_request:
    branches:
      - master
      - develop

# NOTE: Full CI/CD (test + deploy) is now handled by Jenkins.
# GitHub Actions runs lightweight checks on PRs only.

jobs:
  lint:
    name: Lint Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
          cache: 'pip'
      - run: pip install flake8
      - name: Critical lint only
        run: flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

> **Decision:** If you want Jenkins to be the **only** CI/CD system, you can delete `.github/workflows/main.yml` entirely. If you want GitHub Actions as a backup, keep the bridge above.

---

## 8. Secrets Management

### Current `.env` File — Do NOT Check In

Your `.env` file contains live credentials including the **MongoDB Atlas connection string**. On the EC2 server, it should exist at:

```
/home/ubuntu/.env
```

The Docker container reads this file via `--env-file /home/ubuntu/.env` at launch time.

Example `.env` structure:

```bash
# MongoDB Atlas
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/findmyrent?retryWrites=true&w=majority

# Redis (local — accessible via localhost because of --network host)
REDIS_URL=redis://localhost:6379

# Application secrets
SECRET_KEY=<your-secret-key>
# ... other env vars
```

This file is deployed **once manually** and then left in place (it's in `.gitignore`). Updates are applied via SSH.

### Jenkins Environment Variables

All secrets Jenkins needs are stored as **Jenkins Credentials** (see [Section 6.4](#64-configure-credentials-in-jenkins)), never hardcoded in `Jenkinsfile`.

### Terraform Variables

`terraform.tfvars` is in `.gitignore`. For CI-driven Terraform, use environment variables:

```bash
export TF_VAR_ssh_key_name="findmyrent-key"
export TF_VAR_allowed_ssh_cidr="YOUR.IP.ADDRESS/32"
terraform plan
```

### Recommended: AWS Secrets Manager (Future)

For a more robust setup, migrate `.env` secrets to AWS Secrets Manager and fetch them at startup:

```python
# In main.py startup, fetch secrets from AWS Secrets Manager
# instead of loading .env directly
```

---

## 9. MongoDB Atlas Configuration

### Initial Setup

1. **Create a cluster** at <https://cloud.mongodb.com>
   - For development/pilot: **M0 (Free)** or **M2 ($9/month)** is sufficient.
   - Choose a region close to your EC2 instance (e.g., `US East (Virginia)` if your EC2 is in `us-east-1`).

2. **Create a database user:**
   - Go to **Database Access → Add New Database User**
   - Authentication: Password
   - Role: `readWrite` on the `findmyrent` database

3. **Whitelist your EC2 Elastic IP:**
   - Go to **Network Access → Add IP Address**
   - Enter the IP from `terraform output atlas_whitelist_ip`
   - This ensures only your EC2 can reach the Atlas cluster

4. **Get the connection string:**
   - Go to **Database → Connect → Drivers → Python**
   - Copy the `mongodb+srv://` URI and place it in your `.env` file

### Connection from FastAPI

Your application should already be using `motor` (async) or `pymongo` to connect. The connection string points to Atlas — no code changes needed if you're already using a `MONGODB_URI` environment variable:

```python
# settings.py or config.py
MONGODB_URI = os.getenv("MONGODB_URI")
# This works identically for local MongoDB and Atlas
```

### Atlas Security Best Practices

- **Never whitelist `0.0.0.0/0`** — always use the specific EC2 Elastic IP.
- **Use a dedicated database user** per environment (dev, staging, production).
- **Enable Atlas audit logging** for production.
- **Future:** Set up VPC peering between your AWS VPC and Atlas for private connectivity (eliminates public IP whitelisting).

---

## 10. Rollback Strategy

### Automatic Rollback (Jenkinsfile)

Add a `Rollback` stage that runs on failure. Since each Docker image is tagged with its commit SHA, rollback means re-launching the previous image:

```groovy
stage('Rollback') {
    when {
        allOf {
            branch 'master'
            expression { currentBuild.result == 'FAILURE' }
        }
    }
    steps {
        sh '''
            set -e
            echo "==> Rolling back to previous Docker image..."

            # Find the previous image (second-newest tag, excluding 'latest')
            PREV_IMAGE=$(docker images findmyrent-api --format "{{.Tag}}" | grep -v latest | head -1)

            if [ -z "$PREV_IMAGE" ]; then
                echo "No previous image found — cannot rollback"
                exit 1
            fi

            echo "==> Rolling back to: findmyrent-api:${PREV_IMAGE}"
            docker stop findmyrent-api || true
            docker rm findmyrent-api || true

            docker run -d \
                --name findmyrent-api \
                --restart unless-stopped \
                --env-file /home/ubuntu/.env \
                --network host \
                "findmyrent-api:${PREV_IMAGE}"

            sleep 5
            curl -sf http://localhost:8000/health \
                || curl -sf http://localhost:8000/ \
                || (echo "Rollback health check failed!" && exit 1)

            echo "==> Rollback complete"
        '''
    }
}
```

### Manual Rollback via Docker

You can roll back manually via SSH without Jenkins:

```bash
# List available image tags (each is a commit SHA)
docker images findmyrent-api --format "{{.Tag}}  {{.CreatedAt}}"

# Roll back to a specific version
docker stop findmyrent-api
docker rm findmyrent-api
docker run -d \
    --name findmyrent-api \
    --restart unless-stopped \
    --env-file /home/ubuntu/.env \
    --network host \
    findmyrent-api:<commit-sha>
```

### Manual Rollback via Parameterised Build

In Jenkins, add a **parameterised build** that accepts a commit SHA and rebuilds from that commit:

```groovy
parameters {
    string(name: 'ROLLBACK_COMMIT', defaultValue: '', description: 'Git commit SHA to roll back to (leave empty for normal build)')
}

// In Deploy stage:
script {
    def targetCommit = params.ROLLBACK_COMMIT ?: 'origin/master'
    sh "cd /home/ubuntu/FindMyRent-API && git reset --hard ${targetCommit}"
    sh './infrastructure/scripts/deploy.sh'
}
```

---

## 11. Resource Sizing & Monitoring

### Instance Sizing for Combined Server

| Instance Type | vCPU | RAM | Monthly Cost (approx.) | Recommendation |
|---|---|---|---|---|
| t3.small | 2 | 2 GB | ~$15 | Too tight for Jenkins + app |
| **t3.medium** | **2** | **4 GB** | **~$30** | **Recommended for pilot** |
| t3.large | 2 | 8 GB | ~$60 | If builds are memory-heavy |

**Why t3.medium:** Jenkins alone needs ~1–2 GB RAM when building. Combined with FastAPI + Redis, 4 GB provides adequate headroom. The `t3` burstable instances handle intermittent CI load well.

### Memory Budget (t3.medium — 4 GB)

| Process | Typical RAM |
|---|---|
| OS + system services | ~400 MB |
| Docker daemon | ~100–200 MB |
| Jenkins (idle) | ~500 MB |
| Jenkins (during build) | ~1–1.5 GB |
| nginx | ~10–20 MB |
| findmyrent-api container (2 workers) | ~200–400 MB |
| Redis | ~50–100 MB |
| **Total during build** | **~2.5–3.5 GB** |

### Monitoring Recommendations

- **Enable CloudWatch basic monitoring** (free, 5-minute intervals).
- Set a **CloudWatch alarm** for CPU > 80% sustained for 10 minutes.
- Set a **memory alarm** using the CloudWatch agent (requires installation).
- Monitor Jenkins build times — if they degrade, consider upgrading or splitting servers.
- **Monitor TLS certificate expiry** — certbot auto-renews, but verify with `sudo certbot certificates`.

### When to Split Servers

Consider migrating Jenkins to its own EC2 if:

- API response times degrade noticeably during CI builds.
- You add more microservices or team members triggering frequent builds.
- Build times exceed 10 minutes regularly.

---

## 12. Full Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         DEVELOPER                               │
│  git push origin master / git push origin develop               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                        GITHUB                                   │
│  • Stores code                                                  │
│  • Fires webhook on push/PR                                     │
│  • Optional: GitHub Actions for lightweight PR lint checks      │
└────────────────────┬────────────────────────────────────────────┘
                     │  Webhook POST https://ground-shakers.xyz/github-webhook/
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          COMBINED EC2 SERVER (t3.medium)                         │
│          ground-shakers.xyz                                      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  NGINX (:443 HTTPS, :80 → redirect)                   │       │
│  │  ├── /                  → proxy to Docker :8000      │       │
│  │  └── /github-webhook/   → proxy to Jenkins :8080      │       │
│  │  TLS: Let's Encrypt (auto-renewing)                   │       │
│  └──────────────────────────┬───────────────────────────┘       │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────┐        │
│  │  JENKINS (127.0.0.1:8080 — NOT publicly exposed)     │        │
│  │  Accessed via SSH tunnel: ssh -L 8080:localhost:8080  │        │
│  │                                                      │        │
│  │  Stage 1: Checkout   ──► git clone / git fetch       │        │
│  │  Stage 2: Install    ──► pip install -r requirements │        │
│  │  Stage 3: Lint       ──► flake8                      │        │
│  │  Stage 4: Tests      ──► pytest --cov                │        │
│  │  Stage 5: Deploy *   ──► local: docker build + run  │        │
│  │  Stage 6: Rollback * ──► only on failure             │        │
│  │  Post:    Notify     ──► Email via Brevo SMTP        │        │
│  │  (* master branch only)                              │        │
│  └──────────────────────────┬──────────────────────────┘        │
│                              │ local deploy                      │
│  ┌──────────────────────────▼──────────────────────────┐        │
│  │  FINDMYRENT API (Docker container, --network host)   │        │
│  │  ├── docker: findmyrent-api (127.0.0.1:8000)        │        │
│  │  ├── image: findmyrent-api:latest                    │        │
│  │  ├── redis-server (localhost:6379)                    │        │
│  │  └── .env (mounted via --env-file)                   │        │
│  └──────────────────────────┬──────────────────────────┘        │
│                              │                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │ outbound TLS (mongodb+srv://)
                               ▼
                  ┌─────────────────────────────┐
                  │    MONGODB ATLAS (cloud)     │
                  │    • Replica set             │
                  │    • Automated backups       │
                  │    • IP whitelist: EC2 EIP   │
                  └─────────────────────────────┘

Developer ── SSH tunnel (:22) ──► localhost:8080 = Jenkins UI

                  TERRAFORM (run locally or from CI)
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              AWS INFRASTRUCTURE                                 │
│  • VPC + Subnet + IGW + Route Table                             │
│  • Security Group (ports: 22, 80, 443 only)                     │
│  • EC2: Combined Server (EIP: static public IP)                 │
│  • S3: Terraform state bucket                                   │
│  • DynamoDB: Terraform state lock table                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Troubleshooting

### Can't access Jenkins UI

```bash
# 1. Make sure your SSH tunnel is active:
ssh -i ~/.ssh/findmyrent -L 8080:localhost:8080 ubuntu@<SERVER_IP>

# 2. Then open http://localhost:8080 in your browser

# 3. If Jenkins isn't responding, check it's running:
sudo systemctl status jenkins

# 4. Verify Jenkins is bound to localhost:
sudo ss -tlnp | grep 8080
# Should show: 127.0.0.1:8080 (NOT 0.0.0.0:8080)
```

### Jenkins can't deploy the app (permission denied)

**`cd: /home/ubuntu/FindMyRent-API: No such file or directory`**

The repo hasn't been cloned to the server yet. This must be done once manually after the first
`terraform apply` — see [Section 4.9](#49-initial-server-setup-one-time-after-first-apply).

```bash
# Clone the repo (run as ubuntu user)
git clone https://github.com/ground-shakers/FindMyRent-API.git /home/ubuntu/FindMyRent-API
```

**`cd: /home/ubuntu/FindMyRent-API: Permission denied`**

The `jenkins` user can't access `/home/ubuntu` because the home directory defaults to `700` (owner-only).
Fix:

```bash
# Make /home/ubuntu traversable
sudo chmod 755 /home/ubuntu

# Add jenkins to the ubuntu group
sudo usermod -aG ubuntu jenkins

# Ensure the app directory is owned by ubuntu
sudo chown -R ubuntu:ubuntu /home/ubuntu/FindMyRent-API

# Restart Jenkins so the group change takes effect
sudo systemctl restart jenkins
```

**Docker permission denied**

```bash
# Verify jenkins user is in the docker group:
groups jenkins
# Should include: docker

# If not, add it and restart Jenkins:
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins

# Test manually as the jenkins user:
sudo -u jenkins docker ps
```

### App can't connect to MongoDB Atlas

```bash
# Test connectivity from EC2 to Atlas:
python3 -c "
from pymongo import MongoClient
client = MongoClient('mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/')
print(client.server_info()['version'])
"

# Common issues:
# 1. EC2 Elastic IP not whitelisted in Atlas → Network Access → Add IP
# 2. Wrong credentials in .env → check MONGODB_URI
# 3. DNS resolution failure → ensure VPC has enable_dns_support = true
# 4. Outbound blocked → security group must allow all egress (0.0.0.0/0)
```

### HTTPS / SSL certificate issues

```bash
# Check certificate status:
sudo certbot certificates

# Force renewal:
sudo certbot renew --force-renewal

# Verify nginx config:
sudo nginx -t

# Check nginx error log:
sudo tail -50 /var/log/nginx/error.log

# Verify the domain resolves to your server:
dig ground-shakers.xyz +short

# Test HTTPS from the server itself:
curl -I https://ground-shakers.xyz
```

### GitHub webhook not triggering

**Symptom: GitHub shows 404 on webhook delivery**

This usually means nginx is missing the proxy rule for `/github-webhook/`. Check:

```bash
# 1. Verify Jenkins responds to the webhook path directly:
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8080/github-webhook/
# Should return 400 (empty payload) — NOT 404. 400 means Jenkins is listening.

# 2. Check your nginx config has the proxy rule:
sudo grep -A5 "github-webhook" /etc/nginx/sites-available/default
# Should show: proxy_pass http://127.0.0.1:8080/github-webhook/

# 3. If the proxy rule is missing, certbot likely overwrote it. Fix:
sudo tee /etc/nginx/sites-available/default > /dev/null <<'NGINX'
# HTTP → HTTPS redirect
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ground-shakers.xyz;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name ground-shakers.xyz;

    ssl_certificate /etc/letsencrypt/live/ground-shakers.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ground-shakers.xyz/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /github-webhook/ {
        proxy_pass http://127.0.0.1:8080/github-webhook/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
NGINX

sudo nginx -t && sudo systemctl reload nginx

# 4. Test the full chain via HTTPS:
curl -s -o /dev/null -w "%{http_code}" -X POST https://ground-shakers.xyz/github-webhook/
# Should return 400 (success — Jenkins received the empty payload)

# 5. Redeliver from GitHub:
# GitHub → Settings → Webhooks → Recent Deliveries → Redeliver
```

**Symptom: Webhook delivers but builds don't trigger**

```bash
# Check nginx access log for webhook hits:
sudo grep "github-webhook" /var/log/nginx/access.log

# Check Jenkins system log:
# Via SSH tunnel → http://localhost:8080/manage/systemLog

# Ensure the webhook URL in GitHub is exactly:
# https://ground-shakers.xyz/github-webhook/  (trailing slash matters)
```

### Terraform state lock error

```bash
# If a previous apply crashed and left a lock:
terraform force-unlock <LOCK_ID>
# LOCK_ID is shown in the error message
```

### Jenkins failed to install (GPG key error)

If `cloud-init-output.log` shows `NO_PUBKEY 7198F4B714ABFC68` and Jenkins didn't install,
the published `jenkins.io-2023.key` file no longer matches the key Jenkins signs their repo with.
Fix it manually:

```bash
# Import the real signing key from Ubuntu's keyserver
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 7198F4B714ABFC68

# Export it to the file the sources list expects
sudo apt-key export 14ABFC68 | sudo gpg --dearmor -o /usr/share/keyrings/jenkins-keyring.gpg

# Remove any broken repo entries from previous attempts
sudo rm -f /etc/apt/sources.list.d/jenkins.list

# Add the repo with the correct key path
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.gpg] https://pkg.jenkins.io/debian binary/" | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null

# Install
sudo apt-get update -y
sudo apt-get install -y jenkins

# Then configure, enable, and start Jenkins
sudo mkdir -p /etc/systemd/system/jenkins.service.d
echo -e '[Service]\nEnvironment="JENKINS_LISTEN_ADDRESS=127.0.0.1"' | sudo tee /etc/systemd/system/jenkins.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl enable jenkins
sudo systemctl start jenkins

# Verify it's running on localhost
sudo ss -tlnp | grep 8080
```

### Server running out of memory during builds

```bash
# Check current memory usage:
free -h

# Check what's using memory:
ps aux --sort=-%mem | head -20

# Check Docker container resource usage:
docker stats --no-stream

# Quick fixes:
# 1. Reduce uvicorn workers from 2 to 1 in Dockerfile CMD
# 2. Limit Jenkins executors to 1 (Manage Jenkins → Nodes → Built-In Node → # of executors = 1)
# 3. Prune unused Docker images: docker system prune -af
# 4. Upgrade to t3.large if persistent issue
```

### Docker container won't start

```bash
# Check container status:
docker ps -a

# View container logs:
docker logs findmyrent-api

# Common issues:
# 1. Port 8000 already in use → another container or process is running
#    docker ps | grep 8000
# 2. .env file missing → ensure /home/ubuntu/.env exists
# 3. Bad image build → rebuild: docker build -t findmyrent-api:latest .
# 4. Redis not running → sudo systemctl status redis-server
```

### Terraform `InvalidAMI` error

The AMI ID `ami-0c7217cdde317cfec` is region-specific. Find the correct Ubuntu 22.04 AMI for your region:

```bash
aws ec2 describe-images \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
  --query "sort_by(Images, &CreationDate)[-1].ImageId" \
  --region us-east-1
```

---

*Generated for FindMyRent API — FastAPI + Docker + MongoDB Atlas + Redis on AWS EC2, served over HTTPS at ground-shakers.xyz*