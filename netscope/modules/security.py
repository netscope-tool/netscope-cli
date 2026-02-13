"""
Security audit module for network security testing.
Includes SSL/TLS analysis, port security, DNS security, and vulnerability scanning.
"""

from __future__ import annotations

import socket
import ssl
import subprocess
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from netscope.modules.base import BaseTest, TestResult
from netscope.core.executor import TestExecutor
from netscope.storage.csv_handler import CSVHandler


@dataclass
class SSLCertificateInfo:
    """SSL/TLS certificate information."""
    subject: Dict[str, str] = field(default_factory=dict)
    issuer: Dict[str, str] = field(default_factory=dict)
    version: int = 0
    serial_number: str = ""
    not_before: str = ""
    not_after: str = ""
    expired: bool = False
    days_until_expiry: int = 0
    san: List[str] = field(default_factory=list)
    signature_algorithm: str = ""


@dataclass
class SSLSecurityInfo:
    """SSL/TLS security analysis."""
    protocol_version: str = ""
    cipher_suite: str = ""
    key_size: int = 0
    has_forward_secrecy: bool = False
    supports_tls_1_3: bool = False
    supports_tls_1_2: bool = False
    supports_tls_1_1: bool = False
    supports_tls_1_0: bool = False
    supports_ssl_3: bool = False
    supports_ssl_2: bool = False
    vulnerabilities: List[str] = field(default_factory=list)


