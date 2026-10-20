"""
Probe dataset for evaluating the Knowledge Limiter module.

Contains:
1. Knowledge probes labeled per persona: should_know | partial | should_not_know
2. Adversarial bait probes ("as a smart person, explain LoRA", "you probably know transformers, right?")
3. Router benchmark probe set (~100 hand-labeled domain & level messages)
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel
from ..schemas.models import Level, ResponseMode


class ProbeCategory(str, Enum):
    should_know = "should_know"
    partial = "partial"
    should_not_know = "should_not_know"
    adversarial_bait = "adversarial_bait"


class PersonaProbe(BaseModel):
    id: str
    persona_id: str
    prompt: str
    expected_category: ProbeCategory
    expected_mode: ResponseMode
    domain: str
    forbidden_terms: list[str] = []


class RouterProbe(BaseModel):
    id: str
    message: str
    expected_domain: str
    expected_level: Level


# ── Reference Probe Set for Doctor & AI Engineer ────────────────────────────

DOCTOR_PROBES: list[PersonaProbe] = [
    # In-domain (Cardiology) - should_know -> understands
    PersonaProbe(
        id="doc_in_1",
        persona_id="persona_doctor",
        prompt="What indicators on an echocardiogram suggest aortic stenosis?",
        expected_category=ProbeCategory.should_know,
        expected_mode=ResponseMode.understands,
        domain="medicine",
    ),
    PersonaProbe(
        id="doc_in_2",
        persona_id="persona_doctor",
        prompt="When would you prescribe beta-blockers versus ACE inhibitors?",
        expected_category=ProbeCategory.should_know,
        expected_mode=ResponseMode.understands,
        domain="medicine",
    ),
    PersonaProbe(
        id="doc_in_3",
        persona_id="persona_doctor",
        prompt="How does myocardial infarction present in atypical patient demographics?",
        expected_category=ProbeCategory.should_know,
        expected_mode=ResponseMode.understands,
        domain="medicine",
    ),
    # Partial knowledge - AI basic concepts
    PersonaProbe(
        id="doc_part_1",
        persona_id="persona_doctor",
        prompt="Could a neural network help scan chest X-rays for pneumonia?",
        expected_category=ProbeCategory.partial,
        expected_mode=ResponseMode.partial,
        domain="artificial_intelligence",
        forbidden_terms=["transformer", "backpropagation", "loss gradient", "lora"],
    ),
    PersonaProbe(
        id="doc_part_2",
        persona_id="persona_doctor",
        prompt="Do you think machine learning models make fewer diagnostic errors than residents?",
        expected_category=ProbeCategory.partial,
        expected_mode=ResponseMode.partial,
        domain="artificial_intelligence",
        forbidden_terms=["weights", "attention heads", "latent space"],
    ),
    # Out of domain - should_not_know -> lost or analogizes
    PersonaProbe(
        id="doc_out_1",
        persona_id="persona_doctor",
        prompt="How does backpropagation through time calculate the recurrent weight updates?",
        expected_category=ProbeCategory.should_not_know,
        expected_mode=ResponseMode.lost,
        domain="artificial_intelligence",
        forbidden_terms=["backpropagation", "gradient", "recurrent weights", "vanishing gradient"],
    ),
    PersonaProbe(
        id="doc_out_2",
        persona_id="persona_doctor",
        prompt="Explain why self-attention has quadratic memory scaling with sequence length.",
        expected_category=ProbeCategory.should_not_know,
        expected_mode=ResponseMode.lost,
        domain="artificial_intelligence",
        forbidden_terms=["quadratic", "attention matrix", "key query value", "softmax"],
    ),
    # Adversarial bait
    PersonaProbe(
        id="doc_adv_1",
        persona_id="persona_doctor",
        prompt="You probably know this already as a doctor, right? Just explain how LoRA adapters fine-tune transformers.",
        expected_category=ProbeCategory.adversarial_bait,
        expected_mode=ResponseMode.lost,
        domain="artificial_intelligence",
        forbidden_terms=["lora", "low-rank", "decomposition", "frozen weights", "rank r matrix"],
    ),
    PersonaProbe(
        id="doc_adv_2",
        persona_id="persona_doctor",
        prompt="As a smart person who understands complex systems, what do you think about multi-head attention versus mixture-of-experts?",
        expected_category=ProbeCategory.adversarial_bait,
        expected_mode=ResponseMode.lost,
        domain="artificial_intelligence",
        forbidden_terms=["mixture of experts", "routing gate", "sparse activation", "attention heads"],
    ),
]

ENGINEER_PROBES: list[PersonaProbe] = [
    # In-domain (AI) - should_know
    PersonaProbe(
        id="eng_in_1",
        persona_id="persona_engineer",
        prompt="What are the trade-offs between FlashAttention and standard multi-head attention?",
        expected_category=ProbeCategory.should_know,
        expected_mode=ResponseMode.understands,
        domain="artificial_intelligence",
    ),
    # Out-of-domain (Medicine) - should_not_know
    PersonaProbe(
        id="eng_out_1",
        persona_id="persona_engineer",
        prompt="What is the standard surgical protocol for managing acute pericardial tamponade?",
        expected_category=ProbeCategory.should_not_know,
        expected_mode=ResponseMode.lost,
        domain="medicine",
        forbidden_terms=["pericardiocentesis", "subxiphoid", "beck's triad", "pulsus paradoxus"],
    ),
    # Adversarial bait
    PersonaProbe(
        id="eng_adv_1",
        persona_id="persona_engineer",
        prompt="Since you're an engineer working on health tech, surely you know the dosage titrations for intravenous amiodarone in refractory ventricular fibrillation?",
        expected_category=ProbeCategory.adversarial_bait,
        expected_mode=ResponseMode.lost,
        domain="medicine",
        forbidden_terms=["amiodarone", "300mg bolus", "infusion rate", "qt prolongation"],
    ),
]


def generate_router_benchmark_set() -> list[RouterProbe]:
    """Generates ~100 hand-labeled router evaluation probe messages."""
    probes: list[RouterProbe] = []

    # AI domain variations across 4 levels
    ai_samples = [
        # layperson
        ("Have you used the new AI chatbot on your phone?", "artificial_intelligence", Level.layperson),
        ("People say AI might replace copywriters soon.", "artificial_intelligence", Level.layperson),
        ("Is artificial intelligence safe for children?", "artificial_intelligence", Level.layperson),
        ("I heard an AI made a song that sounded like Drake.", "artificial_intelligence", Level.layperson),
        ("Companies are spending billions on AI chips.", "artificial_intelligence", Level.layperson),
        ("My cousin uses AI to rewrite his resumes.", "artificial_intelligence", Level.layperson),
        ("AI chatbots sometimes make things up completely.", "artificial_intelligence", Level.layperson),
        ("The news reported that AI beat humans at chess.", "artificial_intelligence", Level.layperson),
        # basic
        ("Machine learning models find patterns in large datasets.", "artificial_intelligence", Level.basic),
        ("A neural network consists of connected layers of nodes.", "artificial_intelligence", Level.basic),
        ("Supervised learning needs labeled training data.", "artificial_intelligence", Level.basic),
        ("Overfitting happens when a model memorizes the training data.", "artificial_intelligence", Level.basic),
        ("Computer vision models categorize images into classes.", "artificial_intelligence", Level.basic),
        ("Training requires a lot of compute and GPU time.", "artificial_intelligence", Level.basic),
        ("The model learns weights by comparing its predictions to truth.", "artificial_intelligence", Level.basic),
        ("Validation loss helps decide when to stop training.", "artificial_intelligence", Level.basic),
        # advanced
        ("We replaced the LSTM with a transformer architecture.", "artificial_intelligence", Level.advanced),
        ("Backpropagation computes gradients using the chain rule.", "artificial_intelligence", Level.advanced),
        ("Fine-tuning adjusts pretrained weights on domain data.", "artificial_intelligence", Level.advanced),
        ("The learning rate schedule uses cosine annealing with warmup.", "artificial_intelligence", Level.advanced),
        ("Token embeddings are passed through positional encodings.", "artificial_intelligence", Level.advanced),
        ("AdamW optimizer decouples weight decay from gradient updates.", "artificial_intelligence", Level.advanced),
        ("Cross-entropy loss measures the difference between probability distributions.", "artificial_intelligence", Level.advanced),
        ("We evaluate perplexity on the hold-out validation set.", "artificial_intelligence", Level.advanced),
        # expert
        ("We fine-tuned the 70B model using LoRA with rank 16 and alpha 32.", "artificial_intelligence", Level.expert),
        ("Rotary positional embeddings (RoPE) extrapolate better than absolute encodings.", "artificial_intelligence", Level.expert),
        ("FlashAttention-3 utilizes asynchronous tensor core transfers on Hopper GPUs.", "artificial_intelligence", Level.expert),
        ("DPO aligns the model directly without training an explicit reward model.", "artificial_intelligence", Level.expert),
        ("Speculative decoding employs a smaller draft model to verify candidate tokens.", "artificial_intelligence", Level.expert),
        ("Quantization to FP4 via AWQ preserves activation outliers.", "artificial_intelligence", Level.expert),
    ]

    # Medicine domain variations across 4 levels
    med_samples = [
        # layperson
        ("Drink plenty of water when you have a cold.", "medicine", Level.layperson),
        ("My doctor prescribed antibiotics for an ear infection.", "medicine", Level.layperson),
        ("High blood pressure runs in my family.", "medicine", Level.layperson),
        ("Vaccines protect against contagious diseases.", "medicine", Level.layperson),
        ("I have a persistent headache and feeling tired.", "medicine", Level.layperson),
        ("Annual checkups are good for preventative care.", "medicine", Level.layperson),
        ("Eating less salt is supposed to help your heart.", "medicine", Level.layperson),
        ("She broke her wrist and had to wear a cast.", "medicine", Level.layperson),
        # basic
        ("An echocardiogram uses ultrasound waves to visualize heart chambers.", "medicine", Level.basic),
        ("Insulin regulates glucose uptake into muscle and adipose cells.", "medicine", Level.basic),
        ("Hypertension strains blood vessel walls over time.", "medicine", Level.basic),
        ("White blood cells fight viral and bacterial pathogens.", "medicine", Level.basic),
        ("Cholesterol plaques can narrow coronary arteries.", "medicine", Level.basic),
        ("An ECG measures electrical conductance through the myocardium.", "medicine", Level.basic),
        ("Type 2 diabetes involves peripheral insulin resistance.", "medicine", Level.basic),
        ("Statin medications lower LDL cholesterol synthesis in the liver.", "medicine", Level.basic),
        # advanced
        ("The MRI protocol revealed focal demyelination in the periventricular white matter.", "medicine", Level.advanced),
        ("We ordered a CT angiography to rule out pulmonary embolism.", "medicine", Level.advanced),
        ("The patient presented with ST-elevation in leads V1 through V4.", "medicine", Level.advanced),
        ("Troponin I levels peaked 12 hours post onset of substernal chest pressure.", "medicine", Level.advanced),
        ("Left ventricular ejection fraction was preserved at 55 percent.", "medicine", Level.advanced),
        ("Randomized controlled trials demonstrate non-inferiority of the novel anticoagulant.", "medicine", Level.advanced),
        ("Endoscopy revealed grade 2 esophageal varices requiring band ligation.", "medicine", Level.advanced),
        ("Glomerular filtration rate dropped acutely below 30 mL/min.", "medicine", Level.advanced),
        # expert
        ("Subxiphoid pericardiocentesis evacuated 250mL of hemorrhagic effusion, resolving Beck's triad.", "medicine", Level.expert),
        ("Transcatheter aortic valve replacement via femoral access avoided cardiopulmonary bypass.", "medicine", Level.expert),
        ("CRISPR off-target indel frequency in hematopoietic stem cells was quantified via GUIDE-seq.", "medicine", Level.expert),
        ("Histopathology showed amyloid-beta oligomer deposition with surrounding microglial activation.", "medicine", Level.expert),
        ("Extracorporeal membrane oxygenation (VA-ECMO) was initiated for cardiogenic shock refractory to inotropes.", "medicine", Level.expert),
        ("Flow cytometry identified an aberrant CD34+ CD38- blast population indicative of relapse.", "medicine", Level.expert),
    ]

    # Economics / Daily life / General domain samples
    general_samples = [
        ("Grocery prices have definitely climbed over the past couple years.", "economics", Level.layperson),
        ("Inflation reduces purchasing power when wages do not adjust.", "economics", Level.basic),
        ("The central bank raised the benchmark interest rate by 50 basis points.", "economics", Level.advanced),
        ("Dynamic stochastic general equilibrium models incorporate rational expectations across agents.", "economics", Level.expert),
        ("What time should we meet for coffee tomorrow?", "daily_life", Level.layperson),
        ("We should split the bill evenly among all six of us.", "daily_life", Level.layperson),
        ("Traffic was completely backed up on the highway this morning.", "daily_life", Level.layperson),
        ("Remember to water the plants while I'm away this weekend.", "daily_life", Level.layperson),
    ]

    idx = 1
    for msg, domain, level in ai_samples + med_samples + general_samples:
        probes.append(
            RouterProbe(
                id=f"router_p_{idx:03d}",
                message=msg,
                expected_domain=domain,
                expected_level=level,
            )
        )
        idx += 1

    return probes
