from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmotionalState:
    """Tracks current emotions as 0-1 floats with decay and spike mechanics."""
    joy: float = 0.3
    fear: float = 0.1
    anger: float = 0.1
    sadness: float = 0.1
    surprise: float = 0.0
    trust: float = 0.3

    DECAY_RATE: float = field(default=0.08, repr=False)  # Faster decay to prevent pegging at 1.0

    def decay(self) -> None:
        """Decay all emotions toward a neutral baseline each tick."""
        baseline = {"joy": 0.2, "fear": 0.1, "anger": 0.05, "sadness": 0.1, "surprise": 0.0, "trust": 0.3}
        for emotion in baseline:
            current = getattr(self, emotion)
            target = baseline[emotion]
            diff = target - current
            setattr(self, emotion, current + diff * self.DECAY_RATE)

    def spike(self, emotion: str, amount: float) -> None:
        """Spike an emotion by the given amount, clamped to [0, 1]."""
        if hasattr(self, emotion) and emotion != "DECAY_RATE":
            current = getattr(self, emotion)
            setattr(self, emotion, max(0.0, min(1.0, current + amount)))

    def dominant_emotion(self) -> str:
        emotions = {
            "joy": self.joy,
            "fear": self.fear,
            "anger": self.anger,
            "sadness": self.sadness,
            "surprise": self.surprise,
            "trust": self.trust,
        }
        return max(emotions, key=emotions.get)

    def intensity(self) -> float:
        """Overall emotional intensity (0-1)."""
        vals = [self.joy, self.fear, self.anger, self.sadness, self.surprise, self.trust]
        return sum(vals) / len(vals)

    def to_text(self) -> str:
        dominant = self.dominant_emotion()
        parts = []
        for emotion in ["joy", "fear", "anger", "sadness", "surprise", "trust"]:
            val = getattr(self, emotion)
            if val > 0.3:
                level = "strongly" if val > 0.7 else "somewhat"
                parts.append(f"{level} feeling {emotion} ({val:.1f})")
        if not parts:
            parts.append("emotionally calm")
        return f"Dominant emotion: {dominant}. Currently {', '.join(parts)}."

    def to_dict(self) -> dict:
        return {
            "joy": round(self.joy, 3),
            "fear": round(self.fear, 3),
            "anger": round(self.anger, 3),
            "sadness": round(self.sadness, 3),
            "surprise": round(self.surprise, 3),
            "trust": round(self.trust, 3),
        }

    # Event-based emotion updates
    def on_trade_success(self) -> None:
        self.spike("joy", 0.2)
        self.spike("trust", 0.15)

    def on_trade_failure(self) -> None:
        self.spike("anger", 0.15)
        self.spike("trust", -0.1)

    def on_danger(self) -> None:
        self.spike("fear", 0.3)
        self.spike("surprise", 0.2)

    def on_social_positive(self) -> None:
        self.spike("joy", 0.1)
        self.spike("trust", 0.1)

    def on_social_negative(self) -> None:
        self.spike("sadness", 0.15)
        self.spike("trust", -0.15)

    def on_discovery(self) -> None:
        self.spike("surprise", 0.25)
        self.spike("joy", 0.15)

    def on_resource_low(self) -> None:
        self.spike("fear", 0.08)
        self.spike("sadness", 0.1)

    def on_successful_gather(self, drive_urgency: float) -> None:
        """Spike positive emotions on successful gathering, especially if a drive was urgent."""
        if drive_urgency > 0.5:
            self.spike("joy", 0.1 + drive_urgency * 0.1) # More joy if more urgent
            self.spike("trust", 0.05 + drive_urgency * 0.05) # Trust in ability to provide
        else:
            self.spike("joy", 0.05)

    def appraise_event(
        self,
        event_type: str,
        goal_relevance: float,
        drive_urgency: float,
        unexpectedness: float = 0.0,
    ) -> None:
        """Lazarus-style appraisal: compute emotional response from event context.

        Args:
            event_type: descriptor like "action_success", "action_failure", "social"
            goal_relevance: -1.0 (blocks goal) to +1.0 (advances goal)
            drive_urgency: 0.0 to 1.0, how urgent the relevant drive is
            unexpectedness: 0.0 to 1.0, how surprising the event is
        """
        intensity = abs(goal_relevance) * (0.5 + drive_urgency * 0.5)
        intensity = max(0.0, min(1.0, intensity))

        if goal_relevance > 0:
            # Goal-congruent -> positive emotions
            self.spike("joy", intensity * 0.6)
            self.spike("trust", intensity * 0.3)
        else:
            # Goal-incongruent -> negative emotions scaled by urgency
            if drive_urgency > 0.6:
                self.spike("fear", intensity * 0.25)
            self.spike("sadness", intensity * 0.4)
            if drive_urgency > 0.4:
                self.spike("anger", intensity * 0.3)

        # Surprise from unexpected events
        if unexpectedness > 0.3:
            self.spike("surprise", unexpectedness * 0.4)