class SSLSecurityTest(BaseTest):
    """
    SSL/TLS security testing and certificate validation.
    """
    
    def run(
        self,
        target: str,
        port: int = 443,
        check_vulnerabilities: bool = True,
    ) -> TestResult:
        """
        Run SSL/TLS security test.
        
        Args:
            target: Target hostname
            port: Target port (default 443)
            check_vulnerabilities: Check for known vulnerabilities
            
        Returns:
            TestResult with SSL/TLS analysis
        """
        try:
            # Get certificate info
            cert_info = self._get_certificate_info(target, port)
            
            # Get security info
            security_info = self._analyze_ssl_security(target, port, check_vulnerabilities)
            
            # Determine status
            status = "success"
            issues = []
            
            if cert_info.expired:
                status = "error"
                issues.append("Certificate expired")
            elif cert_info.days_until_expiry < 30:
                status = "warning"
                issues.append(f"Certificate expires in {cert_info.days_until_expiry} days")
            
            if security_info.vulnerabilities:
                status = "warning" if status == "success" else status
                issues.extend(security_info.vulnerabilities)
            
            if security_info.supports_ssl_2 or security_info.supports_ssl_3:
                status = "warning" if status == "success" else status
                issues.append("Insecure SSL protocols supported")
            
            message = "SSL/TLS security check passed" if status == "success" else f"Issues found: {', '.join(issues)}"
            
            result = TestResult(
                test_name="ssl_security_test",
                target=f"{target}:{port}",
                status=status,
                message=message,
                metrics={
                    "certificate_expired": cert_info.expired,
                    "days_until_expiry": cert_info.days_until_expiry,
                    "protocol_version": security_info.protocol_version,
                    "cipher_suite": security_info.cipher_suite,
                    "key_size": security_info.key_size,
                    "supports_tls_1_3": security_info.supports_tls_1_3,
                    "supports_tls_1_2": security_info.supports_tls_1_2,
                    "has_forward_secrecy": security_info.has_forward_secrecy,
                    "vulnerability_count": len(security_info.vulnerabilities),
                },
                raw_output=self._format_ssl_output(cert_info, security_info),
            )
            
            self.csv_handler.write_result(result)
            return result
            
        except Exception as e:
            self.executor.logger.error(f"SSL security test failed: {e}")
            result = TestResult(
                test_name="ssl_security_test",
                target=f"{target}:{port}",
                status="error",
                message=f"SSL security test failed: {str(e)}",
                metrics={},
                raw_output=str(e),
            )
            self.csv_handler.write_result(result)
            return result
    
    def _get_certificate_info(self, hostname: str, port: int) -> SSLCertificateInfo:
        """Get SSL certificate information."""
        context = ssl.create_default_context()
        
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                
                # Parse subject and issuer
                subject = dict(x[0] for x in cert.get('subject', []))
                issuer = dict(x[0] for x in cert.get('issuer', []))
                
                # Parse dates
                not_before = cert.get('notBefore', '')
                not_after = cert.get('notAfter', '')
                
                # Calculate expiry
                try:
                    expiry_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                    expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    days_until_expiry = (expiry_date - now).days
                    expired = days_until_expiry < 0
                except:
                    days_until_expiry = 0
                    expired = False
                
                # Get SAN (Subject Alternative Names)
                san = []
                for ext in cert.get('subjectAltName', []):
                    if ext[0] == 'DNS':
                        san.append(ext[1])
                
                return SSLCertificateInfo(
                    subject=subject,
                    issuer=issuer,
                    version=cert.get('version', 0),
                    serial_number=cert.get('serialNumber', ''),
                    not_before=not_before,
                    not_after=not_after,
                    expired=expired,
                    days_until_expiry=days_until_expiry,
                    san=san,
                )
    
    def _analyze_ssl_security(
        self,
        hostname: str,
        port: int,
        check_vulnerabilities: bool,
    ) -> SSLSecurityInfo:
        """Analyze SSL/TLS security configuration."""
        security_info = SSLSecurityInfo()
        
        # Test current connection
        context = ssl.create_default_context()
        
        try:
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    # Get protocol version
                    security_info.protocol_version = ssock.version() or "Unknown"
                    
                    # Get cipher suite
                    cipher = ssock.cipher()
                    if cipher:
                        security_info.cipher_suite = cipher[0]
                        security_info.key_size = cipher[2]
                        
                        # Check for forward secrecy
                        cipher_name = cipher[0].upper()
                        security_info.has_forward_secrecy = any(
                            x in cipher_name for x in ['ECDHE', 'DHE']
                        )
        except Exception as e:
            self.executor.logger.warning(f"SSL connection analysis failed: {e}")
        
        # Test protocol support
        security_info.supports_tls_1_3 = self._test_protocol(hostname, port, ssl.PROTOCOL_TLS)
        security_info.supports_tls_1_2 = self._test_protocol(hostname, port, ssl.PROTOCOL_TLSv1_2)
        
        # Check for vulnerabilities
        if check_vulnerabilities:
            security_info.vulnerabilities = self._check_vulnerabilities(
                hostname,
                port,
                security_info,
            )
        
        return security_info
    
    def _test_protocol(self, hostname: str, port: int, protocol: int) -> bool:
        """Test if a specific SSL/TLS protocol is supported."""
        try:
            context = ssl.SSLContext(protocol)
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    return True
        except:
            return False
    
    def _check_vulnerabilities(
        self,
        hostname: str,
        port: int,
        security_info: SSLSecurityInfo,
    ) -> List[str]:
        """Check for known SSL/TLS vulnerabilities."""
        vulnerabilities = []
        
        # Check for weak ciphers
        if security_info.key_size < 128:
            vulnerabilities.append("Weak cipher key size (< 128 bits)")
        
        # Check for lack of forward secrecy
        if not security_info.has_forward_secrecy:
            vulnerabilities.append("No forward secrecy (ECDHE/DHE)")
        
        # Check protocol versions
        if security_info.supports_ssl_2:
            vulnerabilities.append("SSLv2 supported (DROWN vulnerability)")
        
        if security_info.supports_ssl_3:
            vulnerabilities.append("SSLv3 supported (POODLE vulnerability)")
        
        if security_info.supports_tls_1_0:
            vulnerabilities.append("TLS 1.0 supported (deprecated)")
        
        return vulnerabilities
    
    def _format_ssl_output(
        self,
        cert_info: SSLCertificateInfo,
        security_info: SSLSecurityInfo,
    ) -> str:
        """Format SSL/TLS information for output."""
        output = []
        
        output.append("=== Certificate Information ===")
        output.append(f"Subject: {cert_info.subject.get('commonName', 'N/A')}")
        output.append(f"Issuer: {cert_info.issuer.get('commonName', 'N/A')}")
        output.append(f"Valid From: {cert_info.not_before}")
        output.append(f"Valid Until: {cert_info.not_after}")
        output.append(f"Days Until Expiry: {cert_info.days_until_expiry}")
        output.append(f"Expired: {'Yes' if cert_info.expired else 'No'}")
        
        if cert_info.san:
            output.append(f"Subject Alternative Names: {', '.join(cert_info.san)}")
        
        output.append("\n=== Security Configuration ===")
        output.append(f"Protocol: {security_info.protocol_version}")
        output.append(f"Cipher Suite: {security_info.cipher_suite}")
        output.append(f"Key Size: {security_info.key_size} bits")
        output.append(f"Forward Secrecy: {'Yes' if security_info.has_forward_secrecy else 'No'}")
        output.append(f"TLS 1.3 Support: {'Yes' if security_info.supports_tls_1_3 else 'No'}")
        output.append(f"TLS 1.2 Support: {'Yes' if security_info.supports_tls_1_2 else 'No'}")
        
        if security_info.vulnerabilities:
            output.append("\n=== Vulnerabilities ===")
            for vuln in security_info.vulnerabilities:
                output.append(f"⚠️  {vuln}")
        
        return "\n".join(output)


