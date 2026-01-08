# SecurityAgent - Ethical Hacking & Cybersecurity AI Agent

## ⚠️ LEGAL DISCLAIMER

**YOU MUST:**
- ✅ Have written authorization for ALL testing
- ✅ Stay within defined scope
- ✅ Follow responsible disclosure
- ✅ Comply with all laws and regulations

**NEVER:**
- ❌ Test systems without permission
- ❌ Exploit vulnerabilities maliciously
- ❌ Access unauthorized systems
- ❌ Create malware for malicious purposes

**Unauthorized access is a FEDERAL CRIME.**

---

## 🎯 Project Vision

Transform LocalAgent into SecurityAgent - an AI-powered ethical hacking assistant that:
- Automates penetration testing workflows
- Analyzes code for vulnerabilities
- Assists with security audits
- Generates security reports
- Follows ethical guidelines strictly

---

## 🏗️ Architecture Design

### System Architecture

```
SecurityAgent
├── LocalAgent Core (existing)
│   ├── Agent Loop
│   ├── Tool System
│   └── Conversation Manager
├── Security Tools Module (NEW)
│   ├── Reconnaissance Tools
│   ├── Vulnerability Scanning
│   ├── Exploitation Tools (ethical)
│   ├── Post-Exploitation
│   └── Reporting Tools
├── Security Knowledge Base (NEW)
│   ├── CVE Database
│   ├── Exploit Database
│   ├── Security Patterns
│   └── OWASP Guidelines
├── Authorization System (NEW)
│   ├── Scope Validation
│   ├── Permission Checking
│   └── Audit Logging
└── Safety Layer (CRITICAL)
    ├── Target Validation
    ├── Action Approval
    └── Legal Compliance
```

---

## 🔧 Security Tools to Add

### Phase 1: Reconnaissance Tools

**New file:** `localagent/tools/recon_tools.py`

```python
"""Reconnaissance tools for ethical security testing"""

import subprocess
import json
from typing import Dict, Any, Optional
from .base import Tool

class NmapScanTool(Tool):
    """Network scanning with Nmap (requires authorization)"""
    
    def execute(
        self, 
        target: str, 
        scan_type: str = "basic",
        authorization_code: str = None
    ) -> Dict[str, Any]:
        """
        Perform network scan with Nmap
        
        Args:
            target: Target IP/domain (must be authorized)
            scan_type: basic, full, vuln, stealth
            authorization_code: Required authorization proof
        """
        # CRITICAL: Validate authorization
        if not self._validate_authorization(target, authorization_code):
            return {
                "error": "Authorization required. Provide proof of permission.",
                "legal_warning": "Unauthorized scanning is illegal."
            }
        
        # Log for audit trail
        self._log_security_action("nmap_scan", target, authorization_code)
        
        # Build nmap command
        scan_commands = {
            "basic": ["nmap", "-sV", target],
            "full": ["nmap", "-sV", "-sC", "-p-", target],
            "vuln": ["nmap", "--script=vuln", target],
            "stealth": ["nmap", "-sS", "-sV", target]
        }
        
        cmd = scan_commands.get(scan_type, scan_commands["basic"])
        
        # Show what we're doing
        if self.console:
            self.console.print(f"[yellow]🔍 Scanning:[/yellow] {target}")
            self.console.print(f"[dim]Authorization: {authorization_code[:8]}...[/dim]")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 min timeout
            )
            
            return {
                "success": True,
                "output": result.stdout,
                "scan_type": scan_type,
                "target": target,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _validate_authorization(self, target: str, auth_code: str) -> bool:
        """
        Validate that we have authorization to scan target
        
        In production:
        - Check against authorization database
        - Verify scope boundaries
        - Validate time windows
        """
        if not auth_code:
            return False
        
        # Load authorized targets
        auth_file = Path.home() / ".securityagent" / "authorized_targets.json"
        if not auth_file.exists():
            return False
        
        with open(auth_file) as f:
            authorized = json.load(f)
        
        # Check if target is authorized
        for auth in authorized:
            if auth["target"] == target and auth["code"] == auth_code:
                # Check expiration
                expiry = datetime.fromisoformat(auth["expires"])
                if datetime.now() < expiry:
                    return True
        
        return False
    
    def _log_security_action(self, action: str, target: str, auth: str):
        """Log all security actions for audit trail"""
        log_file = Path.home() / ".securityagent" / "audit.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {action} | {target} | {auth}\n")


class SubdomainEnumTool(Tool):
    """Subdomain enumeration (requires authorization)"""
    
    def execute(self, domain: str, authorization_code: str = None) -> Dict[str, Any]:
        """Enumerate subdomains using various techniques"""
        # Same authorization pattern
        pass


class DNSReconTool(Tool):
    """DNS reconnaissance (requires authorization)"""
    
    def execute(self, domain: str, authorization_code: str = None) -> Dict[str, Any]:
        """DNS enumeration and analysis"""
        pass


class WhoisLookupTool(Tool):
    """WHOIS information gathering (generally legal for public info)"""
    
    def execute(self, domain: str) -> Dict[str, Any]:
        """Lookup WHOIS information"""
        try:
            result = subprocess.run(
                ["whois", domain],
                capture_output=True,
                text=True,
                timeout=30
            )
            return {"success": True, "output": result.stdout}
        except Exception as e:
            return {"error": str(e)}
```

