"""Passive-first website, TLS certificate, and certificate-transparency audit."""
from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from netscope.modules.base import BaseTest, TestResult

SECURITY_HEADERS = (
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
)


def normalize_website_target(target: str) -> Tuple[str, str]:
    """Return (hostname, URL) for a hostname or HTTP(S) URL; reject ambiguity."""
    value = (target or "").strip()
    if not value or any(ch.isspace() for ch in value):
        raise ValueError("Enter a hostname or an http(s) URL.")
    parsed = urlsplit(value if "://" in value else f"https://{value}")
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Website audit accepts only a hostname or an http(s) URL.")
    if parsed.username or parsed.password:
        raise ValueError("User information in website URLs is not supported.")
    try:
        _ = parsed.port  # Validate syntax and the 0–65535 range before starting a worker.
    except ValueError as exc:
        raise ValueError("The website URL contains an invalid port.") from exc
    host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    if len(host) > 253 or not host:
        raise ValueError("The website hostname is invalid.")
    path = parsed.path or "/"
    url = urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc, path, parsed.query, ""))
    return host, url


def inspect_certificate(hostname: str, timeout: float = 5.0, port: int = 443) -> Dict[str, Any]:
    """Inspect the peer certificate and verification result without third-party packages."""
    result: Dict[str, Any] = {"available": False, "verified": False, "port": port}
    verified_cert: Dict[str, Any] = {}
    verification_error: Optional[str] = None
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=hostname) as tls:
                verified_cert = tls.getpeercert()
                result["available"] = True
                result["verified"] = True
                result["protocol"] = tls.version()
                cipher = tls.cipher()
                if cipher:
                    result["cipher"] = cipher[0]
                    result["cipher_bits"] = cipher[2]
    except (OSError, ssl.SSLError) as exc:
        if isinstance(exc, ssl.SSLCertVerificationError):
            verification_error = str(exc)
            result["expired"] = "expired" in verification_error.lower()
        else:
            result["error"] = str(exc)
        # A validation failure should still produce useful expiry/subject facts.
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with socket.create_connection((hostname, port), timeout=timeout) as raw:
                with context.wrap_socket(raw, server_hostname=hostname) as tls:
                    verified_cert = tls.getpeercert()
                    result["available"] = bool(verified_cert)
                    result["protocol"] = tls.version()
                    cipher = tls.cipher()
                    if cipher:
                        result["cipher"] = cipher[0]
                        result["cipher_bits"] = cipher[2]
        except (OSError, ssl.SSLError) as fallback_exc:
            result["error"] = str(fallback_exc)
    if verification_error:
        result["verification_error"] = verification_error

    if verified_cert:
        result["subject"] = _name_to_dict(verified_cert.get("subject", ()))
        result["issuer"] = _name_to_dict(verified_cert.get("issuer", ()))
        names = [value for kind, value in verified_cert.get("subjectAltName", ()) if kind == "DNS"]
        result["dns_names"] = names[:25]
        expiry_text = verified_cert.get("notAfter")
        if expiry_text:
            expires_at = datetime.fromtimestamp(ssl.cert_time_to_seconds(expiry_text), timezone.utc)
            days_left = (expires_at - datetime.now(timezone.utc)).total_seconds() / 86400
            result["expires_at"] = expires_at.isoformat()
            result["days_until_expiry"] = round(days_left, 1)
            result["expired"] = days_left < 0
    return result


def _name_to_dict(name: Any) -> Dict[str, str]:
    output: Dict[str, str] = {}
    for rdn in name or ():
        for key, value in rdn:
            output[str(key)] = str(value)
    return output


def inspect_http(url: str, timeout: float = 8.0) -> Dict[str, Any]:
    """Fetch response headers only (HEAD, then a body-discarding GET fallback)."""
    headers: Dict[str, str] = {}
    status: Optional[int] = None
    final_url = url
    error: Optional[str] = None
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(
            url, method=method, headers={"User-Agent": "NetScope/1.1 (+network diagnostics)"}
        )
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc  # 4xx/5xx responses still have useful security headers.
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = str(getattr(exc, "reason", exc))
            if method == "HEAD":
                # Do not hide transport errors by retrying another verb.
                break
            continue
        try:
            status = int(response.status)
            headers = {key.lower(): value.strip() for key, value in response.headers.items()}
            final_url = response.geturl()
            if method == "HEAD" and status in {405, 501}:
                continue
            error = None
            break
        finally:
            response.close()
    security_headers = {name: headers[name] for name in SECURITY_HEADERS if name in headers}
    missing = [name for name in SECURITY_HEADERS if name not in security_headers]
    return {
        "status_code": status,
        "final_url": final_url,
        "server": headers.get("server"),
        "content_type": headers.get("content-type"),
        "security_headers": security_headers,
        "missing_security_headers": missing,
        "error": error,
    }


