"""Each pattern in the redis, mysql, haproxy and kafka packs, with a line it
must match and a nearby line it must not."""

import pytest

from incopilot.analyzer import analyze
from incopilot.patterns import resolve_packs

CASES = [
    # redis
    ("redis", "redis_oom",
     "OOM command not allowed when used memory > 'maxmemory'.",
     "Server initialized, maxmemory set to 2gb"),
    ("redis", "redis_misconf",
     "MISCONF Redis is configured to save RDB snapshots, but it's currently unable to persist to disk.",
     "Background saving terminated with success"),
    ("redis", "redis_max_clients",
     "ERR max number of clients reached",
     "Accepted 10.0.0.4:51234, 120 clients connected"),
    ("redis", "redis_loading",
     "LOADING Redis is loading the dataset in memory",
     "DB loaded from disk: 1.204 seconds"),
    ("redis", "redis_master_link",
     "Connection with master lost.",
     "MASTER <-> REPLICA sync: Finished with success"),
    # mysql
    ("mysql", "mysql_deadlock",
     "ERROR 1213 (40001): Deadlock found when trying to get lock; try restarting transaction",
     "InnoDB: deadlock detection is enabled"),
    ("mysql", "mysql_lock_wait",
     "ERROR 1205 (HY000): Lock wait timeout exceeded; try restarting transaction",
     "innodb_lock_wait_timeout=50"),
    ("mysql", "mysql_gone_away",
     "(2006, 'MySQL server has gone away')",
     "Connected to MySQL server 8.0.36"),
    ("mysql", "mysql_too_many_connections",
     "Error: ER_CON_COUNT_ERROR: Too many connections",
     "max_connections=151 Threads_connected=40"),
    ("mysql", "mysql_table_full",
     "[ERROR] /usr/sbin/mysqld: The table '/tmp/#sql1a2b_3' is full",
     "Table 'orders' is up to date"),
    # haproxy
    ("haproxy", "haproxy_no_server",
     "backend app_back has no server available!",
     "backend app_back: 3 servers available"),
    ("haproxy", "haproxy_server_down",
     "Server app_back/web1 is DOWN, reason: Layer4 connection problem, check duration: 0ms.",
     "Server app_back/web1 is UP, reason: Layer7 check passed"),
    ("haproxy", "haproxy_nosrv",
     'web~ app_back/<NOSRV> 0/-1/-1/-1/0 503 216 - - SC-- 1/1/0/0/0 0/0 "GET / HTTP/1.1"',
     'web~ app_back/web1 0/0/1/12/13 200 512 - - ---- 1/1/0/0/0 0/0 "GET / HTTP/1.1"'),
    ("haproxy", "haproxy_limit",
     "Proxy web reached the configured maximum connection limit. Please check the global 'maxconn' value.",
     "Proxy web started."),
    # kafka
    ("kafka", "kafka_not_leader",
     "Received error NOT_LEADER_OR_FOLLOWER for partition orders-3",
     "Partition orders-3 leader is broker 2"),
    ("kafka", "kafka_isr_shrink",
     "[Partition orders-3 broker=1] Shrinking ISR from 1,2,3 to 1",
     "[Partition orders-3 broker=1] ISR updated to 1,2,3"),
    ("kafka", "kafka_offline_partitions",
     "There are 4 offline partitions",
     "All partitions online"),
    ("kafka", "kafka_storage",
     "Stopping serving logs in dir /var/lib/kafka/data",
     "Loading logs from dir /var/lib/kafka/data"),
    ("kafka", "kafka_consumer_poll",
     "org.apache.kafka.clients.consumer.CommitFailedException: Commit cannot be completed",
     "Committed offset 1200 for partition orders-3"),
    ("kafka", "kafka_record_too_large",
     "org.apache.kafka.common.errors.RecordTooLargeException: The message is 2097152 bytes",
     "Sent record of 2048 bytes to orders-3"),
]


@pytest.mark.parametrize("pack,key,hit,_miss", CASES, ids=[c[1] for c in CASES])
def test_pack_pattern_matches(pack, key, hit, _miss):
    assert key in analyze(hit, resolve_packs([pack])).findings


@pytest.mark.parametrize("pack,key,_hit,miss", CASES, ids=[c[1] for c in CASES])
def test_pack_pattern_does_not_match_nearby_line(pack, key, _hit, miss):
    assert key not in analyze(miss, resolve_packs([pack])).findings


def test_every_new_pack_pattern_has_a_case():
    covered = {c[1] for c in CASES}
    for pack in ("redis", "mysql", "haproxy", "kafka"):
        for p in resolve_packs([pack]):
            assert p.key in covered, p.key
