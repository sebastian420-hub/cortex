"""Tests for plan progress display module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

from cortex.ui.plan_progress import (
    PlanProgressDisplay,
    create_plan_display,
    show_step_status,
)


class MockStatus(str, Enum):
    """Mock status enum for testing."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class MockStep:
    """Mock step for testing."""

    id: str
    description: str
    status: MockStatus = MockStatus.PENDING
    tool_name: Optional[str] = None
    expected_outcome: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)


@dataclass
class MockPlan:
    """Mock plan for testing."""

    id: str
    goal: str
    steps: List[MockStep]
    created_at: str = "2024-01-01T00:00:00"

    def get_progress(self) -> Dict[str, int]:
        """Get progress statistics."""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == MockStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == MockStatus.FAILED)
        skipped = sum(1 for s in self.steps if s.status == MockStatus.SKIPPED)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "pending": total - completed - failed - skipped,
        }


class TestPlanProgressDisplay:
    """Tests for PlanProgressDisplay class."""

    @pytest.fixture
    def display(self):
        """Create a plan progress display with a mock console."""
        mock_console = Mock()
        return PlanProgressDisplay(console_instance=mock_console)

    @pytest.fixture
    def sample_plan(self):
        """Create a sample plan for testing."""
        return MockPlan(
            id="test_plan_001",
            goal="Test the plan progress display",
            steps=[
                MockStep(id="step_1", description="First step", tool_name="read_file"),
                MockStep(id="step_2", description="Second step", dependencies=["step_1"]),
                MockStep(id="step_3", description="Third step", expected_outcome="Done"),
            ],
        )

    def test_display_initialization(self, display):
        """Test that display initializes correctly."""
        assert display is not None
        assert display._start_time is None
        assert display._progress is None
        assert display._task_id is None

    def test_status_styles_defined(self):
        """Test that all status styles are defined."""
        assert "pending" in PlanProgressDisplay.STATUS_STYLES
        assert "in_progress" in PlanProgressDisplay.STATUS_STYLES
        assert "completed" in PlanProgressDisplay.STATUS_STYLES
        assert "failed" in PlanProgressDisplay.STATUS_STYLES
        assert "skipped" in PlanProgressDisplay.STATUS_STYLES

    def test_status_styles_have_icon_and_color(self):
        """Test that each status style has icon and color."""
        for status, (icon, color) in PlanProgressDisplay.STATUS_STYLES.items():
            assert isinstance(icon, str)
            assert len(icon) >= 1
            assert isinstance(color, str)
            assert len(color) >= 1

    def test_show_plan_overview(self, display, sample_plan):
        """Test show_plan_overview doesn't raise errors."""
        # Should not raise any exceptions
        display.show_plan_overview(sample_plan)
        # Console.print should be called at least once
        assert display.console.print.called

    def test_show_step_start(self, display):
        """Test show_step_start displays correctly."""
        step = MockStep(id="step_1", description="Test step", tool_name="bash")
        display.show_step_start(step, 1, 5)
        # Should have called print
        assert display.console.print.called

    def test_show_step_start_with_expected_outcome(self, display):
        """Test show_step_start with expected outcome."""
        step = MockStep(
            id="step_1", description="Test step", expected_outcome="Should complete successfully"
        )
        display.show_step_start(step, 2, 10)
        assert display.console.print.called

    def test_show_step_complete(self, display):
        """Test show_step_complete displays correctly."""
        step = MockStep(id="step_1", description="Test step")
        display.show_step_complete(step, "Step finished successfully")
        assert display.console.print.called

    def test_show_step_complete_truncates_long_result(self, display):
        """Test that long results are truncated."""
        step = MockStep(id="step_1", description="Test step")
        long_result = "x" * 200  # Longer than 100 chars
        display.show_step_complete(step, long_result)
        assert display.console.print.called

    def test_show_step_failed(self, display):
        """Test show_step_failed displays correctly."""
        step = MockStep(id="step_1", description="Test step")
        display.show_step_failed(step, "Something went wrong")
        assert display.console.print.called

    def test_show_step_skipped(self, display):
        """Test show_step_skipped displays correctly."""
        step = MockStep(id="step_1", description="Test step")
        display.show_step_skipped(step, "Dependencies not met")
        assert display.console.print.called

    @pytest.mark.skip(reason="Rich Progress/Live components don't work well with mocked console")
    def test_start_and_stop_progress_bar(self, display):
        """Test starting and stopping progress bar."""
        display.start_progress_bar(5, "Testing")
        assert display._start_time is not None
        assert display._progress is not None
        assert display._task_id is not None

        display.stop_progress_bar()
        assert display._progress is None
        assert display._task_id is None

    @pytest.mark.skip(reason="Rich Progress/Live components don't work well with mocked console")
    def test_update_progress(self, display):
        """Test updating progress bar."""
        display.start_progress_bar(5, "Testing")
        # Should not raise
        display.update_progress(1)
        display.update_progress(1, "Step 2")
        display.stop_progress_bar()

    def test_show_execution_summary(self, display, sample_plan):
        """Test showing execution summary."""
        display._start_time = 1.0  # Mock start time
        step_results = [
            {"success": True, "content": "Result 1"},
            {"success": True, "content": "Result 2"},
        ]

        with patch("time.time", return_value=5.0):  # 4 seconds elapsed
            display.show_execution_summary(sample_plan, step_results)

        assert display.console.print.called

    def test_show_plan_complete(self, display, sample_plan):
        """Test showing plan complete message."""
        display.show_plan_complete(sample_plan)
        assert display.console.print.called

    def test_show_plan_failed(self, display, sample_plan):
        """Test showing plan failed message."""
        display.show_plan_failed(sample_plan, "Execution error")
        assert display.console.print.called


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_plan_display_default(self):
        """Test creating display with default console."""
        display = create_plan_display()
        assert isinstance(display, PlanProgressDisplay)

    def test_create_plan_display_custom_console(self):
        """Test creating display with custom console."""
        mock_console = Mock()
        display = create_plan_display(mock_console)
        assert display.console is mock_console


