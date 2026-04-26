"""Call chamber — encrypted P2P voice + video for small groups.

Server-side session model + signaling auth validators. v1 is a
4-participant mesh — every participant opens a PeerDataConnection to
every other via the existing signaling server. No media ever touches a
Rapidly machine.
"""