### Phase 2: Vulnerability Scanning

**New file:** `localagent/tools/vuln_scan_tools.py`

```python
"""Vulnerability scanning tools"""

class NiktoScanTool(Tool):
    """Web vulnerability scanning with Nikto"""
    
    def execute(self, url: str, authorization_code: str = None) -> Dict[str, Any]:
        """Scan web application for vulnerabilities"""
        if not self._validate_authorization(url, authorization_code):
            return {"error": "Authorization required"}
        
        try:
            result = subprocess.run(
                ["nikto", "-h", url, "-Format", "json"],
                capture_output=True,
                text=True,
                timeout=600  # 10 min
            )
            return {"success": True, "output": result.stdout}
        except Exception as e:
            return {"error": str(e)}


class SQLMapTool(Tool):
    """SQL injection testing with sqlmap"""
    
    def execute(
        self, 
        url: str, 
        parameter: str = None,
        authorization_code: str = None
    ) -> Dict[str, Any]:
        """Test for SQL injection vulnerabilities"""
        # CRITICAL: This is powerful and dangerous
        # Must have explicit authorization
        if not self._validate_authorization(url, authorization_code):
            return {
                "error": "Explicit authorization required for SQLMap",
                "legal_warning": "SQL injection testing without permission is illegal"
            }
        
        # Additional confirmation
        if self.console:
            from rich.prompt import Confirm
            confirmed = Confirm.ask(
                f"[red]⚠️  SQLMap can be intrusive. Confirm you have written authorization?[/red]"
            )
            if not confirmed:
                return {"error": "User cancelled - authorization not confirmed"}
        
        # Build sqlmap command
        cmd = ["sqlmap", "-u", url]
        if parameter:
            cmd.extend(["-p", parameter])
        cmd.extend(["--batch", "--level=1", "--risk=1"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            return {"success": True, "output": result.stdout}
        except Exception as e:
            return {"error": str(e)}


class BurpScanTool(Tool):
    """Integration with Burp Suite (requires Burp Pro)"""
    
    def execute(self, target: str, authorization_code: str = None) -> Dict[str, Any]:
        """Run Burp Suite scan via REST API"""
        # Integrate with Burp Suite REST API
        pass


class DependencyCheckTool(Tool):
    """Check dependencies for known vulnerabilities (safe, no authorization needed)"""
    
    def execute(self, project_dir: str = ".") -> Dict[str, Any]:
        """Scan dependencies for CVEs"""
        try:
            # For Python projects
            result = subprocess.run(
                ["safety", "check", "--json"],
                capture_output=True,
                text=True,
                cwd=project_dir,
                timeout=60
            )
            
            vulnerabilities = json.loads(result.stdout)
            
            if self.console:
                if vulnerabilities:
                    self.console.print(f"[red]⚠️  Found {len(vulnerabilities)} vulnerabilities[/red]")
                else:
                    self.console.print("[green]✓ No known vulnerabilities[/green]")
            
            return {"success": True, "vulnerabilities": vulnerabilities}
        except Exception as e:
            return {"error": str(e)}
```

