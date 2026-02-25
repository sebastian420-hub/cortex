import unittest
from pathlib import Path
from cortex.core.memory_layers.state import StateManager, AgentFocus

class TestMetacognition(unittest.TestCase):
    def setUp(self):
        self.state_manager = StateManager(project_dir=Path("."))
    
    def test_metacognitive_appraisal_success(self):
        print("\n--- Testing Success Appraisal ---")
        initial_conf = self.state_manager.state.metacognition.confidence_score
        
        # Simulate a successful tool execution
        self.state_manager.update_metacognition("read_file", {"success": True})
        
        new_conf = self.state_manager.state.metacognition.confidence_score
        tone = self.state_manager.state.metacognition.emotional_tone
        
        print(f"Initial Confidence: {initial_conf}")
        print(f"New Confidence: {new_conf}")
        print(f"Tone: {tone}")
        
        self.assertGreater(new_conf, initial_conf)
        self.assertEqual(tone, "confident")

    def test_metacognitive_appraisal_failure(self):
        print("\n--- Testing Failure Appraisal ---")
        # Boost confidence first
        self.state_manager.state.metacognition.confidence_score = 0.9
        
        # Simulate a failed tool execution
        self.state_manager.update_metacognition("read_file", {"success": False, "error": "File not found"})
        
        new_conf = self.state_manager.state.metacognition.confidence_score
        tone = self.state_manager.state.metacognition.emotional_tone
        
        print(f"New Confidence: {new_conf}")
        print(f"Tone: {tone}")
        
        self.assertLess(new_conf, 0.9)
        self.assertEqual(tone, "cautious")

    def test_frustration_and_urgency(self):
        print("\n--- Testing Frustration and Urgency ---")
        # Simulate multiple failures
        self.state_manager.state.failed_tools = 3
        self.state_manager.update_metacognition("read_file", {"success": False})
        
        tone = self.state_manager.state.metacognition.emotional_tone
        urgency = self.state_manager.state.metacognition.urgency_score
        monologue = self.state_manager.state.metacognition.internal_monologue
        
        print(f"Tone: {tone}")
        print(f"Urgency: {urgency}")
        print(f"Internal Monologue: {monologue}")
        
        self.assertEqual(tone, "frustrated")
        self.assertGreater(urgency, 0.1)
        self.assertIn("repeated obstacles", monologue)

    def test_memory_verification(self):
        print("\n--- Testing Memory Verification ---")
        from cortex.core.memory.core_memory import MemoryItem, MemoryType, MemorySource
        
        # Add a memory
        item = MemoryItem(
            type=MemoryType.FACT, 
            content="The config is in config.yaml", 
            source=MemorySource.TOOL_RESULT, 
            confidence=0.5
        )
        self.state_manager.state.session_memory.add(item)
        
        # Verify success
        self.state_manager.state.session_memory.verify_memory("config.yaml", success=True)
        # Find item (MemoryBank.add might dedup or reorder)
        verified_item = None
        for i in self.state_manager.state.session_memory.items:
            if "config.yaml" in i.content:
                verified_item = i
                break
                
        print(f"Confidence after success: {verified_item.confidence}")
        self.assertGreater(verified_item.confidence, 0.5)
        
        # Verify failure
        self.state_manager.state.session_memory.verify_memory("config.yaml", success=False)
        print(f"Confidence after failure: {verified_item.confidence}")
        self.assertLess(verified_item.confidence, 0.6)

if __name__ == "__main__":
    unittest.main()
