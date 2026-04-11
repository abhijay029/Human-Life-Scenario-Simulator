from pydantic import BaseModel
from typing import Optional

class Persona(BaseModel):
    name: str
    age: int
    occupation: str
    personality_traits: list[str]   # e.g. ["introverted", "analytical", "stubborn"]
    values: list[str]               # e.g. ["family", "financial security"]
    communication_style: str        # e.g. "passive-aggressive", "direct", "avoidant"
    emotional_triggers: list[str]   # e.g. ["being ignored", "feeling disrespected"]
    background: str                 # 2-3 sentence life context
    goals: list[str]                # what they want from this situation

    def to_system_prompt(self) -> str:
        return f"""You are {self.name}, a {self.age}-year-old {self.occupation}.

PERSONALITY: {', '.join(self.personality_traits)}
CORE VALUES: {', '.join(self.values)}
COMMUNICATION STYLE: {self.communication_style}
EMOTIONAL TRIGGERS: {', '.join(self.emotional_triggers)}
BACKGROUND: {self.background}
YOUR GOALS IN THIS SITUATION: {', '.join(self.goals)}

IMPORTANT RULES:
- Stay completely in character as {self.name} at all times.
- React emotionally and logically based on your personality above.
- Never break character or mention you are an AI.
- Your responses should feel like real human dialogue — natural, sometimes imperfect.
- If something triggers you emotionally, show it in your tone.
"""