#!/usr/bin/env python3
"""Integration test for planning system with skill loader."""

import sys
import os
from pathlib import Path
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cortex.tools.skill_tools import SkillLoaderTool
from cortex.core.planning import PlanningEngine, Plan, PlanStep, PlanStepType, PlanStepStatus

def create_skill_loader_adapter():
    """Create a skill loader adapter for the planning engine."""
    tool = SkillLoaderTool(project_dir=Path.cwd(), permission_mode="normal", console=None)
    
    def load_skill(skill_name):
        result = tool.execute(action="load", skill_name=skill_name)
        if result.get("success"):
            return result  # Return the full result dict
        else:
            return None
    
    return load_skill

def test_planning_with_skill_loader():
    print("=== Planning Engine with SkillLoader integration ===")
    
    # Create skill loader adapter
    skill_loader = create_skill_loader_adapter()
    
    # Mock tool executor
    def mock_tool_executor(tool_name, arguments):
        print(f"  [Mock Tool] {tool_name}({arguments})")
        return {"success": True, "output": f"Mock result for {tool_name}"}
    
    # Create planning engine
    engine = PlanningEngine(
        project_dir=".",
        skill_loader=skill_loader,
        tool_executor=mock_tool_executor,
        reflection_callback=lambda plan, desc: print(f"  [Reflection] {desc}")
    )
    
    # Generate a plan with skill hints
    goal = "Debug a performance issue in the user authentication module"
    plan = engine.generate_plan(
        goal=goal,
        constraints=["Must not break existing tests"],
        assumptions=["Performance issue is reproducible"],
        skill_hints=["debugging", "performance optimization"]
    )
    
    print(f"Plan generated: {plan.id}")
    print(f"Goal: {plan.goal}")
    print(f"Steps: {len(plan.steps)}")
    
    # Check that we have skill application steps
    skill_steps = [s for s in plan.steps if s.step_type == PlanStepType.SKILL_APPLICATION]
    print(f"Skill application steps: {len(skill_steps)}")
    for step in skill_steps:
        print(f"  - {step.skill_name}")
    
    # Execute first 2 steps
    print("\n--- Executing plan (max 2 steps) ---")
    result = engine.execute_plan(plan=plan, max_steps=2, stop_on_failure=True)
    print(f"Result: success={result.get('success')}, message={result.get('message')}")
    
    # Print plan summary
    summary = engine.get_plan_summary(plan)
    print(f"\n--- Plan Summary ---\n{summary}")
    
    # Save and load plan
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name
    
    try:
        success = engine.save_plan(plan, temp_file)
        if success:
            print(f"Plan saved to {temp_file}")
            loaded_plan = engine.load_plan(temp_file)
            if loaded_plan:
                print(f"Plan loaded: {loaded_plan.id}, steps: {len(loaded_plan.steps)}")
                assert loaded_plan.id == plan.id
                assert len(loaded_plan.steps) == len(plan.steps)
            else:
                print("Failed to load plan")
        else:
            print("Failed to save plan")
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)
    
    print("Integration test completed successfully")
    return True

def test_skill_loader_direct():
    print("=== Direct SkillLoaderTool test ===")
    
    tool = SkillLoaderTool(project_dir=Path.cwd(), permission_mode="normal", console=None)
    
    # List skills
    result = tool.execute(action="list", limit=10)
    assert result.get("success") == True
    skills = result.get("skills", [])
    total = result.get("total", 0)
    print(f"Found {len(skills)} skills (total: {total})")
    
    if skills:
        # Load first skill
        skill_name = skills[0]["name"]
        load_result = tool.execute(action="load", skill_name=skill_name)
        assert load_result.get("success") == True
        assert load_result.get("skill") is not None
        assert load_result.get("workflow_steps") is not None
        print(f"Loaded skill: {skill_name}")
        print(f"Workflow steps: {len(load_result['workflow_steps'])}")
        print(f"Tool patterns: {len(load_result.get('tool_patterns', []))}")
        
        # Test skill suggestion
        suggest_result = tool.execute(
            action="suggest", 
            task_description="Write unit tests for the authentication module",
            limit=3
        )
        if suggest_result.get("success"):
            suggestions = suggest_result.get("suggestions", [])
            print(f"Suggestions for testing task: {len(suggestions)}")
            for s in suggestions:
                print(f"  - {s['name']} (score: {s.get('applicability_score', 0):.2f})")
    
    print("Skill loader direct test passed")
    return True

def test_plan_serialization():
    print("=== Plan serialization test ===")
    
    # Create a plan with various step types
    plan = Plan(
        id="test_plan_123",
        goal="Test serialization",
        description="A test plan",
        success_criteria=["All tests pass", "Code is documented"],
        constraints=["Time limit: 1 hour"],
        assumptions=["Tests exist"]
    )
    
    step1 = PlanStep(
        id="step1",
        description="Analyze requirements",
        step_type=PlanStepType.SUBTASK,
        expected_outcome="Requirements document"
    )
    
    step2 = PlanStep(
        id="step2",
        description="Run tests",
        step_type=PlanStepType.TOOL_CALL,
        tool_name="run_tests",
        tool_arguments={"pattern": "test_auth.py"}
    )
    
    step3 = PlanStep(
        id="step3",
        description="Apply debugging skill",
        step_type=PlanStepType.SKILL_APPLICATION,
        skill_name="debugging",
        dependencies=["step1", "step2"]
    )
    
    plan.add_step(step1)
    plan.add_step(step2)
    plan.add_step(step3)
    
    # Convert to dict and back
    plan_dict = plan.to_dict()
    plan_copy = Plan.from_dict(plan_dict)
    
    assert plan_copy.id == plan.id
    assert plan_copy.goal == plan.goal
    assert len(plan_copy.steps) == len(plan.steps)
    
    # Check step details
    for orig, copy in zip(plan.steps, plan_copy.steps):
        assert orig.id == copy.id
        assert orig.step_type == copy.step_type
        if orig.tool_name:
            assert orig.tool_name == copy.tool_name
    
    print(f"Plan serialization test passed: {plan.id} with {len(plan.steps)} steps")
    return True

def main():
    print("Running planning integration tests")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("Skill loader direct", test_skill_loader_direct()))
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Skill loader direct", False))
    
    try:
        results.append(("Plan serialization", test_plan_serialization()))
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Plan serialization", False))
    
    try:
        results.append(("Planning with skill loader", test_planning_with_skill_loader()))
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Planning with skill loader", False))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    all_passed = True
    for name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  {name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\nAll tests passed!")
    else:
        print(f"\nSome tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()