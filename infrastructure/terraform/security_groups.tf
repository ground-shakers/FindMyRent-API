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