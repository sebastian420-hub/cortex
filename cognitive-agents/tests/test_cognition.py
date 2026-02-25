import unittest
from cognitive_agents.cognition import (
    CognitiveState,
    Drive,
    DriveType,
    Goal,
    GoalStatus,
    Belief,
    AgentModel,
    Milestone,
    Task,
)

class TestCognition(unittest.TestCase):
    def test_cognitive_state_initialization(self):
        cs = CognitiveState()
        self.assertIsInstance(cs, CognitiveState)
        self.assertEqual(len(cs.drives), 0)
        self.assertEqual(len(cs.goals), 0)
        self.assertEqual(len(cs.beliefs), 0)

    def test_drive_creation(self):
        drive = Drive(drive_type=DriveType.SURVIVAL, urgency=0.8)
        self.assertEqual(drive.drive_type, DriveType.SURVIVAL)
        self.assertEqual(drive.urgency, 0.8)

    def test_goal_creation(self):
        goal = Goal(description="Test Goal", priority=0.9, source_drive=DriveType.PURPOSE)
        self.assertEqual(goal.description, "Test Goal")
        self.assertEqual(goal.priority, 0.9)
        self.assertEqual(goal.source_drive, DriveType.PURPOSE)
        self.assertEqual(goal.status, GoalStatus.ACTIVE)

    def test_belief_creation(self):
        belief = Belief(content="The sky is blue", confidence=0.99)
        self.assertEqual(belief.content, "The sky is blue")
        self.assertEqual(belief.confidence, 0.99)

if __name__ == "__main__":
    unittest.main()
