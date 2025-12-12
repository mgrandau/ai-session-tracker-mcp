#!/usr/bin/env python3
"""GitHub Issue Creator w/ Dynamic Label Discovery.

Batch creates GitHub issues from JSON definitions via gh CLI. Provides label
validation, auto-creation of missing labels, and AI-friendly output formats.

Business: Bridges code review findings → GitHub issues. Enables automated
technical debt tracking w/ standardized labels for priority, category, workflow,
and effort estimates. Integrates w/ code_quality_metrics.py via [Est: Xh] format.

Requires: Python ≥3.10 (uses | union types)

Features:
    • Dynamic label discovery ← repository
    • Label validation before issue creation
    • AI-friendly label output format
    • Batch issue creation w/ progress tracking
    • Security: Command injection prevention
    • Retry w/ exponential backoff for rate limits

Usage:
    # Create standard labels in repository
    python create_issues.py --repository owner/repo --create-labels

    # List available labels for AI
    python create_issues.py --repository owner/repo --list-labels

    # Validate issues w/o creating
    python create_issues.py --issues issues.json --repository owner/repo --validate-only

    # Create issues from JSON file
    python create_issues.py --issues issues.json --repository owner/repo

JSON Schema:
    {"issues": [{"title": str, "labels": [str], "estimate": str, "body": {...}}]}
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404 - Required for gh CLI; inputs validated via DANGEROUS_CHARS_REGEX
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ============================================================================
# Configuration Constants
# ============================================================================

MAX_RETRIES = 3
INITIAL_RETRY_DELAY_MS = 1000
MAX_LABEL_LIMIT = 1000
MAX_TITLE_LENGTH = 1000
MAX_BODY_LENGTH = 50000

# Rate limit detection patterns
RATE_LIMIT_PATTERNS = ["rate limit", "API rate limit", "403"]

# Dangerous characters that could cause command injection
# For strict mode: title and labels (passed as command args)
DANGEROUS_CHARS_REGEX = re.compile(r'[;&|`$<>(){}\[\]"\']')

# Label category constants (single source of truth)
CATEGORY_LABELS = frozenset(
    {
        "security",
        "performance",
        "robustness",
        "testability",
        "type-safety",
        "architecture",
    }
)
WORKFLOW_LABELS = frozenset({"needs-triage", "approved-fix", "hold-future"})

# Fallback sort order for malformed estimate labels
MALFORMED_ESTIMATE_SORT_ORDER = 999.0

# Repository format validation pattern
REPO_PATTERN = re.compile(r"^[\w-]+/[\w-]+$")

# ============================================================================
# Color Output Helpers
# ============================================================================


class Colors:
    """ANSI escape codes for colored terminal output.

    Business: Provides visual feedback during CLI execution. Color-coded msgs
    improve UX by distinguishing errors (red), warnings (yellow), success (green).

    Attributes:
        RED: Error msgs, failed operations.
        GREEN: Success msgs, completed operations.
        YELLOW: Warnings, non-fatal issues.
        CYAN: Info msgs, status updates.
        WHITE: Default text.
        GRAY: Secondary info, descriptions.
        MAGENTA: Highlights.
        RESET: Clear formatting.
        BOLD: Emphasis.
    """

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # Priority display colors for CLI output
    PRIORITY_COLORS: dict[str, str] = {}

    @classmethod
    def get_priority_color(cls, priority: str | None) -> str:
        """Get color for priority label, with lazy initialization."""
        if not cls.PRIORITY_COLORS:
            cls.PRIORITY_COLORS = {
                "p1": cls.RED,
                "p2": cls.YELLOW,
                "p3": cls.CYAN,
                "p4": cls.GRAY,
            }
        return cls.PRIORITY_COLORS.get(priority, cls.WHITE) if priority else cls.WHITE


def print_color(message: str, color: str = Colors.WHITE, end: str = "\n") -> None:
    """Print colored msg to stdout w/ ANSI codes.

    Wraps msg w/ color code and RESET to prevent color bleed. Thread-safe
    via print() builtin.

    Business: Provides consistent colored output across all CLI feedback.

    Args:
        message: Text to print. May contain emoji/unicode.
        color: ANSI escape code ∈ Colors.*. Default: WHITE.
        end: Line ending. Default: newline.

    Examples:
        ```python
        print_color("Success!", Colors.GREEN)
        print_color("Loading", Colors.CYAN, end="...")
        ```

    Technical: O(1). ~0.01ms. No buffering issues w/ default flush.
    """
    print(f"{color}{message}{Colors.RESET}", end=end)


def print_error(message: str) -> None:
    """Print error msg in red w/ [ERROR] prefix.

    Business: Standardizes error output format for CLI. Red color ensures
    visibility in terminal output.

    Args:
        message: Error description. Should be user-readable.

    Examples:
        ```python
        print_error("File not found: config.json")
        # Output: [ERROR] File not found: config.json (in red)
        ```
    """
    print_color(f"[ERROR] {message}", Colors.RED)


def print_warning(message: str) -> None:
    """Print warning msg in yellow w/ [WARN] prefix.

    Business: Indicates non-fatal issues that may need attention. Yellow
    distinguishes from errors (red) and success (green).

    Args:
        message: Warning description. Should explain the concern.

    Examples:
        ```python
        print_warning("Missing optional field: estimate")
        # Output: [WARN] Missing optional field: estimate (in yellow)
        ```
    """
    print_color(f"[WARN] {message}", Colors.YELLOW)


def print_success(message: str) -> None:
    """Print success msg in green w/ [OK] prefix.

    Business: Confirms completed operations. Green provides positive feedback.

    Args:
        message: Success description.

    Examples:
        ```python
        print_success("Created: https://github.com/o/r/issues/1")
        # Output: [OK] Created: https://github.com/o/r/issues/1 (in green)
        ```
    """
    print_color(f"[OK] {message}", Colors.GREEN)


def print_info(message: str) -> None:
    """Print info msg in cyan (no prefix).

    Business: Status updates and informational output. Cyan distinguishes
    from regular text and other msg types.

    Args:
        message: Info text. No prefix added.

    Examples:
        ```python
        print_info("Found 5 labels in repository")
        # Output: Found 5 labels in repository (in cyan)
        ```
    """
    print_color(message, Colors.CYAN)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class Label:
    """GitHub label definition for issue categorization.

    Business: Standardizes label structure for creation via gh CLI. Enables
    consistent labeling across priority, category, workflow, and estimate types.

    Attributes:
        name: Label identifier. Max 50 chars. E.g., "p1", "estimate: 2h".
        description: Human-readable purpose. Max 100 chars.
        color: Hex color w/o #. E.g., "d73a4a" (red).
    """

    name: str
    description: str
    color: str


@dataclass
class OperationResult:
    """Result wrapper for gh CLI operations.

    Business: Provides structured success/failure info for retry logic and
    error handling. Captures attempt count for rate limit debugging.

    Attributes:
        success: True if operation completed w/o error.
        result: Operation output (JSON, URL, etc.) if success=True.
        error: Error msg if success=False.
        attempt: Which retry attempt succeeded/failed. Default: 1.
    """

    success: bool
    result: Any = None
    error: str | None = None
    attempt: int = 1


@dataclass
class ValidationResult:
    """Accumulated validation errors and warnings for an issue.

    Business: Separates blocking errors (prevent creation) from warnings
    (informational). Enables batch validation w/ full error reporting.

    Attributes:
        errors: Blocking issues. Issue won't be created if non-empty.
        warnings: Non-blocking concerns. Issue created but flagged.
    """

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


@dataclass
class IssueCreationResult:
    """Result of single GitHub issue creation.

    Business: Captures issue URL on success for summary output. Error msg
    enables debugging failed creations.

    Attributes:
        success: True if issue created.
        issue_url: GitHub issue URL if success=True. E.g., "https://github.com/o/r/issues/1".
        error: gh CLI error msg if success=False.
    """

    success: bool
    issue_url: str | None = None
    error: str | None = None


@dataclass
class BatchCreationResult:
    """Aggregated results from batch issue creation.

    Business: Tracks success/failure counts and details for summary report.
    Enables partial success reporting when some issues fail.

    Attributes:
        success_count: Num issues created. ≥0.
        fail_count: Num issues failed. ≥0.
        created_issues: List of {title, url} for created issues.
        failed_issues: List of {title, error} for failed issues.
    """

    success_count: int = 0
    fail_count: int = 0
    created_issues: list[dict[str, str]] = field(default_factory=list)
    failed_issues: list[dict[str, str]] = field(default_factory=list)


# ============================================================================
# GitHub CLI Functions
# ============================================================================


def check_github_cli_available() -> OperationResult:
    """Validate gh CLI availability and authentication → OperationResult.

    Checks gh version and auth status before any GitHub operations. Fails fast
    if CLI missing or not authenticated, preventing confusing downstream errors.

    Business: Prerequisite check for all GitHub operations. Provides clear
    error msgs guiding users to install gh or run `gh auth login`.

    Returns:
        OperationResult: success=True w/ version string, or success=False w/
        specific error msg (not installed, not authenticated, timeout).

    Raises:
        None (errors captured in OperationResult.error).

    Examples:
        ```python
        result = check_github_cli_available()
        if not result.success:
            print(f"Setup required: {result.error}")
        ```

    Technical: 2 subprocess calls, 30s timeout each. ~100ms typical.
    """
    try:
        # Check gh version
        result = subprocess.run(  # nosec B603 B607 - Fixed command, no user input
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return OperationResult(
                success=False,
                error="GitHub CLI (gh) is not installed or not in PATH",
            )

        version = result.stdout.strip().split("\n")[0]

        # Check authentication
        auth_result = subprocess.run(  # nosec B603 B607 - Fixed command, no user input
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if auth_result.returncode != 0:
            return OperationResult(
                success=False,
                error="GitHub CLI is not authenticated. Run 'gh auth login'",
            )

        return OperationResult(success=True, result=f"GitHub CLI ready: {version}")

    except FileNotFoundError:
        return OperationResult(
            success=False,
            error="GitHub CLI (gh) is not installed",
        )
    except subprocess.TimeoutExpired:
        return OperationResult(
            success=False,
            error="GitHub CLI command timed out",
        )
    except Exception as e:
        return OperationResult(success=False, error=f"Error checking GitHub CLI: {e}")


def invoke_with_retry(
    command: list[str],
    operation: str = "Operation",
    max_retries: int = MAX_RETRIES,
) -> OperationResult:
    """Execute gh CLI command w/ exponential backoff for transient failures.

    Retries on rate limits (403) and timeouts. Doubles delay after each retry
    starting from INITIAL_RETRY_DELAY_MS. Non-retryable errors return immediately.

    Business: Handles GitHub API rate limits gracefully. Prevents batch jobs
    from failing due to transient network/API issues.

    Args:
        command: Full command w/ args. E.g., ["gh", "issue", "create", ...].
        operation: Human-readable name for log msgs. E.g., "Create issue".
        max_retries: Max attempts before giving up. Default: 3.

    Returns:
        OperationResult: success=True w/ stdout, or success=False w/ stderr.
        Includes attempt count for debugging.

    Raises:
        None (all errors captured in OperationResult).

    Examples:
        ```python
        result = invoke_with_retry(["gh", "label", "list"], "Fetch labels")
        if result.success:
            labels = json.loads(result.result)
        ```

    Technical: O(max_retries). Delays: 1s, 2s, 4s (exponential). 120s timeout/attempt.
    """
    attempt = 0
    delay_ms = INITIAL_RETRY_DELAY_MS

    while attempt < max_retries:
        attempt += 1
        try:
            result = subprocess.run(  # nosec B603
                command,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                return OperationResult(
                    success=True,
                    result=result.stdout.strip(),
                    attempt=attempt,
                )

            # Check for rate limit
            output = result.stderr + result.stdout
            rate_limited = any(pattern in output.lower() for pattern in RATE_LIMIT_PATTERNS)

            if rate_limited:
                msg = f"{operation}: Rate limited, waiting {delay_ms}ms "
                msg += f"before retry {attempt}/{max_retries}"
                print_warning(msg)
                time.sleep(delay_ms / 1000)
                delay_ms *= 2
                continue

            # Non-retryable error
            return OperationResult(
                success=False,
                error=result.stderr.strip() or result.stdout.strip(),
                attempt=attempt,
            )

        except subprocess.TimeoutExpired:
            if attempt >= max_retries:
                return OperationResult(
                    success=False,
                    error="Command timed out",
                    attempt=attempt,
                )
            print_warning(f"{operation}: Timeout, retrying in {delay_ms}ms...")
            time.sleep(delay_ms / 1000)
            delay_ms *= 2

        except Exception as e:
            if attempt >= max_retries:
                return OperationResult(
                    success=False,
                    error=str(e),
                    attempt=attempt,
                )
            print_warning(f"{operation}: Attempt {attempt} failed, retrying in {delay_ms}ms...")
            time.sleep(delay_ms / 1000)
            delay_ms *= 2

    return OperationResult(success=False, error="Max retries exceeded", attempt=attempt)


def get_repository_labels(repo: str) -> OperationResult:
    """Fetch all labels from repository via gh CLI → list[dict].

    Retrieves label name, description, and color for validation and display.
    Uses retry logic for rate limit handling.

    Business: Enables label validation before issue creation. Prevents issues
    w/ non-existent labels from failing during batch creation.

    Args:
        repo: Repository in "owner/repo" format. E.g., "mgrandau/copilot-confirm".

    Returns:
        OperationResult: success=True w/ list of {name, description, color} dicts,
        or success=False w/ error msg.

    Raises:
        None (errors captured in OperationResult).

    Examples:
        ```python
        result = get_repository_labels("owner/repo")
        if result.success:
            for label in result.result:
                print(f"{label['name']}: {label['description']}")
        ```

    Technical: Single API call. Returns up to MAX_LABEL_LIMIT (1000) labels.
    """
    result = invoke_with_retry(
        [
            "gh",
            "label",
            "list",
            "--repo",
            repo,
            "--json",
            "name,description,color",
            "--limit",
            str(MAX_LABEL_LIMIT),
        ],
        operation="Fetch labels",
    )

    if not result.success:
        return OperationResult(
            success=False,
            error=f"Failed to fetch labels from {repo}: {result.error}",
        )

    try:
        labels = json.loads(result.result) if result.result else []
        return OperationResult(success=True, result=labels)
    except json.JSONDecodeError as e:
        return OperationResult(
            success=False,
            error=f"Failed to parse label JSON response: {e}",
        )


def create_label(label: Label, repo: str) -> OperationResult:
    """Create single label in repository via gh CLI.

    Uses --force to update existing labels. Handles auth errors specially
    by raising PermissionError to abort batch operations.

    Business: Ensures required labels exist before issue creation. Auto-creates
    missing priority, category, workflow, and estimate labels.

    Args:
        label: Label definition w/ name, description, color.
        repo: Repository in "owner/repo" format.

    Returns:
        OperationResult: success=True if created or already exists.

    Raises:
        PermissionError: If authentication/permission error (401/403).

    Examples:
        ```python
        label = Label("p1", "Critical priority", "d73a4a")
        result = create_label(label, "owner/repo")
        ```

    Technical: Single API call w/ retry. ~1-2s per label.
    """
    print_info(f"Creating label: {label.name}")

    result = invoke_with_retry(
        [
            "gh",
            "label",
            "create",
            label.name,
            "--repo",
            repo,
            "--description",
            label.description,
            "--color",
            label.color,
            "--force",
        ],
        operation=f"Create label '{label.name}'",
    )

    if result.success:
        print_success("Created")
        return OperationResult(success=True, result="Label created")

    # Check if it's just "already exists"
    if result.error and "already exists" in result.error.lower():
        print_color("  [INFO] Already exists", Colors.GRAY)
        return OperationResult(success=True, result="Already exists")

    # Check for auth errors
    if result.error and any(
        x in result.error.lower() for x in ["authentication", "permission", "401", "403"]
    ):
        print_error("Authentication/permission error")
        raise PermissionError(f"Authentication error creating label '{label.name}': {result.error}")

    print_error(f"Failed: {result.error}")
    return OperationResult(success=False, error=result.error)


# ============================================================================
# Label Definitions
# ============================================================================


def get_required_labels() -> list[Label]:
    """Get standard label set for code review issue tracking → list[Label].

    Defines 4 label categories: priority (p1-p4), category (security, etc.),
    workflow (needs-triage, etc.), and effort estimates (0.5h-80h).

    Business: Standardizes issue labeling across projects. Enables filtering,
    reporting, and integration w/ code_quality_metrics.py.

    Returns:
        list[Label]: 22 labels covering all categories. Immutable definitions.

    Examples:
        ```python
        labels = get_required_labels()
        priorities = [l for l in labels if l.name.startswith("p")]
        ```

    Technical: Pure func, no I/O. O(1). Returns new list each call.
    """
    return [
        # Priority labels
        Label(
            "p1",
            "Priority 1: Critical - Security, data integrity, severe performance",
            "d73a4a",
        ),
        Label(
            "p2",
            "Priority 2: High - Testability, maintainability, error handling",
            "ff9800",
        ),
        Label(
            "p3",
            "Priority 3: Medium - Organization, naming, moderate duplication",
            "ffc107",
        ),
        Label(
            "p4",
            "Priority 4: Low - Documentation, formatting, minor refactoring",
            "e0e0e0",
        ),
        # Category labels
        Label("security", "Security-related issues", "d73a4a"),
        Label("performance", "Performance optimization", "0e8a16"),
        Label("robustness", "Error handling and resilience", "1d76db"),
        Label("testability", "Testing and test infrastructure", "ededed"),
        Label("type-safety", "Type hints and type checking", "5319e7"),
        Label("architecture", "Architectural improvements", "0052cc"),
        # Workflow labels
        Label(
            "needs-triage",
            "Workflow: Awaiting developer review and triage decision",
            "8B4789",
        ),
        Label(
            "approved-fix",
            "Workflow: Triaged and approved for implementation",
            "6A1B9A",
        ),
        Label(
            "hold-future",
            "Workflow: Valid issue but deferred to future milestone",
            "9C27B0",
        ),
        # Estimate labels
        Label("estimate: 0.5h", "Estimated effort: 0.5 hours", "c5def5"),
        Label("estimate: 1h", "Estimated effort: 1 hour", "bfd4f2"),
        Label("estimate: 2h", "Estimated effort: 2 hours", "9dc7f4"),
        Label("estimate: 4h", "Estimated effort: 4 hours", "6ba3d2"),
        Label("estimate: 8h", "Estimated effort: 8 hours (1 day)", "3d7fc2"),
        Label("estimate: 16h", "Estimated effort: 16 hours (2 days)", "2e6bb5"),
        Label("estimate: 40h", "Estimated effort: 40 hours (1 week)", "1f5aa8"),
        Label("estimate: 80h", "Estimated effort: 80 hours (2 weeks / month+)", "0d4a9b"),
    ]


def get_missing_labels(existing_labels: list[dict], required_labels: list[Label]) -> list[Label]:
    """Find required labels not in repository → list[Label].

    Compares required label names against existing. Returns labels that need
    to be created before issue creation can proceed.

    Business: Enables auto-creation of missing labels. Prevents batch failures
    due to non-existent label references.

    Args:
        existing_labels: Labels ← get_repository_labels(). List of {name, ...}.
        required_labels: Labels ← get_required_labels().

    Returns:
        list[Label]: Labels in required but not in existing. Empty if all present.

    Examples:
        ```python
        existing = [{"name": "p1"}, {"name": "p2"}]
        required = get_required_labels()
        missing = get_missing_labels(existing, required)
        # Returns labels for p3, p4, security, etc.
        ```

    Technical: O(n+m) where n=existing, m=required. Uses set for O(1) lookup.
    """
    existing_names = {label["name"] for label in existing_labels}
    return [label for label in required_labels if label.name not in existing_names]


def create_labels_batch(labels: list[Label], repo: str) -> None:
    """Create multiple labels in repository sequentially.

    Processes labels one at a time. Continues on individual failures but
    aborts on PermissionError (auth issue affects all labels).

    Business: Batch setup for required labels. Called during --create-labels
    mode or auto-creation of missing labels.

    Args:
        labels: Labels to create. Typically ← get_missing_labels().
        repo: Repository in "owner/repo" format.

    Raises:
        PermissionError: Re-raised from create_label on auth errors.

    Examples:
        ```python
        missing = get_missing_labels(existing, get_required_labels())
        create_labels_batch(missing, "owner/repo")
        ```

    Technical: O(n) API calls. ~1-2s per label. No parallelism (rate limit safe).
    """
    for label in labels:
        try:
            create_label(label, repo)
        except PermissionError:
            raise
        except Exception as e:
            print_error(f"Failed to create label '{label.name}': {e}")


def write_labels_for_ai(labels: list[dict]) -> None:
    """Display labels in AI-friendly categorized format.

    Groups labels by type: priority, category, workflow, estimates, other.
    Includes usage instructions for AI issue generation.

    Business: Enables AI/LLM to generate properly-labeled issues. Output format
    designed for copy-paste into AI prompts or direct consumption.

    Args:
        labels: Labels ← get_repository_labels(). List of {name, description}.

    Examples:
        ```python
        result = get_repository_labels("owner/repo")
        if result.success:
            write_labels_for_ai(result.result)
        ```

    Technical: O(n log n) due to sorting. Prints to stdout. No return value.
    """
    # Categorize labels using module constants
    priorities = [lbl for lbl in labels if re.match(r"^p\d+$", lbl["name"])]
    categories = [lbl for lbl in labels if lbl["name"] in CATEGORY_LABELS]
    workflow = [lbl for lbl in labels if lbl["name"] in WORKFLOW_LABELS]
    estimates = [lbl for lbl in labels if lbl["name"].startswith("estimate:")]
    other = [lbl for lbl in labels if lbl not in priorities + categories + workflow + estimates]

    print()
    print_color("=" * 60, Colors.GREEN)
    print_color("AVAILABLE LABELS FOR ISSUE CREATION", Colors.GREEN)
    print_color("=" * 60, Colors.GREEN)
    print()

    if priorities:
        print_color("PRIORITY LABELS:", Colors.YELLOW)
        for label in sorted(priorities, key=lambda x: x["name"]):
            print_color(f"  - {label['name']}", Colors.WHITE, end="")
            print_color(f" : {label.get('description', '')}", Colors.GRAY)
        print()

    if categories:
        print_color("CATEGORY LABELS:", Colors.YELLOW)
        for label in sorted(categories, key=lambda x: x["name"]):
            print_color(f"  - {label['name']}", Colors.WHITE, end="")
            print_color(f" : {label.get('description', '')}", Colors.GRAY)
        print()

    if workflow:
        print_color("WORKFLOW STATUS LABELS:", Colors.YELLOW)
        for label in sorted(workflow, key=lambda x: x["name"]):
            print_color(f"  - {label['name']}", Colors.WHITE, end="")
            print_color(f" : {label.get('description', '')}", Colors.GRAY)
        print()

    if estimates:
        print_color("EFFORT ESTIMATE LABELS:", Colors.YELLOW)

        def estimate_sort_key(x: dict) -> float:
            """Extract numeric hours from estimate label, with fallback."""
            try:
                return float(x["name"].replace("estimate: ", "").replace("h", ""))
            except ValueError:
                return MALFORMED_ESTIMATE_SORT_ORDER

        for label in sorted(estimates, key=estimate_sort_key):
            print_color(f"  - {label['name']}", Colors.WHITE, end="")
            print_color(f" : {label.get('description', '')}", Colors.GRAY)
        print()

    if other:
        print_color("OTHER LABELS:", Colors.YELLOW)
        for label in sorted(other, key=lambda x: x["name"]):
            print_color(f"  - {label['name']}", Colors.WHITE, end="")
            print_color(f" : {label.get('description', '')}", Colors.GRAY)
        print()

    print_color("USAGE FOR AI:", Colors.CYAN)
    print_color("  When creating issues, select labels from above categories:", Colors.WHITE)
    print_color("  1. One priority label (p1, p2, p3, p4)", Colors.WHITE)
    print_color("  2. One or more category labels (security, performance, etc.)", Colors.WHITE)
    print_color(
        "  3. One workflow status label (needs-triage, approved-fix, hold-future)",
        Colors.WHITE,
    )
    print_color("  4. One estimate label (estimate: 0.5h through estimate: 80h)", Colors.WHITE)
    print()


# ============================================================================
# Input Validation
# ============================================================================


def validate_input_safety(input_string: str, field_name: str, strict: bool = True) -> None:
    """Validate input for command injection and length limits.

    Strict mode (title/labels): Rejects shell metacharacters ;&|`$<>(){}[]"'.
    Relaxed mode (body): Only rejects null bytes. Both enforce length limits.

    Business: Security layer preventing command injection via user-controlled
    JSON input. Titles/labels become CLI args; body written to temp file.

    Args:
        input_string: User-controlled data to validate.
        field_name: Field identifier for error msgs. E.g., "title", "body.location".
        strict: True for CLI args (title, labels). False for body fields.

    Raises:
        ValueError: If dangerous chars found or length exceeded.
            Strict: >1000 chars or shell metacharacters.
            Relaxed: >50000 chars or null bytes.

    Examples:
        ```python
        validate_input_safety("Fix bug in parser", "title")  # OK
        validate_input_safety("Fix; rm -rf /", "title")  # ValueError
        ```

    Technical: O(n) regex scan. ~0.01ms for typical input.
    """
    if strict:
        # Strict validation: title and labels (passed as command args)
        if DANGEROUS_CHARS_REGEX.search(input_string):
            raise ValueError(f"Security: {field_name} contains potentially dangerous characters")
        if len(input_string) > MAX_TITLE_LENGTH:
            raise ValueError(f"Validation: {field_name} exceeds max length ({MAX_TITLE_LENGTH})")
    else:
        # Relaxed validation: body fields (written to temp file)
        if "\x00" in input_string:
            raise ValueError(f"Security: {field_name} contains null bytes")
        if len(input_string) > MAX_BODY_LENGTH:
            raise ValueError(f"Validation: {field_name} exceeds max length ({MAX_BODY_LENGTH})")


def validate_issue_required_fields(issue: dict, issue_number: int) -> ValidationResult:
    """Validate presence of required fields: title and labels.

    Business: First validation pass. Issues w/o title or labels cannot be created.

    Args:
        issue: Issue dict from JSON. Expected keys: title, labels.
        issue_number: 1-indexed position for error msgs.

    Returns:
        ValidationResult: Errors if title missing or labels empty/missing.
    """
    result = ValidationResult()

    if not issue.get("title"):
        result.errors.append(f"Issue #{issue_number}: Missing 'title' field")

    labels = issue.get("labels", [])
    if not labels:
        result.errors.append(f"Issue #{issue_number}: Missing or empty 'labels' field")

    return result


def validate_issue_security(issue: dict, issue_number: int) -> ValidationResult:
    """Validate title and labels for command injection risks.

    Business: Security pass. Prevents shell metacharacters in CLI args.

    Args:
        issue: Issue dict. Validates title and each label string.
        issue_number: 1-indexed position for error msgs.

    Returns:
        ValidationResult: Errors if dangerous chars found in title or labels.
    """
    result = ValidationResult()

    # Validate title
    title = issue.get("title")
    if title:
        try:
            validate_input_safety(title, "title", strict=True)
        except ValueError as e:
            result.errors.append(f"Issue #{issue_number}: {e}")

    # Validate each label
    for label in issue.get("labels", []):
        try:
            validate_input_safety(label, "label", strict=True)
        except ValueError as e:
            result.errors.append(f"Issue #{issue_number}: {e}")

    return result


def validate_issue_labels(
    issue: dict, available_labels: list[dict], issue_number: int
) -> ValidationResult:
    """Validate label existence in repository.

    Business: Prevents gh CLI errors from non-existent labels. All labels must
    exist before issue creation.

    Args:
        issue: Issue dict w/ labels array.
        available_labels: Labels ← get_repository_labels().
        issue_number: 1-indexed position for error msgs.

    Returns:
        ValidationResult: Errors for each label not in repository.
    """
    result = ValidationResult()
    available_names = {label["name"] for label in available_labels}

    for label in issue.get("labels", []):
        if label not in available_names:
            result.errors.append(
                f"Issue #{issue_number}: Label '{label}' does not exist in repository"
            )

    return result


def validate_issue_conventions(issue: dict, issue_number: int) -> ValidationResult:
    """Validate labeling conventions: single priority, single estimate.

    Business: Enforces best practices. Issues should have exactly one priority
    (p1-p4) and one estimate label. Violations are warnings, not errors.

    Args:
        issue: Issue dict w/ labels array.
        issue_number: 1-indexed position for warning msgs.

    Returns:
        ValidationResult: Warnings if missing or multiple priority/estimate labels.
    """
    result = ValidationResult()
    labels = issue.get("labels", [])

    # Check priority label convention
    priority_labels = [lbl for lbl in labels if re.match(r"^p\d+$", lbl)]
    if not priority_labels:
        result.warnings.append(f"Issue #{issue_number}: No priority label (p1-p4)")
    elif len(priority_labels) > 1:
        joined = ", ".join(priority_labels)
        result.warnings.append(f"Issue #{issue_number}: Multiple priorities: {joined}")

    # Check estimate label convention
    estimate_labels = [lbl for lbl in labels if lbl.startswith("estimate:")]
    if not estimate_labels:
        result.warnings.append(f"Issue #{issue_number}: No effort estimate label")
    elif len(estimate_labels) > 1:
        joined = ", ".join(estimate_labels)
        result.warnings.append(f"Issue #{issue_number}: Multiple estimates: {joined}")

    return result


def validate_issue_body_structure(issue: dict, issue_number: int) -> ValidationResult:
    """Validate body structure and field security.

    Checks body dict for security (null bytes, length) and completeness
    (recommended fields). Uses relaxed validation for body content.

    Business: Ensures structured issue bodies. Warns on missing fields that
    improve issue clarity (location, problem, solution, etc.).

    Args:
        issue: Issue dict w/ optional body dict.
        issue_number: 1-indexed position for error/warning msgs.

    Returns:
        ValidationResult: Errors for security issues. Warnings for missing fields.
    """
    result = ValidationResult()
    body = issue.get("body")

    if body and isinstance(body, dict):
        # Security: Validate all body fields (relaxed mode)
        body_fields = [
            "location",
            "current_state",
            "problem",
            "proposed_solution",
            "success_criteria",
        ]
        for field in body_fields:
            value = body.get(field)
            if value:
                try:
                    validate_input_safety(str(value), f"body.{field}", strict=False)
                except ValueError as e:
                    result.errors.append(f"Issue #{issue_number}: {e}")

        # Security: Validate files_affected array (strict mode - filenames)
        files_affected = body.get("files_affected", [])
        for file in files_affected:
            try:
                validate_input_safety(file, "body.files_affected", strict=True)
            except ValueError as e:
                result.errors.append(f"Issue #{issue_number}: {e}")

        # Check for recommended fields
        recommended_fields = [
            "location",
            "current_state",
            "problem",
            "proposed_solution",
            "success_criteria",
            "files_affected",
        ]
        missing_fields = [fld for fld in recommended_fields if fld not in body]
        if missing_fields:
            joined = ", ".join(missing_fields)
            result.warnings.append(f"Issue #{issue_number}: Missing recommended fields: {joined}")

    return result


def validate_issue(
    issue: dict, available_labels: list[dict], issue_number: int
) -> ValidationResult:
    """Orchestrate all validators for single issue → combined ValidationResult.

    Runs 5 validators in sequence: required fields, security, labels, conventions,
    body structure. Aggregates all errors and warnings.

    Business: Single entry point for issue validation. Enables complete error
    reporting before any issue creation begins.

    Args:
        issue: Issue dict from JSON input.
        available_labels: Labels ← get_repository_labels().
        issue_number: 1-indexed position for error msgs.

    Returns:
        ValidationResult: Combined errors/warnings from all validators.
        is_valid=True only if no errors from any validator.

    Examples:
        ```python
        result = validate_issue(issue_data, labels, 1)
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error}")
        ```

    Technical: O(n) where n=num labels. ~0.1ms per issue.
    """
    combined = ValidationResult()

    validators = [
        lambda: validate_issue_required_fields(issue, issue_number),
        lambda: validate_issue_security(issue, issue_number),
        lambda: validate_issue_labels(issue, available_labels, issue_number),
        lambda: validate_issue_conventions(issue, issue_number),
        lambda: validate_issue_body_structure(issue, issue_number),
    ]

    for validator in validators:
        result = validator()
        combined.errors.extend(result.errors)
        combined.warnings.extend(result.warnings)

    return combined


# ============================================================================
# Issue Creation
# ============================================================================


def convert_to_issue_body(body: dict, estimate: str | None, priority: str | None) -> str:
    """Transform JSON body object to markdown w/ code_quality_metrics.py integration.

    Formats body fields into structured Markdown w/ headers. Adds [Est: Xh]
    format for metrics integration and priority section.

    Business: Standardizes issue body format for code review findings. Structure
    enables scanning, filtering, and AI processing of issue details.

    Args:
        body: Body fields from issue definition. Expected keys: location,
            current_state, problem, proposed_solution, success_criteria,
            files_affected.
        estimate: Effort estimate (e.g., "2h"). Becomes [Est: 2h] header.
        priority: Priority label (e.g., "p1"). Becomes ## Priority section.

    Returns:
        Markdown string. Each field becomes ### header + content.
        [Est: Xh] at top for metrics integration.

    Examples:
        ```python
        body = {"location": "src/main.py", "problem": "Missing validation"}
        md = convert_to_issue_body(body, "2h", "p1")
        # Returns: "[Est: 2h]\n\n## Priority: p1 (Critical)\n..."
        ```

    Technical: O(n) where n=num fields. Pure string formatting, no I/O.
    """
    lines = []

    # Add estimate in code_quality_metrics format
    if estimate:
        lines.append(f"[Est: {estimate}]")
        lines.append("")

    # Add priority
    if priority:
        priority_names = {"p1": "Critical", "p2": "High", "p3": "Medium", "p4": "Low"}
        priority_name = priority_names.get(priority, "Unknown")
        lines.append(f"## Priority: {priority} ({priority_name})")
        lines.append("")

    # Add structured sections
    sections = [
        ("location", "Location"),
        ("current_state", "Current State"),
        ("problem", "Problem"),
        ("proposed_solution", "Proposed Solution"),
        ("success_criteria", "Success Criteria"),
    ]

    for section_key, section_title in sections:
        value = body.get(section_key)
        if value:
            lines.append(f"### {section_title}")
            lines.append(str(value))
            lines.append("")

    # Files affected
    files_affected = body.get("files_affected", [])
    if files_affected:
        lines.append("### Files Affected")
        for file in files_affected:
            lines.append(f"- `{file}`")
        lines.append("")

    return "\n".join(lines)


def create_github_issue(
    issue: dict, repo: str, issue_number: int, total_issues: int
) -> IssueCreationResult:
    """Create single GitHub issue via gh CLI → IssueCreationResult.

    Writes body to temp file (security: avoids shell injection in body).
    Auto-adds needs-triage label if missing. Shows progress w/ priority coloring.

    Business: Core issue creation. Converts validated issue dict to gh CLI
    invocation. Returns URL for created issue or error details.

    Args:
        issue: Validated issue dict w/ title, labels, and optional body.
        repo: Repository in "owner/repo" format.
        issue_number: 1-indexed current position for progress display.
        total_issues: Total issues for progress display (e.g., "3/10").

    Returns:
        IssueCreationResult: success=True w/ issue URL, or success=False w/ error.

    Raises:
        None (errors captured in IssueCreationResult).

    Examples:
        ```python
        issue = {"title": "Fix bug", "labels": ["p2", "bug"]}
        result = create_github_issue(issue, "owner/repo", 1, 5)
        if result.success:
            print(f"Created: {result.issue_url}")
        ```

    Technical: 1 API call. Uses tempfile for body (auto-cleaned). 120s timeout.
    """
    labels = issue.get("labels", [])
    priority = next((lbl for lbl in labels if re.match(r"^p\d+$", lbl)), None)

    color = Colors.get_priority_color(priority)

    print()
    print_color(f"[{priority}] Creating issue {issue_number}/{total_issues}...", color)
    print_color(f"  Title: {issue['title']}", Colors.WHITE)

    # Build body
    body_content = issue.get("body")
    if isinstance(body_content, dict):
        body = convert_to_issue_body(body_content, issue.get("estimate"), priority)
    elif isinstance(body_content, str):
        body = body_content
    else:
        body = ""

    # Ensure needs-triage is added
    all_labels = list(labels)
    if "needs-triage" not in all_labels:
        all_labels.append("needs-triage")

    # Create temporary file for body
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body)
        temp_file = f.name

    try:
        # Build command
        cmd = [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            issue["title"],
            "--label",
            ",".join(all_labels),
            "--body-file",
            temp_file,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)  # nosec B603

        if result.returncode == 0:
            issue_url = result.stdout.strip()
            print_success(f"Created: {issue_url}")
            return IssueCreationResult(success=True, issue_url=issue_url)
        else:
            error = result.stderr.strip() or result.stdout.strip()
            print_error(f"Failed: {error}")
            return IssueCreationResult(success=False, error=error)

    finally:
        # Clean up temp file
        Path(temp_file).unlink(missing_ok=True)


# ============================================================================
# Orchestration Functions
# ============================================================================


def initialize_prerequisites(repo: str) -> OperationResult:
    """Validate environment and fetch initial repository labels → OperationResult.

    Checks gh CLI available and authenticated. Fetches repository labels.
    Fails fast w/ clear error msgs if prerequisites not met.

    Business: Gate function for all operations. Ensures env is properly
    configured before any GitHub API calls.

    Args:
        repo: Repository in "owner/repo" format.

    Returns:
        OperationResult: success=True w/ labels list, or success=False w/
        specific error msg (gh not installed, not authenticated, repo inaccessible).

    Examples:
        ```python
        result = initialize_prerequisites("owner/repo")
        if not result.success:
            print(f"Setup required: {result.error}")
            sys.exit(1)
        labels = result.result
        ```

    Technical: 2 API calls (auth check, label fetch). ~1-3s total.
    """
    # Check GitHub CLI
    cli_check = check_github_cli_available()
    if not cli_check.success:
        return OperationResult(success=False, error=cli_check.error)

    print_color(cli_check.result, Colors.GREEN)

    # Fetch labels
    label_result = get_repository_labels(repo)
    if not label_result.success:
        return OperationResult(success=False, error=label_result.error)

    print_info(f"Found {len(label_result.result)} labels in repository")
    return OperationResult(success=True, result=label_result.result)


def handle_label_management(
    repo: str,
    available_labels: list[dict],
    create_labels: bool,
    list_labels: bool,
    validate_only: bool,
) -> tuple[list[dict], bool]:
    """Handle label discovery, validation, and auto-creation → (labels, exit).

    Dispatches to: --list-labels (display AI format), --create-labels (batch
    create all), or auto-create (fill missing). Refreshes label list after creates.

    Business: Supports label setup and discovery workflows. --list-labels
    enables AI to learn available labels. Auto-create ensures standard labels
    exist before issue creation.

    Args:
        repo: Repository in "owner/repo" format.
        available_labels: Current repository labels.
        create_labels: --create-labels flag. Creates all standard labels.
        list_labels: --list-labels flag. Displays labels in AI format.
        validate_only: --validate-only flag. Skip auto-creation if set.

    Returns:
        tuple:
            list[dict]: Updated labels (may be refreshed after creation).
            bool: True if caller should exit (--list-labels, --create-labels).

    Examples:
        ```python
        labels, should_exit = handle_label_management(
            "owner/repo", existing, False, True, False
        )
        if should_exit:
            sys.exit(0)  # --list-labels completed
        ```

    Technical: O(n) API calls for creates. Refreshes label list after mutations.
    """
    required_labels = get_required_labels()
    missing_labels = get_missing_labels(available_labels, required_labels)

    # Auto-create missing labels (unless listing or validating)
    if missing_labels and not list_labels and not validate_only:
        print_warning(f"Missing {len(missing_labels)} required label(s)")
        print_info("Auto-creating missing labels...")
        create_labels_batch(missing_labels, repo)

        # Refresh label list
        refresh_result = get_repository_labels(repo)
        if not refresh_result.success:
            raise RuntimeError(f"Failed to refresh labels: {refresh_result.error}")
        available_labels = refresh_result.result

    # Handle create-labels mode
    if create_labels:
        create_labels_batch(required_labels, repo)
        print_info("\nUse --list-labels to see available labels")
        return available_labels, True

    # Handle list-labels mode
    if list_labels:
        if missing_labels:
            print_warning(f"{len(missing_labels)} required label(s) missing")
            print_info("Run with --create-labels to create them")
        write_labels_for_ai(available_labels)
        return available_labels, True

    return available_labels, False


def validate_all_issues(
    issues_path: str, available_labels: list[dict], validate_only: bool
) -> tuple[list[dict], bool]:
    """Load JSON and validate all issue definitions → (issues, exit).

    Runs full validation on each issue. Reports per-issue errors/warnings.
    Raises on any validation error to prevent partial batch creation.

    Business: Pre-flight check before batch creation. Enables --validate-only
    mode for dry-run validation. Complete error reporting before any API calls.

    Args:
        issues_path: Path to JSON file w/ "issues" array.
        available_labels: Labels ← initialize_prerequisites().
        validate_only: If True, return after validation (don't create).

    Returns:
        tuple:
            list[dict]: Validated issues from JSON.
            bool: True if caller should exit (--validate-only mode).

    Raises:
        RuntimeError: If JSON invalid or any issue fails validation.

    Examples:
        ```python
        issues, should_exit = validate_all_issues(
            "issues.json", labels, args.validate_only
        )
        if should_exit:
            sys.exit(0)  # --validate-only completed
        ```

    Technical: O(n·m) where n=issues, m=labels per issue. ~10ms for 50 issues.
    """
    print_color(f"Loading issues from {issues_path}...", Colors.GREEN)

    with open(issues_path, encoding="utf-8") as f:
        issues_data = json.load(f)

    if "issues" not in issues_data:
        raise RuntimeError("JSON file must contain 'issues' array at root level")

    issues = issues_data["issues"]
    print_info(f"Found {len(issues)} issue(s) to process")

    # Validate all issues
    print_color("\nValidating issues...", Colors.YELLOW)
    all_valid = True

    for i, issue in enumerate(issues, 1):
        result = validate_issue(issue, available_labels, i)

        if not result.is_valid:
            all_valid = False
            for error in result.errors:
                sanitized = error.replace("\r", " ").replace("\n", " ")
                print_color(f"  [ERROR] {sanitized}", Colors.RED)

        for warning in result.warnings:
            sanitized = warning.replace("\r", " ").replace("\n", " ")
            print_warning(sanitized)

    if not all_valid:
        raise RuntimeError("Validation failed. Fix errors before creating issues.")

    print_success("All issues validated successfully")

    if validate_only:
        print_info("\nValidation complete. Use without --validate-only to create issues.")
        return issues, True

    return issues, False


def create_all_issues(issues: list[dict], repo: str) -> BatchCreationResult:
    """Create all validated issues w/ progress tracking → BatchCreationResult.

    Processes issues sequentially (rate limit safe). Tracks successes and
    failures. Shows per-issue progress w/ priority-colored output.

    Business: Batch issue creation w/ progress reporting. Continues on
    individual failures to maximize created issues.

    Args:
        issues: Issues ← validate_all_issues() that passed validation.
        repo: Repository in "owner/repo" format.

    Returns:
        BatchCreationResult: Aggregated counts and details.
            created_issues: [{title, url}] for successes.
            failed_issues: [{title, error}] for failures.

    Examples:
        ```python
        result = create_all_issues(validated_issues, "owner/repo")
        print(f"Created: {result.success_count}, Failed: {result.fail_count}")
        for issue in result.created_issues:
            print(f"  {issue['title']}: {issue['url']}")
        ```

    Technical: O(n) API calls. ~2-5s per issue. Sequential, not parallel.
    """
    print_color(f"\nCreating issues in {repo}...", Colors.GREEN)
    result = BatchCreationResult()

    for i, issue in enumerate(issues, 1):
        creation_result = create_github_issue(issue, repo, i, len(issues))

        if creation_result.success:
            result.success_count += 1
            result.created_issues.append(
                {
                    "title": issue["title"],
                    "url": creation_result.issue_url or "",
                }
            )
        else:
            result.fail_count += 1
            result.failed_issues.append(
                {
                    "title": issue["title"],
                    "error": creation_result.error or "",
                }
            )

    return result


def write_execution_summary(
    result: BatchCreationResult, start_time: float, repo: str, issue_count: int
) -> None:
    """Display comprehensive execution summary w/ performance metrics.

    Shows success/failure counts, timing info, created issue URLs, and
    suggested next steps. Includes links to GitHub issues page.

    Business: Final report for batch operations. Performance metrics help
    tune batch sizes. Next steps guide workflow completion.

    Args:
        result: BatchCreationResult ← create_all_issues().
        start_time: Script start time (time.time()). For duration calc.
        repo: Repository name. For GitHub links.
        issue_count: Total issues processed. For metrics display.

    Examples:
        ```python
        start = time.time()
        result = create_all_issues(issues, "owner/repo")
        write_execution_summary(result, start, "owner/repo", len(issues))
        # Output: === SUMMARY ===\n[OK] Successfully created: 5\n...
        ```

    Technical: Pure output to stdout. O(n) where n=total issues. No return.
    """
    execution_time = time.time() - start_time

    print()
    print_color("=== SUMMARY ===", Colors.GREEN)
    print_success(f"Successfully created: {result.success_count}")
    print_info(f"[PERF] Execution time: {execution_time:.2f}s")
    print_info(f"[PERF] Issues validated: {issue_count}")

    if result.success_count > 0:
        avg_time = execution_time / result.success_count
        print_info(f"[PERF] Avg time per issue: {avg_time:.2f}s")

    if result.created_issues:
        print_color("\nCreated Issues:", Colors.CYAN)
        for created in result.created_issues:
            print_color(f"  - {created['title']}", Colors.WHITE)
            print_color(f"    {created['url']}", Colors.GRAY)

    if result.fail_count > 0:
        print_error(f"Failed: {result.fail_count}")
        print_color("\nFailed Issues:", Colors.RED)
        for failed in result.failed_issues:
            print_color(f"  - {failed['title']}", Colors.WHITE)
            print_color(f"    Error: {failed['error']}", Colors.GRAY)

    print_color("\nNext Steps:", Colors.YELLOW)
    print_color(f"  1. Review issues: https://github.com/{repo}/issues", Colors.WHITE)
    print_color("  2. Run code_quality_metrics.py to see in Technical Debt Report", Colors.WHITE)


# ============================================================================
# Main Entry Point
# ============================================================================


def main() -> int:
    """CLI entry point for GitHub issue creation → exit code.

    Parses args, validates env, dispatches to appropriate handler:
    --list-labels, --create-labels, --validate-only, or full issue creation.

    Business: Orchestrates entire issue creation workflow. Provides structured
    output and exit codes for CI/CD integration and script chaining.

    Returns:
        Exit code:
            0: Operation completed successfully.
            1: Error (missing prereqs, validation failure, any creation failed).

    Examples:
        ```bash
        # List labels for AI
        python create_issues.py -r owner/repo --list-labels

        # Validate only
        python create_issues.py -i issues.json -r owner/repo --validate-only

        # Create issues
        python create_issues.py -i issues.json -r owner/repo
        ```

    Technical: Entry point. Returns exit code (caller uses sys.exit). Handles
    all exceptions w/ troubleshooting guidance.
    """
    parser = argparse.ArgumentParser(
        description="GitHub Issue Creator with Dynamic Label Discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--issues",
        "-i",
        dest="issues_json_path",
        help="Path to JSON file containing issue definitions",
    )
    parser.add_argument(
        "--repository",
        "-r",
        required=True,
        help="GitHub repository in format 'owner/repo'",
    )
    parser.add_argument(
        "--list-labels",
        action="store_true",
        help="List available labels in AI-friendly format and exit",
    )
    parser.add_argument(
        "--create-labels",
        action="store_true",
        help="Create standard code review labels in repository",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate issue definitions without creating issues",
    )

    args = parser.parse_args()

    # Validate repository format
    if not REPO_PATTERN.match(args.repository):
        print_error("Repository must be in format 'owner/repo'")
        return 1

    # Require issues file for create/validate modes
    if not args.list_labels and not args.create_labels and not args.issues_json_path:
        print_error("--issues is required when not using --list-labels or --create-labels")
        return 1

    if args.issues_json_path and not Path(args.issues_json_path).exists():
        print_error(f"Issues file not found: {args.issues_json_path}")
        return 1

    try:
        start_time = time.time()

        # Phase 1: Initialize prerequisites
        prereq_result = initialize_prerequisites(args.repository)
        if not prereq_result.success:
            raise RuntimeError(prereq_result.error)

        available_labels = prereq_result.result

        # Phase 2: Handle label management
        available_labels, should_exit = handle_label_management(
            args.repository,
            available_labels,
            args.create_labels,
            args.list_labels,
            args.validate_only,
        )
        if should_exit:
            return 0

        # Phase 3: Validate issues
        issues, should_exit = validate_all_issues(
            args.issues_json_path,
            available_labels,
            args.validate_only,
        )
        if should_exit:
            return 0

        # Phase 4: Create issues
        creation_result = create_all_issues(issues, args.repository)

        # Phase 5: Display summary
        write_execution_summary(creation_result, start_time, args.repository, len(issues))

        return 0 if creation_result.fail_count == 0 else 1

    except Exception as e:
        print()
        print_error("Fatal error occurred")
        print_error(str(e))
        print_color("\nTroubleshooting:", Colors.YELLOW)
        print_color("  1. Verify GitHub CLI is installed: gh --version", Colors.WHITE)
        print_color("  2. Verify authentication: gh auth status", Colors.WHITE)
        print_color(
            f"  3. Verify repository access: gh repo view {args.repository}",
            Colors.WHITE,
        )
        print_color("  4. Check JSON file format matches schema in help", Colors.WHITE)
        return 1


if __name__ == "__main__":
    sys.exit(main())
