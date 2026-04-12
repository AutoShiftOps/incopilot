"""
Extended pattern packs — uncomment the services you need
and merge into config.py PATTERNS dict.
"""
import re

NGINX_PATTERNS = {
    "nginx_upstream_timeout": re.compile(r"upstream timed out.*nginx", re.IGNORECASE),
    "nginx_upstream_connect":  re.compile(r"connect\(\) failed.*upstream", re.IGNORECASE),
    "nginx_499":               re.compile(r"\b499\b"),
}

POSTGRES_PATTERNS = {
    "pg_deadlock":        re.compile(r"\bdeadlock detected\b", re.IGNORECASE),
    "pg_max_connections": re.compile(r"\bmax_connections\b.*\bexceeded\b", re.IGNORECASE),
    "pg_oom":             re.compile(r"\bout of memory\b.*\bpostgres\b", re.IGNORECASE),
}

NODE_PATTERNS = {
    "node_heap_oom":    re.compile(r"FATAL ERROR.*Reached heap limit", re.IGNORECASE),
    "node_unhandled":   re.compile(r"UnhandledPromiseRejection", re.IGNORECASE),
    "node_econnrefused":re.compile(r"ECONNREFUSED", re.IGNORECASE),
}
