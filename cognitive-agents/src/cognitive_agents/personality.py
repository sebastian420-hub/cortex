from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Personality:
    # Big Five (1-10)
    openness: int = 5
    conscientiousness: int = 5
    extraversion: int = 5
    agreeableness: int = 5
    neuroticism: int = 5

    # Custom traits (1-10)
    curiosity: int = 5
    risk_tolerance: int = 5
    altruism: int = 5
    dominance: int = 5

    @staticmethod
    def random() -> Personality:
        return Personality(
            openness=random.randint(2, 9),
            conscientiousness=random.randint(2, 9),
            extraversion=random.randint(2, 9),
            agreeableness=random.randint(2, 9),
            neuroticism=random.randint(2, 9),
            curiosity=random.randint(2, 9),
            risk_tolerance=random.randint(2, 9),
            altruism=random.randint(2, 9),
            dominance=random.randint(2, 9),
        )

    @staticmethod
    def archetype(name: str) -> Personality:
        archetypes = {
            "explorer": Personality(
                openness=9, conscientiousness=4, extraversion=6,
                agreeableness=5, neuroticism=3,
                curiosity=9, risk_tolerance=8, altruism=5, dominance=4,
            ),
            "builder": Personality(
                openness=5, conscientiousness=9, extraversion=4,
                agreeableness=6, neuroticism=4,
                curiosity=5, risk_tolerance=3, altruism=6, dominance=5,
            ),
            "gatherer": Personality(
                openness=4, conscientiousness=7, extraversion=5,
                agreeableness=7, neuroticism=5,
                curiosity=4, risk_tolerance=3, altruism=7, dominance=3,
            ),
            "scholar": Personality(
                openness=9, conscientiousness=8, extraversion=3,
                agreeableness=5, neuroticism=4,
                curiosity=9, risk_tolerance=4, altruism=6, dominance=4,
            ),
        }
        return archetypes.get(name, Personality.random())

    def to_text(self) -> str:
        def level(val: int) -> str:
            if val <= 3:
                return "low"
            elif val <= 6:
                return "moderate"
            else:
                return "high"

        traits = [
            f"Openness: {level(self.openness)} ({self.openness}/10)",
            f"Conscientiousness: {level(self.conscientiousness)} ({self.conscientiousness}/10)",
            f"Extraversion: {level(self.extraversion)} ({self.extraversion}/10)",
            f"Agreeableness: {level(self.agreeableness)} ({self.agreeableness}/10)",
            f"Neuroticism: {level(self.neuroticism)} ({self.neuroticism}/10)",
            f"Curiosity: {level(self.curiosity)} ({self.curiosity}/10)",
            f"Risk Tolerance: {level(self.risk_tolerance)} ({self.risk_tolerance}/10)",
            f"Altruism: {level(self.altruism)} ({self.altruism}/10)",
            f"Dominance: {level(self.dominance)} ({self.dominance}/10)",
        ]
        return "\n".join(traits)

    def to_dict(self) -> dict:
        return {
            "openness": self.openness,
            "conscientiousness": self.conscientiousness,
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "neuroticism": self.neuroticism,
            "curiosity": self.curiosity,
            "risk_tolerance": self.risk_tolerance,
            "altruism": self.altruism,
            "dominance": self.dominance,
        }

    @staticmethod
    def from_dict(d: dict) -> Personality:
        return Personality(**d)
