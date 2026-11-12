# Security Policy

## Reporting Security Vulnerabilities

**Please do NOT open public GitHub issues for security vulnerabilities.**

If you discover a security vulnerability in firstsignal, please report it responsibly by emailing:

📧 **security@autoshiftops.com**

Include the following information:
- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact
- Suggested remediation (if any)

## Security Considerations

### What firstsignal does
- Reads logs through `journalctl`, `docker logs`, `kubectl logs`, or a file you name
- Runs those tools with a fixed argument list and no shell; values that look like options are rejected
- Masks secrets (passwords, tokens, keys, credentials in URLs, emails) in every report by default
- Writes `report.md` and `report.json` to the directory you choose
- Sends nothing over the network unless you pass `--ai`

### What `--ai` sends
- Only the redacted findings summary: counts, order of appearance, up to two redacted example lines per finding, and the top repeating lines
- Never the raw log, and never anything when `--no-redact` is set
- To the provider you configure with your own key, over HTTPS (plain HTTP is accepted for localhost only, for local models)
- Redaction is pattern-based and cannot guarantee that every secret is caught. Review what your logs contain before enabling `--ai`

### What firstsignal does not do
- Change anything: no restarts, deletes, scaling or config edits. Suggested commands are read-only and are printed, never run
- Execute or act on anything a model returns
- Store credentials. API keys are read from environment variables only

## Supported Python Versions

- Python 3.10, 3.11, 3.12 and 3.13