### Phase 3: Code Security Analysis

**New file:** `localagent/tools/code_security_tools.py`

```python
"""Code security analysis tools"""

class BanditScanTool(Tool):
    """Python security linting with Bandit"""
    
    def execute(self, path: str = ".") -> Dict[str, Any]:
        """Scan Python code for security issues"""
        try:
            result = subprocess.run(
                ["bandit", "-r", path, "-f", "json"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            issues = json.loads(result.stdout)
            
            # Display summary
            if self.console:
                high = len([i for i in issues.get("results", []) if i["severity"] == "HIGH"])
                medium = len([i for i in issues.get("results", []) if i["severity"] == "MEDIUM"])
                
                self.console.print(f"[red]High severity: {high}[/red]")
                self.console.print(f"[yellow]Medium severity: {medium}[/yellow]")
            
            return {"success": True, "issues": issues}
        except Exception as e:
            return {"error": str(e)}


class SemgrepSecurityTool(Tool):
    """Security-focused static analysis with Semgrep"""
    
    def execute(self, path: str = ".") -> Dict[str, Any]:
        """Run Semgrep security rules"""
        try:
            result = subprocess.run(
                ["semgrep", "--config=auto", "--json", path],
                capture_output=True,
                text=True,
                timeout=180
            )
            
            findings = json.loads(result.stdout)
            return {"success": True, "findings": findings}
        except Exception as e:
            return {"error": str(e)}


class SecretScannerTool(Tool):
    """Scan for hardcoded secrets and credentials"""
    
    def execute(self, path: str = ".") -> Dict[str, Any]:
        """Detect hardcoded secrets using truffleHog or gitleaks"""
        try:
            # Use gitleaks
            result = subprocess.run(
                ["gitleaks", "detect", "--source", path, "--report-format", "json"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            secrets = json.loads(result.stdout) if result.stdout else []
            
            if self.console and secrets:
                self.console.print(f"[red]🚨 Found {len(secrets)} potential secrets![/red]")
            
            return {"success": True, "secrets": secrets}
        except Exception as e:
            return {"error": str(e)}
```

### Phase 4: Exploitation Framework Integration

**New file:** `localagent/tools/exploit_tools.py`

