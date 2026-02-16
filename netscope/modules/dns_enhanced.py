"""
Enhanced DNS tests with advanced query options.
Supports multiple record types, custom DNS servers, and detailed analysis.
"""

import re
import platform
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from netscope.modules.base import BaseTest, TestResult


@dataclass
class DNSOptions:
    """Advanced options for DNS queries."""
    record_type: str = "A"  # A, AAAA, MX, NS, TXT, CNAME, SOA, PTR, ANY
    dns_server: Optional[str] = None  # Custom DNS server (e.g., 8.8.8.8)
    timeout: int = 5  # Timeout in seconds
    tcp: bool = False  # Use TCP instead of UDP
    dnssec: bool = False  # Request DNSSEC validation
    
    def __post_init__(self):
        """Validate options."""
        valid_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "PTR", "ANY", "SRV"]
        if self.record_type.upper() not in valid_types:
            raise ValueError(f"Invalid record type. Must be one of: {', '.join(valid_types)}")
        self.record_type = self.record_type.upper()
        
        if self.timeout < 1 or self.timeout > 60:
            raise ValueError("Timeout must be between 1 and 60 seconds")


class DNSTestEnhanced(BaseTest):
    """Enhanced DNS test with advanced query options."""
    
    def run(self, target: str, options: Optional[DNSOptions] = None) -> TestResult:
        """
        Run enhanced DNS query.
        
        Args:
            target: Hostname or IP to query
            options: DNSOptions with advanced settings
            
        Returns:
            TestResult with DNS records and metrics
        """
        if options is None:
            options = DNSOptions()
        
        start_time = datetime.now()
        
        # Build DNS query command
        os_type = platform.system()
        command = self._build_command(target, options, os_type)
        
        # Execute command
        result = self.executor.run_command(command, timeout=options.timeout + 5)
        
        # Parse output
        metrics = self.parse_output(result.stdout, options, os_type) if result.success else {}
        
        # Add options to metrics
        metrics['record_type'] = options.record_type
        if options.dns_server:
            metrics['dns_server'] = options.dns_server
        
        # Determine status and summary
        status, summary = self._determine_status(target, result, metrics, options)
        
        test_result = TestResult(
            test_name=f"DNS Lookup ({options.record_type})",
            target=target,
            status=status,
            timestamp=start_time,
            duration=result.duration,
            metrics=metrics,
            summary=summary,
            raw_output=result.stdout,
            error=result.stderr if not result.success else None,
        )
        
        # Log to CSV
        self._log_to_csv(test_result)
        
        return test_result
    
    def _build_command(self, target: str, options: DNSOptions, os_type: str) -> List[str]:
        """Build DNS query command based on OS and options."""
        if os_type == "Windows":
            # Use nslookup on Windows
            command = ["nslookup"]
            
            # Set query type
            command.extend(["-type=" + options.record_type])
            
            # Set timeout
            command.extend(["-timeout=" + str(options.timeout)])
            
            # Target
            command.append(target)
            
            # Custom DNS server
            if options.dns_server:
                command.append(options.dns_server)
        
        else:
            # Use dig on Linux/macOS (more powerful)
            command = ["dig"]
            
            # Record type
            command.append(options.record_type)
            
            # Target
            command.append(target)
            
            # Custom DNS server
            if options.dns_server:
                command.append(f"@{options.dns_server}")
            
            # Timeout
            command.extend(["+time=" + str(options.timeout)])
            
            # TCP
            if options.tcp:
                command.append("+tcp")
            
            # DNSSEC
            if options.dnssec:
                command.append("+dnssec")
            
            # Additional useful flags
            command.append("+stats")  # Show query statistics
        
        return command
    
    def _determine_status(
        self,
        target: str,
        result,
        metrics: Dict[str, Any],
        options: DNSOptions
    ) -> tuple[str, str]:
        """Determine test status and create summary."""
        if not result.success:
            return "failure", f"DNS query failed: {result.stderr}"
        
        records = metrics.get('records', [])
        
        if not records:
            return "warning", f"No {options.record_type} records found for {target}"
        
        # Build summary based on record type
        summary_parts = [f"Found {len(records)} {options.record_type} record(s) for {target}"]
        
        # Show first few records
        if options.record_type in ["A", "AAAA"]:
            ips = [r.get('value', '') for r in records[:3]]
            summary_parts.append(f"IPs: {', '.join(ips)}")
        elif options.record_type == "MX":
            mx_list = [f"{r.get('value', '')} (priority {r.get('priority', 0)})" for r in records[:3]]
            summary_parts.append(f"Mail servers: {', '.join(mx_list)}")
        elif options.record_type == "NS":
            ns_list = [r.get('value', '') for r in records[:3]]
            summary_parts.append(f"Name servers: {', '.join(ns_list)}")
        elif options.record_type == "TXT":
            txt_list = [r.get('value', '')[:50] for r in records[:2]]
            summary_parts.append(f"TXT: {', '.join(txt_list)}")
        else:
            values = [str(r.get('value', ''))[:50] for r in records[:3]]
            summary_parts.append(f"Values: {', '.join(values)}")
        
        # Query time
        query_time = metrics.get('query_time_ms')
        if query_time is not None:
            summary_parts.append(f"Query time: {query_time:.0f} ms")
        
        summary = ". ".join(summary_parts) + "."
        
        return "success", summary
    
    def parse_output(self, output: str, options: DNSOptions, os_type: str) -> Dict[str, Any]:
        """Parse DNS query output based on record type and OS."""
        metrics = {}
        records = []
        
        if os_type == "Windows":
            records = self._parse_nslookup(output, options.record_type)
        else:
            records = self._parse_dig(output, options.record_type)
        
        metrics['records'] = records
        metrics['record_count'] = len(records)
        
        # Parse query time from dig output
        if os_type != "Windows":
            time_match = re.search(r'Query time:\s+(\d+)\s+msec', output)
            if time_match:
                metrics['query_time_ms'] = int(time_match.group(1))
            
            # Parse server used
            server_match = re.search(r'SERVER:\s+([^\s#]+)', output)
            if server_match:
                metrics['server_used'] = server_match.group(1)
        
        return metrics
    
    def _parse_nslookup(self, output: str, record_type: str) -> List[Dict[str, Any]]:
        """Parse nslookup output."""
        records = []
        
        if record_type in ["A", "AAAA"]:
            # IPv4 pattern
            ipv4_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
            # IPv6 pattern
            ipv6_pattern = re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){1,7}[0-9a-fA-F]{1,4}\b|::1')
            
            for line in output.split('\n'):
                if 'Address' in line and ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        ip = parts[1].strip()
                        if (record_type == "A" and ipv4_pattern.match(ip)) or \
                           (record_type == "AAAA" and ipv6_pattern.search(ip)):
                            records.append({'value': ip, 'type': record_type})
        
        elif record_type == "MX":
            # MX records: "mail exchanger = 10 mail.example.com"
            mx_pattern = re.compile(r'mail exchanger\s*=\s*(\d+)\s+(\S+)')
            for line in output.split('\n'):
                match = mx_pattern.search(line)
                if match:
                    records.append({
                        'value': match.group(2).rstrip('.'),
                        'priority': int(match.group(1)),
                        'type': 'MX'
                    })
        
        elif record_type == "NS":
            # NS records: "nameserver = ns1.example.com"
            ns_pattern = re.compile(r'nameserver\s*=\s*(\S+)')
            for line in output.split('\n'):
                match = ns_pattern.search(line)
                if match:
                    records.append({
                        'value': match.group(1).rstrip('.'),
                        'type': 'NS'
                    })
        
        elif record_type == "TXT":
            # TXT records can span multiple lines
            in_txt = False
            txt_value = ""
            for line in output.split('\n'):
                if 'text =' in line.lower():
                    in_txt = True
                    txt_value = line.split('=', 1)[1].strip().strip('"')
                elif in_txt and line.strip().startswith('"'):
                    txt_value += " " + line.strip().strip('"')
                elif in_txt and txt_value:
                    records.append({'value': txt_value, 'type': 'TXT'})
                    in_txt = False
                    txt_value = ""
        
        elif record_type == "CNAME":
            # CNAME: "canonical name = www.example.com"
            cname_pattern = re.compile(r'canonical name\s*=\s*(\S+)')
            for line in output.split('\n'):
                match = cname_pattern.search(line)
                if match:
                    records.append({
                        'value': match.group(1).rstrip('.'),
                        'type': 'CNAME'
                    })
        
        return records
    
    def _parse_dig(self, output: str, record_type: str) -> List[Dict[str, Any]]:
        """Parse dig output."""
        records = []
        
        # Find ANSWER SECTION
        answer_section = False
        for line in output.split('\n'):
            line = line.strip()
            
            if ';; ANSWER SECTION:' in line:
                answer_section = True
                continue
            
            if answer_section:
                # End of answer section
                if line.startswith(';;') or not line:
                    break
                
                # Parse record line: example.com. 300 IN A 93.184.216.34
                parts = line.split()
                if len(parts) >= 5:
                    rec_type = parts[3]
                    
                    if rec_type == "A" or rec_type == "AAAA":
                        records.append({
                            'value': parts[4],
                            'ttl': int(parts[1]) if parts[1].isdigit() else 0,
                            'type': rec_type
                        })
                    
                    elif rec_type == "MX":
                        if len(parts) >= 6:
                            records.append({
                                'value': parts[5].rstrip('.'),
                                'priority': int(parts[4]),
                                'ttl': int(parts[1]) if parts[1].isdigit() else 0,
                                'type': 'MX'
                            })
                    
                    elif rec_type == "NS":
                        records.append({
                            'value': parts[4].rstrip('.'),
                            'ttl': int(parts[1]) if parts[1].isdigit() else 0,
                            'type': 'NS'
                        })
                    
                    elif rec_type == "TXT":
                        txt_value = ' '.join(parts[4:]).strip('"')
                        records.append({
                            'value': txt_value,
                            'ttl': int(parts[1]) if parts[1].isdigit() else 0,
                            'type': 'TXT'
                        })
                    
                    elif rec_type == "CNAME":
                        records.append({
                            'value': parts[4].rstrip('.'),
                            'ttl': int(parts[1]) if parts[1].isdigit() else 0,
                            'type': 'CNAME'
                        })
                    
                    elif rec_type == "SOA":
                        if len(parts) >= 6:
                            records.append({
                                'value': f"{parts[4]} {parts[5]}",
                                'ttl': int(parts[1]) if parts[1].isdigit() else 0,
                                'type': 'SOA'
                            })
        
        return records
    
    def _log_to_csv(self, result: TestResult):
        """Log result to CSV."""
        # Log aggregate metrics
        for metric_name, metric_value in result.metrics.items():
            if metric_name == 'records':
                continue  # Skip detailed records
            
            if isinstance(metric_value, (int, float)):
                self.csv_handler.write_result(
                    timestamp=result.timestamp,
                    test_name=result.test_name,
                    target=result.target,
                    metric=metric_name,
                    value=metric_value,
                    status=result.status,
                    details=result.summary or "",
                )
