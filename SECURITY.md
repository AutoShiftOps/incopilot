# Security Policy

## Reporting Security Vulnerabilities

**Please do NOT open public GitHub issues for security vulnerabilities.**

If you discover a security vulnerability in incopilot, please report it responsibly by emailing:

📧 **security@autoshiftops.com**

Include the following information:
- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact
- Suggested remediation (if any)

## Security Considerations

### What incopilot Does
- Reads and analyzes local log files
- Executes `journalctl` and `docker logs` commands on your system
- Generates reports containing log patterns and analysis
- Does NOT send data to external services
- Does NOT store data persistently

### What incopilot Does NOT Do
- Execute destructive commands (read-only operations only)
- Connect to remote services or cloud APIs
- Store credentials or secrets
- Modify system configuration

## Supported Python Versions

- Python 3.10+
- Python 3.11+
- Python 3.12+
