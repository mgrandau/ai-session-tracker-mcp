#!/usr/bin/env python3
"""Analyze all Python files in the source directory.

This utility script runs the DocScope analyzer against every Python file
in the src directory, outputting JSON for use as prompt context.

Usage:
    python utils/analyze_all_source.py
    python utils/analyze_all_source.py --output analysis.json
    python utils/analyze_all_source.py --pretty

Examples:
    # Analyze with custom project root
    main(project_root=Path("/my/project"))

    # Test with mock analyzer
    main(analyzer=mock_analyzer)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docscope_mcp.analyzers.python import PythonAnalyzer

# Patterns to exclude from file discovery
EXCLUDED_PATTERNS = ("__pycache__", ".pyc")


def find_python_files(target_dir: Path) -> list[Path]:
    """Find all Python files in the target directory.

    Recursively discovers Python source files while filtering out
    cache directories and compiled bytecode.

    Business context:
    Enables batch analysis of entire codebases by discovering all
    analyzable files. Used as the first step in documentation audits.

    Args:
        target_dir: Path to the directory to scan. Must exist.

    Returns:
        List of paths to Python files, sorted alphabetically.
        Excludes __pycache__ directories and .pyc files.

    Raises:
        OSError: If target_dir is not accessible or doesn't exist.

    Examples:
        >>> files = find_python_files(Path("src"))
        >>> [f.name for f in files[:2]]
        ['__init__.py', 'analyzer.py']
    """
    python_files = [
        py_file
        for py_file in target_dir.rglob("*.py")
        if not any(pattern in str(py_file) for pattern in EXCLUDED_PATTERNS)
    ]
    return sorted(python_files)


def analyze_file(
    analyzer: PythonAnalyzer,
    file_path: Path,
    project_root: Path,
) -> dict:
    """Analyze a single Python file and return structured results.

    Reads the file, runs documentation quality analysis, and formats
    results for JSON output. Handles errors gracefully by returning
    error information instead of raising.

    Business context:
    Core analysis function that produces per-file quality metrics.
    Results feed into aggregate reports for documentation audits.

    Args:
        analyzer: The PythonAnalyzer instance to use for quality assessment.
        file_path: Absolute path to the Python file to analyze.
        project_root: Root directory for computing relative paths in output.

    Returns:
        Dictionary with keys:
        - file: Relative path from project_root
        - functions_needing_improvement: Count of functions with issues
        - functions: List of function analysis dicts
        - error: (optional) Error message if analysis failed

    Raises:
        ValueError: If file_path is not under project_root.

    Examples:
        >>> result = analyze_file(analyzer, Path("src/main.py"), Path("."))
        >>> result["file"]
        'src/main.py'
        >>> len(result["functions"]) >= 0
        True
    """
    relative_path = str(file_path.relative_to(project_root))

    try:
        code = file_path.read_text(encoding="utf-8")
        results = analyzer.analyze(code, str(file_path))

        # Clean up results for JSON output
        functions = [
            {
                "name": func.get("function_name", "unknown"),
                "line": func.get("line_number", 0),
                "quality": func.get("quality_assessment", {}).get("quality", "unknown"),
                "priority": func.get("priority", 0),
                "missing": func.get("quality_assessment", {}).get("missing", []),
                "has_docstring": bool(func.get("current_docstring")),
            }
            for func in results
            if "error" not in func
        ]

        return {
            "file": relative_path,
            "functions_needing_improvement": len(functions),
            "functions": functions,
        }

    except (OSError, UnicodeDecodeError, SyntaxError) as e:
        return {
            "file": relative_path,
            "error": str(e),
            "functions_needing_improvement": 0,
            "functions": [],
        }


def main(
    project_root: Path | None = None,
    analyzer: PythonAnalyzer | None = None,
) -> int:
    """Analyze all source files and output JSON.

    Scans all Python files in src directory and outputs structured
    JSON for use as context in AI prompts.

    Args:
        project_root: Root directory of the project. Defaults to parent of utils/.
        analyzer: PythonAnalyzer instance to use. Creates default if None.

    Returns:
        Exit code: 0 on success, 1 on error.

    Raises:
        ValueError: If project_root does not contain a src/ directory.
    """
    # Set up project root and imports
    if project_root is None:
        project_root = Path(__file__).parent.parent

    src_dir = project_root / "src"
    if not src_dir.exists():
        raise ValueError(f"Invalid project_root: {project_root} has no src/ directory")

    # Guard against duplicate sys.path entries
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from docscope_mcp.analyzers.python import PythonAnalyzer as Analyzer
    from docscope_mcp.models import DEFAULT_CONFIG

    parser = argparse.ArgumentParser(
        description="Analyze documentation quality for all Python files in src"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Write JSON output to file (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="Pretty-print JSON output with indentation",
    )
    args = parser.parse_args()

    python_files = find_python_files(src_dir)
    if not python_files:
        print("No Python files found in src directory", file=sys.stderr)
        return 1

    if analyzer is None:
        analyzer = Analyzer(config=DEFAULT_CONFIG)

    # Build JSON report
    report = {
        "report_type": "source_analysis",
        "generated_at": datetime.now(UTC).isoformat(),
        "target_directory": "src",
        "files_scanned": len(python_files),
        "summary": {
            "total_files": len(python_files),
            "files_with_issues": 0,
            "total_functions_to_improve": 0,
        },
        "files": [],
    }

    for py_file in python_files:
        file_result = analyze_file(analyzer, py_file, project_root)
        report["files"].append(file_result)

        func_count = file_result["functions_needing_improvement"]
        if func_count > 0:
            report["summary"]["files_with_issues"] += 1
            report["summary"]["total_functions_to_improve"] += func_count

    # Output JSON
    indent = 2 if args.pretty else None
    json_output = json.dumps(report, indent=indent)

    if args.output:
        Path(args.output).write_text(json_output, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(json_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
