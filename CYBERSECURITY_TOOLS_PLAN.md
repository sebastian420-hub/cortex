# Cybersecurity Tools Integration Plan for Cortex

## Executive Summary

This document outlines a comprehensive plan to add cybersecurity capabilities to Cortex, enabling it to perform security assessments, vulnerability scanning, and defensive security operations. The tools are designed with **safety-first** principles, requiring explicit permissions and operating in sandboxed modes.

---

## 1. Current Security Architecture Analysis

### 1.1 Existing Security Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Path Validation | `cortex/core/security.py` | Prevents directory traversal attacks |
| Dangerous Command Detection | `cortex/core/security.py` | Blocks harmful shell commands |
| Permission Modes | `cortex/models.py` | NORMAL/PLAN/AUTO_APPROVE modes |
| Transaction Rollback | `cortex/core/transaction.py` | File operation recovery |
| Tool Timeout System | `cortex/tools/base.py` | Prevents hanging operations |

### 1.2 Security Patterns Used

```python
# Current pattern for dangerous command detection
DANGEROUS_PATTERNS = [
    "rm -rf /", "mkfs.", "dd if=/dev/zero",
    ":(){ :|:& };:",  # Fork bomb
    "chmod 777 /", "chown root",
]
```

---

## 2. Proposed Cybersecurity Tool Suite

### 2.1 Reconnaissance Tools

#### 2.1.1 Port Scanner Tool
```python
class PortScanTool(Tool):
    """Network port scanning using nmap or pure Python"""
    
    Features:
    - Scan single IP or IP range
    - Scan specific ports or port ranges
    - Service version detection
    - Operating system fingerprinting (if permitted)
    - Export results in multiple formats
```

**Safety Considerations:**
- Only scan user-owned networks or explicit IPs
- Rate limiting to avoid being flagged as attack
- Default to non-intrusive SYN scans
- Require explicit permission for full-connect scans

#### 2.1.2 Network Discovery Tool
```python
class NetworkDiscoveryTool(Tool):
    """Discover devices on local network"""
    
    Features:
    - ARP scanning for local devices
    - Hostname resolution
    - MAC address vendor identification
    - Network topology mapping
```

### 2.2 Web Application Security

#### 2.2.1 Web Vulnerability Scanner
```python
class WebVulnScanTool(Tool):
    """Web application vulnerability assessment"""
    
    Features:
    - SQL injection detection
    - XSS (Cross-Site Scripting) detection
    - CSRF vulnerability checks
    - Security header analysis
    - SSL/TLS configuration scan
    
    Integration Options:
    - sqlmap API for SQL injection testing
    - OWASP ZAP API for comprehensive scanning
    - Custom Python scanners using requests/BeautifulSoup
```

#### 2.2.2 Directory/Endpoint Brute Forcer
```python
class DirBruteTool(Tool):
    """Directory and file enumeration"""
    
    Features:
    - Common directory wordlist
    - File extension enumeration
    - Status code filtering
    - Response size analysis
    - Hidden parameter discovery
```

### 2.3 System Security Assessment

#### 2.3.1 Configuration Audit Tool
```python
class ConfigAuditTool(Tool):
    """Audit system and application configurations"""
    
    Features:
    - SSH configuration audit
    - Database configuration check
    - Web server (Apache/Nginx) config review
    - Cloud storage (S3) permission audit
    - API key/token exposure detection
```

#### 2.3.2 File Integrity Monitor
```python
class FileIntegrityTool(Tool):
    """Monitor and verify file integrity"""
    
    Features:
    - Create baseline hash database
    - Detect file modifications
    - Monitor critical system files
    - Alert on unauthorized changes
```

### 2.4 Password Security

#### 2.4.1 Password Policy Auditor
```python
class PasswordAuditTool(Tool):
    """Audit password policies and strength"""
    
    Features:
    - Test password complexity requirements
    - Check against common password lists
    - Evaluate hashing algorithms in use
    - Test for default/weak credentials
    
    Safeguards:
    - No actual password cracking (only policy testing)
    - Hash-only analysis, never plaintext
```

### 2.5 Vulnerability Management

