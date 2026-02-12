"""
Network utility functions.
"""

import re
import socket


def is_valid_ip(ip: str) -> bool:
    """
    Check if a string is a valid IP address.
    
    Args:
        ip: String to check
        
    Returns:
        True if valid IP address
    """
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False


def is_valid_hostname(hostname: str) -> bool:
    """
    Check if a string is a valid hostname.
    
    Args:
        hostname: String to check
        
    Returns:
        True if valid hostname
    """
    if len(hostname) > 255:
        return False
    
    # Remove trailing dot
    if hostname.endswith('.'):
        hostname = hostname[:-1]
    
    # Check each label
    allowed = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$')

    return all(allowed.match(label) for label in hostname.split('.'))