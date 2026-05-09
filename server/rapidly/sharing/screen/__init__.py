"""Screen chamber — P2P screen sharing.

Server-side session model + signaling auth validators. No WebSocket logic
lives here; the Screen chamber reuses the shared signaling server and
registers two auth validators for ``session_kind="screen"``.
"""
