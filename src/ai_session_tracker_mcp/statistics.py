"""
Statistics engine for AI Session Tracker.

PURPOSE: Calculate ROI metrics, productivity statistics, and analytics.
AI CONTEXT: Pure data processing - no visualization, no I/O.

METRIC CATEGORIES:
1. Time Metrics: Session duration, interaction time
2. Effectiveness Metrics: Rating distribution, iteration counts
3. Code Metrics: Complexity, documentation quality, effort scores
4. ROI Metrics: Human vs AI cost comparison, savings calculation

ROI CALCULATION MODEL:
- Human baseline: Estimated time * hourly rate
- AI actual: Tracked time * hourly rate + AI subscription cost
- Savings: Human baseline - AI actual
- Multiplier: Human cost / AI cost

USAGE:
    engine = StatisticsEngine()
    stats = engine.calculate_session_stats(sessions, interactions, issues)
    roi = engine.calculate_roi_metrics(sessions, interactions)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import Config


class StatisticsEngine:
    """
    Calculator for AI productivity and ROI statistics.

    DESIGN:
    - Stateless: Each method operates on provided data
    - Pure: No side effects, only data transformation
    - Configurable: Cost parameters from Config or constructor

    COST PARAMETERS:
    - human_hourly_rate: Developer cost including overhead
    - ai_monthly_cost: AI subscription cost
    - ai_hourly_rate: Calculated from monthly / 160 hours
    """

    def __init__(
        self,
        human_hourly_rate: float | None = None,
        ai_monthly_cost: float | None = None,
    ) -> None:
        """
        Initialize statistics engine with configurable cost parameters.

        Creates a new statistics engine instance with custom or default cost
        settings for ROI calculations. Defaults come from Config class which
        provides reasonable baseline values for typical enterprise settings.

        Business context: Different organizations have different cost structures.
        Allowing custom rates enables accurate ROI calculations that reflect
        actual organizational costs rather than industry averages.

        Args:
            human_hourly_rate: Fully-burdened developer cost in USD/hour.
                Includes salary, benefits (30%), and overhead (40%).
                Default: Config.HUMAN_HOURLY_RATE ($130.00)
            ai_monthly_cost: Monthly AI subscription cost in USD.
                Typically includes Copilot ($20) + ChatGPT/Claude ($20).
                Default: Config.AI_MONTHLY_COST ($40.00)

        Raises:
            TypeError: If rate parameters are not numeric when provided.

        Example:
            >>> # Use default rates
            >>> engine = StatisticsEngine()
            >>> engine.human_hourly_rate
            130.0
            >>> # Custom rates for different organization
            >>> engine = StatisticsEngine(human_hourly_rate=150.0, ai_monthly_cost=60.0)
            >>> engine.ai_hourly_rate
            0.375
        """
        self.human_hourly_rate = human_hourly_rate or Config.HUMAN_HOURLY_RATE
        self.ai_monthly_cost = ai_monthly_cost or Config.AI_MONTHLY_COST
        self.ai_hourly_rate = self.ai_monthly_cost / Config.WORKING_HOURS_PER_MONTH

    def calculate_session_duration_minutes(self, session: dict[str, Any]) -> float:
        """
        Calculate session duration in minutes from start and end timestamps.

        Parses ISO 8601 timestamps and computes the difference. Handles both
        'Z' suffix and '+00:00' timezone formats for UTC times. Returns 0
        for invalid or missing timestamps to ensure downstream calculations
        don't fail.

        Business context: Session duration is a key metric for ROI calculation.
        It represents actual AI-assisted work time that's compared against
        human baseline estimates to compute productivity gains.

        Args:
            session: Session data dict containing 'start_time' and 'end_time'
                keys with ISO 8601 formatted datetime strings. Both must be
                present and valid for a non-zero result.

        Returns:
            Duration in minutes as float. Returns 0.0 if either timestamp
            is missing, empty, or cannot be parsed as ISO 8601 datetime.

        Raises:
            TypeError: If session is not a dict.

        Example:
            >>> engine = StatisticsEngine()
            >>> session = {
            ...     'start_time': '2025-01-01T10:00:00+00:00',
            ...     'end_time': '2025-01-01T10:30:00+00:00'
            ... }
            >>> engine.calculate_session_duration_minutes(session)
            30.0
        """
        start_str = session.get("start_time", "")
        end_str = session.get("end_time", "")

        if not start_str or not end_str:
            return 0.0

        try:
            # Handle both Z suffix and +00:00 timezone formats
            start_str = start_str.replace("Z", "+00:00")
            end_str = end_str.replace("Z", "+00:00")

            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
            delta = end - start
            return delta.total_seconds() / 60.0
        except (ValueError, TypeError):
            return 0.0

    def calculate_effectiveness_distribution(
        self, interactions: list[dict[str, Any]]
    ) -> dict[int, int]:
        """
        Count interactions by effectiveness rating to show rating distribution.

        Aggregates all interactions into a histogram of effectiveness ratings,
        providing insight into overall AI performance quality. The distribution
        helps identify whether AI outputs are consistently high quality or if
        there are patterns of low-rated interactions needing investigation.

        Business context: This distribution is displayed in dashboards and reports
        to give stakeholders a quick visual understanding of AI effectiveness.
        A left-skewed distribution (more 4s and 5s) indicates healthy AI adoption.

        Args:
            interactions: List of interaction records, each containing an
                'effectiveness_rating' key with integer value 1-5. Ratings
                outside this range are ignored.

        Returns:
            Dict mapping each rating (1-5) to its count. All five keys are
            always present, with zero values for ratings with no interactions.
            Example: {1: 0, 2: 2, 3: 5, 4: 10, 5: 8}

        Raises:
            TypeError: If interactions is not a list.

        Example:
            >>> engine = StatisticsEngine()
            >>> dist = engine.calculate_effectiveness_distribution([
            ...     {'effectiveness_rating': 5},
            ...     {'effectiveness_rating': 4},
            ...     {'effectiveness_rating': 5}
            ... ])
            >>> dist[5]
            2
            >>> dist[1]
            0
        """
        dist: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for interaction in interactions:
            rating = interaction.get("effectiveness_rating", 0)
            if 1 <= rating <= 5:
                dist[rating] += 1
        return dist

    def calculate_average_effectiveness(self, interactions: list[dict[str, Any]]) -> float:
        """
        Calculate mean effectiveness rating across all interactions.

        Computes the arithmetic mean of effectiveness ratings to provide
        a single summary metric for AI performance quality. This metric
        is displayed prominently in dashboards and reports.

        Business context: Average effectiveness is a key performance indicator
        for AI adoption success. Target is typically 3.5+ indicating AI outputs
        require only minor adjustments on average.

        Args:
            interactions: List of interaction records, each containing an
                'effectiveness_rating' key with integer value 1-5.

        Returns:
            Mean rating as float on 1-5 scale. Returns 0.0 if the
            interactions list is empty to avoid division by zero.

        Raises:
            TypeError: If interactions is not a list.

        Example:
            >>> engine = StatisticsEngine()
            >>> avg = engine.calculate_average_effectiveness([
            ...     {'effectiveness_rating': 5},
            ...     {'effectiveness_rating': 4},
            ...     {'effectiveness_rating': 3}
            ... ])
            >>> avg
            4.0
        """
        if not interactions:
            return 0.0

        total: int = sum(int(i.get("effectiveness_rating", 0)) for i in interactions)
        return float(total) / len(interactions)

    def calculate_issue_summary(self, issues: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Aggregate issues by type and severity for trend analysis.

        Groups flagged AI issues into summary statistics that help identify
        patterns in AI failures. This enables teams to focus improvement
        efforts on the most common or severe issue categories.

        Business context: Issue tracking is essential for AI adoption success.
        High counts of 'hallucination' or 'incorrect_output' issues may indicate
        need for better prompting strategies or model selection changes.

        Args:
            issues: List of issue records, each containing 'issue_type' (str)
                and 'severity' (str: 'low', 'medium', 'high', 'critical') keys.
                Missing keys default to 'unknown'.

        Returns:
            Dict with three keys:
            - 'total': int - Total number of issues
            - 'by_type': dict[str, int] - Count per issue type
            - 'by_severity': dict[str, int] - Count per severity level
            Example: {'total': 5, 'by_type': {'hallucination': 2}, 'by_severity': {'high': 1}}

        Raises:
            TypeError: If issues is not a list.

        Example:
            >>> engine = StatisticsEngine()
            >>> summary = engine.calculate_issue_summary([
            ...     {'issue_type': 'hallucination', 'severity': 'high'},
            ...     {'issue_type': 'incorrect_output', 'severity': 'medium'}
            ... ])
            >>> summary['total']
            2
            >>> summary['by_severity']['high']
            1
        """
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for issue in issues:
            issue_type = issue.get("issue_type", "unknown")
            severity = issue.get("severity", "unknown")

            by_type[issue_type] = by_type.get(issue_type, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "total": len(issues),
            "by_type": by_type,
            "by_severity": by_severity,
        }

    def calculate_code_metrics_summary(self, sessions: dict[str, Any]) -> dict[str, Any]:
        """
        Aggregate code quality metrics across all sessions.

        Collects and summarizes code metrics from all sessions including
        function counts, lines of code changes, complexity scores, and
        documentation quality. Provides both totals and averages.

        Business context: Code metrics demonstrate the tangible output of
        AI-assisted development. Total effort scores help quantify the
        volume of work completed, while quality metrics (complexity, docs)
        ensure AI isn't just fast but also producing maintainable code.

        Args:
            sessions: Dict of session_id -> session_data where each session
                may contain a 'code_metrics' list of file-level metrics,
                each with 'functions' containing individual function metrics.

        Returns:
            Dict with aggregated metrics:
            - 'total_functions': int - Number of functions analyzed
            - 'total_lines_added': int - Sum of lines added by AI
            - 'total_lines_modified': int - Sum of lines modified
            - 'avg_complexity': float - Average cyclomatic complexity
            - 'avg_doc_score': float - Average documentation quality (0-100)
            - 'total_effort_score': float - Sum of effort scores

        Raises:
            TypeError: If sessions is not a dict.

        Example:
            >>> engine = StatisticsEngine()
            >>> summary = engine.calculate_code_metrics_summary({
            ...     's1': {'code_metrics': [{'functions': [
            ...         {'context': {'final_complexity': 5},
            ...          'documentation': {'quality_score': 80},
            ...          'value_metrics': {'effort_score': 10.0},
            ...          'ai_contribution': {'lines_added': 50, 'lines_modified': 10}}
            ...     ]}]}
            ... })
            >>> summary['total_functions']
            1
        """
        total_functions = 0
        total_complexity = 0
        total_doc_score = 0
        total_effort = 0.0
        total_lines_added = 0
        total_lines_modified = 0

        for session in sessions.values():
            code_metrics = session.get("code_metrics", [])
            for file_metrics in code_metrics:
                functions = file_metrics.get("functions", [])
                for func in functions:
                    total_functions += 1
                    total_complexity += func.get("context", {}).get("final_complexity", 0)
                    total_doc_score += func.get("documentation", {}).get("quality_score", 0)
                    total_effort += func.get("value_metrics", {}).get("effort_score", 0)
                    ai_contrib = func.get("ai_contribution", {})
                    total_lines_added += ai_contrib.get("lines_added", 0)
                    total_lines_modified += ai_contrib.get("lines_modified", 0)

        return {
            "total_functions": total_functions,
            "total_lines_added": total_lines_added,
            "total_lines_modified": total_lines_modified,
            "avg_complexity": total_complexity / total_functions if total_functions else 0,
            "avg_doc_score": total_doc_score / total_functions if total_functions else 0,
            "total_effort_score": round(total_effort, 2),
        }

    def calculate_roi_metrics(
        self,
        sessions: dict[str, Any],
        interactions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Calculate comprehensive ROI metrics for AI-assisted development.

        Computes time savings, cost savings, and productivity metrics by comparing
        actual AI-assisted time against estimated human baseline. Uses a conservative
        3x multiplier assumption (AI is 3x faster than human for tracked tasks).

        Business context: ROI metrics are the primary justification for AI tool
        investment. This calculation provides the data needed for budget discussions,
        tool adoption decisions, and productivity improvement tracking.

        Methodology:
        1. Filter to productive sessions only (excludes 'human_review' task type)
        2. Sum actual AI session time from completed sessions
        3. Estimate human baseline time (AI time × 3 as conservative estimate)
        4. Calculate costs: human cost vs (AI subscription + human oversight)
        5. Compute savings and ROI percentage

        Args:
            sessions: Dict of session_id -> session_data containing completed
                sessions with start_time, end_time, status, and task_type.
            interactions: List of interaction records for productivity metrics
                calculation (average effectiveness, interactions per session).

        Returns:
            Nested dict with three sections:
            - 'time_metrics': total_ai_minutes, total_ai_hours, estimated_human_hours,
              time_saved_hours, completed_sessions
            - 'cost_metrics': human_baseline_cost, ai_subscription_cost, oversight_cost,
              total_ai_cost, cost_saved, roi_percentage
            - 'productivity_metrics': total_interactions, average_effectiveness,
              interactions_per_session
            - 'config': Applied cost parameters for transparency

        Raises:
            TypeError: If sessions is not a dict or interactions is not a list.

        Example:
            >>> engine = StatisticsEngine(human_hourly_rate=100.0)
            >>> roi = engine.calculate_roi_metrics(
            ...     sessions={'s1': {'status': 'completed', 'start_time': '...'}},
            ...     interactions=[]
            ... )
            >>> roi['cost_metrics']['roi_percentage']
            66.7  # Example: 66.7% ROI
        """
        # Filter to productive sessions only
        productive = Config.filter_productive_sessions(sessions)

        # Calculate total AI time
        total_ai_minutes = 0.0
        completed_sessions = 0

        for session in productive.values():
            if session.get("status") == "completed":
                duration = self.calculate_session_duration_minutes(session)
                total_ai_minutes += duration
                completed_sessions += 1

        total_ai_hours = total_ai_minutes / 60.0

        # Estimate human baseline (conservative 3x multiplier)
        # This assumes AI is ~3x faster than human for tracked tasks
        estimated_human_hours = total_ai_hours * 3.0

        # Calculate costs
        human_cost = estimated_human_hours * self.human_hourly_rate
        ai_subscription_cost = total_ai_hours * self.ai_hourly_rate
        # AI cost also includes human oversight (assume 20% of AI time)
        oversight_hours = total_ai_hours * 0.2
        oversight_cost = oversight_hours * self.human_hourly_rate
        total_ai_cost = ai_subscription_cost + oversight_cost

        # Calculate savings
        cost_saved = human_cost - total_ai_cost
        roi_percentage = (cost_saved / human_cost * 100) if human_cost > 0 else 0

        # Productivity metrics
        avg_effectiveness = self.calculate_average_effectiveness(interactions)
        total_interactions = len(interactions)
        interactions_per_session = (
            total_interactions / completed_sessions if completed_sessions else 0
        )

        return {
            "time_metrics": {
                "total_ai_minutes": round(total_ai_minutes, 1),
                "total_ai_hours": round(total_ai_hours, 2),
                "estimated_human_hours": round(estimated_human_hours, 2),
                "time_saved_hours": round(estimated_human_hours - total_ai_hours, 2),
                "completed_sessions": completed_sessions,
            },
            "cost_metrics": {
                "human_baseline_cost": round(human_cost, 2),
                "ai_subscription_cost": round(ai_subscription_cost, 2),
                "oversight_cost": round(oversight_cost, 2),
                "total_ai_cost": round(total_ai_cost, 2),
                "cost_saved": round(cost_saved, 2),
                "roi_percentage": round(roi_percentage, 1),
            },
            "productivity_metrics": {
                "total_interactions": total_interactions,
                "average_effectiveness": round(avg_effectiveness, 2),
                "interactions_per_session": round(interactions_per_session, 1),
            },
            "config": {
                "human_hourly_rate": self.human_hourly_rate,
                "ai_monthly_cost": self.ai_monthly_cost,
                "ai_hourly_rate": round(self.ai_hourly_rate, 4),
            },
        }

    def generate_summary_report(
        self,
        sessions: dict[str, Any],
        interactions: list[dict[str, Any]],
        issues: list[dict[str, Any]],
    ) -> str:
        """
        Generate comprehensive text summary of all AI productivity metrics.

        Creates a formatted analytics report combining session statistics, ROI metrics,
        effectiveness distribution, issue summary, and code quality metrics. The report
        is designed for terminal/console display and provides stakeholders with a
        complete overview of AI-assisted development performance.

        Business context: This report serves as the primary deliverable for ROI
        justification to management and helps teams identify productivity patterns
        and areas needing improvement in AI-assisted workflows.

        Args:
            sessions: Dict of session_id -> session_data containing all tracked
                sessions with their metadata, duration, and outcome information.
            interactions: List of interaction records with effectiveness ratings,
                prompts, and response summaries from AI exchanges.
            issues: List of flagged issue records with type, severity, and
                descriptions of problematic AI interactions.

        Returns:
            Multi-line formatted text report with emoji icons, section headers,
            and aligned metrics. Includes session counts, ROI percentages, cost
            savings, effectiveness distribution (star ratings), issue breakdown
            by severity, and code quality averages.

        Raises:
            TypeError: If sessions is not a dict or interactions/issues are not lists.

        Example:
            >>> engine = StatisticsEngine()
            >>> report = engine.generate_summary_report(
            ...     sessions={'s1': {...}},
            ...     interactions=[{'effectiveness_rating': 4, ...}],
            ...     issues=[{'severity': 'medium', ...}]
            ... )
            >>> print(report)
            ==================================================
            AI SESSION TRACKER - ANALYTICS REPORT
            ...
        """
        roi = self.calculate_roi_metrics(sessions, interactions)
        effectiveness_dist = self.calculate_effectiveness_distribution(interactions)
        issue_summary = self.calculate_issue_summary(issues)
        code_summary = self.calculate_code_metrics_summary(sessions)

        lines = [
            "=" * 50,
            "AI SESSION TRACKER - ANALYTICS REPORT",
            "=" * 50,
            "",
            "📊 SESSION SUMMARY",
            f"  • Total sessions: {len(sessions)}",
            f"  • Completed sessions: {roi['time_metrics']['completed_sessions']}",
            f"  • Total AI time: {roi['time_metrics']['total_ai_hours']:.1f} hours",
            "",
            "💰 ROI METRICS",
            f"  • Human baseline cost: ${roi['cost_metrics']['human_baseline_cost']:,.2f}",
            f"  • AI total cost: ${roi['cost_metrics']['total_ai_cost']:,.2f}",
            f"  • Cost saved: ${roi['cost_metrics']['cost_saved']:,.2f}",
            f"  • ROI: {roi['cost_metrics']['roi_percentage']:.1f}%",
            "",
            "⭐ EFFECTIVENESS DISTRIBUTION",
        ]

        for rating in range(5, 0, -1):
            count = effectiveness_dist.get(rating, 0)
            stars = "★" * rating + "☆" * (5 - rating)
            lines.append(f"  {stars}: {count}")

        lines.extend(
            [
                "",
                f"  Average: {roi['productivity_metrics']['average_effectiveness']:.1f}/5",
                "",
                "🐛 ISSUES SUMMARY",
                f"  • Total issues: {issue_summary['total']}",
            ]
        )

        for severity in ["critical", "high", "medium", "low"]:
            count = issue_summary["by_severity"].get(severity, 0)
            if count > 0:
                lines.append(f"  • {severity.capitalize()}: {count}")

        lines.extend(
            [
                "",
                "📝 CODE METRICS",
                f"  • Functions analyzed: {code_summary['total_functions']}",
                f"  • Lines added: {code_summary['total_lines_added']}",
                f"  • Avg complexity: {code_summary['avg_complexity']:.1f}",
                f"  • Avg doc score: {code_summary['avg_doc_score']:.0f}/100",
                f"  • Total effort score: {code_summary['total_effort_score']:.1f}",
                "",
                "=" * 50,
            ]
        )

        return "\n".join(lines)
