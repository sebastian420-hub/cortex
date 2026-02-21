"""
AST Analyze Tool - Code analysis using AST parsing.

Provides tools for code complexity analysis, dependency tracking,
and other code quality metrics.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict

from ...tools.base import Tool
from ...core.security import validate_path, SecurityError
from ...utils.errors import create_error_response, create_success_response, ErrorType
from ...code_ast import ASTService, detect_language, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


# Schema for tool registration
AST_ANALYZE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ast_analyze",
        "description": """Analyze code for complexity, dependencies, and potential issues.

Use ast_analyze when you need to:
- Get code complexity metrics (function count, class count, lines, cyclomatic complexity)
- Analyze dependencies and imports (internal, external, circular dependencies)
- Find potential issues (long functions, too many parameters, TODO comments, print statements)
- Calculate maintainability index

Returns detailed metrics and actionable insights about code quality.""",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory or file to analyze"},
                "analysis_type": {
                    "type": "string",
                    "enum": ["complexity", "dependencies", "issues", "all"],
                    "description": "Type of analysis: 'complexity' for metrics, 'dependencies' for import analysis, 'issues' for code smells, 'all' for everything",  # noqa: E501
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth for dependency analysis. Default: 3",
                },
                "include_metrics": {
                    "type": "boolean",
                    "description": "Include code metrics (lines, functions, classes). Default: true",  # noqa: E501
                },
                "include_dependencies": {
                    "type": "boolean",
                    "description": "Include dependency analysis. Default: true",
                },
                "include_issues": {
                    "type": "boolean",
                    "description": "Include potential issues. Default: true",
                },
            },
            "required": ["path"],
        },
    },
}


class ASTAnalyzeTool(Tool):
    """
    Code analysis tool using AST parsing.

    Provides metrics for code complexity, dependencies, and quality.
    """

    timeout_category = "analyze"
    default_timeout = 60

    def __init__(self, *args, **kwargs):
        """Initialize AST analyze tool."""
        super().__init__(*args, **kwargs)
        self.ast_service = ASTService(cache_size=50, enable_cache=True)

    def execute(
        self,
        path: str,
        analysis_type: str = "complexity",
        max_depth: int = 3,
        include_metrics: bool = True,
        include_dependencies: bool = True,
        include_issues: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze code using AST parsing.

        Args:
            path: Directory or file to analyze
            analysis_type: "complexity", "dependencies", "issues", or "all"
            max_depth: Maximum depth for dependency analysis
            include_metrics: Include code metrics
            include_dependencies: Include dependency analysis
            include_issues: Include potential issues

        Returns:
            Standardized response with analysis results
        """
        if self.console:
            self.console.print(f"[cyan]Analyzing:[/cyan] {path}")
            self.console.print(f"[dim]Analysis type: {analysis_type}[/dim]")

        # Validate path
        try:
            full_path = validate_path(self.project_dir, path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY, {"path": path})

        if not full_path.exists():
            return create_error_response(
                f"Path not found: {path}", ErrorType.NOT_FOUND, {"path": path}
            )

        # Validate analysis type
        valid_types = ["complexity", "dependencies", "issues", "all"]
        if analysis_type not in valid_types:
            return create_error_response(
                f"Invalid analysis_type: {analysis_type}. Must be one of: {valid_types}",
                ErrorType.VALIDATION,
                {"analysis_type": analysis_type},
            )

        # Find files to analyze
        files = self._find_files(full_path)

        if not files:
            return create_success_response(
                {
                    "analysis": {},
                    "file_count": 0,
                    "message": "No files to analyze",
                }
            )

        results = {
            "files_analyzed": len(files),
            "analysis_type": analysis_type,
            "metrics": {},
            "dependencies": {},
            "issues": [],
        }

        for file_path in files:
            # Detect language
            language = detect_language(file_path)
            if not language or language not in SUPPORTED_LANGUAGES:
                continue

            # Analyze file
            file_analysis = self._analyze_file(
                file_path,
                language,
                analysis_type,
                max_depth,
                include_metrics,
                include_dependencies,
                include_issues,
            )

            if file_analysis:
                rel_path = str(file_path.relative_to(self.project_dir))
                results["metrics"][rel_path] = file_analysis.get("metrics", {})

                if "dependencies" in file_analysis:
                    results["dependencies"][rel_path] = file_analysis["dependencies"]

                if "issues" in file_analysis:
                    results["issues"].extend(file_analysis["issues"])

        # Calculate aggregate metrics
        if results["metrics"]:
            results["aggregate_metrics"] = self._calculate_aggregate_metrics(results["metrics"])

        # Calculate dependency graph
        if results["dependencies"]:
            results["dependency_graph"] = self._build_dependency_graph(results["dependencies"])

        return create_success_response(results)

    def _analyze_file(
        self,
        file_path: Path,
        language: str,
        analysis_type: str,
        max_depth: int,
        include_metrics: bool,
        include_dependencies: bool,
        include_issues: bool,
    ) -> Dict[str, Any]:
        """
        Analyze a single file.

        Args:
            file_path: Path to the file
            language: Programming language
            analysis_type: Type of analysis
            max_depth: Maximum depth for dependencies
            include_metrics: Include metrics
            include_dependencies: Include dependencies
            include_issues: Include issues

        Returns:
            File analysis results
        """
        results = {}
        _rel_path = str(file_path.relative_to(self.project_dir))

        if include_metrics or analysis_type in ["complexity", "all"]:
            results["metrics"] = self._calculate_file_metrics(file_path, language)

        if include_dependencies or analysis_type in ["dependencies", "all"]:
            results["dependencies"] = self._analyze_dependencies(file_path, language, max_depth)

        if include_issues or analysis_type in ["issues", "all"]:
            results["issues"] = self._find_potential_issues(file_path, language)

        return results

    def _calculate_file_metrics(self, file_path: Path, language: str) -> Dict[str, Any]:
        """
        Calculate code metrics for a file.

        Args:
            file_path: Path to the file
            language: Programming language

        Returns:
            Code metrics
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            # Basic metrics
            metrics = {
                "lines": len(lines),
                "non_empty_lines": sum(1 for line in lines if line.strip()),
                "comment_lines": sum(
                    1
                    for line in lines
                    if line.strip().startswith("#") or line.strip().startswith("//")
                ),
            }

            # AST-based metrics
            functions = self.ast_service.extract_functions(file_path, language)
            classes = self.ast_service.extract_classes(file_path, language)
            imports = self.ast_service.extract_imports(file_path, language)

            metrics.update(
                {
                    "function_count": len(functions),
                    "class_count": len(classes),
                    "import_count": len(imports),
                    "average_function_length": self._calculate_average_function_length(functions),
                    "max_function_length": self._calculate_max_function_length(functions),
                    "average_parameters": self._calculate_average_parameters(functions),
                }
            )

            # Complexity metrics
            metrics["cyclomatic_complexity"] = self._estimate_cyclomatic_complexity(
                content, language
            )
            metrics["maintainability_index"] = self._calculate_maintainability_index(metrics)

            return metrics

        except Exception as e:
            logger.error(f"Failed to calculate metrics for {file_path}: {e}")
            return {}

    def _analyze_dependencies(
        self, file_path: Path, language: str, max_depth: int
    ) -> Dict[str, Any]:
        """
        Analyze dependencies for a file.

        Args:
            file_path: Path to the file
            language: Programming language
            max_depth: Maximum depth

        Returns:
            Dependency analysis
        """
        try:
            imports = self.ast_service.extract_imports(file_path, language)

            dependencies = {
                "imports": [],
                "internal_deps": [],
                "external_deps": [],
                "standard_lib_deps": [],
            }

            for imp in imports:
                dep_info = {
                    "module": imp.module,
                    "imports": imp.imports,
                    "line": imp.line,
                }

                dependencies["imports"].append(dep_info)

                # Categorize dependencies
                if self._is_standard_library(imp.module, language):
                    dependencies["standard_lib_deps"].append(imp.module)
                elif self._is_internal_dependency(imp.module, file_path):
                    dependencies["internal_deps"].append(imp.module)
                else:
                    dependencies["external_deps"].append(imp.module)

            # Remove duplicates
            for key in dependencies:
                if key == "imports":
                    continue
                if isinstance(dependencies[key], list):
                    dependencies[key] = list(set(dependencies[key]))

            return dependencies

        except Exception as e:
            logger.error(f"Failed to analyze dependencies for {file_path}: {e}")
            return {}

    def _find_potential_issues(self, file_path: Path, language: str) -> List[Dict[str, Any]]:
        """
        Find potential issues in a file.

        Args:
            file_path: Path to the file
            language: Programming language

        Returns:
            List of potential issues
        """
        issues = []
        rel_path = str(file_path.relative_to(self.project_dir))

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            # Check for long functions
            functions = self.ast_service.extract_functions(file_path, language)
            for func in functions:
                length = func.end_line - func.start_line + 1
                if length > 50:  # Threshold for long functions
                    issues.append(
                        {
                            "type": "long_function",
                            "file": rel_path,
                            "line": func.start_line,
                            "message": f"Function '{func.name}' is {length} lines long (consider refactoring)",  # noqa: E501
                            "severity": "warning",
                        }
                    )

                # Check for many parameters
                if len(func.parameters) > 7:  # Threshold for many parameters
                    issues.append(
                        {
                            "type": "many_parameters",
                            "file": rel_path,
                            "line": func.start_line,
                            "message": f"Function '{func.name}' has {len(func.parameters)} parameters (consider using data classes or kwargs)",  # noqa: E501
                            "severity": "warning",
                        }
                    )

            # Check for TODO/FIXME comments
            for i, line in enumerate(lines, 1):
                line_lower = line.lower()
                if "todo" in line_lower or "fixme" in line_lower or "xxx" in line_lower:
                    issues.append(
                        {
                            "type": "todo_comment",
                            "file": rel_path,
                            "line": i,
                            "message": f"TODO/FIXME comment found: {line.strip()[:100]}",
                            "severity": "info",
                        }
                    )

            # Check for print statements (in Python)
            if language == "python":
                for i, line in enumerate(lines, 1):
                    if "print(" in line and not line.strip().startswith("#"):
                        issues.append(
                            {
                                "type": "print_statement",
                                "file": rel_path,
                                "line": i,
                                "message": "Print statement found (consider using logging)",
                                "severity": "info",
                            }
                        )

            return issues

        except Exception as e:
            logger.error(f"Failed to find issues for {file_path}: {e}")
            return []

    def _calculate_average_function_length(self, functions: List) -> float:
        """Calculate average function length."""
        if not functions:
            return 0.0

        total_length = sum(func.end_line - func.start_line + 1 for func in functions)
        return total_length / len(functions)

    def _calculate_max_function_length(self, functions: List) -> int:
        """Calculate maximum function length."""
        if not functions:
            return 0

        return max((func.end_line - func.start_line + 1 for func in functions), default=0)

    def _calculate_average_parameters(self, functions: List) -> float:
        """Calculate average number of parameters."""
        if not functions:
            return 0.0

        total_params = sum(len(func.parameters) for func in functions)
        return total_params / len(functions)

    def _estimate_cyclomatic_complexity(self, content: str, language: str) -> int:
        """
        Estimate cyclomatic complexity.

        This is a simplified estimation based on control flow keywords.
        """
        complexity = 1  # Base complexity

        # Count control flow keywords
        keywords = []
        if language == "python":
            keywords = ["if", "elif", "for", "while", "except", "and", "or"]
        elif language in ["javascript", "typescript"]:
            keywords = ["if", "else if", "for", "while", "catch", "&&", "||", "case"]
        elif language == "java":
            keywords = ["if", "else if", "for", "while", "catch", "case", "&&", "||"]

        for keyword in keywords:
            complexity += content.lower().count(keyword)

        return complexity

    def _calculate_maintainability_index(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate maintainability index.

        Simplified formula based on common metrics.
        """
        # Simplified maintainability index calculation
        lines = metrics.get("lines", 0)
        complexity = metrics.get("cyclomatic_complexity", 1)
        comment_ratio = metrics.get("comment_lines", 0) / max(lines, 1)

        # Basic formula (simplified)
        mi = 171 - 5.2 * (complexity**0.5) - 0.23 * (lines**0.5) + 50 * (comment_ratio**0.5)

        # Clamp to reasonable range
        return max(0, min(100, mi))

    def _is_standard_library(self, module: str, language: str) -> bool:
        """Check if module is from standard library."""
        # Simplified check - in practice would use language-specific standard lib lists
        stdlib_prefixes = {
            "python": ["os", "sys", "json", "re", "datetime", "collections", "itertools", "math"],
            "javascript": [],  # Node.js doesn't have a clear stdlib
            "typescript": [],
            "java": ["java.", "javax."],
        }

        if language in stdlib_prefixes:
            for prefix in stdlib_prefixes[language]:
                if module.startswith(prefix):
                    return True

        return False

    def _is_internal_dependency(self, module: str, file_path: Path) -> bool:
        """Check if module is an internal dependency."""
        # Check if module could be a local file
        if module.startswith("."):
            return True

        # Check if module exists in project
        project_root = self.project_dir
        possible_paths = [
            project_root / f"{module}.py",
            project_root / module / "__init__.py",
            project_root / f"{module}.js",
            project_root / f"{module}.ts",
        ]

        return any(path.exists() for path in possible_paths)

    def _calculate_aggregate_metrics(self, metrics_by_file: Dict[str, Dict]) -> Dict[str, Any]:
        """Calculate aggregate metrics across all files."""
        if not metrics_by_file:
            return {}

        aggregate = {
            "total_files": len(metrics_by_file),
            "total_lines": 0,
            "total_functions": 0,
            "total_classes": 0,
            "total_imports": 0,
            "average_complexity": 0.0,
            "average_maintainability": 0.0,
        }

        total_complexity = 0
        total_maintainability = 0
        file_count = 0

        for file_metrics in metrics_by_file.values():
            if not file_metrics:
                continue

            aggregate["total_lines"] += file_metrics.get("lines", 0)
            aggregate["total_functions"] += file_metrics.get("function_count", 0)
            aggregate["total_classes"] += file_metrics.get("class_count", 0)
            aggregate["total_imports"] += file_metrics.get("import_count", 0)

            total_complexity += file_metrics.get("cyclomatic_complexity", 0)
            total_maintainability += file_metrics.get("maintainability_index", 0)
            file_count += 1

        if file_count > 0:
            aggregate["average_complexity"] = total_complexity / file_count
            aggregate["average_maintainability"] = total_maintainability / file_count

        return aggregate

    def _build_dependency_graph(self, dependencies_by_file: Dict[str, Dict]) -> Dict[str, Any]:
        """Build dependency graph from file dependencies."""
        graph = {
            "nodes": [],
            "edges": [],
            "circular_dependencies": [],
        }

        # Add nodes
        for file_path in dependencies_by_file:
            graph["nodes"].append(
                {
                    "id": file_path,
                    "type": "file",
                }
            )

        # Add edges
        for file_path, deps in dependencies_by_file.items():
            for dep in deps.get("imports", []):
                module = dep.get("module", "")
                if module:
                    graph["edges"].append(
                        {
                            "source": file_path,
                            "target": module,
                            "type": "import",
                        }
                    )

        # Simple circular dependency detection (simplified)
        visited = set()

        def dfs(node, path):
            if node in path:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                if len(cycle) > 2:  # Only report non-trivial cycles
                    graph["circular_dependencies"].append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            path.append(node)

            # Find outgoing edges
            for edge in graph["edges"]:
                if edge["source"] == node:
                    dfs(edge["target"], path.copy())

        for node in graph["nodes"]:
            dfs(node["id"], [])

        return graph

    def _find_files(self, path: Path) -> List[Path]:
        """
        Find files to analyze.

        Args:
            path: Base path

        Returns:
            List of file paths
        """
        if path.is_file():
            return [path]

        # Collect all supported code files
        files = []

        for lang_config in SUPPORTED_LANGUAGES.values():
            for ext in lang_config["extensions"]:
                pattern = f"**/*{ext}"
                files.extend(path.glob(pattern))

        # Filter to actual files and skip hidden/binary
        filtered = []
        for f in files:
            if not f.is_file():
                continue

            # Skip hidden files and common binary/generated directories
            parts = f.relative_to(path).parts
            skip_dirs = {
                ".git",
                ".svn",
                ".hg",
                "node_modules",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".coverage",
                "dist",
                "build",
                "target",
                "out",
                "bin",
                "obj",
                ".next",
            }

            if any(part.startswith(".") for part in parts):
                continue

            if any(part in skip_dirs for part in parts):
                continue

            filtered.append(f)

        return filtered
