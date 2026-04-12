import re

PATTERNS = {
    "oom_kill":     re.compile(r"\b(OOM|Out of memory|Killed process)\b", re.IGNORECASE),
    "timeout":      re.compile(r"\b(timeout|timed out|ETIMEDOUT|context deadline exceeded)\b", re.IGNORECASE),
    "conn_refused": re.compile(r"\b(Connection refused|ECONNREFUSED)\b", re.IGNORECASE),
    "dns":          re.compile(r"\b(temporary failure in name resolution|NXDOMAIN|SERVFAIL)\b", re.IGNORECASE),
    "disk_full":    re.compile(r"\b(No space left on device|ENOSPC|disk full)\b", re.IGNORECASE),
    "permission":   re.compile(r"\b(permission denied|EACCES|forbidden)\b", re.IGNORECASE),
    "http_5xx":     re.compile(r"\b 5\d\d \b"),
    "panic_fatal":  re.compile(r"\b(panic|fatal|segfault|SIGSEGV)\b", re.IGNORECASE),
    "restart_loop": re.compile(r"\b(restarting|crash loop|back-off)\b", re.IGNORECASE),
}

NOISE = [
    re.compile(r"\b(healthcheck|readyz|livez)\b", re.IGNORECASE),
]

SIGNAL_MAP = {
    "latency":    ["timeout"],
    "traffic":    [],
    "errors":     ["http_5xx", "conn_refused", "dns", "permission", "panic_fatal"],
    "saturation": ["oom_kill", "disk_full"],
}

SAFE_NEXT_COMMANDS = [
    ("Confirm service logs (recent)",      "journalctl -u <service> --since '30 min ago' --no-pager | tail -200"),
    ("Follow service logs live",           "journalctl -u <service> -f"),
    ("Top CPU processes",                  "ps aux --sort=-%cpu | head -15"),
    ("Memory overview",                    "free -h"),
    ("Disk usage",                         "df -h"),
    ("Disk I/O saturation",                "iostat -x 1 3"),
    ("Listening ports",                    "ss -tuln"),
    ("Docker container resource snapshot", "docker stats --no-stream"),
    ("Docker container logs (last hour)",  "docker logs --since 1h <container>"),
]
