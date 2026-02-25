import unittest
from cognitive_agents.personality import Personality

class TestPersonality(unittest.TestCase):
    def test_personality_initialization(self):
        p = Personality()
        self.assertIsInstance(p, Personality)
        self.assertEqual(p.openness, 5)

    def test_random_personality(self):
        p1 = Personality.random()
        p2 = Personality.random()
        self.assertNotEqual(p1.to_dict(), p2.to_dict())

    def test_archetype_personality(self):
        explorer = Personality.archetype("explorer")
        self.assertEqual(explorer.openness, 9)
        self.assertEqual(explorer.curiosity, 9)

if __name__ == "__main__":
    unittest.main()
