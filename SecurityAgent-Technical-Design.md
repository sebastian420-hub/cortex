# SecurityAgent Technical Design Document

**Version:** 1.0.0  
**Status:** Draft  
**Author:** Security Engineering Team  
**Last Updated:** January 2025

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Goals and Non-Goals](#2-goals-and-non-goals)
3. [System Architecture](#3-system-architecture)
4. [Component Design](#4-component-design)
5. [Data Models](#5-data-models)
6. [Security Tools Specification](#6-security-tools-specification)
7. [Hook System Extensions](#7-hook-system-extensions)
8. [Workflow Engine](#8-workflow-engine)
9. [Safety and Compliance](#9-safety-and-compliance)
10. [API Specification](#10-api-specification)
11. [Configuration Schema](#11-configuration-schema)
12. [Deployment Architecture](#12-deployment-architecture)
13. [Testing Strategy](#13-testing-strategy)
14. [Migration Path](#14-migration-path)
15. [Appendices](#15-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

SecurityAgent extends LocalAgent to create a **security tool orchestrator** that coordinates cybersecurity tools through natural language interaction. It transforms manual, fragmented security workflows into cohesive, auditable, and methodology-driven assessments.

### 1.2 Problem Statement

Security professionals currently face:

| Challenge | Impact |
|-----------|--------|
| Tool fragmentation | Context lost between tools |
| Manual correlation | Time-consuming, error-prone |
| Inconsistent methodology | Gaps in coverage |
| Poor documentation | Audit failures, knowledge loss |
| Scope creep risk | Legal/ethical violations |

### 1.3 Solution Overview

SecurityAgent provides:

- **Natural language interface** to security tools
- **Contextual memory** across assessment phases
- **Methodology enforcement** via configurable workflows
- **Automated evidence collection** and reporting
- **Strict scope enforcement** to prevent violations
- **Audit trail** for compliance requirements

### 1.4 Key Metrics

| Metric | Target |
|--------|--------|
| Tool integration time | < 2 hours per tool |
| Scope violation rate | 0% |
| Assessment time reduction | 40% |
| Documentation coverage | 100% automated |
| Audit compliance | Full traceability |

---

## 2. Goals and Non-Goals

### 2.1 Goals

1. **G1: Tool Orchestration**
   - Coordinate 20+ security tools through unified interface
   - Maintain context across tool executions
   - Enable natural language tool invocation

2. **G2: Safety First**
   - Zero out-of-scope actions
   - Mandatory engagement authorization
   - Rate limiting to prevent detection/blocking

3. **G3: Methodology Compliance**
   - Enforce structured assessment phases
   - Track coverage against methodology
   - Prevent phase skipping

4. **G4: Evidence Management**
   - Automatic capture of all tool outputs
   - Structured finding documentation
   - Report generation

5. **G5: Extensibility**
   - Plugin architecture for new tools
   - Custom workflow definitions
   - Integration with existing toolchains

### 2.2 Non-Goals

1. **NG1: Autonomous Exploitation**
   - No automated exploitation without explicit approval
   - No lateral movement automation
   - No payload generation

2. **NG2: Replace Human Judgment**
   - Findings require human validation
   - Risk ratings are suggestions only
   - Remediation requires expert review

3. **NG3: Real-time Attack Detection**
   - Not a SIEM or IDS replacement
   - Not for production monitoring
   - Offensive security focus only

4. **NG4: Cloud-based Processing**
   - All processing remains local
   - No external API dependencies for core function
   - Offline operation required

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SECURITY AGENT                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         CLI / API Layer                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │ Interactive  │  │   One-shot   │  │      REST API            │  │   │
│  │  │    REPL      │  │    Mode      │  │   (Future)               │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      SecurityAgent Core                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │   │
│  │  │ Engagement  │  │  Workflow   │  │   Finding   │  │  Report   │  │   │
│  │  │  Manager    │  │   Engine    │  │   Manager   │  │ Generator │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       LocalAgent Core                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │   │
│  │  │Conversation │  │    Tool     │  │    Hook     │  │  Output   │  │   │
│  │  │  Manager    │  │  Registry   │  │   Manager   │  │ Formatter │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       Security Hooks Layer                           │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │   │
│  │  │   Scope   │ │   Audit   │ │   Rate    │ │ Evidence  │           │   │
│  │  │ Enforcer  │ │  Logger   │ │  Limiter  │ │ Collector │           │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Security Tools Layer                            │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
│  │  │  Recon  │ │  Enum   │ │  Vuln   │ │  Web    │ │ Report  │       │   │
│  │  │  Tools  │ │  Tools  │ │ Scanner │ │  Tools  │ │  Tools  │       │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
└─────────────────────────────────────┼────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           External Systems                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐    │
│  │   Ollama    │  │   Target    │  │  File       │  │   Security      │    │
│  │   (LLM)     │  │   Systems   │  │  System     │  │   Tools         │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Relationships

```
┌──────────────────┐      inherits       ┌──────────────────┐
│  SecurityAgent   │ ◄────────────────── │   LocalAgent     │
└────────┬─────────┘                     └──────────────────┘
         │
         │ composes
         │
         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│EngagementManager │     │  WorkflowEngine  │     │  FindingManager  │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
         │                        │                        │
         ▼                        ▼                        ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Engagement     │     │ MethodologyPhase │     │     Finding      │
│   (DataClass)    │     │   (DataClass)    │     │   (DataClass)    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

### 3.3 Data Flow

```
┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  User   │───▶│   Validate  │───▶│   Process   │───▶│   Execute   │
│ Request │    │    Scope    │    │   Request   │    │    Tool     │
└─────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘
                                                            │
┌─────────┐    ┌─────────────┐    ┌─────────────┐          │
│ Display │◀───│   Format    │◀───│   Collect   │◀─────────┘
│ Results │    │   Output    │    │  Evidence   │
└─────────┘    └─────────────┘    └─────────────┘
```

---

## 4. Component Design

### 4.1 SecurityAgent Class

```python
# security_agent/agent.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from localagent.agent import LocalAgent
from localagent.hooks import HookManager
from localagent.config import AgentConfig

from .engagement import EngagementManager, Engagement
from .workflow import WorkflowEngine, Methodology
from .findings import FindingManager, Finding
from .reports import ReportGenerator
from .hooks import create_security_hooks


@dataclass
class SecurityConfig:
    """Security-specific configuration"""
    
    # Engagement settings
    require_authorization: bool = True
    authorization_file: str = "engagement.json"
    
    # Scope settings
    scope_enforcement: str = "strict"  # strict | warn | disabled
    
    # Rate limiting
    max_requests_per_minute: int = 60
    max_requests_per_target: int = 1000
    
    # Evidence collection
    evidence_dir: str = "evidence"
    auto_screenshot: bool = True
    
    # Reporting
    report_format: str = "markdown"  # markdown | html | pdf
    
    # Methodology
    methodology: str = "ptes"  # ptes | owasp | custom
    enforce_methodology: bool = True
    
    # Tool restrictions
    allowed_tool_categories: List[str] = field(default_factory=lambda: [
        "recon", "enum", "vuln", "web", "report"
    ])
    blocked_tools: List[str] = field(default_factory=list)


class SecurityAgent(LocalAgent):
    """
    Security-focused agent extending LocalAgent.
    
    Provides:
    - Engagement management
    - Scope enforcement
    - Methodology-driven workflows
    - Evidence collection
    - Finding management
    - Report generation
    """
    
    def __init__(
        self,
        model: str = "llama3.3:70b",
        project_dir: str = ".",
        engagement_id: Optional[str] = None,
        security_config: Optional[SecurityConfig] = None,
        **kwargs
    ):
        # Initialize security configuration
        self.security_config = security_config or SecurityConfig()
        
        # Initialize engagement manager
        self.engagement_manager = EngagementManager(
            base_dir=Path(project_dir),
            config=self.security_config
        )
        
        # Load or create engagement
        if engagement_id:
            self.engagement = self.engagement_manager.load(engagement_id)
        else:
            self.engagement = None
        
        # Initialize finding manager
        self.finding_manager = FindingManager(
            evidence_dir=Path(project_dir) / self.security_config.evidence_dir
        )
        
        # Initialize workflow engine
        self.workflow_engine = WorkflowEngine(
            methodology=self.security_config.methodology
        )
        
        # Initialize report generator
        self.report_generator = ReportGenerator(
            format=self.security_config.report_format
        )
        
        # Create security-specific hooks
        hook_manager = self._create_security_hooks()
        
        # Initialize parent
        super().__init__(
            model=model,
            project_dir=project_dir,
            hook_manager=hook_manager,
            **kwargs
        )
        
        # Register security tools
        self._register_security_tools()
        
        # Override system prompt
        self._update_system_prompt()
    
    def _create_security_hooks(self) -> HookManager:
        """Create security-specific hook manager"""
        return create_security_hooks(
            engagement=self.engagement,
            config=self.security_config,
            finding_manager=self.finding_manager
        )
    
    def _register_security_tools(self) -> None:
        """Register security tool plugins"""
        from .tools import SECURITY_TOOLS
        from localagent.tools import get_registry
        
        registry = get_registry()
        for tool in SECURITY_TOOLS:
            if tool["name"] not in self.security_config.blocked_tools:
                registry.register(
                    name=tool["name"],
                    tool_class=tool["class"],
                    schema=tool["schema"],
                    namespace="security"
                )
    
    def _update_system_prompt(self) -> None:
        """Update system prompt for security context"""
        prompt = self._get_security_prompt()
        self.conversation.history[0]["content"] = prompt
    
    def _get_security_prompt(self) -> str:
        """Generate security-focused system prompt"""
        scope_info = ""
        if self.engagement:
            scope_info = f"""
## Engagement Details
- **Engagement ID:** {self.engagement.id}
- **Client:** {self.engagement.client_name}
- **Start Date:** {self.engagement.start_date}
- **End Date:** {self.engagement.end_date}

## Authorized Scope
### In-Scope Targets:
{self._format_scope(self.engagement.in_scope)}

### Out-of-Scope (DO NOT TARGET):
{self._format_scope(self.engagement.out_of_scope)}
"""
        
        methodology_info = self.workflow_engine.get_methodology_prompt()
        
        return f"""You are a security assessment assistant for authorized penetration testing.

{scope_info}

## Rules of Engagement
1. **NEVER** target systems outside the authorized scope
2. **ALWAYS** document findings with evidence
3. **STOP** and ask before any potentially destructive action
4. **FOLLOW** the defined methodology phases
5. **REPORT** all findings, including informational

## Current Methodology: {self.security_config.methodology.upper()}
{methodology_info}

## Available Security Tools
{self._list_security_tools()}

## Finding Severity Levels
- **Critical:** Immediate exploitation possible, high impact
- **High:** Exploitation likely, significant impact
- **Medium:** Exploitation possible, moderate impact
- **Low:** Minor issues, limited impact
- **Informational:** No direct security impact

## Your Responsibilities
1. Execute security testing within authorized scope
2. Document all findings with evidence
3. Provide remediation recommendations
4. Follow methodology phases in order
5. Maintain professional communication
"""
    
    def _format_scope(self, scope_items: List[Dict[str, Any]]) -> str:
        """Format scope items for prompt"""
        if not scope_items:
            return "- None specified"
        
        lines = []
        for item in scope_items:
            lines.append(f"- {item['target']} ({item.get('type', 'unknown')})")
            if item.get('notes'):
                lines.append(f"  Notes: {item['notes']}")
        return "\n".join(lines)
    
    def _list_security_tools(self) -> str:
        """List available security tools"""
        from localagent.tools import get_registry
        
        registry = get_registry()
        security_tools = registry.list_tools(namespace="security")
        
        if not security_tools:
            return "No security tools registered"
        
        return "\n".join(f"- {tool}" for tool in security_tools)
    
    # Public API Methods
    
    def start_engagement(
        self,
        engagement_id: str,
        client_name: str,
        scope: List[Dict[str, Any]],
        **kwargs
    ) -> Engagement:
        """Start a new security engagement"""
        self.engagement = self.engagement_manager.create(
            engagement_id=engagement_id,
            client_name=client_name,
            scope=scope,
            **kwargs
        )
        self._update_system_prompt()
        return self.engagement
    
    def add_finding(
        self,
        title: str,
        severity: str,
        description: str,
        evidence: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Finding:
        """Add a security finding"""
        return self.finding_manager.create(
            title=title,
            severity=severity,
            description=description,
            evidence=evidence,
            engagement_id=self.engagement.id if self.engagement else None,
            **kwargs
        )
    
    def generate_report(self, output_path: Optional[str] = None) -> str:
        """Generate assessment report"""
        return self.report_generator.generate(
            engagement=self.engagement,
            findings=self.finding_manager.get_all(),
            methodology_status=self.workflow_engine.get_status(),
            output_path=output_path
        )
    
    def get_methodology_status(self) -> Dict[str, Any]:
        """Get current methodology phase status"""
        return self.workflow_engine.get_status()
    
    def advance_phase(self, phase_name: str) -> bool:
        """Advance to next methodology phase"""
        return self.workflow_engine.advance_to(phase_name)
```

### 4.2 Engagement Manager

```python
# security_agent/engagement.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, date
import json
import uuid


@dataclass
class ScopeItem:
    """Individual scope item"""
    target: str
    type: str  # ip, cidr, domain, url, application
    ports: Optional[List[int]] = None
    protocols: Optional[List[str]] = None
    notes: Optional[str] = None
    
    def matches(self, target: str) -> bool:
        """Check if target matches this scope item"""
        import ipaddress
        import re
        
        if self.type == "ip":
            try:
                return ipaddress.ip_address(target) == ipaddress.ip_address(self.target)
            except ValueError:
                return False
        
        elif self.type == "cidr":
            try:
                network = ipaddress.ip_network(self.target, strict=False)
                return ipaddress.ip_address(target) in network
            except ValueError:
                return False
        
        elif self.type == "domain":
            # Match domain and subdomains
            target_lower = target.lower()
            scope_lower = self.target.lower()
            return target_lower == scope_lower or target_lower.endswith("." + scope_lower)
        
        elif self.type == "url":
            return target.startswith(self.target)
        
        else:
            return target == self.target


@dataclass
class Engagement:
    """Security engagement definition"""
    
    id: str
    client_name: str
    start_date: date
    end_date: date
    
    # Scope
    in_scope: List[ScopeItem] = field(default_factory=list)
    out_of_scope: List[ScopeItem] = field(default_factory=list)
    
    # Authorization
    authorization_document: Optional[str] = None
    authorized_by: Optional[str] = None
    authorization_date: Optional[date] = None
    
    # Constraints
    testing_hours: Optional[str] = None  # e.g., "09:00-17:00 EST"
    excluded_dates: List[date] = field(default_factory=list)
    rate_limits: Dict[str, int] = field(default_factory=dict)
    
    # Methodology
    methodology: str = "ptes"
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "active"  # active | paused | completed | cancelled
    
    def is_in_scope(self, target: str) -> bool:
        """Check if target is within authorized scope"""
        # First check out-of-scope (takes precedence)
        for item in self.out_of_scope:
            if item.matches(target):
                return False
        
        # Then check in-scope
        for item in self.in_scope:
            if item.matches(target):
                return True
        
        # Default: not in scope
        return False
    
    def is_active(self) -> bool:
        """Check if engagement is currently active"""
        today = date.today()
        return (
            self.status == "active" and
            self.start_date <= today <= self.end_date and
            today not in self.excluded_dates
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "id": self.id,
            "client_name": self.client_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "in_scope": [vars(s) for s in self.in_scope],
            "out_of_scope": [vars(s) for s in self.out_of_scope],
            "authorization_document": self.authorization_document,
            "authorized_by": self.authorized_by,
            "authorization_date": self.authorization_date.isoformat() if self.authorization_date else None,
            "testing_hours": self.testing_hours,
            "excluded_dates": [d.isoformat() for d in self.excluded_dates],
            "rate_limits": self.rate_limits,
            "methodology": self.methodology,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Engagement":
        """Deserialize from dictionary"""
        return cls(
            id=data["id"],
            client_name=data["client_name"],
            start_date=date.fromisoformat(data["start_date"]),
            end_date=date.fromisoformat(data["end_date"]),
            in_scope=[ScopeItem(**s) for s in data.get("in_scope", [])],
            out_of_scope=[ScopeItem(**s) for s in data.get("out_of_scope", [])],
            authorization_document=data.get("authorization_document"),
            authorized_by=data.get("authorized_by"),
            authorization_date=date.fromisoformat(data["authorization_date"]) if data.get("authorization_date") else None,
            testing_hours=data.get("testing_hours"),
            excluded_dates=[date.fromisoformat(d) for d in data.get("excluded_dates", [])],
            rate_limits=data.get("rate_limits", {}),
            methodology=data.get("methodology", "ptes"),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            status=data.get("status", "active"),
        )


class EngagementManager:
    """Manages security engagements"""
    
    def __init__(self, base_dir: Path, config: "SecurityConfig"):
        self.base_dir = base_dir
        self.config = config
        self.engagements_dir = base_dir / "engagements"
        self.engagements_dir.mkdir(parents=True, exist_ok=True)
    
    def create(
        self,
        engagement_id: str,
        client_name: str,
        scope: List[Dict[str, Any]],
        **kwargs
    ) -> Engagement:
        """Create a new engagement"""
        # Parse scope
        in_scope = []
        out_of_scope = []
        
        for item in scope:
            scope_item = ScopeItem(
                target=item["target"],
                type=item.get("type", "domain"),
                ports=item.get("ports"),
                protocols=item.get("protocols"),
                notes=item.get("notes"),
            )
            
            if item.get("excluded", False):
                out_of_scope.append(scope_item)
            else:
                in_scope.append(scope_item)
        
        # Create engagement
        engagement = Engagement(
            id=engagement_id,
            client_name=client_name,
            start_date=kwargs.get("start_date", date.today()),
            end_date=kwargs.get("end_date", date.today()),
            in_scope=in_scope,
            out_of_scope=out_of_scope,
            **{k: v for k, v in kwargs.items() if k not in ["start_date", "end_date"]}
        )
        
        # Save
        self.save(engagement)
        
        return engagement
    
    def save(self, engagement: Engagement) -> None:
        """Save engagement to file"""
        filepath = self.engagements_dir / f"{engagement.id}.json"
        with open(filepath, "w") as f:
            json.dump(engagement.to_dict(), f, indent=2)
    
    def load(self, engagement_id: str) -> Optional[Engagement]:
        """Load engagement from file"""
        filepath = self.engagements_dir / f"{engagement_id}.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath) as f:
            data = json.load(f)
        
        return Engagement.from_dict(data)
    
    def list_engagements(self) -> List[Engagement]:
        """List all engagements"""
        engagements = []
        
        for filepath in self.engagements_dir.glob("*.json"):
            try:
                engagement = self.load(filepath.stem)
                if engagement:
                    engagements.append(engagement)
            except Exception:
                continue
        
        return engagements
```

### 4.3 Finding Manager

```python
# security_agent/findings.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from enum import Enum
import json
import uuid
import hashlib


class Severity(Enum):
    """Finding severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"
    
    @property
    def cvss_range(self) -> tuple:
        """CVSS score range for severity"""
        ranges = {
            "critical": (9.0, 10.0),
            "high": (7.0, 8.9),
            "medium": (4.0, 6.9),
            "low": (0.1, 3.9),
            "informational": (0.0, 0.0),
        }
        return ranges.get(self.value, (0.0, 0.0))


class FindingStatus(Enum):
    """Finding status"""
    OPEN = "open"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    REMEDIATED = "remediated"
    ACCEPTED = "accepted"


@dataclass
class Evidence:
    """Evidence attached to a finding"""
    id: str
    type: str  # screenshot, request, response, file, log
    description: str
    filepath: Optional[str] = None
    content: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "filepath": self.filepath,
            "content": self.content[:1000] if self.content else None,  # Truncate for storage
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Finding:
    """Security finding"""
    
    id: str
    title: str
    severity: Severity
    description: str
    
    # Classification
    category: str = "general"  # injection, auth, crypto, config, etc.
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    
    # Location
    affected_asset: Optional[str] = None
    affected_component: Optional[str] = None
    affected_parameter: Optional[str] = None
    
    # Details
    technical_details: Optional[str] = None
    reproduction_steps: Optional[List[str]] = None
    impact: Optional[str] = None
    
    # Remediation
    remediation: Optional[str] = None
    remediation_effort: Optional[str] = None  # low, medium, high
    references: List[str] = field(default_factory=list)
    
    # Evidence
    evidence: List[Evidence] = field(default_factory=list)
    
    # Metadata
    engagement_id: Optional[str] = None
    discovered_at: datetime = field(default_factory=datetime.now)
    discovered_by: str = "security_agent"
    status: FindingStatus = FindingStatus.OPEN
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "severity": self.severity.value,
            "description": self.description,
            "category": self.category,
            "cwe_id": self.cwe_id,
            "cvss_score": self.cvss_score,
            "cvss_vector": self.cvss_vector,
            "affected_asset": self.affected_asset,
            "affected_component": self.affected_component,
            "affected_parameter": self.affected_parameter,
            "technical_details": self.technical_details,
            "reproduction_steps": self.reproduction_steps,
            "impact": self.impact,
            "remediation": self.remediation,
            "remediation_effort": self.remediation_effort,
            "references": self.references,
            "evidence": [e.to_dict() for e in self.evidence],
            "engagement_id": self.engagement_id,
            "discovered_at": self.discovered_at.isoformat(),
            "discovered_by": self.discovered_by,
            "status": self.status.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Finding":
        return cls(
            id=data["id"],
            title=data["title"],
            severity=Severity(data["severity"]),
            description=data["description"],
            category=data.get("category", "general"),
            cwe_id=data.get("cwe_id"),
            cvss_score=data.get("cvss_score"),
            cvss_vector=data.get("cvss_vector"),
            affected_asset=data.get("affected_asset"),
            affected_component=data.get("affected_component"),
            affected_parameter=data.get("affected_parameter"),
            technical_details=data.get("technical_details"),
            reproduction_steps=data.get("reproduction_steps"),
            impact=data.get("impact"),
            remediation=data.get("remediation"),
            remediation_effort=data.get("remediation_effort"),
            references=data.get("references", []),
            evidence=[Evidence(**e) for e in data.get("evidence", [])],
            engagement_id=data.get("engagement_id"),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
            discovered_by=data.get("discovered_by", "security_agent"),
            status=FindingStatus(data.get("status", "open")),
        )


class FindingManager:
    """Manages security findings"""
    
    def __init__(self, evidence_dir: Path):
        self.evidence_dir = evidence_dir
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.findings: Dict[str, Finding] = {}
    
    def create(
        self,
        title: str,
        severity: str,
        description: str,
        evidence: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Finding:
        """Create a new finding"""
        finding_id = f"FIND-{uuid.uuid4().hex[:8].upper()}"
        
        finding = Finding(
            id=finding_id,
            title=title,
            severity=Severity(severity.lower()),
            description=description,
            **kwargs
        )
        
        # Add evidence if provided
        if evidence:
            self.add_evidence(finding_id, evidence)
        
        self.findings[finding_id] = finding
        self._save_finding(finding)
        
        return finding
    
    def add_evidence(
        self,
        finding_id: str,
        evidence_data: Dict[str, Any]
    ) -> Evidence:
        """Add evidence to a finding"""
        evidence_id = f"EV-{uuid.uuid4().hex[:8].upper()}"
        
        evidence = Evidence(
            id=evidence_id,
            type=evidence_data.get("type", "file"),
            description=evidence_data.get("description", ""),
        )
        
        # Save content to file if provided
        if "content" in evidence_data:
            filepath = self._save_evidence_file(
                finding_id,
                evidence_id,
                evidence_data["content"],
                evidence_data.get("filename", "evidence.txt")
            )
            evidence.filepath = str(filepath)
        
        # Add to finding
        if finding_id in self.findings:
            self.findings[finding_id].evidence.append(evidence)
            self._save_finding(self.findings[finding_id])
        
        return evidence
    
    def _save_evidence_file(
        self,
        finding_id: str,
        evidence_id: str,
        content: str,
        filename: str
    ) -> Path:
        """Save evidence content to file"""
        finding_dir = self.evidence_dir / finding_id
        finding_dir.mkdir(exist_ok=True)
        
        filepath = finding_dir / f"{evidence_id}_{filename}"
        filepath.write_text(content)
        
        return filepath
    
    def _save_finding(self, finding: Finding) -> None:
        """Save finding to disk"""
        finding_dir = self.evidence_dir / finding.id
        finding_dir.mkdir(exist_ok=True)
        
        filepath = finding_dir / "finding.json"
        with open(filepath, "w") as f:
            json.dump(finding.to_dict(), f, indent=2)
    
    def get(self, finding_id: str) -> Optional[Finding]:
        """Get finding by ID"""
        return self.findings.get(finding_id)
    
    def get_all(self) -> List[Finding]:
        """Get all findings"""
        return list(self.findings.values())
    
    def get_by_severity(self, severity: str) -> List[Finding]:
        """Get findings by severity"""
        return [
            f for f in self.findings.values()
            if f.severity.value == severity.lower()
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get finding statistics"""
        stats = {
            "total": len(self.findings),
            "by_severity": {},
            "by_status": {},
            "by_category": {},
        }
        
        for finding in self.findings.values():
            # By severity
            sev = finding.severity.value
            stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1
            
            # By status
            status = finding.status.value
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            # By category
            cat = finding.category
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        
        return stats
```

---

## 5. Data Models

### 5.1 Entity Relationship Diagram

```
┌─────────────────┐       1:N        ┌─────────────────┐
│   Engagement    │─────────────────▶│     Finding     │
├─────────────────┤                  ├─────────────────┤
│ id              │                  │ id              │
│ client_name     │                  │ title           │
│ start_date      │                  │ severity        │
│ end_date        │                  │ description     │
│ status          │                  │ engagement_id   │
└────────┬────────┘                  └────────┬────────┘
         │                                    │
         │ 1:N                                │ 1:N
         ▼                                    ▼
┌─────────────────┐                  ┌─────────────────┐
│   ScopeItem     │                  │    Evidence     │
├─────────────────┤                  ├─────────────────┤
│ target          │                  │ id              │
│ type            │                  │ type            │
│ ports           │                  │ filepath        │
│ notes           │                  │ content         │
└─────────────────┘                  └─────────────────┘

┌─────────────────┐       1:N        ┌─────────────────┐
│   Methodology   │─────────────────▶│     Phase       │
├─────────────────┤                  ├─────────────────┤
│ id              │                  │ id              │
│ name            │                  │ name            │
│ description     │                  │ order           │
│ phases          │                  │ status          │
└─────────────────┘                  │ tools           │
                                     └─────────────────┘
```

### 5.2 State Diagrams

#### Engagement States

```
                    ┌───────────┐
                    │  Created  │
                    └─────┬─────┘
                          │
                          ▼
┌───────────┐       ┌───────────┐       ┌───────────┐
│  Paused   │◀─────▶│  Active   │──────▶│ Completed │
└───────────┘       └─────┬─────┘       └───────────┘
                          │
                          ▼
                    ┌───────────┐
                    │ Cancelled │
                    └───────────┘
```

#### Finding States

```
┌───────────┐       ┌───────────┐       ┌───────────┐
│   Open    │──────▶│ Confirmed │──────▶│Remediated │
└─────┬─────┘       └───────────┘       └───────────┘
      │
      │             ┌───────────┐
      └────────────▶│  False    │
                    │ Positive  │
                    └───────────┘
```

---

## 6. Security Tools Specification

### 6.1 Tool Categories

| Category | Purpose | Risk Level |
|----------|---------|------------|
| **Recon** | Information gathering | Low |
| **Enum** | Service enumeration | Low-Medium |
| **Vuln** | Vulnerability scanning | Medium |
| **Web** | Web application testing | Medium-High |
| **Exploit** | Proof of concept | High |
| **Report** | Documentation | None |

### 6.2 Tool Implementations

```python
# security_agent/tools/recon.py

from typing import Dict, Any, Optional, List
import subprocess
import json

from localagent.tools.base import Tool
from localagent.utils.errors import create_success_response, create_error_response, ErrorType


class NmapTool(Tool):
    """
    Network port scanning with Nmap.
    
    Supports various scan types with safety controls.
    """
    
    SCAN_PROFILES = {
        "quick": "-T4 -F",
        "standard": "-sV -sC -T4",
        "comprehensive": "-sV -sC -A -T4",
        "stealth": "-sS -T2",
        "udp": "-sU --top-ports 100",
    }
    
    def execute(
        self,
        target: str,
        profile: str = "quick",
        ports: Optional[str] = None,
        scripts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute Nmap scan.
        
        Args:
            target: Target IP or hostname
            profile: Scan profile (quick, standard, comprehensive, stealth, udp)
            ports: Custom port specification (e.g., "22,80,443" or "1-1000")
            scripts: Additional NSE scripts to run
        
        Returns:
            Scan results with parsed output
        """
        # Build command
        cmd = ["nmap"]
        
        # Add profile options
        profile_opts = self.SCAN_PROFILES.get(profile, self.SCAN_PROFILES["quick"])
        cmd.extend(profile_opts.split())
        
        # Custom ports
        if ports:
            cmd.extend(["-p", ports])
        
        # Additional scripts
        if scripts:
            cmd.extend(["--script", ",".join(scripts)])
        
        # Output format
        cmd.extend(["-oX", "-"])  # XML to stdout
        
        # Target
        cmd.append(target)
        
        # Display command
        if self.console:
            self.console.print(f"[cyan]Running:[/cyan] {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=self.project_dir
            )
            
            if result.returncode != 0:
                return create_error_response(
                    f"Nmap failed: {result.stderr}",
                    ErrorType.EXECUTION,
                    {"command": " ".join(cmd)}
                )
            
            # Parse results
            parsed = self._parse_nmap_xml(result.stdout)
            
            return create_success_response({
                "target": target,
                "profile": profile,
                "raw_output": result.stdout,
                "parsed": parsed,
                "open_ports": parsed.get("ports", []),
                "services": parsed.get("services", []),
            })
            
        except subprocess.TimeoutExpired:
            return create_error_response(
                "Nmap scan timed out after 5 minutes",
                ErrorType.TIMEOUT,
                {"target": target}
            )
        except FileNotFoundError:
            return create_error_response(
                "Nmap not found. Please install nmap.",
                ErrorType.NOT_FOUND
            )
        except Exception as e:
            return create_error_response(
                str(e),
                ErrorType.EXECUTION
            )
    
    def _parse_nmap_xml(self, xml_output: str) -> Dict[str, Any]:
        """Parse Nmap XML output"""
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(xml_output)
            
            result = {
                "ports": [],
                "services": [],
                "os": None,
                "scripts": [],
            }
            
            for host in root.findall(".//host"):
                # Ports
                for port in host.findall(".//port"):
                    port_info = {
                        "port": int(port.get("portid")),
                        "protocol": port.get("protocol"),
                        "state": port.find("state").get("state") if port.find("state") is not None else "unknown",
                    }
                    
                    service = port.find("service")
                    if service is not None:
                        port_info["service"] = {
                            "name": service.get("name"),
                            "product": service.get("product"),
                            "version": service.get("version"),
                        }
                        result["services"].append(port_info["service"])
                    
                    result["ports"].append(port_info)
                
                # OS detection
                os_match = host.find(".//osmatch")
                if os_match is not None:
                    result["os"] = {
                        "name": os_match.get("name"),
                        "accuracy": os_match.get("accuracy"),
                    }
                
                # Scripts
                for script in host.findall(".//script"):
                    result["scripts"].append({
                        "id": script.get("id"),
                        "output": script.get("output"),
                    })
            
            return result
            
        except ET.ParseError:
            return {"error": "Failed to parse XML", "raw": xml_output}


class SubdomainEnumTool(Tool):
    """
    Subdomain enumeration using multiple sources.
    """
    
    def execute(
        self,
        domain: str,
        passive_only: bool = True,
        wordlist: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enumerate subdomains for a domain.
        
        Args:
            domain: Target domain
            passive_only: Only use passive sources (safer)
            wordlist: Custom wordlist for active bruteforcing
        
        Returns:
            List of discovered subdomains
        """
        subdomains = set()
        
        # Passive enumeration
        passive_sources = [
            self._crtsh_enum,
            self._dns_enum,
        ]
        
        for source in passive_sources:
            try:
                results = source(domain)
                subdomains.update(results)
            except Exception as e:
                if self.console:
                    self.console.print(f"[yellow]Warning:[/yellow] {source.__name__} failed: {e}")
        
        # Active bruteforcing (if enabled and wordlist provided)
        if not passive_only and wordlist:
            try:
                active_results = self._active_brute(domain, wordlist)
                subdomains.update(active_results)
            except Exception as e:
                if self.console:
                    self.console.print(f"[yellow]Warning:[/yellow] Active brute failed: {e}")
        
        return create_success_response({
            "domain": domain,
            "subdomains": sorted(list(subdomains)),
            "count": len(subdomains),
        })
    
    def _crtsh_enum(self, domain: str) -> List[str]:
        """Query crt.sh for certificate transparency logs"""
        import urllib.request
        import json
        
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode())
        
        subdomains = set()
        for entry in data:
            name = entry.get("name_value", "")
            for subdomain in name.split("\n"):
                subdomain = subdomain.strip().lower()
                if subdomain.endswith(domain):
                    subdomains.add(subdomain)
        
        return list(subdomains)
    
    def _dns_enum(self, domain: str) -> List[str]:
        """Basic DNS enumeration"""
        import socket
        
        common_prefixes = [
            "www", "mail", "ftp", "admin", "api", "dev", "staging",
            "test", "beta", "app", "portal", "secure", "vpn", "remote"
        ]
        
        subdomains = []
        for prefix in common_prefixes:
            subdomain = f"{prefix}.{domain}"
            try:
                socket.gethostbyname(subdomain)
                subdomains.append(subdomain)
            except socket.gaierror:
                pass
        
        return subdomains
    
    def _active_brute(self, domain: str, wordlist: str) -> List[str]:
        """Active subdomain bruteforcing"""
        # Implementation would use a wordlist file
        # This is a placeholder
        return []


class WhoisTool(Tool):
    """WHOIS lookup tool"""
    
    def execute(self, target: str) -> Dict[str, Any]:
        """
        Perform WHOIS lookup.
        
        Args:
            target: Domain or IP to lookup
        
        Returns:
            WHOIS information
        """
        try:
            result = subprocess.run(
                ["whois", target],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return create_error_response(
                    f"WHOIS failed: {result.stderr}",
                    ErrorType.EXECUTION
                )
            
            parsed = self._parse_whois(result.stdout)
            
            return create_success_response({
                "target": target,
                "raw": result.stdout,
                "parsed": parsed,
            })
            
        except subprocess.TimeoutExpired:
            return create_error_response(
                "WHOIS lookup timed out",
                ErrorType.TIMEOUT
            )
        except FileNotFoundError:
            return create_error_response(
                "whois command not found",
                ErrorType.NOT_FOUND
            )
    
    def _parse_whois(self, output: str) -> Dict[str, Any]:
        """Parse WHOIS output"""
        parsed = {}
        
        # Common WHOIS fields
        field_mappings = {
            "Registrar:": "registrar",
            "Creation Date:": "created",
            "Registry Expiry Date:": "expires",
            "Name Server:": "nameservers",
            "Registrant Organization:": "organization",
        }
        
        for line in output.split("\n"):
            for field, key in field_mappings.items():
                if line.strip().startswith(field):
                    value = line.split(":", 1)[1].strip()
                    if key == "nameservers":
                        if key not in parsed:
                            parsed[key] = []
                        parsed[key].append(value)
                    else:
                        parsed[key] = value
        
        return parsed
```

### 6.3 Tool Registration

```python
# security_agent/tools/__init__.py

from .recon import NmapTool, SubdomainEnumTool, WhoisTool
from .web import NiktoTool, GobusterTool, SSLScanTool
from .vuln import NucleiTool, SearchsploitTool
from .report import FindingTool, EvidenceTool, ReportTool


# Tool definitions for registration
SECURITY_TOOLS = [
    # Reconnaissance
    {
        "name": "nmap_scan",
        "class": NmapTool,
        "category": "recon",
        "schema": {
            "type": "function",
            "function": {
                "name": "nmap_scan",
                "description": "Scan target for open ports and services using Nmap. Use for network reconnaissance.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Target IP address or hostname"
                        },
                        "profile": {
                            "type": "string",
                            "enum": ["quick", "standard", "comprehensive", "stealth", "udp"],
                            "description": "Scan profile (default: quick)"
                        },
                        "ports": {
                            "type": "string",
                            "description": "Custom port specification (e.g., '22,80,443' or '1-1000')"
                        }
                    },
                    "required": ["target"]
                }
            }
        }
    },
    {
        "name": "subdomain_enum",
        "class": SubdomainEnumTool,
        "category": "recon",
        "schema": {
            "type": "function",
            "function": {
                "name": "subdomain_enum",
                "description": "Enumerate subdomains for a target domain using passive sources.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Target domain (e.g., 'example.com')"
                        },
                        "passive_only": {
                            "type": "boolean",
                            "description": "Only use passive enumeration (default: true)"
                        }
                    },
                    "required": ["domain"]
                }
            }
        }
    },
    {
        "name": "whois_lookup",
        "class": WhoisTool,
        "category": "recon",
        "schema": {
            "type": "function",
            "function": {
                "name": "whois_lookup",
                "description": "Perform WHOIS lookup for domain or IP registration information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Domain or IP to lookup"
                        }
                    },
                    "required": ["target"]
                }
            }
        }
    },
    
    # Web Application
    {
        "name": "nikto_scan",
        "class": NiktoTool,
        "category": "web",
        "schema": {
            "type": "function",
            "function": {
                "name": "nikto_scan",
                "description": "Scan web server for known vulnerabilities and misconfigurations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Target URL or host"
                        },
                        "port": {
                            "type": "integer",
                            "description": "Target port (default: 80)"
                        },
                        "ssl": {
                            "type": "boolean",
                            "description": "Use SSL/TLS (default: false)"
                        }
                    },
                    "required": ["target"]
                }
            }
        }
    },
    {
        "name": "dir_bruteforce",
        "class": GobusterTool,
        "category": "web",
        "schema": {
            "type": "function",
            "function": {
                "name": "dir_bruteforce",
                "description": "Bruteforce directories and files on a web server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Target URL"
                        },
                        "wordlist": {
                            "type": "string",
                            "description": "Wordlist to use (default: common.txt)"
                        },
                        "extensions": {
                            "type": "string",
                            "description": "File extensions to try (e.g., 'php,html,txt')"
                        }
                    },
                    "required": ["url"]
                }
            }
        }
    },
    
    # Vulnerability Scanning
    {
        "name": "nuclei_scan",
        "class": NucleiTool,
        "category": "vuln",
        "schema": {
            "type": "function",
            "function": {
                "name": "nuclei_scan",
                "description": "Scan target with Nuclei templates for known vulnerabilities.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Target URL"
                        },
                        "templates": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific templates to use"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["info", "low", "medium", "high", "critical"],
                            "description": "Minimum severity to report"
                        }
                    },
                    "required": ["target"]
                }
            }
        }
    },
    
    # Finding Management
    {
        "name": "create_finding",
        "class": FindingTool,
        "category": "report",
        "schema": {
            "type": "function",
            "function": {
                "name": "create_finding",
                "description": "Create a new security finding with evidence.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Finding title"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low", "informational"],
                            "description": "Finding severity"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description"
                        },
                        "affected_asset": {
                            "type": "string",
                            "description": "Affected system or URL"
                        },
                        "remediation": {
                            "type": "string",
                            "description": "Remediation recommendation"
                        }
                    },
                    "required": ["title", "severity", "description"]
                }
            }
        }
    },
    {
        "name": "add_evidence",
        "class": EvidenceTool,
        "category": "report",
        "schema": {
            "type": "function",
            "function": {
                "name": "add_evidence",
                "description": "Add evidence to an existing finding.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "finding_id": {
                            "type": "string",
                            "description": "Finding ID to add evidence to"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["screenshot", "request", "response", "log", "file"],
                            "description": "Evidence type"
                        },
                        "description": {
                            "type": "string",
                            "description": "Evidence description"
                        },
                        "content": {
                            "type": "string",
                            "description": "Evidence content or file path"
                        }
                    },
                    "required": ["finding_id", "type", "description"]
                }
            }
        }
    },
]
```

---

## 7. Hook System Extensions

### 7.1 Security-Specific Hooks

```python
# security_agent/hooks/security_hooks.py

