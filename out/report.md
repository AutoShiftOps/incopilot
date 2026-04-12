# Incident Copilot Report

- Generated : 2026-04-12 03:33:26 UTC
- Source    : docker
- Target    : pedantic_edison
- Since     : 1h

## Golden Signals (heuristic)
- No clear golden-signal pattern detected.

## Findings (pattern counts)
- No pattern matches.

## Top repeating lines (normalized)

## Suggested next steps
- No strong pattern. Start with baseline host signals (CPU/mem/disk/IO), then narrow by service logs.
- Run the safe next-commands checklist below (non-destructive).

## Safe next-commands checklist (non-destructive)
- **Confirm service logs (recent)**: `journalctl -u <service> --since '30 min ago' --no-pager | tail -200`
- **Follow service logs live**: `journalctl -u <service> -f`
- **Top CPU processes**: `ps aux --sort=-%cpu | head -15`
- **Memory overview**: `free -h`
- **Disk usage**: `df -h`
- **Disk I/O saturation**: `iostat -x 1 3`
- **Listening ports**: `ss -tuln`
- **Docker container resource snapshot**: `docker stats --no-stream`
- **Docker container logs (last hour)**: `docker logs --since 1h <container>`

## Examples (first 3 per pattern)