```python
"""Exploitation tools (EXTREME CAUTION REQUIRED)"""

class MetasploitTool(Tool):
    """
    Integration with Metasploit Framework
    
    ⚠️  CRITICAL WARNING ⚠️ 
    - Requires explicit written authorization
    - Only use in controlled environments
    - Log all actions for audit
    - Can cause system damage if misused
    """
    
    def execute(
        self,
        exploit: str,
        target: str,
        options: Dict[str, str],
        authorization_code: str = None,
        dry_run: bool = True  # Default to safe mode
    ) -> Dict[str, Any]:
        """
        Execute Metasploit exploit
        
        Args:
            exploit: Metasploit module path (e.g., "exploit/windows/smb/ms17_010_eternalblue")
            target: Target IP/host
            options: Exploit options (RHOST, LHOST, etc.)
            authorization_code: REQUIRED authorization proof
            dry_run: If True, only show what would be done (safe)
        """
        # TRIPLE authorization check
        if not authorization_code:
            return {
                "error": "Authorization code REQUIRED for exploitation",
                "legal_warning": "Unauthorized exploitation is a serious crime"
            }
        
        if not self._validate_authorization(target, authorization_code):
            return {
                "error": "Invalid or expired authorization",
                "contact": "Obtain proper authorization before proceeding"
            }
        
        # Require explicit confirmation
        if self.console and not dry_run:
            from rich.prompt import Confirm
            self.console.print("[red bold]⚠️  EXPLOITATION ATTEMPT ⚠️[/red bold]")
            self.console.print(f"Exploit: {exploit}")
            self.console.print(f"Target: {target}")
            self.console.print(f"Authorization: {authorization_code[:8]}...")
            
            confirmed = Confirm.ask(
                "[red]You have WRITTEN AUTHORIZATION for this action?[/red]"
            )
            if not confirmed:
                return {"error": "Exploitation cancelled - authorization not confirmed"}
        
        # Log EVERYTHING
        self._log_exploitation_attempt(exploit, target, authorization_code, dry_run)
        
        if dry_run:
            # Safe mode - just show what would happen
            return {
                "dry_run": True,
                "message": "DRY RUN - No actual exploitation performed",
                "would_execute": {
                    "exploit": exploit,
                    "target": target,
                    "options": options
                }
            }
        
        # ACTUAL EXPLOITATION (use with extreme caution)
        try:
            # Build msfconsole resource file
            rc_file = self._create_msf_resource_file(exploit, target, options)
            
            # Execute via msfconsole
            result = subprocess.run(
                ["msfconsole", "-r", rc_file, "-x", "exit"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            return {
                "success": True,
                "output": result.stdout,
                "audit_logged": True
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _log_exploitation_attempt(self, exploit, target, auth, dry_run):
        """Log ALL exploitation attempts - critical for legal protection"""
        log_file = Path.home() / ".securityagent" / "exploitation_audit.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(f"""
{'='*80}
Timestamp: {datetime.now().isoformat()}
Action: {'DRY_RUN' if dry_run else 'EXPLOITATION_ATTEMPT'}
Exploit: {exploit}
Target: {target}
Authorization: {auth}
User: {os.getenv('USER', 'unknown')}
{'='*80}
""")


class ExploitDBSearchTool(Tool):
    """Search ExploitDB for known exploits (informational only)"""
    
    def execute(self, query: str) -> Dict[str, Any]:
        """Search ExploitDB database"""
        try:
            result = subprocess.run(
                ["searchsploit", query, "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            exploits = json.loads(result.stdout)
            return {"success": True, "exploits": exploits}
        except Exception as e:
            return {"error": str(e)}
```

### Phase 5: Reporting Tools

**New file:** `localagent/tools/security_report_tools.py`

```python
"""Security reporting and documentation tools"""

class PentestReportTool(Tool):
    """Generate penetration test reports"""
    
    def execute(
        self,
        findings: List[Dict],
        client: str,
        scope: str,
        format: str = "markdown"
    ) -> Dict[str, Any]:
        """
        Generate professional penetration test report
        
        Args:
            findings: List of vulnerabilities found
            client: Client name
            scope: Testing scope
            format: markdown, html, pdf
        """
        # Generate report sections
        report = self._generate_report_structure(findings, client, scope)
        
        if format == "markdown":
            output = self._format_as_markdown(report)
        elif format == "html":
            output = self._format_as_html(report)
        elif format == "pdf":
            output = self._format_as_pdf(report)
        
        # Save report
        report_file = f"pentest_report_{client}_{datetime.now().strftime('%Y%m%d')}.{format}"
        Path(report_file).write_text(output)
        
        return {
            "success": True,
            "report_file": report_file,
            "findings_count": len(findings)
        }
    
    def _generate_report_structure(self, findings, client, scope):
        """Generate standardized report structure"""
        return {
            "executive_summary": self._generate_executive_summary(findings),
            "scope": scope,
            "methodology": self._generate_methodology(),
            "findings": self._categorize_findings(findings),
            "recommendations": self._generate_recommendations(findings),
            "appendix": self._generate_appendix()
        }


class CVSSCalculatorTool(Tool):
    """Calculate CVSS scores for vulnerabilities"""
    
    def execute(self, vulnerability: Dict) -> Dict[str, Any]:
        """Calculate CVSS v3.1 score"""
        # Implement CVSS calculation
        pass


class RiskMatrixTool(Tool):
    """Generate risk matrix visualization"""
    
    def execute(self, findings: List[Dict]) -> Dict[str, Any]:
        """Create risk matrix from findings"""
        # Create visual risk matrix
        pass
```

---

## 🔐 Authorization System

**New file:** `localagent/core/authorization.py`

