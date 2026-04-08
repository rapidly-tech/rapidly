# Rapidly infrastructure — outputs consumed by the deploy workflow.

output "app_server_ipv4" {
  description = "Public IPv4 address of the application server. Cloudflare DNS records for rapidly.tech and api.rapidly.tech point here."
  value       = hcloud_server.app.ipv4_address
}

output "app_server_ipv6" {
  description = "Public IPv6 address of the application server."
  value       = hcloud_server.app.ipv6_address
}

output "database_private_ipv4" {
  description = "Private IPv4 address of the PostgreSQL server, reachable from the app server over the rapidly private network."
  value       = one(hcloud_server.database.network).ip
}

output "cache_private_ipv4" {
  description = "Private IPv4 address of the Redis server, reachable from the app server over the rapidly private network."
  value       = one(hcloud_server.cache.network).ip
}

output "network_id" {
  description = "ID of the private network shared by every Rapidly server."
  value       = hcloud_network.rapidly.id
}

output "database_volume_id" {
  description = "ID of the persistent volume backing PostgreSQL data."
  value       = hcloud_volume.pgdata.id
}