#### 2.5.1 CVE Lookup Tool
```python
class CVELookupTool(Tool):
    """Search and analyze CVE vulnerabilities"""
    
    Features:
    - Search CVE by keyword or product
    - Get detailed vulnerability information
    - Check exploit availability
    - Get remediation guidance
    
    Data Sources:
    - NVD (National Vulnerability Database) API
    - MITRE CVE database
```

#### 2.5.2 Exploit Checker
```python
class ExploitCheckTool(Tool):
    """Check for known exploits affecting systems"""
    
    Features:
    - Search Exploit-DB
    - Check Metasploit modules
    - Filter by verified exploits only
    - Show exploit complexity/impact
    
    Safety:
    - INFORMATIONAL ONLY
    - Never executes exploits
    - Requires explicit permission to search
```

---

## 3. Tool Architecture Design

### 3.1 Security Tool Base Class

```python
class SecurityTool(Tool):
    """Base class for all cybersecurity tools"""
    
    # Special security considerations
    requires_network_access: bool = True
    requires_root: bool = False
    scan_intensity: str = "passive"  # passive, light, medium, aggressive
    legal_disclaimer_required: bool = True
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._validate_legal_scope()
    
    def _validate_legal_scope(self):
        """Ensure scans are only performed on authorized targets"""
        pass
    
    def _check_rate_limit(self):
        """Prevent aggressive scanning that could be flagged as attack"""
        pass
```

### 3.2 Enhanced Permission System

```python
class SecurityPermissionMode:
    """Extended permission modes for security operations"""
    
    SCAN_PASSIVE = "scan_passive"      # Read-only reconnaissance
    SCAN_ACTIVE = "scan_active"        # Active probing with limits
    TEST_VULNERABILITY = "test_vuln"   # Non-destructive vulnerability tests
    FULL_PENTEST = "full_pentest"      # Comprehensive testing (requires explicit approval per action)
```

### 3.3 Target Authorization System

```python
@dataclass
class AuthorizedTarget:
    """Represents an authorized security scan target"""
    
    target: str  # IP, domain, or IP range
    authorized_by: str  # User who authorized
    authorization_time: datetime
    scope: List[str]  # Allowed scan types
    expiration: datetime
    max_intensity: str
```

---

## 4. Implementation Roadmap

### Phase 1: Foundation (Week 1)

#### 4.1.1 Create Security Module Structure
```
cortex/
├── tools/
│   └── security/
│       ├── __init__.py
│       ├── base.py              # SecurityTool base class
│       ├── reconnaissance.py    # PortScanTool, NetworkDiscoveryTool
│       ├── web_security.py      # WebVulnScanTool, DirBruteTool
│       ├── system_audit.py      # ConfigAuditTool, FileIntegrityTool
│       ├── vuln_management.py   # CVELookupTool, ExploitCheckTool
│       └── schemas.py           # Tool schemas
```

#### 4.1.2 Implement Base Security Infrastructure
- [ ] Create `SecurityTool` base class with enhanced safeguards
- [ ] Implement target authorization system
- [ ] Add security audit logging
- [ ] Create security-focused permission modes

### Phase 2: Reconnaissance Tools (Week 2)

#### 4.2.1 Port Scanner Implementation
```python
# Dependencies
# pip install python-nmap

class PortScanTool(SecurityTool):
    default_timeout = 300  # 5 minutes for comprehensive scans
    timeout_category = "security"
    
    def execute(
        self,
        target: str,
        ports: Union[str, List[int]] = "top-1000",
        scan_type: str = "syn",  # syn, connect, udp, comprehensive
        service_detection: bool = False,
        os_detection: bool = False,
        rate_limit: int = 1000,  # packets per second
    ) -> Dict[str, Any]:
        """
        Execute port scan with safety checks.
        
        Args:
            target: IP address, hostname, or CIDR range
            ports: Port specification (e.g., "80,443", "1-1000", "top-1000")
            scan_type: Type of scan to perform
            service_detection: Enable version detection
            os_detection: Enable OS fingerprinting (requires root)
            rate_limit: Maximum packets per second
        """
```

#### 4.2.2 Network Discovery
```python
class NetworkDiscoveryTool(SecurityTool):
    def execute(
        self,
        network: str,  # e.g., "192.168.1.0/24"
        method: str = "arp",  # arp, ping, both
        timeout: int = 60,
    ) -> Dict[str, Any]:
```

