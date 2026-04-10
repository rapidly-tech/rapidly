# Rapidly infrastructure — outputs.

output "app_server_ipv4" {
  description = "Public IPv4 address of the application server."
  value       = hcloud_server.app.ipv4_address
}

output "app_server_ipv6" {
  description = "Public IPv6 address of the application server."
  value       = hcloud_server.app.ipv6_address
}

output "database_private_ipv4" {
  description = "Private IPv4 address of the PostgreSQL server."
  value       = try(one(hcloud_server.database.network).ip, "10.0.0.3")
}

output "cache_private_ipv4" {
  description = "Private IPv4 address of the Redis server."
  value       = try(one(hcloud_server.cache.network).ip, "10.0.0.4")
}

output "network_id" {
  description = "ID of the private network."
  value       = hcloud_network.rapidly.id
}