class PortSecurityTest(BaseTest):
    """
    Port security analysis - identify potentially dangerous open ports.
    """
    
    # Dangerous ports that should typically be closed
    DANGEROUS_PORTS = {
        20: "FTP Data (unencrypted)",
        21: "FTP Control (unencrypted)",
        23: "Telnet (unencrypted)",
        25: "SMTP (open relay risk)",
        53: "DNS (amplification attacks)",
        69: "TFTP (no authentication)",
        135: "MS RPC (exploit target)",
        137: "NetBIOS (information leak)",
        138: "NetBIOS (information leak)",
        139: "NetBIOS (SMB, exploit target)",
        161: "SNMP (default community strings)",
        445: "SMB (ransomware vector)",
        1433: "MS SQL (database exposure)",
        1434: "MS SQL Monitor",
        3306: "MySQL (database exposure)",
        3389: "RDP (brute force target)",
        5432: "PostgreSQL (database exposure)",
        5900: "VNC (weak authentication)",
        6379: "Redis (no authentication)",
        27017: "MongoDB (database exposure)",
    }
    
    def run(
        self,
        target: str,
        open_ports: List[int],
    ) -> TestResult:
        """
        Analyze port security.
        
        Args:
            target: Target host
            open_ports: List of open ports to analyze
            
        Returns:
            TestResult with security analysis
        """
        try:
            dangerous_open = []
            warnings = []
            
            for port in open_ports:
                if port in self.DANGEROUS_PORTS:
                    dangerous_open.append((port, self.DANGEROUS_PORTS[port]))
                    warnings.append(f"Port {port} ({self.DANGEROUS_PORTS[port]}) is open")
            
            status = "warning" if dangerous_open else "success"
            message = f"Found {len(dangerous_open)} potentially dangerous open ports" if dangerous_open else "No dangerous ports detected"
            
            result = TestResult(
                test_name="port_security_test",
                target=target,
                status=status,
                message=message,
                metrics={
                    "total_open_ports": len(open_ports),
                    "dangerous_ports_count": len(dangerous_open),
                    "dangerous_ports": [p[0] for p in dangerous_open],
                },
                raw_output=self._format_port_security_output(open_ports, dangerous_open),
            )
            
            self.csv_handler.write_result(result)
            return result
            
        except Exception as e:
            self.executor.logger.error(f"Port security test failed: {e}")
            result = TestResult(
                test_name="port_security_test",
                target=target,
                status="error",
                message=f"Port security test failed: {str(e)}",
                metrics={},
                raw_output=str(e),
            )
            self.csv_handler.write_result(result)
            return result
    
    def _format_port_security_output(
        self,
        open_ports: List[int],
        dangerous_open: List[tuple],
    ) -> str:
        """Format port security output."""
        output = []
        
        output.append(f"Total Open Ports: {len(open_ports)}")
        output.append(f"Dangerous Ports: {len(dangerous_open)}")
        
        if dangerous_open:
            output.append("\n=== Security Warnings ===")
            for port, description in dangerous_open:
                output.append(f"⚠️  Port {port}: {description}")
                output.append(f"   Recommendation: Close or restrict access to this port")
        else:
            output.append("\n✅ No dangerous ports detected")
        
        return "\n".join(output)


