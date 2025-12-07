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
        Initialize with cost parameters.

        Args:
            human_hourly_rate: Override Config.HUMAN_HOURLY_RATE
            ai_monthly_cost: Override Config.AI_MONTHLY_COST
        """
        self.human_hourly_rate = human_hourly_rate or Config.HUMAN_HOURLY_RATE
        self.ai_monthly_cost = ai_monthly_cost or Config.AI_MONTHLY_COST
        self.ai_hourly_rate = self.ai_monthly_cost / Config.WORKING_HOURS_PER_MONTH

    def calculate_session_duration_minutes(self, session: dict[str, Any]) -> float:
        """
        Calculate session duration in minutes.

        Args:
            session: Session data with start_time, end_time

        Returns:
            Duration in minutes. 0 if timestamps invalid.
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
        Count interactions by effectiveness rating.

        Args:
            interactions: List of interaction records

        Returns:
            Dict of rating (1-5) -> count
        """
        dist: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for interaction in interactions:
            rating = interaction.get("effectiveness_rating", 0)
            if 1 <= rating <= 5:
                dist[rating] += 1
        return dist

    def calculate_average_effectiveness(self, interactions: list[dict[str, Any]]) -> float:
        """
        Calculate mean effectiveness rating.

        Args:
            interactions: List of interaction records

        Returns:
            Average rating (1-5 scale). 0 if no interactions.
        """
        if not interactions:
            return 0.0

        total: int = sum(int(i.get("effectiveness_rating", 0)) for i in interactions)
        return float(total) / len(interactions)

    def calculate_issue_summary(self, issues: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Summarize issues by type and severity.

        Args:
            issues: List of issue records

        Returns:
            Dict with by_type and by_severity counts.
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
        Aggregate code metrics across all sessions.

        Args:
            sessions: Dict of session_id -> session_data

        Returns:
            Summary with totals and averages for complexity, docs, effort.
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
        Calculate comprehensive ROI metrics.

        METHODOLOGY:
        1. Sum actual AI session time from completed sessions
        2. Estimate human baseline time (AI time * 3 as conservative estimate)
        3. Calculate costs using hourly rates
        4. Compute savings and ROI percentage

        Args:
            sessions: Dict of session_id -> session_data
            interactions: List of interaction records

        Returns:
            Dict with time_metrics, cost_metrics, productivity_metrics.
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
        Generate text summary of all metrics.

        Args:
            sessions: Dict of session_id -> session_data
            interactions: List of interaction records
            issues: List of issue records

        Returns:
            Formatted text report suitable for display.
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