def discover_ct_subdomains(domain: str, timeout: float = 12.0, limit: int = 50) -> Dict[str, Any]:
    """Query public Certificate Transparency search results for issued DNS names.

    This is passive discovery: results come from public certificate records;
    NetScope does not connect to or probe discovered subdomains.
    """
    query = urllib.parse.urlencode({"q": f"%.{domain}", "output": "json"})
    url = f"https://crt.sh/?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "NetScope/1.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            records = json.loads(response.read(3_000_000).decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as exc:
        return {"names": [], "status": "unavailable", "note": str(getattr(exc, "reason", exc))}
    found = set()
    if isinstance(records, list):
        for record in records:
            for value in str(record.get("name_value", "")).splitlines():
                name = value.strip().lower().lstrip("*.").rstrip(".")
                if name == domain or name.endswith("." + domain):
                    found.add(name)
    names = sorted(found)
    return {
        "names": names[:limit],
        "status": "complete" if len(names) <= limit else "truncated",
        "total_observed": len(names),
    }


class WebsiteAuditTest(BaseTest):
    """Collect a concise web/TLS snapshot and passive CT subdomain inventory."""

    def run(
        self,
        target: str,
        include_subdomains: bool = True,
        timeout: float = 8.0,
        max_subdomains: int = 50,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> TestResult:
        started = datetime.now()
        hostname, url = normalize_website_target(target)
        parsed_url = urlsplit(url)
        tls_port = parsed_url.port if parsed_url.scheme == "https" and parsed_url.port else 443
        if progress_callback:
            progress_callback(f"TLS certificate · {hostname}:{tls_port}")
        certificate = inspect_certificate(hostname, timeout=min(timeout, 8.0), port=tls_port)
        if progress_callback:
            progress_callback(f"HTTP security headers · {url}")
        http = inspect_http(url, timeout=timeout)
        if progress_callback and include_subdomains:
            progress_callback(f"Passive Certificate Transparency lookup · {hostname}")
        subdomains = (
            discover_ct_subdomains(hostname, timeout=min(timeout * 2, 20.0), limit=max_subdomains)
            if include_subdomains else {"names": [], "status": "skipped", "total_observed": 0}
        )
        findings: List[str] = []
        recommendations: List[str] = []
        if subdomains.get("status") == "unavailable":
            findings.append("Certificate Transparency lookup is unavailable; subdomain coverage is incomplete.")
            recommendations.append("Retry the passive lookup later or check the CT search source manually.")
        elif subdomains.get("status") == "truncated":
            findings.append(f"Certificate Transparency results were limited to {max_subdomains} names.")
            recommendations.append("Increase the result limit if a fuller passive name inventory is needed.")
        if certificate.get("verification_error"):
            findings.append("TLS certificate could not be verified by the local trust store.")
            recommendations.append("Review the hostname, validity period, certificate chain, and client trust-store configuration.")
        elif certificate.get("error"):
            findings.append(f"TLS certificate details could not be retrieved: {certificate['error']}")
            recommendations.append("Check whether the hostname resolves and exposes a TLS service on the selected port.")
        if certificate.get("expired"):
            findings.append("TLS certificate is expired.")
            recommendations.append("Renew the certificate and confirm the server presents the renewed chain.")
        days_left = certificate.get("days_until_expiry")
        if isinstance(days_left, (int, float)) and 0 <= days_left < 30:
            findings.append(f"TLS certificate expires in {days_left:g} day(s).")
            recommendations.append("Plan certificate renewal before expiry and verify automated renewal monitoring.")
        missing = http.get("missing_security_headers") or []
        if missing:
            findings.append(f"{len(missing)} common HTTP security header(s) were not present.")
            recommendations.append("Review the missing headers against application behavior and deploy suitable policies, especially CSP and HSTS, with testing.")
        if http.get("error"):
            findings.append(f"HTTP response headers could not be retrieved: {http['error']}")
            recommendations.append("Check DNS, network reachability, redirect behavior, and the target URL; rerun when reachable.")

        metrics = {
            "hostname": hostname,
            "url": url,
            "http": http,
            "tls_certificate": certificate,
            "subdomains": subdomains.get("names", []),
            "subdomain_count": subdomains.get("total_observed", len(subdomains.get("names", []))),
            "subdomain_source_status": subdomains.get("status"),
            "findings": findings,
            "recommendations": recommendations,
            "scope_note": "CT names are passive observations; NetScope does not probe the discovered hosts.",
        }
        status = "success" if http.get("status_code") is not None or certificate.get("available") else "failure"
        if status == "success" and findings:
            status = "warning"
        summary = (
            f"Collected website headers and TLS certificate details for {hostname}; "
            f"observed {metrics['subdomain_count']} certificate-transparency name(s)."
        )
        result = TestResult(
            test_name="Website Exposure Audit", target=hostname, status=status,
            timestamp=started, duration=(datetime.now() - started).total_seconds(),
            metrics=metrics, summary=summary, raw_output=None,
            error=None if status != "failure" else "No HTTP or TLS response was obtained.",
        )
        self._log_to_csv(result)
        return result

    def parse_output(self, output: str) -> Dict[str, Any]:
        return {"raw_output": output}

    def _log_to_csv(self, result: TestResult) -> None:
        for key, value in result.metrics.items():
            if key in {"scope_note"}:
                continue
            if isinstance(value, (dict, list)):
                serialized = json.dumps(value, sort_keys=True, ensure_ascii=False)
            else:
                serialized = value
            self.csv_handler.write_result(
                timestamp=result.timestamp, test_name=result.test_name, target=result.target,
                metric=key, value=serialized, status=result.status, details=result.summary or "",
            )
