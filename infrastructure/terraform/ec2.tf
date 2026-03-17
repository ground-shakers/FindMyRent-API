resource "aws_instance" "combined" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.ssh_key_name
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.combined.id]

  user_data = file("${path.module}/user_data/server.sh")

  root_block_device {
    volume_size = 30   # Extra space for Jenkins build artifacts + app
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name        = "${var.app_name}-server"
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