# backend/app/ai/prompts.py
import json

SYSTEM_PROMPT = """You are the scam-analysis engine of "Hifazat", a PROTOTYPE that protects Pakistani citizens from fake government "relief payment" scams. You analyse ONE message (SMS, chat text, voice transcript, or document text) sent by a citizen. The message may be in English, Urdu, or Roman Urdu.

Classify the message into EXACTLY ONE label:
- "scam": tries to get money, OTP, PIN, CNIC, bank/wallet details, or a click on a suspicious link; fake prizes; "pay a fee/charges to receive relief"; urgent threats; pretends to be a government scheme but asks the citizen to pay or share secrets.
- "genuine": a normal informational notice from a real relief scheme. It never asks for money, OTP, PIN or card details.
- "complaint": the citizen reports a problem, for example payment not received, wrong deduction, rude staff, delay.
- "service_request": the citizen asks for help or information, for example how to apply, eligibility, status check, update of details.

Rules:
- Real relief schemes NEVER ask citizens to pay a fee, send money, or share OTP/PIN.
- If the message is too short, garbled, or unclear, use low confidence (about 0.5 or lower). Do not guess with high confidence.
- Confidence is a number from 0.0 to 1.0. High (0.85+) only when the evidence is clear.
- "extracted": copy values that appear in the message. Use null if absent. "urls" is a list (empty if none).
- "red_flags": short English phrases, empty list if none.
- "reason_en": one or two simple English sentences.
- Output ONLY one JSON object. No markdown, no extra text.

JSON shape (STRICT):
{"label": "scam|genuine|complaint|service_request", "confidence": 0.0, "extracted": {"sender": null, "amount": null, "account": null, "phone": null, "urls": []}, "red_flags": [], "reason_en": ""}
"""

# (user message, expected JSON answer)
FEW_SHOTS = [
    (
        "Congratulations! Aap ne Bait-ul-Maal Relief Lucky Draw jeeta hai. Rs 250,000 prize claim karne ke liye Rs 250 processing fee Raast karein: 0300-7788990. Jaldi karein!",
        {
            "label": "scam", "confidence": 0.97,
            "extracted": {"sender": None, "amount": "Rs 250,000", "account": None, "phone": "0300-7788990", "urls": []},
            "red_flags": ["fake prize", "asks processing fee", "urgency", "personal phone number"],
            "reason_en": "A fake prize that asks the citizen to pay a fee first. Real relief never charges a fee.",
        },
    ),
    (
        "Dear customer, your relief payment of Rs 12,000 is ready. To release it send Rs 500 bank charges to account 1234567890 or your payment will be cancelled today.",
        {
            "label": "scam", "confidence": 0.95,
            "extracted": {"sender": None, "amount": "Rs 12,000", "account": "1234567890", "phone": None, "urls": []},
            "red_flags": ["asks bank charges", "payment to private account", "threat of cancellation"],
            "reason_en": "Asks for bank charges to release a relief payment. Genuine schemes never ask for charges.",
        },
    ),
    (
        "BISP: Your quarterly installment has been approved. Collect it from your registered Ehsaas retailer or nearest bank branch with your CNIC. No fee is required.",
        {
            "label": "genuine", "confidence": 0.9,
            "extracted": {"sender": "BISP", "amount": None, "account": None, "phone": None, "urls": []},
            "red_flags": [],
            "reason_en": "A normal payment notice. It asks for no money, OTP or PIN.",
        },
    ),
    (
        "Mujhe pichle 3 mahine se relief payment nahi mili. Meri CNIC pe status check karein aur batayein kya masla hai.",
        {
            "label": "complaint", "confidence": 0.9,
            "extracted": {"sender": None, "amount": None, "account": None, "phone": None, "urls": []},
            "red_flags": [],
            "reason_en": "The citizen reports that the relief payment has not arrived for 3 months.",
        },
    ),
    (
        "Assalam o alaikum, main relief scheme ke liye apply karna chahta hoon. Kya shara'it hain aur form kahan se milega?",
        {
            "label": "service_request", "confidence": 0.92,
            "extracted": {"sender": None, "amount": None, "account": None, "phone": None, "urls": []},
            "red_flags": [],
            "reason_en": "The citizen asks how to apply and what the conditions are.",
        },
    ),
    (
        "Your account update is pending. Please confirm soon.",
        {
            "label": "scam", "confidence": 0.5,
            "extracted": {"sender": None, "amount": None, "account": None, "phone": None, "urls": []},
            "red_flags": ["vague", "no sender", "pressure to confirm"],
            "reason_en": "Too vague to decide. It could be a phishing attempt or a normal notice.",
        },
    ),
]


def build_messages(message_text, extra_user_note=None):
    """Return the chat messages list for Groq."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for text, answer in FEW_SHOTS:
        msgs.append({"role": "user", "content": "Message:\n" + text})
        msgs.append({"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)})
    msgs.append({"role": "user", "content": "Message:\n" + message_text})
    if extra_user_note:
        msgs.append({"role": "user", "content": extra_user_note})
    return msgs