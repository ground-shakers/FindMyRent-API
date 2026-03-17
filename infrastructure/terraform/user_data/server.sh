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
# ============================================================
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key | \
  tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null

echo deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] \
  https://pkg.jenkins.io/debian-stable binary/ | \
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
chown ubuntu:ubuntu /home/ubuntu/FindMyRent-API

# ============================================================
# Add jenkins and ubuntu users to docker group
# ============================================================
usermod -aG docker jenkins
usermod -aG docker ubuntu

# Allow jenkins to manage Docker containers without sudo
cat > /etc/sudoers.d/jenkins-deploy <<'EOF'
jenkins ALL=(ALL) NOPASSWD: /usr/bin/docker *
EOF

# ============================================================
# Configure nginx — initial HTTP-only config
# (HTTPS is added after DNS is pointed and certbot runs)
# ============================================================
cat > /etc/nginx/sites-available/findmyrent <<'NGINX'
server {
    listen 80;
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

ln -sf /etc/nginx/sites-available/findmyrent /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "Combined server bootstrap complete"
echo "Jenkins initial admin password:"
cat /var/lib/jenkins/secrets/initialAdminPassword 2>/dev/null || echo "(not yet available — check after Jenkins starts)"
echo ""
echo "NEXT STEPS:"
echo "  1. Point ground-shakers.xyz DNS A record to this server's Elastic IP"
echo "  2. Run: sudo certbot --nginx -d ground-shakers.xyz"
echo "  3. Access Jenkins via: ssh -L 8080:localhost:8080 ubuntu@<SERVER_IP>"