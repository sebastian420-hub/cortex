#!/usr/bin/env python3
"""
Audit script for error handling patterns in Cortex tools.

This script analyzes all tool files to identify error handling patterns
and compliance with the create_error_response() standard.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
import sys

# Tool files to analyze (excluding base.py and registry.py)
TOOL_FILES = [
    "ask_user_tool.py",
    "command_tools.py", 
    "edit_tool.py",
    "file_tools.py",
    "git_tools.py",
    "glob_tool.py",
    "grep_tool.py",
    "search_tools.py",
    "skill_tools.py",
    "test_tools.py",
    "todo_tool.py",
    "web_tools.py",
]

def analyze_file(file_path: Path) -> Dict[str, Any]:
    """Analyze a single tool file for error handling patterns."""
    
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return {
            "file": str(file_path),
            "error": f"Failed to read file: {e}",
            "compliance_score": 0,
            "issues": ["File read error"]
        }
    
    analysis = {
        "file": str(file_path),
        "imports_errors_module": False,
        "uses_create_error_response": False,
        "manual_error_returns": 0,
        "error_patterns": [],
        "compliance_score": 0,
        "issues": [],
        "recommendations": []
    }
    
    # Check for imports from errors module
    if "from ..utils.errors import" in content or "from cortex.utils.errors import" in content:
        analysis["imports_errors_module"] = True
        
        # Check specifically for create_error_response import
        if "create_error_response" in content:
            analysis["uses_create_error_response"] = True
    
    # Count manual error returns (non-standard patterns)
    manual_patterns = [
        r'return\s*{[^}]*["\']error["\'][^}]*:',
        r'return\s*{[^}]*["\']error_type["\'][^}]*:',
        r'{\s*["\']success["\']\s*:\s*False',
    ]
    
    for pattern in manual_patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        analysis["manual_error_returns"] += len(matches)
    
    # Look for specific error return patterns
    lines = content.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Manual dictionary returns
        if line.startswith('return {') and ('"error"' in line or "'error'" in line):
            analysis["error_patterns"].append({
                "line": i + 1,
                "pattern": "manual_error_dict",
                "code": line[:100] + ("..." if len(line) > 100 else "")
            })
        
        # create_error_response calls
        elif "create_error_response(" in line:
            analysis["error_patterns"].append({
                "line": i + 1,
                "pattern": "create_error_response",
                "code": line[:100] + ("..." if len(line) > 100 else "")
            })
        
        # Permission denial patterns
        elif "create_permission_denial(" in line:
            analysis["error_patterns"].append({
                "line": i + 1,
                "pattern": "create_permission_denial",
                "code": line[:100] + ("..." if len(line) > 100 else "")
            })
    
    # Calculate compliance score (0-100)
    score = 0
    
    if analysis["imports_errors_module"]:
        score += 30
    
    if analysis["uses_create_error_response"]:
        score += 40
    
    # Penalize for manual error returns
    manual_penalty = min(analysis["manual_error_returns"] * 10, 70)
    score = max(0, score - manual_penalty)
    
    # Bonus for using permission denial helper
    if any(p["pattern"] == "create_permission_denial" for p in analysis["error_patterns"]):
        score += 10
    
    analysis["compliance_score"] = score
    
    # Generate issues and recommendations
    if not analysis["imports_errors_module"]:
        analysis["issues"].append("Missing import from utils.errors module")
        analysis["recommendations"].append("Add: from ..utils.errors import create_error_response, create_success_response, ErrorType")
    
    if analysis["manual_error_returns"] > 0:
        analysis["issues"].append(f"Found {analysis['manual_error_returns']} manual error returns")
        analysis["recommendations"].append("Replace manual error dictionaries with create_error_response()")
    
    if score < 70:
        analysis["issues"].append(f"Low compliance score: {score}/100")
        analysis["recommendations"].append("Review and standardize error handling patterns")
    
    return analysis

def generate_report(analyses: List[Dict[str, Any]]) -> str:
    """Generate a comprehensive audit report."""
    
    import datetime
    
    report_lines = []
    report_lines.append("# Cortex Tool Error Handling Audit Report")
    report_lines.append(f"Generated: {datetime.datetime.now().isoformat()}")
    report_lines.append(f"Total files analyzed: {len(analyses)}\n")
    
    # Summary statistics
    total_score = sum(a["compliance_score"] for a in analyses)
    avg_score = total_score / len(analyses) if analyses else 0
    
    compliant_files = sum(1 for a in analyses if a["compliance_score"] >= 70)
    non_compliant_files = len(analyses) - compliant_files
    
    report_lines.append("## Executive Summary")
    report_lines.append(f"- Average compliance score: {avg_score:.1f}/100")
    report_lines.append(f"- Compliant files (≥70): {compliant_files}/{len(analyses)}")
    report_lines.append(f"- Non-compliant files: {non_compliant_files}/{len(analyses)}")
    report_lines.append(f"- Total manual error returns: {sum(a['manual_error_returns'] for a in analyses)}")
    report_lines.append("")
    
    # Detailed file analysis
    report_lines.append("## File-by-File Analysis")
    report_lines.append("")
    
    for analysis in sorted(analyses, key=lambda x: x["compliance_score"]):
        status = "[PASS]" if analysis["compliance_score"] >= 70 else "[FAIL]"
        report_lines.append(f"### {status} {Path(analysis['file']).name} ({analysis['compliance_score']}/100)")
        report_lines.append(f"**File**: `{analysis['file']}`")
        report_lines.append(f"**Imports errors module**: {analysis['imports_errors_module']}")
        report_lines.append(f"**Uses create_error_response**: {analysis['uses_create_error_response']}")
        report_lines.append(f"**Manual error returns**: {analysis['manual_error_returns']}")
        
        if analysis["error_patterns"]:
            report_lines.append("**Error patterns found**:")
            for pattern in analysis["error_patterns"][:5]:  # Limit to first 5
                report_lines.append(f"  - Line {pattern['line']}: {pattern['pattern']} - `{pattern['code']}`")
            if len(analysis["error_patterns"]) > 5:
                report_lines.append(f"  - ... and {len(analysis['error_patterns']) - 5} more")
        
        if analysis["issues"]:
            report_lines.append("**Issues**:")
            for issue in analysis["issues"]:
                report_lines.append(f"  - {issue}")
        
        if analysis["recommendations"]:
            report_lines.append("**Recommendations**:")
            for rec in analysis["recommendations"]:
                report_lines.append(f"  - {rec}")
        
        report_lines.append("")
    
    # Compliance breakdown
    report_lines.append("## Compliance Breakdown")
    report_lines.append("")
    
    score_groups = {
        "Excellent (90-100)": 0,
        "Good (70-89)": 0,
        "Fair (50-69)": 0,
        "Poor (0-49)": 0,
    }
    
    for analysis in analyses:
        score = analysis["compliance_score"]
        if score >= 90:
            score_groups["Excellent (90-100)"] += 1
        elif score >= 70:
            score_groups["Good (70-89)"] += 1
        elif score >= 50:
            score_groups["Fair (50-69)"] += 1
        else:
            score_groups["Poor (0-49)"] += 1
    
    for group, count in score_groups.items():
        percentage = (count / len(analyses)) * 100 if analyses else 0
        report_lines.append(f"- {group}: {count} files ({percentage:.1f}%)")
    
    report_lines.append("")
    
    # Priority fixes
    report_lines.append("## Priority Fixes")
    report_lines.append("")
    
    high_priority = [a for a in analyses if a["compliance_score"] < 70]
    if high_priority:
        report_lines.append("**High Priority (Score < 70)**:")
        for analysis in sorted(high_priority, key=lambda x: x["compliance_score"]):
            report_lines.append(f"- `{Path(analysis['file']).name}`: {analysis['compliance_score']}/100")
            if analysis["issues"]:
                report_lines.append(f"  - Main issue: {analysis['issues'][0]}")
        report_lines.append("")
    
    # Action items
    report_lines.append("## Recommended Action Items")
    report_lines.append("")
    
    report_lines.append("1. **Immediate fixes** (files with score < 70):")
    for analysis in sorted([a for a in analyses if a["compliance_score"] < 70], 
                          key=lambda x: x["compliance_score"]):
        report_lines.append(f"   - Fix `{Path(analysis['file']).name}`")
    
    report_lines.append("\n2. **Standardization steps**:")
    report_lines.append("   - Ensure all tools import from utils.errors")
    report_lines.append("   - Replace manual error dictionaries with create_error_response()")
    report_lines.append("   - Add error context for better debugging")
    report_lines.append("   - Use consistent error_type values")
    
    report_lines.append("\n3. **Validation**:")
    report_lines.append("   - Run this audit script after changes")
    report_lines.append("   - Add error handling tests")
    report_lines.append("   - Verify no silent exceptions")
    
    return "\n".join(report_lines)

def main():
    """Main audit function."""
    
    # Get the project root
    project_root = Path(__file__).parent.parent
    tools_dir = project_root / "cortex" / "tools"
    
    if not tools_dir.exists():
        print(f"Error: Tools directory not found: {tools_dir}")
        sys.exit(1)
    
    print(f"[AUDIT] Analyzing error handling patterns in {tools_dir}")
    print(f"[AUDIT] Tool files to analyze: {len(TOOL_FILES)}")
    print()
    
    analyses = []
    
    for tool_file in TOOL_FILES:
        file_path = tools_dir / tool_file
        if not file_path.exists():
            print(f"[WARN] File not found: {tool_file}")
            continue
        
        print(f"  Analyzing: {tool_file}")
        analysis = analyze_file(file_path)
        analyses.append(analysis)
    
    print(f"\n[OK] Analysis complete. Analyzed {len(analyses)} files.")
    
    # Generate report
    report = generate_report(analyses)
    
    # Save report
    report_path = project_root / "ERROR_HANDLING_AUDIT.md"
    report_path.write_text(report, encoding="utf-8")
    
    print(f"[REPORT] Report saved to: {report_path}")
    
    # Print summary
    avg_score = sum(a["compliance_score"] for a in analyses) / len(analyses) if analyses else 0
    non_compliant = sum(1 for a in analyses if a["compliance_score"] < 70)
    
    print(f"\n[SUMMARY] Results:")
    print(f"  Average compliance: {avg_score:.1f}/100")
    print(f"  Non-compliant files (<70): {non_compliant}/{len(analyses)}")
    
    if non_compliant > 0:
        print(f"\n[ISSUES] Files needing attention:")
        for analysis in sorted(analyses, key=lambda x: x["compliance_score"]):
            if analysis["compliance_score"] < 70:
                print(f"  - {Path(analysis['file']).name}: {analysis['compliance_score']}/100")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())