### Phase 3: Web Security Tools (Week 3)

#### 4.3.1 Web Vulnerability Scanner
```python
class WebVulnScanTool(SecurityTool):
    """Non-intrusive web vulnerability assessment"""
    
    def execute(
        self,
        url: str,
        checks: List[str] = None,  # ["headers", "ssl", "forms", "cors"]
        follow_redirects: bool = True,
        max_depth: int = 2,
    ) -> Dict[str, Any]:
```

#### 4.3.2 Directory Brute Forcer
```python
class DirBruteTool(SecurityTool):
    def execute(
        self,
        url: str,
        wordlist: str = "common",  # common, big, or custom path
        extensions: List[str] = None,
        threads: int = 10,
    ) -> Dict[str, Any]:
```

### Phase 4: System Audit Tools (Week 4)

#### 4.4.1 Configuration Auditor
```python
class ConfigAuditTool(SecurityTool):
    def execute(
        self,
        config_path: str,
        service_type: str,  # ssh, mysql, nginx, apache, etc.
        strict_mode: bool = False,
    ) -> Dict[str, Any]:
```

#### 4.4.2 File Integrity Monitor
```python
class FileIntegrityTool(SecurityTool):
    def execute(
        self,
        action: str,  # "create_baseline", "verify", "compare"
        paths: List[str],
        algorithm: str = "sha256",
    ) -> Dict[str, Any]:
```

### Phase 5: Vulnerability Management (Week 5)

#### 4.5.1 CVE Lookup
```python
class CVELookupTool(SecurityTool):
    def execute(
        self,
        query: str,
        search_type: str = "keyword",  # keyword, product, cve_id
        severity_filter: List[str] = None,  # ["Critical", "High", "Medium", "Low"]
        date_range: Tuple[str, str] = None,
    ) -> Dict[str, Any]:
```

#### 4.5.2 Exploit Database Search
```python
class ExploitCheckTool(SecurityTool):
    def execute(
        self,
        software: str,
        version: str = None,
        verified_only: bool = True,
    ) -> Dict[str, Any]:
```

---

## 5. Safety and Legal Framework

### 5.1 Legal Compliance

#### 5.1.1 Required Disclaimers
Every security tool must display:
```
⚠️  SECURITY TOOL NOTICE ⚠️

You are about to use a security scanning tool. By proceeding, you confirm:

1. You have explicit authorization to scan the target system(s)
2. You understand that unauthorized scanning may violate laws
3. You will use these tools only for defensive security purposes
4. You accept full responsibility for any actions taken

Target: {target}
Scope: {scope}
Intensity: {intensity}

Proceed? [y/N]
```

#### 5.1.2 Target Authorization Validation
```python
def validate_target_authorization(target: str) -> bool:
    """
    Ensure target is authorized for scanning.
    Checks:
    1. Is it a private IP range (10.x, 192.168.x, 172.16-31.x)?
    2. Is it a loopback address?
    3. Is it explicitly authorized by user?
    4. Does it match patterns in authorized_targets config?
    """
```

### 5.2 Technical Safeguards

#### 5.2.1 Rate Limiting
```python
class RateLimiter:
    """Prevent scans from being flagged as attacks"""
    
    def __init__(self, max_requests_per_second: int = 10):
        self.max_rps = max_requests_per_second
        self.request_times = []
    
    def check_and_wait(self):
        """Block if rate limit would be exceeded"""
        pass
```

#### 5.2.2 Scan Intensity Levels
```python
SCAN_INTENSITY_CONFIG = {
    "passive": {
        "max_packets_per_second": 1,
        "timeout_between_requests": 1.0,
        "max_threads": 1,
        "allowed_scan_types": ["syn", "service_detection"],
    },
    "light": {
        "max_packets_per_second": 10,
        "timeout_between_requests": 0.1,
        "max_threads": 5,
        "allowed_scan_types": ["syn", "connect", "service_detection"],
    },
    "medium": {
        "max_packets_per_second": 50,
        "timeout_between_requests": 0.02,
        "max_threads": 20,
        "allowed_scan_types": ["syn", "connect", "udp", "service_detection", "os_detection"],
    },
    "aggressive": {
        "max_packets_per_second": 100,
        "timeout_between_requests": 0.01,
        "max_threads": 50,
        "allowed_scan_types": ["all"],
        "requires_explicit_approval_per_action": True,
    },
}
```

