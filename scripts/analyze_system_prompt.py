#!/usr/bin/env python3
"""Analyze the Cortex system prompt structure and token usage."""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("Warning: tiktoken not installed. Install with: pip install tiktoken")
    print("Falling back to character-based estimation.")


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken or fallback."""
    if TIKTOKEN_AVAILABLE:
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except (KeyError, ValueError):
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
    # Fallback: rough estimate (4 chars per token)
    return len(text) // 4


def extract_system_prompt() -> str:
    """Extract the system prompt from agent.py."""
    agent_path = Path("cortex/agent.py")
    if not agent_path.exists():
        agent_path = Path(__file__).parent.parent / "cortex" / "agent.py"
    
    content = agent_path.read_text(encoding="utf-8")
    
    # Find the _get_system_prompt method
    method_start = content.find("def _get_system_prompt(self) -> str:")
    if method_start == -1:
        raise ValueError("Could not find _get_system_prompt method")
    
    # Find the return statement with triple quotes
    # Look for return f"""...""" pattern
    pattern = r'return f?"""(.*?)"""'
    match = re.search(pattern, content[method_start:], re.DOTALL)
    if not match:
        # Try alternative pattern with escaped quotes
        pattern = r'return f?"""([\s\S]*?)"""'
        match = re.search(pattern, content[method_start:], re.DOTALL)
    
    if not match:
        raise ValueError("Could not find system prompt in method")
    
    prompt = match.group(1)
    return prompt


def analyze_sections(prompt: str) -> List[Dict]:
    """Analyze prompt sections and their sizes."""
    sections = []
    
    # Define section patterns
    section_patterns = [
        ("Identity & Context", r"You are Cortex.*?(?=# Mental Model|$)"),
        ("Mental Model", r"# Mental Model.*?(?=# Self-Awareness|$)"),
        ("Self-Awareness", r"# Self-Awareness.*?(?=# Efficiency Patterns|$)"),
        ("Efficiency Patterns", r"# Efficiency Patterns.*?(?=# Proactive Behavior|$)"),
        ("Proactive Behavior", r"# Proactive Behavior.*?(?=# Tool Reference|$)"),
        ("Tool Reference", r"# Tool Reference.*?(?=# Error Recovery|$)"),
        ("Error Recovery", r"# Error Recovery.*?(?=# Response Style|$)"),
        ("Response Style", r"# Response Style.*?(?=# Quick Reference|$)"),
        ("Quick Reference", r"# Quick Reference.*?(?=Remember:|$)"),
        ("Final Reminder", r"Remember:.*"),
    ]
    
    for name, pattern in section_patterns:
        match = re.search(pattern, prompt, re.DOTALL | re.IGNORECASE)
        if match:
            section_text = match.group(0)
            lines = section_text.count('\n') + 1
            chars = len(section_text)
            tokens = count_tokens(section_text)
            
            sections.append({
                "name": name,
                "lines": lines,
                "chars": chars,
                "tokens": tokens,
                "text_preview": section_text[:100].replace('\n', ' ') + "..."
            })
    
    return sections


def generate_report(prompt: str, sections: List[Dict], args) -> None:
    """Generate and display analysis report."""
    total_lines = prompt.count('\n') + 1
    total_chars = len(prompt)
    total_tokens = count_tokens(prompt)
    
    print("=" * 80)
    print("SYSTEM PROMPT ANALYSIS REPORT")
    print("=" * 80)
    print()
    print("OVERALL STATISTICS")
    print(f"   Total lines: {total_lines}")
    print(f"   Total characters: {total_chars:,}")
    print(f"   Estimated tokens: {total_tokens:,}")
    print(f"   Average chars per line: {total_chars / total_lines:.1f}")
    print()
    
    print("SECTION BREAKDOWN")
    print("-" * 80)
    print(f"{'Section':<25} {'Lines':>6} {'Chars':>10} {'Tokens':>10} {'% Total':>8}")
    print("-" * 80)
    
    for section in sections:
        pct_lines = (section["lines"] / total_lines) * 100
        pct_tokens = (section["tokens"] / total_tokens) * 100
        print(f"{section['name']:<25} {section['lines']:>6} {section['chars']:>10,} "
              f"{section['tokens']:>10,} {pct_tokens:>7.1f}%")
    
    print("-" * 80)
    
    # Calculate candidate sections for removal
    candidate_sections = ["Tool Reference", "Error Recovery", "Quick Reference"]
    candidate_lines = sum(s["lines"] for s in sections if s["name"] in candidate_sections)
    candidate_tokens = sum(s["tokens"] for s in sections if s["name"] in candidate_sections)
    
    print()
    print("OPTIMIZATION OPPORTUNITIES")
    print("-" * 80)
    print(f"Candidate sections for removal (move to /help):")
    for name in candidate_sections:
        section = next((s for s in sections if s["name"] == name), None)
        if section:
            pct = (section["tokens"] / total_tokens) * 100
            print(f"  * {name}: {section['lines']} lines, {section['tokens']:,} tokens ({pct:.1f}%)")
    
    print()
    print(f"Potential reduction: {candidate_lines} lines ({candidate_tokens:,} tokens)")
    print(f"New total would be: {total_lines - candidate_lines} lines, "
          f"{total_tokens - candidate_tokens:,} tokens")
    reduction_pct = (candidate_tokens / total_tokens) * 100
    print(f"Reduction: {reduction_pct:.1f}%")
    
    print()
    print("RECOMMENDATIONS")
    print("-" * 80)
    print("1. Move 'Tool Reference', 'Error Recovery', and 'Quick Reference' to /help")
    print("2. Add reference: 'For detailed tool reference, use `/help tools`'")
    print("3. Add reference: 'For error recovery guidance, use `/help error`'")
    print("4. Add reference: 'For CLI commands list, use `/help commands`'")
    print("5. Keep 'Mental Model', 'Self-Awareness', 'Efficiency Patterns', 'Proactive Behavior'")
    
    if args.save:
        output_path = Path(args.save)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("System Prompt Analysis Report\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Total lines: {total_lines}\n")
            f.write(f"Total characters: {total_chars}\n")
            f.write(f"Estimated tokens: {total_tokens}\n\n")
            
            f.write("Section Breakdown:\n")
            for section in sections:
                f.write(f"- {section['name']}: {section['lines']} lines, "
                       f"{section['tokens']} tokens\n")
            
            f.write(f"\nOptimization potential: {candidate_lines} lines, "
                   f"{candidate_tokens} tokens ({reduction_pct:.1f}% reduction)\n")
        print(f"\nReport saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze Cortex system prompt")
    parser.add_argument("--save", type=str, help="Save report to file")
    parser.add_argument("--model", type=str, default="gpt-4", 
                       help="Model for token counting (default: gpt-4)")
    args = parser.parse_args()
    
    try:
        print("Analyzing system prompt...")
        prompt = extract_system_prompt()
        sections = analyze_sections(prompt)
        generate_report(prompt, sections, args)
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())