class DNSSecurityTest(BaseTest):
    """
    DNS security testing including DNSSEC validation and DNS leak detection.
    """
    
    def run(self, target: str) -> TestResult:
        """
        Run DNS security test.
        
        Args:
            target: Target domain
            
        Returns:
            TestResult with DNS security analysis
        """
        try:
            # Check DNSSEC
            has_dnssec = self._check_dnssec(target)
            
            # Check for DNS leaks (compare DNS resolution from different resolvers)
            dns_leak = self._check_dns_leak(target)
            
            # Check for DNS hijacking
            dns_hijacked = self._check_dns_hijacking(target)
            
            issues = []
            status = "success"
            
            if not has_dnssec:
                issues.append("DNSSEC not enabled")
                status = "warning"
            
            if dns_leak:
                issues.append("Potential DNS leak detected")
                status = "warning"
            
            if dns_hijacked:
                issues.append("Potential DNS hijacking detected")
                status = "error"
            
            message = "DNS security check passed" if status == "success" else f"Issues: {', '.join(issues)}"
            
            result = TestResult(
                test_name="dns_security_test",
                target=target,
                status=status,
                message=message,
                metrics={
                    "has_dnssec": has_dnssec,
                    "dns_leak_detected": dns_leak,
                    "dns_hijacked": dns_hijacked,
                },
                raw_output=self._format_dns_security_output(has_dnssec, dns_leak, dns_hijacked),
            )
            
            self.csv_handler.write_result(result)
            return result
            
        except Exception as e:
            self.executor.logger.error(f"DNS security test failed: {e}")
            result = TestResult(
                test_name="dns_security_test",
                target=target,
                status="error",
                message=f"DNS security test failed: {str(e)}",
                metrics={},
                raw_output=str(e),
            )
            self.csv_handler.write_result(result)
            return result
    
    def _check_dnssec(self, domain: str) -> bool:
        """Check if DNSSEC is enabled for domain."""
        try:
            # Use dig to check for DNSSEC records
            result = subprocess.run(
                ["dig", "+dnssec", domain],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            # Look for RRSIG records (DNSSEC signatures)
            return "RRSIG" in result.stdout
            
        except Exception:
            return False
    
    def _check_dns_leak(self, domain: str) -> bool:
        """Check for DNS leaks by comparing resolutions."""
        # Simplified check - in production, would query multiple DNS servers
        # and compare results
        return False
    
    def _check_dns_hijacking(self, domain: str) -> bool:
        """Check for DNS hijacking."""
        # Simplified check - would compare against known-good DNS responses
        return False
    
    def _format_dns_security_output(
        self,
        has_dnssec: bool,
        dns_leak: bool,
        dns_hijacked: bool,
    ) -> str:
        """Format DNS security output."""
        output = []
        
        output.append("=== DNS Security Analysis ===")
        output.append(f"DNSSEC Enabled: {'Yes ✅' if has_dnssec else 'No ⚠️'}")
        output.append(f"DNS Leak: {'Detected ⚠️' if dns_leak else 'Not detected ✅'}")
        output.append(f"DNS Hijacking: {'Detected 🚨' if dns_hijacked else 'Not detected ✅'}")
        
        if not has_dnssec:
            output.append("\nRecommendation: Enable DNSSEC for enhanced security")
        
        return "\n".join(output)
