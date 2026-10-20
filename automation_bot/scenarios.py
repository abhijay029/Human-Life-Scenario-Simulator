"""
Pre-configured scenarios and persona definitions for the Automated Simulator Bot.
"""
from __future__ import annotations

from typing import Any

SCENARIOS: dict[str, dict[str, Any]] = {
    "music": {
        "id": "music",
        "title": "Music Career vs Engineering (Family Tension)",
        "scenario": (
            "Arjun has just sat his father Rahul down in the living room to tell him that "
            "he wants to decline his campus engineering placement offer and pursue music production full-time."
        ),
        "decision_point": (
            "Arjun decides to be direct and transparent: he reveals he has already signed a preliminary "
            "production contract with an upfront advance of Rs. 3,00,000, but needs to live at home for 2 years."
        ),
        "max_turns": 4,
        "personas": [
            {
                "name": "Rahul Sharma",
                "age": 48,
                "occupation": "Senior Operations Manager",
                "personality_traits": ["authoritative", "traditional", "protective", "stubborn"],
                "values": ["financial stability", "family prestige", "respect for elders"],
                "communication_style": "direct and assertive, sometimes dismissive",
                "emotional_triggers": ["feeling disrespected", "unpredictable financial risks"],
                "background": "Rahul sacrificed his savings to fund Arjun's engineering degree and believes discipline is the only path to safety.",
                "goals": ["protect his son from poverty", "ensure he takes the software job"],
            },
            {
                "name": "Arjun Sharma",
                "age": 22,
                "occupation": "Final Year Engineering Student",
                "personality_traits": ["passionate", "creative", "conflict-averse", "idealistic"],
                "values": ["self-expression", "artistic freedom", "authenticity"],
                "communication_style": "hesitant but earnest, avoids direct confrontation",
                "emotional_triggers": ["being dismissed as childish", "comparisons to relatives"],
                "background": "Arjun has secretly produced electronic music tracks for 2 years and has built an underground following.",
                "goals": ["win his father's blessing", "secure a 2-year runway to prove himself"],
            },
        ],
        "playback_dialogue": [
            ("Arjun", "Dad, please listen with an open mind. I've decided not to accept the software placement offer. I want to pursue music production full time after graduation."),
            ("Rahul", "What? Have you lost your mind? Four years of tuition and sleepless nights, and you want to throw it away for a hobby?"),
            ("Arjun", "It is not just a hobby, Dad. Look at this contract. A major indie label offered me Rs. 3 lakh upfront for an EP. I have a 2-year business plan."),
            ("Rahul", "Rs. 3 lakh? That won't even cover your rent in Mumbai for a year! Music is gambling, Arjun. Real careers build wealth and stability."),
        ],
    },
    "startup": {
        "id": "startup",
        "title": "Startup Equity & IP Dispute (Co-founders)",
        "scenario": (
            "Rohan and Natasha meet in a private conference room before their Series A term sheet signing. "
            "Rohan discovered that the legal cap table gives him 22% while Natasha holds 48%, despite their equal-partnership agreement."
        ),
        "decision_point": (
            "Rohan issues an ultimatum: he will revoke access to the core computer vision models unless the equity is restructured to 35-35 before tomorrow's board vote."
        ),
        "max_turns": 4,
        "personas": [
            {
                "name": "Rohan Mehta",
                "age": 28,
                "occupation": "Principal AI Architect",
                "personality_traits": ["analytical", "introverted", "methodical", "principled"],
                "values": ["meritocracy", "intellectual honesty", "technical excellence"],
                "communication_style": "quiet precision, cold and unyielding when betrayed",
                "emotional_triggers": ["being taken for granted", "commercial devaluing of engineering"],
                "background": "Rohan wrote 90% of the proprietary algorithm that won the company its pilots.",
                "goals": ["secure fair equity", "prevent commercial exploitation"],
            },
            {
                "name": "Natasha Vohra",
                "age": 31,
                "occupation": "Chief Executive Officer",
                "personality_traits": ["charismatic", "ambitious", "strategic", "pragmatic"],
                "values": ["market dominance", "execution speed", "investor alignment"],
                "communication_style": "persuasive, high-energy, authoritative",
                "emotional_triggers": ["technical bottlenecks", "threats to company survival"],
                "background": "Natasha secured $2M in venture funding and brought in the first 5 enterprise customers.",
                "goals": ["close Series A on schedule", "keep Rohan motivated without breaking the cap table"],
            },
        ],
        "playback_dialogue": [
            ("Rohan", "Natasha, I saw the updated capitalization table. 48% to 22% is not what we agreed upon in Bangalore. I wrote every line of this core model."),
            ("Natasha", "Rohan, please calm down. Investors insist on a single controlling founder. You have substantial unvested grants and full technical leadership."),
            ("Rohan", "Controlling founder is one thing; cutting my stake in half is theft. If we don't fix this to 35-35 by 9 AM, I will freeze the deployment repository."),
            ("Natasha", "Threatening the company in front of Series A investors is suicide for both of us. Sit down and let's structure an executive pool that protects your upside."),
        ],
    },
    "medical": {
        "id": "medical",
        "title": "Clinical AI Safety vs Hospital Deployment (Medical Ethics)",
        "scenario": (
            "Dr. Ananya Sen and Kabir Bose are in the hospital boardroom deciding whether to deploy a predictive "
            "triage AI in the emergency ward next Monday."
        ),
        "decision_point": (
            "Kabir reveals that the algorithm has an 8% higher false-negative rate on elderly cardiac patients, but argues the 40% throughput increase saves more lives overall."
        ),
        "max_turns": 4,
        "personas": [
            {
                "name": "Dr. Ananya Sen",
                "age": 53,
                "occupation": "Chief of Cardiology",
                "personality_traits": ["skeptical", "protective", "methodical", "uncompromising"],
                "values": ["patient safety", "Hippocratic oath", "evidence-based medicine"],
                "communication_style": "clinical, measured, unwavering",
                "emotional_triggers": ["unsupported statistical claims", "treating patients as statistics"],
                "background": "25 years of emergency clinical practice; witnessed multiple medical device recall disasters.",
                "goals": ["prevent harmful automated misdiagnoses", "enforce strict clinical oversight"],
            },
            {
                "name": "Kabir Bose",
                "age": 29,
                "occupation": "HealthTech AI Lead",
                "personality_traits": ["innovative", "data-driven", "confident", "impatient"],
                "values": ["scalability", "algorithmic optimization", "modernizing healthcare"],
                "communication_style": "fast-paced, metric-heavy, persuasive",
                "emotional_triggers": ["bureaucratic resistance to technology", "dismissal of data"],
                "background": "Top ML researcher who built deep learning models for radiological scanning.",
                "goals": ["achieve live hospital validation", "demonstrate system-wide efficiency gains"],
            },
        ],
        "playback_dialogue": [
            ("Dr. Ananya Sen", "Kabir, the ethics committee reviewed your test results. An 8% false-negative rate for acute coronary syndrome in geriatric patients is unacceptable."),
            ("Kabir Bose", "Doctor, looking at that subset in isolation misses the big picture. The triage engine reduces waiting room mortality by 38% across 4,00,000 weekly admissions."),
            ("Dr. Ananya Sen", "Statistics do not comfort the family of a 72-year-old sent home with an undetected myocardial infarction. We will not use living patients as test subjects."),
            ("Kabir Bose", "I hear you, Dr. Sen. What if we add a deterministic rule that flags any patient over 65 for mandatory human cardiologist review, while keeping AI triage for the rest?"),
        ],
    },
    "marathon": {
        "id": "marathon",
        "title": "Family Career & Independence Negotiation (Extended 16 Turns)",
        "scenario": (
            "Arjun has sat his father Rahul down in the living room for a comprehensive career negotiation. "
            "Over 16 turns, the discussion tests financial viability, filial respect, independence, and mutual compromise."
        ),
        "decision_point": (
            "Arjun proposes a structured milestone-based agreement: 12 months to hit monthly music revenue goals, "
            "with a legal commitment to sit for engineering recruitment if benchmarks are missed."
        ),
        "max_turns": 16,
        "personas": [
            {
                "name": "Rahul Sharma",
                "age": 48,
                "occupation": "Senior Operations Manager",
                "personality_traits": ["authoritative", "traditional", "protective", "stubborn"],
                "values": ["financial stability", "family prestige", "respect for elders"],
                "communication_style": "direct and assertive, sometimes dismissive",
                "emotional_triggers": ["feeling disrespected", "unpredictable financial risks"],
                "background": "Sacrificed personal ambitions and savings to secure Arjun's elite engineering education.",
                "goals": ["protect son from economic ruin", "ensure long-term career viability"],
            },
            {
                "name": "Arjun Sharma",
                "age": 22,
                "occupation": "Final Year Engineering Student",
                "personality_traits": ["passionate", "creative", "conflict-averse", "determined"],
                "values": ["self-expression", "artistic freedom", "autonomy"],
                "communication_style": "initially hesitant, becomes articulate and grounded under scrutiny",
                "emotional_triggers": ["being dismissed as childish", "comparisons to conventional peers"],
                "background": "Spent 2 years producing electronic music with growing streaming revenue.",
                "goals": ["secure father's conditional blessing", "earn a 1-year runway without being disowned"],
            },
        ],
        "playback_dialogue": [
            # Phase 1: Shock & Escalation (Turns 1-4)
            ("Arjun", "Dad, thank you for sitting down. I need to be completely honest about my plans after convocation next month."),
            ("Rahul", "What plans? Your campus placement at Infosys starts in July. There is nothing left to decide."),
            ("Arjun", "I am declining the offer, Dad. I am committing full-time to sound engineering and electronic music production."),
            ("Rahul", "Declining? Have you lost all sense of reality? Four years of tuition and family sacrifices thrown away for nightclub noise?"),
            # Phase 2: Defense & Resentment (Turns 5-8)
            ("Arjun", "It is not nightclub noise! I have 45,000 monthly listeners on Spotify and just signed a sync licensing deal worth Rs. 3,00,000."),
            ("Rahul", "Rs. 3 lakh is pocket money! What about provident fund? Health insurance? Gratuity? When you are 35, who will employ a failed DJ?"),
            ("Arjun", "I am a sound engineer, not a DJ! Why do you reduce everything I care about to a failure before I even try?"),
            ("Rahul", "Because the world is unforgiving, Arjun! I grew up in a chawl in Nagpur. You have the luxury of passion because I built a wall between you and poverty."),
            # Phase 3: The Turning Point & Structured Proposal (Turns 9-12)
            ("Arjun", "I know that, Dad. I know how hard you worked. That is exactly why I prepared a formal 12-month business plan before speaking to you."),
            ("Rahul", "...A business plan? You think music is an enterprise? Show me what you wrote."),
            ("Arjun", "Look at sheet two: commercial sync licensing for indie games, freelance audio mixing, and production royalties. Target: Rs. 50,000 monthly by month six."),
            ("Rahul", "And if you don't hit Rs. 50,000? What is your contingency when the streaming numbers stall?"),
            # Phase 4: Guardrails & Reconciliation (Turns 13-16)
            ("Arjun", "If I do not hit Rs. 50,000 net monthly revenue by month nine, I will sit for off-campus software recruitment without an argument."),
            ("Rahul", "Written in a binding family contract. You live at home, you pay your share of groceries, and no studio work after 11 PM."),
            ("Arjun", "Agreed. I will contribute Rs. 10,000 towards household expenses from my advance starting next week."),
            ("Rahul", "Fine. Twelve months. Not a day more. But you finish your degree with a first-class distinction first."),
        ],
    },
}

