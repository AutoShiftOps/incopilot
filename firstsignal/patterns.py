"""Detection patterns, grouped into packs.

Each pattern maps a log signature to one of the Four Golden Signals and a
severity, and carries a short piece of read-only advice. Add your own in
`firstsignal.toml` (see README) rather than editing this file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SIGNALS = ("latency", "traffic", "errors", "saturation")
SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass(frozen=True)
class Pattern:
    """One detection rule."""

    key: str
    regex: re.Pattern
    signal: str
    severity: str
    title: str
    advice: str
    pack: str = "core"


def _p(key, rx, signal, severity, title, advice, pack="core") -> Pattern:
    return Pattern(key, re.compile(rx, re.IGNORECASE), signal, severity, title, advice, pack)


# HTTP status codes are only trusted next to something that says "this is a
# status code", so "took 512 ms" does not count as a 5xx.
_STATUS_CTX = r"(?:HTTP/\d(?:\.\d)?\"?\s+|\bHTTP\s+|\bstatus(?:[_ ]?code)?\"?\s*[=:]\s*\"?)"

CORE = [
    _p("oom_kill",
       r"\b(out of memory|oom[- ]?kill(?:ed|er)?|killed process \d+|OOMKilled|cannot allocate memory|ENOMEM)\b",
       "saturation", "critical", "Out of memory",
       "Memory pressure. Compare usage against limits and look for growth before the kill."),
    _p("disk_full",
       r"\b(no space left on device|ENOSPC|disk (?:is )?full|disk quota exceeded)\b",
       "saturation", "critical", "Disk full",
       "Disk is full. Check df and du, and find the fastest-growing directory (logs, images, tmp)."),
    _p("fd_exhaustion",
       r"\b(too many open files|EMFILE|ENFILE)\b",
       "saturation", "high", "File descriptors exhausted",
       "File descriptor limit reached. Compare open descriptors with ulimit; look for leaked connections."),
    _p("conn_limit",
       r"\b(too many connections|connection pool (?:exhausted|timeout|is full)"
       r"|max(?:imum)? (?:number of )?connections? (?:reached|exceeded)|worker_connections are not enough)\b",
       "saturation", "high", "Connection limit reached",
       "A connection limit was hit. Check pool size against concurrent demand and for unreleased connections."),
    _p("timeout",
       r"\b(timed out|timeout (?:exceeded|expired|while|waiting|error|occurred)|ETIMEDOUT|deadline exceeded"
       r"|i/o timeout|(?:read|write|connect|connection|request|gateway|upstream) timeout)\b",
       "latency", "high", "Timeouts",
       "Timeouts. Check the health and latency of whatever this service calls, then its own saturation."),
    _p("slow",
       r"\b(slow (?:query|request|response|log)|took longer than|response time (?:>|exceeded))",
       "latency", "medium", "Slow operations",
       "Slow operations reported. Correlate with load and with recent deploys or query changes."),
    _p("conn_refused",
       r"\b(connection refused|ECONNREFUSED)\b",
       "errors", "high", "Connection refused",
       "Connection refused. The target is not listening: check that it is running and on the expected port."),
    _p("conn_reset",
       r"\b(connection reset by peer|ECONNRESET|broken pipe|EPIPE)\b",
       "errors", "medium", "Connection reset",
       "Connections dropped mid-flight. Check for restarts or timeouts on the peer or a proxy in between."),
    _p("dns",
       r"\b(temporary failure in name resolution|NXDOMAIN|SERVFAIL|no such host|could not resolve host"
       r"|getaddrinfo (?:ENOTFOUND|EAI_AGAIN))\b",
       "errors", "high", "DNS failures",
       "Name resolution is failing. Check resolver health and whether the name still exists."),
    _p("tls",
       r"(certificate (?:has expired|verify failed|is not valid|expired)|\bx509:|SSL handshake failed"
       r"|tls: handshake failure|SSL_ERROR)",
       "errors", "high", "TLS or certificate errors",
       "TLS failures. Check certificate expiry and chain on both ends, and clock skew."),
    _p("permission",
       r"\b(permission denied|EACCES|access denied|forbidden)\b",
       "errors", "medium", "Permission denied",
       "Access was denied. Check file ownership, roles or policies that changed recently."),
    _p("auth_failure",
       r"\b(authentication failed|unauthorized|invalid credentials|login failed|invalid token|token (?:has )?expired)\b",
       "errors", "medium", "Authentication failures",
       "Authentication is failing. Check for rotated or expired credentials."),
    _p("http_5xx",
       _STATUS_CTX + r"5\d\d\b|\b(internal server error|bad gateway|service unavailable|gateway timeout)\b",
       "errors", "high", "HTTP 5xx responses",
       "Server errors. Correlate the start time with recent deploys or config changes."),
    _p("panic_fatal",
       r"(\bpanic\b|\bfatal\b|\bsegfault\b|SIGSEGV|core dumped|Traceback \(most recent call last\)"
       r"|unhandled exception|uncaught exception)",
       "errors", "critical", "Crashes and fatal errors",
       "The process is crashing. Read the first stack trace, not the last; later ones are often knock-on."),
    _p("restart_loop",
       r"(CrashLoopBackOff|crash loop|back-off restarting|restarting failed|start request repeated too quickly"
       r"|\brestarting (?:container|service)\b)",
       "errors", "high", "Restart loop",
       "The service keeps restarting. Find the first failure before the loop began."),
    _p("rate_limited",
       _STATUS_CTX + r"429\b|\b(too many requests|rate limit(?:ed| exceeded)?|throttl(?:ed|ing))\b",
       "traffic", "medium", "Rate limiting",
       "Requests are being throttled. Check for a traffic spike, a retry storm or a lowered quota."),
]

NGINX = [
    _p("nginx_upstream_timeout", r"upstream timed out", "latency", "high", "nginx: upstream timed out",
       "nginx gave up waiting for the upstream. Check upstream latency and proxy_read_timeout.", "nginx"),
    _p("nginx_upstream_connect", r"connect\(\) failed .*while connecting to upstream", "errors", "high",
       "nginx: cannot connect to upstream",
       "nginx cannot reach the upstream. Check that the upstream process is up and listening.", "nginx"),
    _p("nginx_no_live_upstreams", r"no live upstreams", "errors", "critical", "nginx: no live upstreams",
       "Every upstream is marked down. Check upstream health; nginx is failing all requests.", "nginx"),
    _p("nginx_499", r"\" 499 ", "traffic", "low", "nginx: client closed request (499)",
       "Clients are giving up before a response. Usually a symptom of slow upstreams.", "nginx"),
]

POSTGRES = [
    _p("pg_deadlock", r"\bdeadlock detected\b", "errors", "high", "PostgreSQL: deadlock",
       "Deadlocks. Look at the two statements named in the log and their lock order.", "postgres"),
    _p("pg_too_many_clients", r"(too many clients already|remaining connection slots are reserved)",
       "saturation", "critical", "PostgreSQL: out of connections",
       "PostgreSQL is out of connections. Check pg_stat_activity for idle sessions and pool sizing.", "postgres"),
    _p("pg_statement_timeout", r"canceling statement due to statement timeout", "latency", "high",
       "PostgreSQL: statement timeout",
       "Statements are hitting the timeout. Find the slow queries and check for lock waits.", "postgres"),
    _p("pg_unavailable", r"the database system is (?:in recovery mode|starting up|shutting down)",
       "errors", "critical", "PostgreSQL: not accepting connections",
       "The database is restarting or recovering. Check why it went down.", "postgres"),
]

NODE = [
    _p("node_heap_oom", r"(reached heap limit|JavaScript heap out of memory)", "saturation", "critical",
       "Node.js: heap out of memory",
       "The V8 heap is exhausted. Check for a leak or raise --max-old-space-size after confirming usage.", "node"),
    _p("node_unhandled", r"(UnhandledPromiseRejection|unhandledRejection)", "errors", "high",
       "Node.js: unhandled promise rejection",
       "A promise rejection is unhandled. Fix the first one in the log.", "node"),
]

KUBERNETES = [
    _p("k8s_image_pull", r"(ImagePullBackOff|ErrImagePull)", "errors", "high", "Kubernetes: image pull failing",
       "The image cannot be pulled. Check the tag exists and the pull secret is valid.", "kubernetes"),
    _p("k8s_probe_failed", r"(liveness|readiness|startup) probe failed", "errors", "high",
       "Kubernetes: probe failing",
       "Probes are failing. Check whether the app is slow to respond or the probe is misconfigured.", "kubernetes"),
    _p("k8s_evicted", r"(\bevicted\b|the node was low on resource)", "saturation", "high",
       "Kubernetes: pod evicted",
       "Pods are being evicted. Check node pressure (memory, disk) and pod requests.", "kubernetes"),
    _p("k8s_scheduling", r"(FailedScheduling|insufficient (?:cpu|memory))", "saturation", "high",
       "Kubernetes: cannot schedule",
       "Pods cannot be scheduled. Check cluster capacity against requests.", "kubernetes"),
]

JVM = [
    _p("jvm_oom", r"java\.lang\.OutOfMemoryError", "saturation", "critical", "JVM: OutOfMemoryError",
       "The JVM ran out of memory. Note which space (heap, metaspace, direct) the error names.", "jvm"),
    _p("jvm_stack_overflow", r"java\.lang\.StackOverflowError", "errors", "high", "JVM: StackOverflowError",
       "Unbounded recursion. The repeating frames in the trace show where.", "jvm"),
]

REDIS = [
    _p("redis_oom", r"OOM command not allowed when used memory > 'maxmemory'", "saturation", "critical",
       "Redis: maxmemory reached",
       "Redis refuses writes at maxmemory. Check used_memory against maxmemory and the eviction policy.", "redis"),
    _p("redis_misconf", r"(MISCONF Redis is configured to save RDB snapshots|Background saving error"
       r"|Can't save in background)", "errors", "critical", "Redis: snapshot failing, writes refused",
       "RDB persistence is failing, so writes are refused. Check disk space and fork memory on the Redis host.",
       "redis"),
    _p("redis_max_clients", r"max number of clients reached", "saturation", "high",
       "Redis: out of client connections",
       "Redis hit maxclients. Check client counts per host (CLIENT LIST) for leaked connections.", "redis"),
    _p("redis_loading", r"LOADING Redis is loading the dataset in memory", "errors", "high",
       "Redis: still loading the dataset",
       "Redis restarted and is loading its dataset. Find out why it restarted.", "redis"),
    _p("redis_master_link", r"(Connection with (?:master|primary) lost|Error condition on socket for SYNC"
       r"|MASTER aborted replication)", "errors", "high", "Redis: replication link broken",
       "A replica lost its primary. Check the primary's health and the network between them.", "redis"),
]

MYSQL = [
    _p("mysql_deadlock", r"Deadlock found when trying to get lock", "errors", "high", "MySQL: deadlock",
       "Deadlocks. SHOW ENGINE INNODB STATUS names the two transactions and the locks they held.", "mysql"),
    _p("mysql_lock_wait", r"Lock wait timeout exceeded", "latency", "high", "MySQL: lock wait timeout",
       "Statements waited too long for row locks. Look for long-running transactions holding them.", "mysql"),
    _p("mysql_gone_away", r"(MySQL server has gone away|Lost connection to MySQL server)", "errors", "high",
       "MySQL: connection lost",
       "Connections to MySQL dropped. Check for a server restart, wait_timeout or max_allowed_packet.", "mysql"),
    _p("mysql_too_many_connections", r"(ER_CON_COUNT_ERROR|ERROR 1040\b)", "saturation", "critical",
       "MySQL: out of connections",
       "MySQL is out of connections. Compare Threads_connected with max_connections and pool sizes.", "mysql"),
    _p("mysql_table_full", r"The table '[^']+' is full", "saturation", "high", "MySQL: table full",
       "A table cannot grow. Check disk space and tmp_table_size for internal temporary tables.", "mysql"),
]

HAPROXY = [
    _p("haproxy_no_server", r"has no server available!", "errors", "critical",
       "HAProxy: backend has no server available",
       "Every server in a backend is down; HAProxy returns 503. Check backend health checks.", "haproxy"),
    _p("haproxy_server_down", r"\bServer \S+ is DOWN\b(?! for maintenance)", "errors", "high", "HAProxy: server marked down",
       "A health check took a server out. The log line gives the check result; check that server.", "haproxy"),
    _p("haproxy_nosrv", r"<NOSRV>", "errors", "high", "HAProxy: requests with no server (<NOSRV>)",
       "Requests were not routed to any server. Check backend health and use_backend rules.", "haproxy"),
    _p("haproxy_limit", r"reached (?:the configured maximum connection limit|process FD limit"
       r"|system memory limit|system FD limit)", "saturation", "high", "HAProxy: connection limit reached",
       "HAProxy reached a limit and is queueing or dropping connections. Check maxconn and ulimit.", "haproxy"),
]

KAFKA = [
    _p("kafka_not_leader", r"(NOT_LEADER_OR_FOLLOWER|NotLeaderOrFollowerException|NotLeaderForPartition"
       r"|LEADER_NOT_AVAILABLE)", "errors", "medium", "Kafka: partition leader unavailable",
       "Clients are hitting partitions without a leader. Check for broker restarts or leader elections.", "kafka"),
    _p("kafka_isr_shrink", r"Shrinking ISR from", "errors", "high", "Kafka: ISR shrinking",
       "Replicas fell out of sync. Check the lagging broker's disk, network and GC.", "kafka"),
    _p("kafka_offline_partitions", r"(OfflinePartitionsCount\D{0,12}[1-9]|\b[1-9]\d* offline partitions?\b)", "errors", "critical",
       "Kafka: offline partitions",
       "Partitions have no live leader and cannot be read or written. Bring back the brokers holding them.",
       "kafka"),
    _p("kafka_storage", r"(KafkaStorageException|Stopping serving logs in dir)", "saturation", "critical",
       "Kafka: log directory failed",
       "A broker log directory failed. Check that disk for errors or a full filesystem.", "kafka"),
    _p("kafka_consumer_poll", r"(CommitFailedException|poll timeout has expired)",
       "latency", "high", "Kafka: consumer kicked from its group",
       "A consumer took too long between polls and lost its partitions. Check processing time per batch.",
       "kafka"),
    _p("kafka_record_too_large", r"(RecordTooLargeException|MESSAGE_TOO_LARGE)", "errors", "medium",
       "Kafka: record too large",
       "A record exceeds max.request.size or message.max.bytes. Compare the sizes on producer and broker.",
       "kafka"),
]

PACKS = {
    "core": CORE,
    "nginx": NGINX,
    "postgres": POSTGRES,
    "node": NODE,
    "kubernetes": KUBERNETES,
    "jvm": JVM,
    "redis": REDIS,
    "mysql": MYSQL,
    "haproxy": HAPROXY,
    "kafka": KAFKA,
}
DEFAULT_PACKS = ("core",)

DEFAULT_NOISE = [
    re.compile(r"(healthcheck|health[-_ ]check|/healthz?\b|/readyz|/livez|kube-probe|ELB-HealthChecker)",
               re.IGNORECASE),
]


def resolve_packs(names) -> list[Pattern]:
    """Return the patterns for the named packs. 'all' selects every pack."""
    names = list(names) or list(DEFAULT_PACKS)
    if "all" in names:
        names = list(PACKS)
    out: list[Pattern] = []
    for name in names:
        if name not in PACKS:
            raise ValueError(f"unknown pattern pack '{name}' (available: {', '.join(PACKS)}, all)")
        out.extend(PACKS[name])
    return out