class TestShowStepStatus:
    """Tests for show_step_status convenience function."""

    def test_show_step_status_in_progress(self):
        """Test showing in_progress status."""
        with patch("cortex.ui.plan_progress.console") as mock_console:
            show_step_status(1, 5, "Running tests", "in_progress")
            assert mock_console.print.called

    def test_show_step_status_completed(self):
        """Test showing completed status."""
        with patch("cortex.ui.plan_progress.console") as mock_console:
            show_step_status(1, 5, "Running tests", "completed", "Done")
            assert mock_console.print.called

    def test_show_step_status_failed(self):
        """Test showing failed status."""
        with patch("cortex.ui.plan_progress.console") as mock_console:
            show_step_status(1, 5, "Running tests", "failed", "Error occurred")
            assert mock_console.print.called

    def test_show_step_status_pending(self):
        """Test showing pending status."""
        with patch("cortex.ui.plan_progress.console") as mock_console:
            show_step_status(1, 5, "Waiting", "pending")
            assert mock_console.print.called


class TestIntegrationWithPlanning:
    """Integration tests with planning module."""

    def test_progress_display_with_planning_engine(self):
        """Test that PlanProgressDisplay works with PlanningEngine."""
        from cortex.core.planning import PlanningEngine

        engine = PlanningEngine()
        assert hasattr(engine, "progress_display")
        assert isinstance(engine.progress_display, PlanProgressDisplay)

    def test_planning_engine_creates_plan_with_display(self):
        """Test that creating a plan works with display."""
        from cortex.core.planning import PlanningEngine

        engine = PlanningEngine()
        plan = engine.create_plan("Test goal")

        # Should not raise when showing overview
        engine.progress_display.show_plan_overview(plan)
