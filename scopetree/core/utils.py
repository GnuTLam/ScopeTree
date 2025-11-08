"""
Utility functions: chứa các hàm dùng chung, độc lập với domain cụ thể. 
Mục tiêu: tái sử dụng, giảm lặp code và chuẩn hoá các thao tác phổ biến.
"""
import re
from typing import List, Set

# Subdomain processing
def validate_domain(domain: str) -> bool:
    """
    Validate a domain name according to RFC standards.
    
    Args:
        domain: Domain name to validate (e.g., 'example.com', 'subdomain.example.co.uk')
        
    Returns:
        bool: True if domain is valid, False otherwise
    """
    if not isinstance(domain, str) or not domain.strip():
        return False

    domain = domain.strip().lower()
    

    if domain.endswith('.'):
        domain = domain[:-1]
    
    if not domain:
        return False
    
    try:
        domain_ascii = domain.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError, Exception):
        return False
    
    if len(domain_ascii) > 253:
        return False
    
    labels = domain_ascii.split('.')
    
    if len(labels) < 2:
        return False
    
    label_pattern = re.compile(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$', re.IGNORECASE)
    
    for i, label in enumerate(labels):
        if not (1 <= len(label) <= 63):
            return False
        
        if not label_pattern.match(label):
            return False
        
        if i == len(labels) - 1:
            if label.isdigit():
                return False
            if len(label) < 2:
                pass
    return True
    