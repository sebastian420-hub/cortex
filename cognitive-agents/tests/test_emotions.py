import unittest
from cognitive_agents.emotions import EmotionalState

class TestEmotions(unittest.TestCase):
    def test_emotional_state_initialization(self):
        es = EmotionalState()
        self.assertIsInstance(es, EmotionalState)
        self.assertAlmostEqual(es.joy, 0.3)
        self.assertAlmostEqual(es.fear, 0.1)
        self.assertAlmostEqual(es.anger, 0.1)
        self.assertAlmostEqual(es.sadness, 0.1)
        self.assertAlmostEqual(es.surprise, 0.0)
        self.assertAlmostEqual(es.trust, 0.3)

    def test_emotion_decay(self):
        es = EmotionalState(joy=1.0)
        es.decay()
        self.assertLess(es.joy, 1.0)

    def test_emotion_spike(self):
        es = EmotionalState(joy=0.5)
        es.spike("joy", 0.2)
        self.assertAlmostEqual(es.joy, 0.7)
        es.spike("joy", 0.5)
        self.assertAlmostEqual(es.joy, 1.0)

if __name__ == "__main__":
    unittest.main()
