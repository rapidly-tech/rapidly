"""Watch chamber — synchronised P2P video viewing.

Server-side session model + signaling auth validators. The Watch chamber
reuses the shared signaling server and registers two auth validators for
``session_kind="watch"``. Playback synchronisation itself happens in the
browser over the existing ``PeerDataConnection`` — the backend does not
see video bytes or playback state.
"""
