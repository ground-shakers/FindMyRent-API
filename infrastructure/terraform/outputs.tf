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