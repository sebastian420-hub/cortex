"""
Unit tests for planning engine (cortex/core/planning.py).
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pytest

from cortex.core.planning import (
    PlanStepStatus,
    PlanStepType,
    PlanStep,
    Plan,
    PlanningEngine
)


class TestPlanStepStatus:
    """Test PlanStepStatus enum."""
    
    def test_enum_values(self):
        """Test that PlanStepStatus has correct values."""
        assert PlanStepStatus.PENDING == "pending"
        assert PlanStepStatus.IN_PROGRESS == "in_progress"
        assert PlanStepStatus.COMPLETED == "completed"
        assert PlanStepStatus.FAILED == "failed"
        assert PlanStepStatus.SKIPPED == "skipped"


class TestPlanStepType:
    """Test PlanStepType enum."""
    
    def test_enum_values(self):
        """Test that PlanStepType has correct values."""
        assert PlanStepType.TOOL_CALL == "tool_call"
        assert PlanStepType.SUBTASK == "subtask"
        assert PlanStepType.DECISION == "decision"
        assert PlanStepType.CHECKPOINT == "checkpoint"
        assert PlanStepType.REFLECTION == "reflection"
        assert PlanStepType.SKILL_APPLICATION == "skill_application"


class TestPlanStep:
    """Test PlanStep dataclass."""
    
    def test_plan_step_creation(self):
        """Test creating a basic PlanStep."""
        step = PlanStep(
            id="step_1",
            description="Read configuration file",
            step_type=PlanStepType.TOOL_CALL,
            status=PlanStepStatus.PENDING,
            dependencies=["step_0"],
            expected_outcome="Configuration loaded",
            tool_name="read_file",
            tool_arguments={"path": "config.yaml"}
        )
        
        assert step.id == "step_1"
        assert step.description == "Read configuration file"
        assert step.step_type == PlanStepType.TOOL_CALL
        assert step.status == PlanStepStatus.PENDING
        assert step.dependencies == ["step_0"]
        assert step.expected_outcome == "Configuration loaded"
        assert step.tool_name == "read_file"
        assert step.tool_arguments == {"path": "config.yaml"}
        assert step.created_at is not None
    
    def test_plan_step_to_dict(self):
        """Test conversion to dictionary."""
        step = PlanStep(
            id="step_1",
            description="Test step",
            step_type=PlanStepType.TOOL_CALL,
            status=PlanStepStatus.COMPLETED,
            tool_name="read_file",
            tool_arguments={"path": "test.txt"},
            started_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T00:00:05",
            error=None
        )
        
        data = step.to_dict()
        
        assert data["id"] == "step_1"
        assert data["description"] == "Test step"
        assert data["step_type"] == "tool_call"
        assert data["status"] == "completed"
        assert data["tool_name"] == "read_file"
        assert data["tool_arguments"] == {"path": "test.txt"}
        assert data["started_at"] == "2024-01-01T00:00:00"
        assert data["completed_at"] == "2024-01-01T00:00:05"
        assert data["error"] is None
    
    def test_plan_step_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "step_2",
            "description": "Another step",
            "step_type": "tool_call",
            "status": "pending",
            "dependencies": [],
            "expected_outcome": "File read",
            "tool_name": "read_file",
            "tool_arguments": {"path": "file.txt"},
            "created_at": "2024-01-01T00:00:00"
        }
        
        step = PlanStep.from_dict(data)
        
        assert step.id == "step_2"
        assert step.description == "Another step"
        assert step.step_type == PlanStepType.TOOL_CALL
        assert step.status == PlanStepStatus.PENDING
        assert step.tool_name == "read_file"
        assert step.tool_arguments == {"path": "file.txt"}
    
    def test_plan_step_status_transitions(self):
        """Test updating step status."""
        step = PlanStep(id="step_1", description="Test")
        
        # Start the step
        step.status = PlanStepStatus.IN_PROGRESS
        step.started_at = datetime.now().isoformat()
        
        # Complete the step
        step.status = PlanStepStatus.COMPLETED
        step.completed_at = datetime.now().isoformat()
        step.actual_outcome = "Success"
        
        assert step.status == PlanStepStatus.COMPLETED
        assert step.started_at is not None
        assert step.completed_at is not None


class TestPlan:
    """Test Plan dataclass."""
    
    def test_plan_creation(self):
        """Test creating a Plan."""
        steps = [
            PlanStep(id="step_1", description="First step"),
            PlanStep(id="step_2", description="Second step")
        ]
        
        plan = Plan(
            id="plan_123",
            goal="Test goal",
            steps=steps,
            status=PlanStepStatus.PENDING,
            created_at="2024-01-01T00:00:00"
        )
        
        assert plan.id == "plan_123"
        assert plan.goal == "Test goal"
        assert plan.steps == steps
        assert plan.status == "pending"
        assert len(plan) == 2
        assert plan[0] == steps[0]
        assert plan[1] == steps[1]
    
    def test_plan_iteration(self):
        """Test iterating over plan steps."""
        steps = [
            PlanStep(id="step_1", description="Step 1"),
            PlanStep(id="step_2", description="Step 2")
        ]
        plan = Plan(id="plan_1", goal="Test", steps=steps)
        
        step_descriptions = [step.description for step in plan]
        assert step_descriptions == ["Step 1", "Step 2"]
    
    def test_plan_to_dict(self):
        """Test converting plan to dictionary."""
        steps = [PlanStep(id="step_1", description="Step 1")]
        plan = Plan(
            id="plan_1",
            goal="Test goal",
            steps=steps,
            status=PlanStepStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            started_at="2024-01-01T00:00:01",
            completed_at="2024-01-01T00:00:10"
        )
        
        data = plan.to_dict()
        
        assert data["id"] == "plan_1"
        assert data["goal"] == "Test goal"
        assert data["status"] == "completed"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["id"] == "step_1"
        assert data["created_at"] == "2024-01-01T00:00:00"
        assert data["started_at"] == "2024-01-01T00:00:01"
        assert data["completed_at"] == "2024-01-01T00:00:10"
    
    def test_plan_from_dict(self):
        """Test creating plan from dictionary."""
        data = {
            "id": "plan_1",
            "goal": "Test goal",
            "status": "pending",
            "steps": [
                {
                    "id": "step_1",
                    "description": "Step 1",
                    "step_type": "tool_call",
                    "status": "pending"
                }
            ],
            "created_at": "2024-01-01T00:00:00"
        }
        
        plan = Plan.from_dict(data)
        
        assert plan.id == "plan_1"
        assert plan.goal == "Test goal"
        assert plan.status == "pending"
        assert len(plan.steps) == 1
        assert plan.steps[0].id == "step_1"
    
    def test_get_step_by_id(self):
        """Test retrieving a step by ID."""
        steps = [
            PlanStep(id="step_1", description="Step 1"),
            PlanStep(id="step_2", description="Step 2")
        ]
        plan = Plan(id="plan_1", goal="Test", steps=steps)
        
        step = plan.get_step_by_id("step_2")
        assert step is not None
        assert step.id == "step_2"
        
        # Non-existent step
        assert plan.get_step_by_id("step_3") is None


class TestPlanningEngine:
    """Test PlanningEngine class."""
    
    @pytest.fixture
    def mock_skill_loader(self):
        """Mock skill loader function."""
        return Mock()

    @pytest.fixture
    def mock_tool_executor(self):
        """Mock tool executor function."""
        return Mock()

    @pytest.fixture
    def mock_reflection_callback(self):
        """Mock reflection callback function."""
        return Mock()

    @pytest.fixture
    def planning_engine(self, mock_skill_loader, mock_tool_executor, mock_reflection_callback):
        """Create a PlanningEngine instance."""
        return PlanningEngine(
            project_dir="test_project",
            skill_loader=mock_skill_loader,
            tool_executor=mock_tool_executor,
            reflection_callback=mock_reflection_callback
        )
    
    def test_initialization(self, mock_skill_loader, mock_tool_executor, mock_reflection_callback):
        """Test PlanningEngine initialization."""
        engine = PlanningEngine(
            project_dir="test_project",
            skill_loader=mock_skill_loader,
            tool_executor=mock_tool_executor,
            reflection_callback=mock_reflection_callback,
            max_plan_steps=50
        )
        
        assert engine.project_dir.name == 'test_project'
        assert engine.skill_loader == mock_skill_loader
        assert engine.tool_executor == mock_tool_executor
        assert engine.reflection_callback == mock_reflection_callback
        assert engine.max_plan_steps == 50
        assert engine.active_plan is None
        assert isinstance(engine.plans, dict)
        assert len(engine.plans) == 0
    
    def test_create_plan(self, planning_engine):
        """Test creating a new plan."""
        goal = "Add logging to application"
        
        plan = planning_engine.create_plan(goal)
        
        assert plan is not None
        assert plan.goal == goal
        assert plan.status == "pending"
        assert plan.id is not None
        assert plan.id in planning_engine.plans
        assert planning_engine.active_plan == plan
    
    def test_add_step_to_plan(self):
        """Test adding a step to a plan."""
        planning_engine = PlanningEngine()
        # Create a plan
        plan = planning_engine.create_plan("Test goal")
        
        # Add a step
        step = planning_engine.add_step(
            plan_id=plan.id,
            description="Read configuration",
            step_type=PlanStepType.TOOL_CALL,
            tool_name="read_file",
            tool_arguments={"path": "config.yaml"}
        )
        
        assert step is not None
        assert step.id is not None
        assert step.description == "Read configuration"
        assert step.step_type == PlanStepType.TOOL_CALL
        assert step.tool_name == "read_file"
        assert step.tool_arguments == {"path": "config.yaml"}
        
        # Verify step is in plan
        assert len(plan) == 1
        assert plan[0].id == step.id
    
    def test_get_plan(self, planning_engine):
        """Test retrieving a plan by ID."""
        plan = planning_engine.create_plan("Test goal")
        
        retrieved = planning_engine.get_plan(plan.id)
        assert retrieved == plan
        
        # Non-existent plan
        assert planning_engine.get_plan("nonexistent") is None
    
    def test_update_step_status(self):
        """Test updating step status."""
        planning_engine = PlanningEngine()
        plan = planning_engine.create_plan("Test")
        step = planning_engine.add_step(plan.id, "Test step")
        
        # Update status
        updated = planning_engine.update_step_status(
            plan_id=plan.id,
            step_id=step.id,
            status=PlanStepStatus.IN_PROGRESS
        )
        
        assert updated is True
        assert step.status == PlanStepStatus.IN_PROGRESS
        
        # Update with error
        planning_engine.update_step_status(
            plan_id=plan.id,
            step_id=step.id,
            status=PlanStepStatus.FAILED,
            error="Something went wrong"
        )
        
        assert step.status == PlanStepStatus.FAILED
        assert step.error == "Something went wrong"
    
    def test_execute_step_tool_call(self, mock_tool_executor):
        """Test executing a tool call step."""
        planning_engine = PlanningEngine(tool_executor=mock_tool_executor)
        # Setup
        mock_tool_executor.return_value = {
            "success": True,
            "content": "File content"
        }
        
        plan = planning_engine.create_plan("Test")
        step = planning_engine.add_step(
            plan.id,
            "Read file",
            step_type=PlanStepType.TOOL_CALL,
            tool_name="read_file",
            tool_arguments={"path": "test.txt"}
        )
        
        # Execute step
        result = planning_engine.execute_step(plan.id, step.id)
        
        # Verify tool executor was called
        mock_tool_executor.assert_called_once_with(
            "read_file",
            {"path": "test.txt"}
        )
        
        # Verify step status updated
        assert step.status == PlanStepStatus.COMPLETED
        assert step.actual_outcome == "File content"
        assert result["success"] is True
    
    def test_execute_step_with_error(self, mock_tool_executor):
        """Test executing a step that results in error."""
        planning_engine = PlanningEngine(tool_executor=mock_tool_executor)
        mock_tool_executor.return_value = {
            "success": False,
            "error": "File not found"
        }
        
        plan = planning_engine.create_plan("Test")
        step = planning_engine.add_step(
            plan.id,
            "Read file",
            step_type=PlanStepType.TOOL_CALL,
            tool_name="read_file",
            tool_arguments={"path": "missing.txt"}
        )
        
        result = planning_engine.execute_step(plan.id, step.id)
        
        assert step.status == PlanStepStatus.FAILED
        assert step.error == "File not found"
        assert result["success"] is False
    
    def test_execute_plan(self, mock_tool_executor):
        """Test executing an entire plan."""
        planning_engine = PlanningEngine(tool_executor=mock_tool_executor)
        # Setup mock tool executor to succeed
        mock_tool_executor.return_value = {"success": True, "content": "OK"}
        
        # Create plan with steps
        plan = planning_engine.create_plan("Test plan")
        
        step1 = planning_engine.add_step(
            plan.id,
            "Step 1",
            step_type=PlanStepType.TOOL_CALL,
            tool_name="read_file",
            tool_arguments={"path": "file1.txt"}
        )
        
        step2 = planning_engine.add_step(
            plan.id,
            "Step 2",
            step_type=PlanStepType.TOOL_CALL,
            tool_name="read_file",
            tool_arguments={"path": "file2.txt"}
        )
        
        # Execute plan
        results = planning_engine.execute_plan(plan)
        
        # Verify both steps were executed
        assert mock_tool_executor.call_count == 2
        assert step1.status == PlanStepStatus.COMPLETED
        assert step2.status == PlanStepStatus.COMPLETED
        assert plan.status == "completed"
        assert len(results) == 2
        assert all(r["success"] for r in results)
    
    def test_save_and_load_plan(self, tmp_path):
        """Test saving and loading a plan to/from file."""
        planning_engine = PlanningEngine(project_dir=str(tmp_path))
        # Create a plan with steps
        plan = planning_engine.create_plan("Test plan")
        planning_engine.add_step(plan.id, "Step 1")
        
        # Save plan
        save_path = tmp_path / "plan.json"
        assert planning_engine.save_plan(plan, save_path) is True
        assert save_path.exists()
        
        # Load plan
        loaded_plan = planning_engine.load_plan(save_path)
        
        assert loaded_plan is not None
        assert loaded_plan.id == plan.id
        assert loaded_plan.goal == plan.goal
        assert len(loaded_plan) == 1
        assert loaded_plan[0].description == "Step 1"
    
    def test_DISABLED_generate_plan_from_goal(self, planning_engine):
        """Test generating a plan from a goal description."""
        # This is a complex method that might use AI/LLM
        # We'll mock the internal generation
        with patch.object(planning_engine, '_generate_plan_steps') as mock_generate:
            mock_generate.return_value = [
                PlanStep(id="gen_1", description="Generated step 1"),
                PlanStep(id="gen_2", description="Generated step 2")
            ]
            
            plan = planning_engine.generate_plan_from_goal(
                goal="Add logging",
                context="Python application"
            )
            
            assert plan is not None
            assert plan.goal == "Add logging"
            assert len(plan) == 2
            mock_generate.assert_called_once_with("Add logging", "Python application")
    
    def test_reflect_on_plan(self, mock_reflection_callback):
        """Test reflecting on a completed plan."""
        planning_engine = PlanningEngine(reflection_callback=mock_reflection_callback)
        plan = planning_engine.create_plan("Test plan")
        plan.status = "completed"
        
        reflection = "The plan worked well but could be optimized."
        planning_engine.reflect_on_plan(plan, reflection)
        
        # Verify reflection callback was called
        mock_reflection_callback.assert_called_once_with(plan, reflection)