### 5.3 Audit Logging

```python
class SecurityAuditLogger:
    """Log all security tool usage for accountability"""
    
    def log_scan_initiated(
        self,
        tool_name: str,
        target: str,
        user: str,
        scan_params: Dict,
    ):
        """Log when a scan is started"""
        pass
    
    def log_scan_completed(
        self,
        tool_name: str,
        target: str,
        findings_count: int,
        duration: float,
    ):
        """Log when a scan completes"""
        pass
```

---

## 6. Dependencies

### 6.1 Required Python Packages

```txt
# Security Tools Dependencies
python-nmap>=0.7.1       # Nmap integration
requests>=2.31.0         # HTTP requests for web scanning
beautifulsoup4>=4.12.0   # HTML parsing
cryptography>=41.0.0     # SSL/TLS analysis
scapy>=2.5.0             # Packet crafting (optional, powerful)
netaddr>=0.9.0           # Network address manipulation
```

### 6.2 System Dependencies

```bash
# Required system tools
nmap                     # Network scanning
openssl                  # SSL/TLS testing
# Optional but recommended
nikto                    # Web vulnerability scanner
sqlmap                   # SQL injection testing (external integration)
```

---

## 7. Example Usage

### 7.1 Port Scanning
```python
# User prompt: "Scan my local network for open ports"

# Agent executes with safety checks:
scan_result = port_scan_tool.execute(
    target="192.168.1.0/24",
    ports="top-100",
    scan_type="syn",
    rate_limit=100,
)

# Result:
{
    "success": True,
    "data": {
        "scan_summary": {
            "hosts_up": 5,
            "total_ports_scanned": 500,
            "open_ports_found": 12
        },
        "hosts": [
            {
                "ip": "192.168.1.1",
                "hostname": "router.local",
                "ports": [
                    {"port": 80, "service": "http", "state": "open"},
                    {"port": 443, "service": "https", "state": "open"},
                ]
            }
        ]
    }
}
```

### 7.2 Web Vulnerability Check
```python
# User prompt: "Check if my website has security vulnerabilities"

web_scan_result = web_vuln_scan_tool.execute(
    url="https://example.com",
    checks=["headers", "ssl", "forms"],
)
```

### 7.3 CVE Lookup
```python
# User prompt: "Are there any known vulnerabilities in Apache 2.4.41?"

cve_result = cve_lookup_tool.execute(
    query="Apache 2.4.41",
    search_type="product",
    severity_filter=["Critical", "High"],
)
```

---

## 8. Testing Strategy

### 8.1 Unit Tests
- Mock all external network calls
- Test permission validation logic
- Test rate limiting functionality
- Test target authorization

### 8.2 Integration Tests
- Use local test targets only (127.0.0.1, Docker containers)
- Test with intentionally vulnerable Docker images (DVWA, WebGoat)
- Verify scan results accuracy

### 8.3 Security Tests
- Test that unauthorized targets are blocked
- Test that dangerous operations require explicit approval
- Test rate limiting enforcement
- Test audit logging

---

## 9. Future Enhancements

### 9.1 Advanced Features (Future Phases)
- [ ] Integration with Metasploit Framework
- [ ] Automated vulnerability exploitation (with explicit permission)
- [ ] Compliance scanning (PCI-DSS, HIPAA, SOC2)
- [ ] Cloud security scanning (AWS, Azure, GCP)
- [ ] Container security scanning
- [ ] CI/CD security pipeline integration

### 9.2 Reporting
- [ ] Generate PDF security reports
- [ ] CVSS scoring for findings
- [ ] Remediation recommendations
- [ ] Trend analysis over time

---

## 10. Conclusion

This cybersecurity tool suite will make Cortex a powerful defensive security assistant while maintaining strict safety controls. The phased approach ensures careful implementation with proper safeguards at every step.

**Key Principles:**
1. **Safety First**: All tools require explicit authorization
2. **Legal Compliance**: Clear disclaimers and target validation
3. **Audit Trail**: Complete logging of all security activities
4. **Defense Focus**: Tools designed for security assessment, not attack
