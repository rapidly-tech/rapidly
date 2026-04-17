"""Shared Redis Lua scripts for the file sharing module."""

# Lua script for atomic download limit check + increment.
# Only increments if current count < max_downloads, preventing TOCTOU race.
# KEYS: [download_count_key]
# ARGV: [max_downloads, counter_ttl]
# Returns: -1 = limit reached (not incremented), otherwise = new count after increment
ATOMIC_DOWNLOAD_INCR_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0') or 0
local max_dl = tonumber(ARGV[1]) or 0
if current >= max_dl then
    return -1
end
local new_count = redis.call('INCR', KEYS[1])
if new_count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return new_count
"""

# Lua script for atomic INCR + EXPIRE (prevents orphaned keys on crash)
ATOMIC_INCR_EXPIRE_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""

# Atomic channel destruction: check pending flag + delete all keys.
# IMPORTANT: Caller MUST verify the secret via constant-time comparison
# (hmac.compare_digest) BEFORE invoking this script. The Lua script
# no longer re-verifies the secret to avoid a non-constant-time string
# comparison side-channel in Redis.
# KEYS: [channel_key, pending_destruction_key, ...ancillary_keys_to_delete]
# ARGV: (none)
# Returns: 0 = channel not found, -2 = no pending confirmation, 1 = destroyed
ATOMIC_DESTROY_CHANNEL_LUA = """
local channel_json = redis.call('GET', KEYS[1])
if not channel_json then
    return 0
end

local pending = redis.call('GET', KEYS[2])
if not pending then
    return -2
end

-- Delete all provided keys atomically
for i = 1, #KEYS do
    redis.call('DEL', KEYS[i])
end
return 1
"""

# Atomic pending destruction: check existing pending + set pending marker.
# IMPORTANT: Caller MUST verify the secret via constant-time comparison
# (hmac.compare_digest) BEFORE invoking this script.
# KEYS: [channel_key, pending_destruction_key]
# ARGV: [delay_seconds, destruction_info_json]
# Returns: 0 = channel not found, 1 = pending set,
#           2 = already pending (caller should use ATOMIC_DESTROY_CHANNEL_LUA)
ATOMIC_PENDING_DESTRUCTION_LUA = """
local channel_json = redis.call('GET', KEYS[1])
if not channel_json then
    return 0
end

local pending = redis.call('GET', KEYS[2])
if pending then
    return 2
end

redis.call('SETEX', KEYS[2], ARGV[1], ARGV[2])
return 1
"""


# Atomic peer registration for the Redis-backed RoomTransport (PR 4c).
#
# Consolidates the three admission checks (HOST_TAKEN, ROOM_FULL, write) into
# one round-trip so two workers can't both succeed at host-registration for the
# same slug.
#
# KEYS: [peers_hash_key, host_string_key]
# ARGV: [peer_id, role ("host"|"guest"), peer_meta_json, max_peers_per_room, ttl_seconds]
# Returns: "OK" | "HOST_TAKEN" | "ROOM_FULL"
ATOMIC_REGISTER_PEER_LUA = """
local peer_id   = ARGV[1]
local role      = ARGV[2]
local meta      = ARGV[3]
local max_peers = tonumber(ARGV[4])
local ttl       = tonumber(ARGV[5])

-- one-host-per-room check
if role == "host" then
    local existing_host = redis.call('GET', KEYS[2])
    if existing_host and existing_host ~= '' then
        return "HOST_TAKEN"
    end
end

-- per-room peer cap
local current = redis.call('HLEN', KEYS[1])
if current >= max_peers then
    return "ROOM_FULL"
end

-- write
redis.call('HSET', KEYS[1], peer_id, meta)
redis.call('EXPIRE', KEYS[1], ttl)
if role == "host" then
    redis.call('SET', KEYS[2], peer_id, 'EX', ttl)
end
return "OK"
"""
