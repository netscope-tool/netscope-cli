# Security

## Reporting a vulnerability

If you believe you’ve found a security vulnerability in NetScope CLI, please report it responsibly.

**Do not** open a public GitHub issue for security-sensitive bugs.

### How to report

1. **Email** the maintainers (see contact in [pyproject.toml](pyproject.toml) or the repository’s “About” / README), or  
2. Use **GitHub Security Advisories**: go to the repository → **Security** tab → **Report a vulnerability**.

Include:

- A short description of the issue  
- Steps to reproduce (if possible)  
- Impact (e.g. local only, network exposure, data exposure)  
- Your environment (OS, Python version) if relevant  

We will acknowledge your report and work with you to understand and address it. We may ask for more detail or a patch.

### What to expect

- We’ll try to confirm the issue and assess severity.  
- For valid issues we’ll work on a fix and plan a release.  
- We’ll credit you in the release notes / advisory unless you prefer to stay anonymous.  
- We ask that you avoid public disclosure until a fix has been released or we agree on a disclosure timeline.

### Supported versions

Security fixes are applied to the **current stable** release line. We encourage users to upgrade to the latest version. Older versions may not receive patches.

## Security-related features

NetScope CLI runs network tests (ping, traceroute, port scans, etc.) that can be sensitive in locked-down environments. Use appropriate permissions and only run it in environments you’re authorized to test. See the [README](README.md) and [docs](docs/) for usage and best practices.