```python
"""Authorization and scope management for security testing"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class AuthorizationManager:
    """Manage security testing authorizations"""
    
    def __init__(self):
        self.auth_file = Path.home() / ".securityagent" / "authorized_targets.json"
        self.auth_file.parent.mkdir(exist_ok=True)
        
        if not self.auth_file.exists():
            self.auth_file.write_text("[]")
    
    def add_authorization(
        self,
        target: str,
        scope: List[str],
        expires_days: int = 30,
        notes: str = "",
        client: str = ""
    ) -> str:
        """
        Add new authorization for security testing
        
        Returns:
            Authorization code to use with tools
        """
        import uuid
        
        auth_code = str(uuid.uuid4())
        
        authorization = {
            "code": auth_code,
            "target": target,
            "scope": scope,
            "expires": (datetime.now() + timedelta(days=expires_days)).isoformat(),
            "created": datetime.now().isoformat(),
            "client": client,
            "notes": notes
        }
        
        # Load existing authorizations
        with open(self.auth_file) as f:
            authorizations = json.load(f)
        
        authorizations.append(authorization)
        
        # Save updated list
        with open(self.auth_file, "w") as f:
            json.dump(authorizations, f, indent=2)
        
        return auth_code
    
    def validate(self, target: str, auth_code: str) -> bool:
        """Validate authorization for target"""
        with open(self.auth_file) as f:
            authorizations = json.load(f)
        
        for auth in authorizations:
            if auth["code"] == auth_code and auth["target"] == target:
                # Check expiration
                expires = datetime.fromisoformat(auth["expires"])
                if datetime.now() < expires:
                    return True
        
        return False
    
    def list_authorizations(self) -> List[Dict]:
        """List all active authorizations"""
        with open(self.auth_file) as f:
            authorizations = json.load(f)
        
        # Filter expired
        active = [
            auth for auth in authorizations
            if datetime.fromisoformat(auth["expires"]) > datetime.now()
        ]
        
        return active
    
    def revoke(self, auth_code: str):
        """Revoke an authorization"""
        with open(self.auth_file) as f:
            authorizations = json.load(f)
        
        authorizations = [a for a in authorizations if a["code"] != auth_code]
        
        with open(self.auth_file, "w") as f:
            json.dump(authorizations, f, indent=2)
```

---

## 📋 Tool Definitions

**Add to `localagent/tools/__init__.py`:**

```python
SECURITY_TOOLS = [
    # Reconnaissance
    {
        "type": "function",
        "function": {
            "name": "nmap_scan",
            "description": "Network scanning with Nmap. REQUIRES AUTHORIZATION.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target IP or domain"},
                    "scan_type": {"type": "string", "enum": ["basic", "full", "vuln", "stealth"]},
                    "authorization_code": {"type": "string", "description": "REQUIRED authorization proof"}
                },
                "required": ["target", "authorization_code"]
            }
        }
    },
    
    # Vulnerability Scanning
    {
        "type": "function",
        "function": {
            "name": "dependency_check",
            "description": "Check project dependencies for known vulnerabilities (CVEs). No authorization needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_dir": {"type": "string", "description": "Project directory to scan"}
                }
            }
        }
    },
    
    # Code Security
    {
        "type": "function",
        "function": {
            "name": "bandit_scan",
            "description": "Scan Python code for security issues. No authorization needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to scan"}
                }
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "secret_scanner",
            "description": "Scan for hardcoded secrets and credentials. No authorization needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to scan"}
                }
            }
        }
    },
    
    # Reporting
    {
        "type": "function",
        "function": {
            "name": "generate_pentest_report",
            "description": "Generate professional penetration test report",
            "parameters": {
                "type": "object",
                "properties": {
                    "client": {"type": "string"},
                    "scope": {"type": "string"},
                    "format": {"type": "string", "enum": ["markdown", "html", "pdf"]}
                },
                "required": ["client", "scope"]
            }
        }
    }
]
```

---

## 🎓 Usage Examples

### Example 1: Bug Bounty Workflow