from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import logging
import json

from localagent.hooks import BaseHook, HookEvent, HookResult, HookAction
from localagent.hooks.events import EVENT_PRE_TOOL_USE, EVENT_POST_TOOL_USE

from ..engagement import Engagement
from ..findings import FindingManager


class ScopeEnforcementHook(BaseHook):
    """
    CRITICAL: Enforces engagement scope on all network tools.
    
    This hook MUST run first and MUST NOT be disabled.
    """
    
    handles = [EVENT_PRE_TOOL_USE]
    priority = 1  # Highest priority - run first
    name = "ScopeEnforcementHook"
    
    # Tools that require scope validation
    NETWORK_TOOLS = {
        "nmap_scan",
        "subdomain_enum",
        "nikto_scan",
        "dir_bruteforce",
        "nuclei_scan",
        "ssl_scan",
        "http_request",
    }
    
    def __init__(self, engagement: Optional[Engagement] = None):
        super().__init__()
        self.engagement = engagement
        self.logger = logging.getLogger("security_agent.scope")
    
    def execute(self, event: HookEvent) -> HookResult:
        """Validate target is in scope before tool execution"""
        tool_name = event.data.get("tool_name", "")
        
        # Skip non-network tools
        if tool_name not in self.NETWORK_TOOLS:
            return HookResult.continue_execution()
        
        # Check engagement exists
        if not self.engagement:
            return HookResult.abort_operation(
                "No active engagement. Create an engagement before running security tools."
            )
        
        # Check engagement is active
        if not self.engagement.is_active():
            return HookResult.abort_operation(
                f"Engagement '{self.engagement.id}' is not active. "
                f"Status: {self.engagement.status}, "
                f"Valid: {self.engagement.start_date} to {self.engagement.end_date}"
            )
        
        # Extract target from arguments
        arguments = event.data.get("arguments", {})
        target = self._extract_target(tool_name, arguments)
        
        if not target:
            return HookResult.abort_operation(
                f"Could not extract target from {tool_name} arguments"
            )
        
        # Validate scope
        if not self.engagement.is_in_scope(target):
            self.logger.critical(
                f"SCOPE VIOLATION BLOCKED: {tool_name} attempted on {target}"
            )
            return HookResult.abort_operation(
                f"🚫 SCOPE VIOLATION: Target '{target}' is NOT in authorized scope.\n"
                f"Authorized targets: {self._format_scope()}"
            )
        
        self.logger.info(f"Scope check passed: {target}")
        return HookResult.continue_execution()
    
    def _extract_target(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """Extract target from tool arguments"""
        # Common target parameter names
        target_params = ["target", "host", "url", "domain", "ip"]
        
        for param in target_params:
            if param in arguments:
                target = arguments[param]
                # Extract hostname from URL if needed
                if target.startswith(("http://", "https://")):
                    from urllib.parse import urlparse
                    parsed = urlparse(target)
                    return parsed.hostname
                return target
        
        return None
    
    def _format_scope(self) -> str:
        """Format scope for error message"""
        if not self.engagement:
            return "None"
        
        targets = [item.target for item in self.engagement.in_scope]
        return ", ".join(targets[:5]) + ("..." if len(targets) > 5 else "")


class AuditLoggingHook(BaseHook):
    """
    Logs all security tool usage for compliance and audit trail.
    """
    
    handles = [EVENT_PRE_TOOL_USE, EVENT_POST_TOOL_USE]
    priority = 5
    name = "AuditLoggingHook"
    
    def __init__(self, engagement_id: Optional[str] = None, log_file: Optional[str] = None):
        super().__init__()
        self.engagement_id = engagement_id
        self.log_file = log_file or f"audit_{engagement_id or 'default'}.jsonl"
        self.logger = logging.getLogger("security_agent.audit")
    
    def execute(self, event: HookEvent) -> HookResult:
        """Log tool usage"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "engagement_id": self.engagement_id,
            "event_type": event.event_type,
            "tool_name": event.data.get("tool_name"),
        }
        
        if event.event_type == EVENT_PRE_TOOL_USE:
            log_entry["arguments"] = self._sanitize_arguments(
                event.data.get("arguments", {})
            )
        
        elif event.event_type == EVENT_POST_TOOL_USE:
            log_entry["success"] = event.data.get("success")
            log_entry["duration_ms"] = event.data.get("duration_ms")
            if not event.data.get("success"):
                log_entry["error"] = event.data.get("result", {}).get("error")
        
        # Write to log file
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")
        
        return HookResult.continue_execution()
    
    def _sanitize_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from arguments before logging"""
        sanitized = {}
        sensitive_keys = {"password", "token", "key", "secret", "credential"}
        
        for key, value in arguments.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        
        return sanitized


class RateLimitHook(BaseHook):
    """
    Rate limits tool execution to prevent detection and blocking.
    """
    
    handles = [EVENT_PRE_TOOL_USE]
    priority = 10
    name = "RateLimitHook"
    
    def __init__(
        self,
        max_per_minute: int = 60,
        max_per_target: int = 1000,
    ):
        super().__init__()
        self.max_per_minute = max_per_minute
        self.max_per_target = max_per_target
        self.requests: List[datetime] = []
        self.target_counts: Dict[str, int] = {}
    
    def execute(self, event: HookEvent) -> HookResult:
        """Check and enforce rate limits"""
        import time
        
        now = datetime.now()
        
        # Clean old requests
        self.requests = [
            r for r in self.requests
            if (now - r).total_seconds() < 60
        ]
        
        # Check per-minute limit
        if len(self.requests) >= self.max_per_minute:
            wait_time = 60 - (now - self.requests[0]).total_seconds()
            time.sleep(wait_time)
            self.requests = []
        
        # Check per-target limit
        arguments = event.data.get("arguments", {})
        target = arguments.get("target") or arguments.get("url") or arguments.get("host")
        
        if target:
            self.target_counts[target] = self.target_counts.get(target, 0) + 1
            if self.target_counts[target] > self.max_per_target:
                return HookResult.abort_operation(
                    f"Rate limit exceeded for target {target}. "
                    f"Max {self.max_per_target} requests per engagement."
                )
        
        # Record this request
        self.requests.append(now)
        
        return HookResult.continue_execution()


class EvidenceCollectionHook(BaseHook):
    """
    Automatically collects evidence from tool executions.
    """
    
    handles = [EVENT_POST_TOOL_USE]
    priority = 90  # Run late to capture final results
    name = "EvidenceCollectionHook"
    
    # Tools that generate evidence worth capturing
    EVIDENCE_TOOLS = {
        "nmap_scan",
        "nikto_scan",
        "nuclei_scan",
        "dir_bruteforce",
    }
    
    def __init__(self, finding_manager: FindingManager):
        super().__init__()
        self.finding_manager = finding_manager
    
    def execute(self, event: HookEvent) -> HookResult:
        """Capture evidence from tool results"""
        tool_name = event.data.get("tool_name", "")
        
        if tool_name not in self.EVIDENCE_TOOLS:
            return HookResult.continue_execution()
        
        if not event.data.get("success"):
            return HookResult.continue_execution()
        
        # Store raw output as potential evidence
        result = event.data.get("result", {})
        
        # Auto-create informational finding for significant results
        if self._is_significant(tool_name, result):
            self._auto_create_finding(tool_name, result)
        
        return HookResult.continue_execution()
    
    def _is_significant(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """Determine if result is significant enough to auto-document"""
        if tool_name == "nmap_scan":
            ports = result.get("open_ports", [])
            return len(ports) > 0
        
        if tool_name == "nuclei_scan":
            findings = result.get("findings", [])
            return any(f.get("severity") in ["high", "critical"] for f in findings)
        
        return False
    
    def _auto_create_finding(self, tool_name: str, result: Dict[str, Any]) -> None:
        """Auto-create finding from significant result"""
        # Implementation would create appropriate finding
        pass


def create_security_hooks(
    engagement: Optional[Engagement],
    config: "SecurityConfig",
    finding_manager: FindingManager,
) -> "HookManager":
    """Factory function to create configured security hooks"""
    from localagent.hooks import HookManager
    
    manager = HookManager()
    
    # Scope enforcement (CRITICAL - always enabled)
    scope_hook = ScopeEnforcementHook(engagement)
    manager.register(scope_hook)
    
    # Audit logging
    audit_hook = AuditLoggingHook(
        engagement_id=engagement.id if engagement else None
    )
    manager.register(audit_hook)
    
    # Rate limiting
    rate_hook = RateLimitHook(
        max_per_minute=config.max_requests_per_minute,
        max_per_target=config.max_requests_per_target,
    )
    manager.register(rate_hook)
    
    # Evidence collection
    evidence_hook = EvidenceCollectionHook(finding_manager)
    manager.register(evidence_hook)
    
    return manager
```

---

## 8. Workflow Engine

### 8.1 Methodology Definitions

```python
# security_agent/workflow/methodologies.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class PhaseStatus(Enum):
    """Phase completion status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


@dataclass
class Phase:
    """Methodology phase definition"""
    id: str
    name: str
    description: str
    order: int
    
    # Required tools/checks for completion
    required_tools: List[str] = field(default_factory=list)
    optional_tools: List[str] = field(default_factory=list)
    
    # Completion criteria
    min_tool_executions: int = 1
    requires_findings_review: bool = False
    
    # Status tracking
    status: PhaseStatus = PhaseStatus.NOT_STARTED
    tools_executed: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class Methodology:
    """Complete testing methodology"""
    id: str
    name: str
    description: str
    phases: List[Phase]
    
    def get_current_phase(self) -> Optional[Phase]:
        """Get current active phase"""
        for phase in self.phases:
            if phase.status == PhaseStatus.IN_PROGRESS:
                return phase
        
        # Return first not-started phase
        for phase in self.phases:
            if phase.status == PhaseStatus.NOT_STARTED:
                return phase
        
        return None
    
    def get_phase(self, phase_id: str) -> Optional[Phase]:
        """Get phase by ID"""
        for phase in self.phases:
            if phase.id == phase_id:
                return phase
        return None


# Predefined methodologies

PTES_METHODOLOGY = Methodology(
    id="ptes",
    name="Penetration Testing Execution Standard",
    description="Industry-standard penetration testing methodology",
    phases=[
        Phase(
            id="pre_engagement",
            name="Pre-Engagement",
            description="Scope definition, authorization, rules of engagement",
            order=1,
            required_tools=[],
            min_tool_executions=0,
        ),
        Phase(
            id="intelligence_gathering",
            name="Intelligence Gathering",
            description="Passive and active information gathering",
            order=2,
            required_tools=["subdomain_enum", "whois_lookup"],
            optional_tools=["nmap_scan"],
            min_tool_executions=2,
        ),
        Phase(
            id="threat_modeling",
            name="Threat Modeling",
            description="Identify potential attack vectors",
            order=3,
            required_tools=[],
            min_tool_executions=0,
        ),
        Phase(
            id="vulnerability_analysis",
            name="Vulnerability Analysis",
            description="Identify and validate vulnerabilities",
            order=4,
            required_tools=["nmap_scan", "nuclei_scan"],
            optional_tools=["nikto_scan", "ssl_scan"],
            min_tool_executions=3,
        ),
        Phase(
            id="exploitation",
            name="Exploitation",
            description="Attempt to exploit identified vulnerabilities",
            order=5,
            required_tools=[],
            min_tool_executions=0,
            requires_findings_review=True,
        ),
        Phase(
            id="post_exploitation",
            name="Post-Exploitation",
            description="Determine value of compromised systems",
            order=6,
            required_tools=[],
            min_tool_executions=0,
        ),
        Phase(
            id="reporting",
            name="Reporting",
            description="Document findings and recommendations",
            order=7,
            required_tools=["generate_report"],
            min_tool_executions=1,
        ),
    ]
)


OWASP_METHODOLOGY = Methodology(
    id="owasp",
    name="OWASP Testing Guide",
    description="Web application security testing methodology",
    phases=[
        Phase(
            id="information_gathering",
            name="Information Gathering",
            description="Collect information about the target application",
            order=1,
            required_tools=["subdomain_enum"],
            optional_tools=["whois_lookup"],
            min_tool_executions=1,
        ),
        Phase(
            id="configuration_testing",
            name="Configuration Testing",
            description="Test application and infrastructure configuration",
            order=2,
            required_tools=["ssl_scan", "nikto_scan"],
            min_tool_executions=2,
        ),
        Phase(
            id="identity_management",
            name="Identity Management Testing",
            description="Test authentication and session management",
            order=3,
            required_tools=[],
            min_tool_executions=1,
        ),
        Phase(
            id="authentication_testing",
            name="Authentication Testing",
            description="Test authentication mechanisms",
            order=4,
            required_tools=[],
            min_tool_executions=1,
        ),
        Phase(
            id="authorization_testing",
            name="Authorization Testing",
            description="Test access control mechanisms",
            order=5,
            required_tools=[],
            min_tool_executions=1,
        ),
        Phase(
            id="session_management",
            name="Session Management Testing",
            description="Test session handling",
            order=6,
            required_tools=[],
            min_tool_executions=1,
        ),
        Phase(
            id="input_validation",
            name="Input Validation Testing",
            description="Test for injection vulnerabilities",
            order=7,
            required_tools=["nuclei_scan"],
            min_tool_executions=2,
        ),
        Phase(
            id="error_handling",
            name="Error Handling Testing",
            description="Test error handling and logging",
            order=8,
            required_tools=[],
            min_tool_executions=1,
        ),
        Phase(
            id="cryptography_testing",
            name="Cryptography Testing",
            description="Test cryptographic implementations",
            order=9,
            required_tools=["ssl_scan"],
            min_tool_executions=1,
        ),
        Phase(
            id="business_logic",
            name="Business Logic Testing",
            description="Test business logic flaws",
            order=10,
            required_tools=[],
            min_tool_executions=0,
        ),
        Phase(
            id="client_side",
            name="Client-Side Testing",
            description="Test client-side vulnerabilities",
            order=11,
            required_tools=[],
            min_tool_executions=1,
        ),
    ]
)


METHODOLOGIES = {
    "ptes": PTES_METHODOLOGY,
    "owasp": OWASP_METHODOLOGY,
}
```

### 8.2 Workflow Engine

```python
# security_agent/workflow/engine.py

from typing import Dict, Any, Optional, List
from datetime import datetime

from .methodologies import Methodology, Phase, PhaseStatus, METHODOLOGIES


class WorkflowEngine:
    """
    Manages methodology-driven security testing workflows.
    """
    
    def __init__(self, methodology: str = "ptes"):
        self.methodology_id = methodology
        self.methodology = self._load_methodology(methodology)
        self.tool_history: List[Dict[str, Any]] = []
    
    def _load_methodology(self, methodology_id: str) -> Methodology:
        """Load methodology definition"""
        if methodology_id not in METHODOLOGIES:
            raise ValueError(f"Unknown methodology: {methodology_id}")
        
        # Create a copy to avoid modifying the template
        import copy
        return copy.deepcopy(METHODOLOGIES[methodology_id])
    
    def get_methodology_prompt(self) -> str:
        """Generate methodology guidance for system prompt"""
        phases_text = []
        
        for phase in self.methodology.phases:
            status_indicator = {
                PhaseStatus.NOT_STARTED: "⬜",
                PhaseStatus.IN_PROGRESS: "🔄",
                PhaseStatus.COMPLETED: "✅",
                PhaseStatus.SKIPPED: "⏭️",
            }.get(phase.status, "⬜")
            
            tools = ", ".join(phase.required_tools) if phase.required_tools else "None required"
            phases_text.append(
                f"{status_indicator} **Phase {phase.order}: {phase.name}**\n"
                f"   {phase.description}\n"
                f"   Required tools: {tools}"
            )
        
        return "\n".join(phases_text)
    
    def get_current_phase(self) -> Optional[Phase]:
        """Get the current active phase"""
        return self.methodology.get_current_phase()
    
    def start_phase(self, phase_id: str) -> bool:
        """Start a methodology phase"""
        phase = self.methodology.get_phase(phase_id)
        if not phase:
            return False
        
        # Check if previous phases are completed
        for p in self.methodology.phases:
            if p.order < phase.order and p.status == PhaseStatus.NOT_STARTED:
                # Previous phase not started - warn but allow
                pass
        
        phase.status = PhaseStatus.IN_PROGRESS
        phase.started_at = datetime.now().isoformat()
        
        return True
    
    def complete_phase(self, phase_id: str) -> bool:
        """Mark a phase as completed"""
        phase = self.methodology.get_phase(phase_id)
        if not phase:
            return False
        
        # Check completion criteria
        if not self._check_phase_completion(phase):
            return False
        
        phase.status = PhaseStatus.COMPLETED
        phase.completed_at = datetime.now().isoformat()
        
        # Auto-start next phase
        next_phase = self._get_next_phase(phase)
        if next_phase:
            self.start_phase(next_phase.id)
        
        return True
    
    def _check_phase_completion(self, phase: Phase) -> bool:
        """Check if phase completion criteria are met"""
        # Check minimum tool executions
        if len(phase.tools_executed) < phase.min_tool_executions:
            return False
        
        # Check required tools
        for tool in phase.required_tools:
            if tool not in phase.tools_executed:
                return False
        
        return True
    
    def _get_next_phase(self, current: Phase) -> Optional[Phase]:
        """Get the next phase in sequence"""
        for phase in self.methodology.phases:
            if phase.order == current.order + 1:
                return phase
        return None
    
    def record_tool_execution(self, tool_name: str) -> None:
        """Record that a tool was executed"""
        current_phase = self.get_current_phase()
        if current_phase:
            if tool_name not in current_phase.tools_executed:
                current_phase.tools_executed.append(tool_name)
        
        self.tool_history.append({
            "tool": tool_name,
            "phase": current_phase.id if current_phase else None,
            "timestamp": datetime.now().isoformat(),
        })
    
    def advance_to(self, phase_name: str) -> bool:
        """Advance to a specific phase"""
        # Find phase by name or ID
        target_phase = None
        for phase in self.methodology.phases:
            if phase.id == phase_name or phase.name.lower() == phase_name.lower():
                target_phase = phase
                break
        
        if not target_phase:
            return False
        
        # Complete all previous phases
        for phase in self.methodology.phases:
            if phase.order < target_phase.order:
                if phase.status != PhaseStatus.COMPLETED:
                    phase.status = PhaseStatus.SKIPPED
        
        return self.start_phase(target_phase.id)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current workflow status"""
        current = self.get_current_phase()
        
        completed = sum(1 for p in self.methodology.phases if p.status == PhaseStatus.COMPLETED)
        total = len(self.methodology.phases)
        
        return {
            "methodology": self.methodology.name,
            "current_phase": current.name if current else None,
            "current_phase_id": current.id if current else None,
            "progress": f"{completed}/{total}",
            "progress_percent": int((completed / total) * 100) if total > 0 else 0,
            "phases": [
                {
                    "id": p.id,
                    "name": p.name,
                    "status": p.status.value,
                    "tools_executed": p.tools_executed,
                }
                for p in self.methodology.phases
            ],
            "tools_used": len(self.tool_history),
        }
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations for current phase"""
        current = self.get_current_phase()
        if not current:
            return ["All phases completed. Generate report."]
        
        recommendations = []
        
        # Check required tools not yet executed
        missing_required = [
            t for t in current.required_tools
            if t not in current.tools_executed
        ]
        if missing_required:
            recommendations.append(
                f"Required tools not yet run: {', '.join(missing_required)}"
            )
        
        # Suggest optional tools
        optional_not_run = [
            t for t in current.optional_tools
            if t not in current.tools_executed
        ]
        if optional_not_run:
            recommendations.append(
                f"Consider running optional tools: {', '.join(optional_not_run)}"
            )
        
        # Check if ready to complete
        if self._check_phase_completion(current):
            recommendations.append(
                f"Phase '{current.name}' criteria met. Ready to advance."
            )
        
        return recommendations
```

---

## 9. Safety and Compliance

### 9.1 Safety Requirements

| Requirement | Implementation | Priority |
|-------------|----------------|----------|
| Scope enforcement | ScopeEnforcementHook | CRITICAL |
| Engagement validation | EngagementManager | CRITICAL |
| Audit logging | AuditLoggingHook | HIGH |
| Rate limiting | RateLimitHook | HIGH |
| Dangerous action confirmation | CLI prompts | HIGH |
| Evidence integrity | SHA256 hashing | MEDIUM |

### 9.2 Compliance Controls

```python
# security_agent/compliance.py

from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import Path
import hashlib
import json
from datetime import datetime


@dataclass
class AuditRecord:
    """Immutable audit record"""
    timestamp: str
    event_type: str
    actor: str
    action: str
    target: str
    result: str
    evidence_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return vars(self)


class ComplianceManager:
    """
    Manages compliance requirements for security assessments.
    
    Supports:
    - PCI-DSS penetration testing requirements
    - SOC 2 security assessment documentation
    - HIPAA security risk assessments
    """
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.audit_dir = base_dir / "audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
    
    def log_action(
        self,
        event_type: str,
        action: str,
        target: str,
        result: str,
        evidence: str = "",
    ) -> AuditRecord:
        """Log an auditable action"""
        record = AuditRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=event_type,
            actor="security_agent",
            action=action,
            target=target,
            result=result,
            evidence_hash=self._hash_evidence(evidence) if evidence else "",
        )
        
        self._append_audit_log(record)
        return record
    
    def _hash_evidence(self, evidence: str) -> str:
        """Create SHA256 hash of evidence for integrity"""
        return hashlib.sha256(evidence.encode()).hexdigest()
    
    def _append_audit_log(self, record: AuditRecord) -> None:
        """Append record to audit log (append-only)"""
        log_file = self.audit_dir / "audit.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
    
    def verify_audit_integrity(self) -> bool:
        """Verify audit log has not been tampered with"""
        # Implementation would use chained hashes or signatures
        return True
    
    def generate_compliance_report(
        self,
        framework: str = "pci-dss"
    ) -> Dict[str, Any]:
        """Generate compliance-specific report"""
        # Implementation would map findings to compliance requirements
        return {}
```

---

## 10. API Specification

### 10.1 CLI Commands

```bash
# Start interactive session with engagement
security-agent --engagement pentest-2024-001

# Load engagement from file
security-agent --engagement-file ./engagement.json

# Start with specific methodology
security-agent --engagement pentest-2024-001 --methodology owasp

# Generate report
security-agent report --engagement pentest-2024-001 --format pdf

# List findings
security-agent findings --engagement pentest-2024-001 --severity high

# Export audit log
security-agent audit --engagement pentest-2024-001 --export audit.json
```

### 10.2 Python API

```python
from security_agent import SecurityAgent, SecurityConfig, Engagement

# Create configuration
config = SecurityConfig(
    methodology="ptes",
    enforce_methodology=True,
    max_requests_per_minute=30,
)

# Initialize agent
agent = SecurityAgent(
    model="llama3.3:70b",
    security_config=config,
)

# Start engagement
engagement = agent.start_engagement(
    engagement_id="pentest-2024-001",
    client_name="Acme Corp",
    scope=[
        {"target": "192.168.1.0/24", "type": "cidr"},
        {"target": "*.acme.com", "type": "domain"},
        {"target": "10.0.0.0/8", "type": "cidr", "excluded": True},
    ],
    start_date=date.today(),
    end_date=date.today() + timedelta(days=14),
)

# Process natural language request
agent._process_message("Scan 192.168.1.100 for open ports")

# Add finding programmatically
finding = agent.add_finding(
    title="Open MySQL Port",
    severity="high",
    description="MySQL port 3306 is externally accessible",
    affected_asset="192.168.1.100",
    remediation="Restrict MySQL to localhost or use firewall rules",
)

# Generate report
report_path = agent.generate_report(output_path="./report.md")

# Get workflow status
status = agent.get_methodology_status()
print(f"Current phase: {status['current_phase']}")
print(f"Progress: {status['progress_percent']}%")
```

---

## 11. Configuration Schema

### 11.1 Engagement File Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Security Engagement",
  "type": "object",
  "required": ["id", "client_name", "start_date", "end_date", "in_scope"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9-]+$",
      "description": "Unique engagement identifier"
    },
    "client_name": {
      "type": "string",
      "description": "Client organization name"
    },
    "start_date": {
      "type": "string",
      "format": "date",
      "description": "Engagement start date (YYYY-MM-DD)"
    },
    "end_date": {
      "type": "string",
      "format": "date",
      "description": "Engagement end date (YYYY-MM-DD)"
    },
    "in_scope": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/scope_item"
      },
      "description": "Authorized targets"
    },
    "out_of_scope": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/scope_item"
      },
      "description": "Explicitly excluded targets"
    },
    "authorization": {
      "type": "object",
      "properties": {
        "document": {"type": "string"},
        "authorized_by": {"type": "string"},
        "authorization_date": {"type": "string", "format": "date"}
      }
    },
    "constraints": {
      "type": "object",
      "properties": {
        "testing_hours": {"type": "string"},
        "rate_limits": {
          "type": "object",
          "additionalProperties": {"type": "integer"}
        }
      }
    },
    "methodology": {
      "type": "string",
      "enum": ["ptes", "owasp", "custom"],
      "default": "ptes"
    }
  },
  "definitions": {
    "scope_item": {
      "type": "object",
      "required": ["target", "type"],
      "properties": {
        "target": {"type": "string"},
        "type": {
          "type": "string",
          "enum": ["ip", "cidr", "domain", "url", "application"]
        },
        "ports": {
          "type": "array",
          "items": {"type": "integer"}
        },
        "protocols": {
          "type": "array",
          "items": {"type": "string"}
        },
        "notes": {"type": "string"}
      }
    }
  }
}
```

### 11.2 Example Engagement File

```json
{
  "id": "pentest-acme-2024-q1",
  "client_name": "Acme Corporation",
  "start_date": "2024-01-15",
  "end_date": "2024-01-29",
  "in_scope": [
    {
      "target": "192.168.1.0/24",
      "type": "cidr",
      "notes": "Internal network segment"
    },
    {
      "target": "acme.com",
      "type": "domain",
      "notes": "Main domain and all subdomains"
    },
    {
      "target": "https://app.acme.com",
      "type": "url",
      "notes": "Primary web application"
    }
  ],
  "out_of_scope": [
    {
      "target": "192.168.1.1",
      "type": "ip",
      "notes": "Production router - do not test"
    },
    {
      "target": "10.0.0.0/8",
      "type": "cidr",
      "notes": "Corporate network - out of scope"
    }
  ],
  "authorization": {
    "document": "authorization/acme-authorization-2024.pdf",
    "authorized_by": "John Smith, CISO",
    "authorization_date": "2024-01-10"
  },
  "constraints": {
    "testing_hours": "09:00-17:00 EST",
    "rate_limits": {
      "requests_per_minute": 30,
      "requests_per_target": 500
    }
  },
  "methodology": "ptes"
}
```

---

## 12. Deployment Architecture

### 12.1 Directory Structure

```
security-agent/
├── security_agent/
│   ├── __init__.py
│   ├── agent.py              # SecurityAgent class
│   ├── config.py             # SecurityConfig
│   │
│   ├── engagement/
│   │   ├── __init__.py
│   │   ├── manager.py        # EngagementManager
│   │   └── models.py         # Engagement, ScopeItem
│   │
│   ├── findings/
│   │   ├── __init__.py
│   │   ├── manager.py        # FindingManager
│   │   └── models.py         # Finding, Evidence, Severity
│   │
│   ├── workflow/
│   │   ├── __init__.py
│   │   ├── engine.py         # WorkflowEngine
│   │   └── methodologies.py  # PTES, OWASP definitions
│   │
│   ├── hooks/
│   │   ├── __init__.py
│   │   ├── scope.py          # ScopeEnforcementHook
│   │   ├── audit.py          # AuditLoggingHook
│   │   ├── rate_limit.py     # RateLimitHook
│   │   └── evidence.py       # EvidenceCollectionHook
│   │
│   ├── tools/
│   │   ├── __init__.py       # SECURITY_TOOLS registry
│   │   ├── recon/
│   │   │   ├── nmap.py
│   │   │   ├── subdomain.py
│   │   │   └── whois.py
│   │   ├── web/
│   │   │   ├── nikto.py
│   │   │   ├── gobuster.py
│   │   │   └── ssl_scan.py
│   │   ├── vuln/
│   │   │   ├── nuclei.py
│   │   │   └── searchsploit.py
│   │   └── report/
│   │       ├── finding.py
│   │       └── evidence.py
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── generator.py      # ReportGenerator
│   │   └── templates/
│   │       ├── executive.md.j2
│   │       ├── technical.md.j2
│   │       └── findings.md.j2
│   │
│   ├── compliance/
│   │   ├── __init__.py
│   │   └── manager.py        # ComplianceManager
│   │
│   └── cli.py                # CLI entry point
│
├── tests/
│   ├── test_engagement.py
│   ├── test_findings.py
│   ├── test_workflow.py
│   ├── test_hooks.py
│   └── test_tools/
│       ├── test_nmap.py
│       └── test_nuclei.py
│
├── docs/
│   ├── user-guide.md
│   ├── tool-development.md
│   └── api-reference.md
│
├── examples/
│   ├── engagement.json
│   └── config.yaml
│
├── pyproject.toml
├── requirements.txt
└── README.md
```

### 12.2 Dependencies

```toml
# pyproject.toml additions

[project]
name = "security-agent"
version = "1.0.0"
dependencies = [
    "localagent>=1.0.0",
    "jinja2>=3.0.0",       # Report templating
    "python-dateutil>=2.8", # Date handling
]

[project.optional-dependencies]
full = [
    "python-nmap>=0.7.0",  # Nmap integration
    "dnspython>=2.0.0",    # DNS operations
    "requests>=2.28.0",    # HTTP operations
]

[project.scripts]
security-agent = "security_agent.cli:main"
```

---

## 13. Testing Strategy

### 13.1 Test Categories

| Category | Purpose | Coverage Target |
|----------|---------|-----------------|
| Unit | Individual components | 80% |
| Integration | Component interaction | 60% |
| Security | Safety controls | 100% |
| End-to-End | Full workflows | Key paths |

### 13.2 Critical Test Cases

```python
# tests/test_scope_enforcement.py

import pytest
from security_agent.hooks import ScopeEnforcementHook
from security_agent.engagement import Engagement, ScopeItem
from localagent.hooks import PreToolUseEvent, HookAction


class TestScopeEnforcement:
    """Tests for scope enforcement - CRITICAL security control"""
    
    @pytest.fixture
    def engagement(self):
        return Engagement(
            id="test-001",
            client_name="Test",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            in_scope=[
                ScopeItem(target="192.168.1.0/24", type="cidr"),
                ScopeItem(target="example.com", type="domain"),
            ],
            out_of_scope=[
                ScopeItem(target="192.168.1.1", type="ip"),
            ],
        )
    
    def test_blocks_out_of_scope_ip(self, engagement):
        """CRITICAL: Must block IPs outside scope"""
        hook = ScopeEnforcementHook(engagement)
        
        event = PreToolUseEvent(
            tool_name="nmap_scan",
            arguments={"target": "10.0.0.1"},
            permission_mode="normal"
        )
        
        result = hook.execute(event)
        
        assert result.action == HookAction.ABORT
        assert "SCOPE VIOLATION" in result.message
    
    def test_blocks_explicitly_excluded(self, engagement):
        """CRITICAL: Must block explicitly excluded targets"""
        hook = ScopeEnforcementHook(engagement)
        
        event = PreToolUseEvent(
            tool_name="nmap_scan",
            arguments={"target": "192.168.1.1"},  # Explicitly excluded
            permission_mode="normal"
        )
        
        result = hook.execute(event)
        
        assert result.action == HookAction.ABORT
    
    def test_allows_in_scope_ip(self, engagement):
        """Must allow IPs within scope"""
        hook = ScopeEnforcementHook(engagement)
        
        event = PreToolUseEvent(
            tool_name="nmap_scan",
            arguments={"target": "192.168.1.100"},
            permission_mode="normal"
        )
        
        result = hook.execute(event)
        
        assert result.action == HookAction.CONTINUE
    
    def test_allows_in_scope_subdomain(self, engagement):
        """Must allow subdomains of in-scope domains"""
        hook = ScopeEnforcementHook(engagement)
        
        event = PreToolUseEvent(
            tool_name="subdomain_enum",
            arguments={"target": "api.example.com"},
            permission_mode="normal"
        )
        
        result = hook.execute(event)
        
        assert result.action == HookAction.CONTINUE
    
    def test_blocks_without_engagement(self):
        """CRITICAL: Must block all network tools without engagement"""
        hook = ScopeEnforcementHook(engagement=None)
        
        event = PreToolUseEvent(
            tool_name="nmap_scan",
            arguments={"target": "192.168.1.100"},
            permission_mode="normal"
        )
        
        result = hook.execute(event)
        
        assert result.action == HookAction.ABORT
        assert "No active engagement" in result.message
    
    def test_blocks_expired_engagement(self, engagement):
        """CRITICAL: Must block if engagement expired"""
        engagement.end_date = date.today() - timedelta(days=1)
        hook = ScopeEnforcementHook(engagement)
        
        event = PreToolUseEvent(
            tool_name="nmap_scan",
            arguments={"target": "192.168.1.100"},
            permission_mode="normal"
        )
        
        result = hook.execute(event)
        
        assert result.action == HookAction.ABORT
        assert "not active" in result.message
```

---

## 14. Migration Path

### 14.1 From LocalAgent to SecurityAgent

```python
# Before: Using LocalAgent for security tasks
from localagent import LocalAgent

agent = LocalAgent(model="llama3.3:70b")
agent._process_message("scan 192.168.1.100")  # UNSAFE - no scope control

# After: Using SecurityAgent with proper controls
from security_agent import SecurityAgent, SecurityConfig

config = SecurityConfig(
    require_authorization=True,
    scope_enforcement="strict",
)

agent = SecurityAgent(
    model="llama3.3:70b",
    security_config=config,
)

# Create engagement first
agent.start_engagement(
    engagement_id="test-001",
    client_name="Client",
    scope=[{"target": "192.168.1.0/24", "type": "cidr"}],
    start_date=date.today(),
    end_date=date.today() + timedelta(days=7),
)

# Now safe to run
agent._process_message("scan 192.168.1.100")  # SAFE - scope validated
```

### 14.2 Implementation Phases

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1** | 2 weeks | Core SecurityAgent, Engagement, Scope hooks |
| **Phase 2** | 2 weeks | Finding manager, Evidence collection |
| **Phase 3** | 2 weeks | Workflow engine, Methodologies |
| **Phase 4** | 2 weeks | Reporting, Security tools (5 tools) |
| **Phase 5** | 2 weeks | Testing, Documentation, Additional tools |

---

## 15. Appendices

### A. Glossary

| Term | Definition |
|------|------------|
| **Engagement** | Authorized security assessment with defined scope |
| **Scope** | Authorized targets for testing |
| **Finding** | Discovered security issue |
| **Evidence** | Proof supporting a finding |
| **Methodology** | Structured testing approach (PTES, OWASP) |
| **Phase** | Stage within a methodology |

### B. References

- [PTES Technical Guidelines](http://www.pentest-standard.org/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [NIST SP 800-115](https://csrc.nist.gov/publications/detail/sp/800-115/final)

### C. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01 | Security Team | Initial draft |

---

**End of Technical Design Document**
