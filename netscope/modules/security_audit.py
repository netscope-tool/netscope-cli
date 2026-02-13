"""
Comprehensive security audit orchestrator.
Combines multiple security tests into a unified audit report.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from netscope.modules.base import BaseTest, TestResult
from netscope.modules.security import SSLSecurityTest, PortSecurityTest, DNSSecurityTest
from netscope.core.executor import TestExecutor
from netscope.storage.csv_handler import CSVHandler


@dataclass
class SecurityAuditResult:
    """Comprehensive security audit result."""
    target: str
    timestamp: datetime
    overall_score: int  # 0-100
    risk_level: str  # low, medium, high, critical
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    ssl_result: Optional[TestResult] = None
    port_result: Optional[TestResult] = None
    dns_result: Optional[TestResult] = None


class SecurityAudit(BaseTest):
    """
    Comprehensive security audit combining multiple security tests.
    """
    
    # Risk scoring weights
    WEIGHTS = {
        "ssl_expired": 30,
        "ssl_weak_cipher": 15,
        "ssl_no_forward_secrecy": 10,
        "ssl_old_protocol": 15,
        "dangerous_port_open": 20,
        "no_dnssec": 5,
        "dns_leak": 10,
        "dns_hijacking": 25,
    }
    
    def __init__(
        self,
        executor: TestExecutor,
        csv_handler: CSVHandler,
    ):
        """
        Initialize security audit.
        
        Args:
            executor: Test executor instance
            csv_handler: CSV handler for logging
        """
        super().__init__(executor, csv_handler)
        self.ssl_test = SSLSecurityTest(executor, csv_handler)
        self.port_test = PortSecurityTest(executor, csv_handler)
        self.dns_test = DNSSecurityTest(executor, csv_handler)
    
    def run(
        self,
        target: str,
        port: int = 443,
        open_ports: Optional[List[int]] = None,
        include_ssl: bool = True,
        include_ports: bool = True,
        include_dns: bool = True,
    ) -> SecurityAuditResult:
        """
        Run comprehensive security audit.
        
        Args:
            target: Target host/domain
            port: SSL/TLS port (default 443)
            open_ports: List of open ports to audit (if None, will scan)
            include_ssl: Include SSL/TLS security test
            include_ports: Include port security test
            include_dns: Include DNS security test
            
        Returns:
            SecurityAuditResult with comprehensive findings
        """
        audit_result = SecurityAuditResult(
            target=target,
            timestamp=datetime.now(),
            overall_score=100,  # Start with perfect score
            risk_level="low",
        )
        
        findings = []
        recommendations = []
        
        # SSL/TLS Security Test
        if include_ssl:
            try:
                ssl_result = self.ssl_test.run(target, port)
                audit_result.ssl_result = ssl_result
                
                # Analyze SSL findings
                ssl_findings, ssl_score = self._analyze_ssl_result(ssl_result)
                findings.extend(ssl_findings)
                audit_result.overall_score -= (100 - ssl_score)
                
                # SSL recommendations
                if ssl_result.metrics.get("certificate_expired"):
                    recommendations.append("Renew SSL/TLS certificate immediately")
                if not ssl_result.metrics.get("supports_tls_1_3"):
                    recommendations.append("Enable TLS 1.3 for better security")
                if not ssl_result.metrics.get("has_forward_secrecy"):
                    recommendations.append("Enable forward secrecy (ECDHE/DHE ciphers)")
                
            except Exception as e:
                findings.append({
                    "category": "SSL/TLS",
                    "severity": "error",
                    "finding": f"SSL test failed: {str(e)}",
                })
        
        # Port Security Test
        if include_ports:
            try:
                # If open_ports not provided, use common dangerous ports
                if open_ports is None:
                    open_ports = self._scan_common_ports(target)
                
                port_result = self.port_test.run(target, open_ports)
                audit_result.port_result = port_result
                
                # Analyze port findings
                port_findings, port_score = self._analyze_port_result(port_result)
                findings.extend(port_findings)
                audit_result.overall_score -= (100 - port_score)
                
                # Port recommendations
                dangerous_count = port_result.metrics.get("dangerous_ports_count", 0)
                if dangerous_count > 0:
                    recommendations.append(f"Close or restrict {dangerous_count} dangerous port(s)")
                    recommendations.append("Implement firewall rules to limit port exposure")
                
            except Exception as e:
                findings.append({
                    "category": "Port Security",
                    "severity": "error",
                    "finding": f"Port security test failed: {str(e)}",
                })
        
        # DNS Security Test
        if include_dns:
            try:
                dns_result = self.dns_test.run(target)
                audit_result.dns_result = dns_result
                
                # Analyze DNS findings
                dns_findings, dns_score = self._analyze_dns_result(dns_result)
                findings.extend(dns_findings)
                audit_result.overall_score -= (100 - dns_score)
                
                # DNS recommendations
                if not dns_result.metrics.get("has_dnssec"):
                    recommendations.append("Enable DNSSEC for DNS security")
                if dns_result.metrics.get("dns_leak_detected"):
                    recommendations.append("Configure DNS to prevent leaks")
                
            except Exception as e:
                findings.append({
                    "category": "DNS Security",
                    "severity": "error",
                    "finding": f"DNS security test failed: {str(e)}",
                })
        
        # Ensure score is within bounds
        audit_result.overall_score = max(0, min(100, audit_result.overall_score))
        
        # Determine risk level
        audit_result.risk_level = self._calculate_risk_level(audit_result.overall_score)
        
        # Store findings and recommendations
        audit_result.findings = findings
        audit_result.recommendations = recommendations
        
        # Log to CSV
        self._log_audit_result(audit_result)
        
        return audit_result
    
    def _analyze_ssl_result(self, result: TestResult) -> tuple[List[Dict], int]:
        """Analyze SSL test result and return findings and score."""
        findings = []
        score = 100
        
        if result.metrics.get("certificate_expired"):
            findings.append({
                "category": "SSL/TLS",
                "severity": "critical",
                "finding": "SSL certificate has expired",
            })
            score -= self.WEIGHTS["ssl_expired"]
        
        if result.metrics.get("key_size", 256) < 128:
            findings.append({
                "category": "SSL/TLS",
                "severity": "high",
                "finding": f"Weak cipher key size: {result.metrics.get('key_size')} bits",
            })
            score -= self.WEIGHTS["ssl_weak_cipher"]
        
        if not result.metrics.get("has_forward_secrecy"):
            findings.append({
                "category": "SSL/TLS",
                "severity": "medium",
                "finding": "No forward secrecy (ECDHE/DHE)",
            })
            score -= self.WEIGHTS["ssl_no_forward_secrecy"]
        
        if not result.metrics.get("supports_tls_1_2"):
            findings.append({
                "category": "SSL/TLS",
                "severity": "high",
                "finding": "TLS 1.2 not supported",
            })
            score -= self.WEIGHTS["ssl_old_protocol"]
        
        return findings, max(0, score)
    
    def _analyze_port_result(self, result: TestResult) -> tuple[List[Dict], int]:
        """Analyze port security result and return findings and score."""
        findings = []
        score = 100
        
        dangerous_ports = result.metrics.get("dangerous_ports", [])
        
        for port in dangerous_ports:
            findings.append({
                "category": "Port Security",
                "severity": "high",
                "finding": f"Dangerous port {port} is open",
            })
            score -= self.WEIGHTS["dangerous_port_open"]
        
        return findings, max(0, score)
    
    def _analyze_dns_result(self, result: TestResult) -> tuple[List[Dict], int]:
        """Analyze DNS security result and return findings and score."""
        findings = []
        score = 100
        
        if not result.metrics.get("has_dnssec"):
            findings.append({
                "category": "DNS Security",
                "severity": "low",
                "finding": "DNSSEC not enabled",
            })
            score -= self.WEIGHTS["no_dnssec"]
        
        if result.metrics.get("dns_leak_detected"):
            findings.append({
                "category": "DNS Security",
                "severity": "medium",
                "finding": "Potential DNS leak detected",
            })
            score -= self.WEIGHTS["dns_leak"]
        
        if result.metrics.get("dns_hijacked"):
            findings.append({
                "category": "DNS Security",
                "severity": "critical",
                "finding": "Potential DNS hijacking detected",
            })
            score -= self.WEIGHTS["dns_hijacking"]
        
        return findings, max(0, score)
    
    def _calculate_risk_level(self, score: int) -> str:
        """Calculate risk level from score."""
        if score >= 90:
            return "low"
        elif score >= 70:
            return "medium"
        elif score >= 50:
            return "high"
        else:
            return "critical"
    
    def _scan_common_ports(self, target: str) -> List[int]:
        """Scan common dangerous ports."""
        # In a real implementation, this would perform an actual scan
        # For now, return empty list (would need port scanner integration)
        return []
    
    def _log_audit_result(self, result: SecurityAuditResult) -> None:
        """Log audit result to CSV."""
        self.csv_handler.write_result(
            timestamp=result.timestamp,
            test_name="security_audit",
            target=result.target,
            metric="overall_score",
            value=str(result.overall_score),
            status=result.risk_level,
            details=f"Risk: {result.risk_level}, Findings: {len(result.findings)}, Recommendations: {len(result.recommendations)}",
        )


def format_audit_report(audit_result: SecurityAuditResult) -> str:
    """
    Format security audit result as a readable report.
    
    Args:
        audit_result: Security audit result
        
    Returns:
        Formatted report string
    """
    lines = []
    
    # Header
    lines.append("=" * 70)
    lines.append("SECURITY AUDIT REPORT")
    lines.append("=" * 70)
    lines.append(f"Target: {audit_result.target}")
    lines.append(f"Timestamp: {audit_result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Overall Score: {audit_result.overall_score}/100")
    lines.append(f"Risk Level: {audit_result.risk_level.upper()}")
    lines.append("=" * 70)
    
    # Findings
    if audit_result.findings:
        lines.append("\nFINDINGS:")
        lines.append("-" * 70)
        
        # Group by severity
        critical = [f for f in audit_result.findings if f.get("severity") == "critical"]
        high = [f for f in audit_result.findings if f.get("severity") == "high"]
        medium = [f for f in audit_result.findings if f.get("severity") == "medium"]
        low = [f for f in audit_result.findings if f.get("severity") == "low"]
        
        for severity, findings in [("CRITICAL", critical), ("HIGH", high), ("MEDIUM", medium), ("LOW", low)]:
            if findings:
                lines.append(f"\n{severity} Severity:")
                for finding in findings:
                    lines.append(f"  • [{finding['category']}] {finding['finding']}")
    else:
        lines.append("\n✓ No security issues found")
    
    # Recommendations
    if audit_result.recommendations:
        lines.append("\nRECOMMENDATIONS:")
        lines.append("-" * 70)
        for i, rec in enumerate(audit_result.recommendations, 1):
            lines.append(f"{i}. {rec}")
    
    lines.append("\n" + "=" * 70)
    
    return "\n".join(lines)
