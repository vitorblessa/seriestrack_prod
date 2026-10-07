"""Rate limiting via slowapi, keyed by client IP.

In-memory storage — fine for Render's free tier (one process, one instance).
If the backend ever scales to multiple instances, swap in a Redis storage_uri
(slowapi supports it natively) so limits are shared across processes.

Limits here are deliberately generous: the goal is blocking brute-force /
spam against auth endpoints, not throttling normal use.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
