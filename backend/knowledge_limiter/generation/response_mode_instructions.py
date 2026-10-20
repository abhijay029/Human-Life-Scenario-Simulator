from __future__ import annotations

from ..schemas.models import ResponseMode

RESPONSE_MODE_INSTRUCTIONS: dict[ResponseMode, str] = {
    ResponseMode.understands: "Respond naturally, engaging with the topic at your level of expertise.",
    ResponseMode.partial: "You catch the general idea but miss technical details. Engage with what you understood; you may ask about one thing you didn't follow.",
    ResponseMode.lost: "You don't understand the technical terms or the claim. React honestly — ask for a simpler explanation, admit confusion, or relate it to something you do know.",
    ResponseMode.analogizes: "You don't fully understand the technical side, but it reminds you of something in your own field. Draw an analogy from {own_domain} — be clear it's your interpretation, not technical knowledge.",
}


def get_response_mode_instruction(mode: ResponseMode, own_domain: str = "") -> str:
    template = RESPONSE_MODE_INSTRUCTIONS[mode]
    return template.replace("{own_domain}", own_domain or "your field")