```bash
# 1. Add authorization for bug bounty program
securityagent auth add \
  --target example.com \
  --scope "Web application testing only" \
  --expires 30 \
  --notes "HackerOne program"

# Authorization code: abc123-def456-...

# 2. Start reconnaissance
securityagent --model qwen2.5:7b

> I need to test example.com for vulnerabilities
> Authorization code: abc123-def456-...
> Start with subdomain enumeration

🤖 I'll begin reconnaissance:
   1. First, let me enumerate subdomains
   2. Then check for common vulnerabilities
   3. Finally, generate a report

> [Executes authorized tools]

# 3. Generate report
> generate penetration test report for client "Example Corp"
```

### Example 2: Internal Security Audit

```bash
securityagent

> audit this codebase for security issues
> check dependencies for CVEs
> scan for hardcoded secrets
> identify OWASP Top 10 vulnerabilities
> generate security report
```

### Example 3: Responsible Disclosure

```bash
securityagent

> I found a vulnerability in my company's application
> Help me write a responsible disclosure report
> Include: description, impact, remediation steps
```

---

## 🎯 Implementation Roadmap

### Week 1: Foundation
- [ ] Add authorization system
- [ ] Implement audit logging
- [ ] Add safe tools (dependency check, code scanning)
- [ ] Test with legal targets only

### Week 2: Reconnaissance
- [ ] Add nmap integration
- [ ] Add subdomain enumeration
- [ ] Add WHOIS/DNS tools
- [ ] Test on authorized targets

### Week 3: Vulnerability Scanning
- [ ] Add Nikto integration
- [ ] Add Bandit/Semgrep
- [ ] Add secret scanning
- [ ] Comprehensive testing

### Week 4: Reporting
- [ ] Report generation
- [ ] Risk assessment
- [ ] Documentation tools
- [ ] Polish UI

---

## ⚖️ Legal Compliance Checklist

Before using SecurityAgent:

- [ ] Written authorization from target owner
- [ ] Defined scope of testing
- [ ] Clear rules of engagement
- [ ] Incident response plan
- [ ] Non-disclosure agreement (if needed)
- [ ] Audit logging enabled
- [ ] Insurance coverage (professional liability)
- [ ] Emergency contact information
- [ ] Data handling procedures
- [ ] Responsible disclosure policy

---

## 🎓 Recommended Certifications

To use SecurityAgent professionally:

**Essential:**
- CEH (Certified Ethical Hacker) - $1,199
- OSCP (Offensive Security Certified Professional) - $1,649
- Security+ - $381

**Advanced:**
- OSWE (Web Application Testing)
- GPEN (GIAC Penetration Tester)
- OSCE (Offensive Security Certified Expert)

**These prove you understand legal and ethical boundaries.**

---

## 📚 Learning Resources

**Practice Environments (Legal):**
- HackTheBox - https://hackthebox.eu
- TryHackMe - https://tryhackme.com
- PentesterLab - https://pentesterlab.com
- PortSwigger Web Security Academy - Free

**Bug Bounty Platforms:**
- HackerOne
- Bugcrowd
- Synack
- Intigriti

---

## 🎯 Success Metrics

**Track:**
- Vulnerabilities found
- False positive rate
- Report quality
- Client satisfaction
- Legal compliance
- Zero unauthorized access incidents

---

## ⚠️ Final Warning

**SecurityAgent is a powerful tool that can:**
- ✅ Help find vulnerabilities
- ✅ Improve security posture
- ✅ Automate tedious tasks

**But it can also:**
- ❌ Break laws if misused
- ❌ Damage systems
- ❌ Violate privacy
- ❌ Get you arrested

**ALWAYS:**
1. Get written authorization first
2. Stay within defined scope
3. Log all actions
4. Follow responsible disclosure
5. Respect legal boundaries

**The line between ethical hacking and cybercrime is authorization.**

---

## 🎉 Career Opportunities

With SecurityAgent in your portfolio:

**Roles:**
- Penetration Tester ($80-150k)
- Security Engineer ($120-200k)
- Bug Bounty Hunter ($50k-500k+)
- Security Consultant ($150-300/hr)
- Red Team Operator ($150-250k)

**This combination (AI + Security) is extremely rare and valuable.**