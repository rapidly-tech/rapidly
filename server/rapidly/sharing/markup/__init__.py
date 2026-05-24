"""Collab chamber — realtime peer-to-peer docs and whiteboards.

Server-side session model + signaling auth validators. The CRDT
itself (Yjs) lives in the browser; the backend only authenticates
peers and relays signaling frames.
"""
