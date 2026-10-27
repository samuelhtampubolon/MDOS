"""Deterministic research-design generator: business question to framing, design, questionnaire,
sampling plan and fieldwork plan.

This is the offline core of the design agents. When Claude is configured, the agents use it to improve
wording, but the structure produced here (constructs from the library, variable names, price module,
analysis plan) stays the backbone so outputs remain consistent and testable.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from ..analytics.power import margin_of_error, sample_size_proportion
from .constructs import AGREE5_EN, AGREE5_ID, LIBRARY

PRICE_RE = re.compile(
    r"(?:(?P<cur>rp\.?|idr|usd|\$|eur|€|sgd|myr|rm)\s*)?(?P<num>\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(?P<unit>ribu|rb|k|juta|jt|million|thousand)?",
    re.IGNORECASE,
)
INTENT_KEYWORDS = {
    "pricing": ["pay", "price", "pricing", "willing", "harga", "bayar", "worth", "afford", "cost", "tarif", "wtp", "rp"],
    "concept": ["new", "launch", "concept", "idea", "product", "service", "experience", "baru", "produk", "demand", "minat"],
    "satisfaction": ["satisf", "puas", "kepuasan", "quality", "kualitas", "complain", "keluhan", "service quality"],
    "loyalty": ["loyal", "retain", "retention", "repeat", "churn", "kembali", "recommend", "rekomendasi"],
    "brand": ["brand", "merek", "aware", "image", "citra", "perception", "persepsi", "position"],
    "segmentation": ["segment", "who are", "target", "persona", "profil", "segmen"],
    "channel": ["channel", "instagram", "tiktok", "social media", "media sosial", "ads", "iklan", "campaign", "kampanye", "influencer"],
}
POPULATIONS = [
    (r"tourist|traveler|traveller|visitor|wisatawan|turis|pengunjung", "tourists", "wisatawan"),
    (r"student|mahasiswa|pelajar", "students", "mahasiswa"),
    (r"gen ?z", "Gen Z consumers", "konsumen Gen Z"),
    (r"millennial|milenial", "millennial consumers", "konsumen milenial"),
    (r"sme|umkm|small business", "small business owners", "pelaku UMKM"),
    (r"guest|tamu", "guests", "tamu"),
    (r"customer|consumer|pelanggan|konsumen|buyer|pembeli", "customers", "pelanggan"),
    (r"parent|orang tua", "parents", "orang tua"),
]


@dataclass
class ParsedQuestion:
    text: str
    intents: list[str]
    price: float | None
    currency: str
    population_en: str
    population_id: str
    offering: str
    tourism: bool
    cultural: bool
    notes: list[str] = field(default_factory=list)


def parse_price(text: str) -> tuple[float | None, str | None]:
    best: tuple[float, str] | None = None
    for m in PRICE_RE.finditer(text):
        cur = (m.group("cur") or "").lower()
        unit = (m.group("unit") or "").lower()
        raw = m.group("num")
        if not cur and not unit:
            continue
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
            value = float(re.sub(r"[.,]", "", raw))
        else:
            value = float(raw.replace(",", "."))
        value *= {"ribu": 1e3, "rb": 1e3, "k": 1e3, "thousand": 1e3, "juta": 1e6, "jt": 1e6, "million": 1e6}.get(unit, 1)
        currency = {"rp": "IDR", "rp.": "IDR", "idr": "IDR", "$": "USD", "usd": "USD", "eur": "EUR", "€": "EUR",
                    "sgd": "SGD", "myr": "MYR", "rm": "MYR"}.get(cur, "IDR")
        if value > 0 and (best is None or value > best[0]):
            best = (value, currency)
    return (best[0], best[1]) if best else (None, None)


def parse_question(text: str, default_currency: str = "IDR", industry: str = "") -> ParsedQuestion:
    low = text.lower()
    intents = [k for k, words in INTENT_KEYWORDS.items() if any(w in low for w in words)]
    price, currency = parse_price(text)
    if price is not None and "pricing" not in intents:
        intents.insert(0, "pricing")
    if not intents:
        intents = ["concept"]
    pop_en, pop_id = "target customers", "pelanggan sasaran"
    for pattern, en, idn in POPULATIONS:
        if re.search(pattern, low):
            pop_en, pop_id = en, idn
            break
    offering = ""
    m = re.search(r"\bfor (?:a |an |the |our |my )?(new [^?.,;]+|[^?.,;]{4,80})", text, re.IGNORECASE)
    if m:
        offering = m.group(1).strip()
        offering = re.sub(r"^(new )", "a new ", offering, flags=re.IGNORECASE)
    tourism = bool(re.search(r"touris|travel|wisata|destination|destinasi|hotel|lake|danau|toba|bali|resort|tour", low)) or industry == "tourism"
    cultural = bool(re.search(r"cultur|budaya|heritage|tradition|tradisi|batak|adat|authentic", low))
    notes = []
    if price is None and "pricing" in intents:
        notes.append("No explicit price found; the price module uses a placeholder target price.")
    return ParsedQuestion(text=text, intents=intents, price=price, currency=currency or default_currency,
                          population_en=pop_en, population_id=pop_id, offering=offering or "the offer",
                          tourism=tourism, cultural=cultural, notes=notes)


def fmt_money(value: float, currency: str) -> str:
    if currency == "IDR":
        return "Rp " + f"{value:,.0f}".replace(",", ".")
    return f"{currency} {value:,.2f}"


def nice_price(value: float) -> float:
    """Round to a price a respondent would recognize (for IDR: steps of 5,000 or 25,000)."""
    if value >= 100_000:
        step = 25_000
    elif value >= 10_000:
        step = 5_000
    elif value >= 1_000:
        step = 500
    elif value >= 10:
        step = 1
    else:
        step = 0.5
    return max(step, round(value / step) * step)


def price_ladder(target: float) -> list[float]:
    ladder = sorted({nice_price(target * f) for f in (0.667, 0.833, 1.167, 1.333)} - {nice_price(target)})
    return ladder


def price_suffix(value: float, currency: str) -> str:
    if currency == "IDR" and value >= 1000 and value % 1000 == 0:
        return f"{int(value // 1000)}k"
    return str(int(value)) if float(value).is_integer() else str(value).replace(".", "_")


# ----------------------------------------------------------------------------------------------
# Framing and design
# ----------------------------------------------------------------------------------------------


def framing(parsed: ParsedQuestion, project: dict[str, Any]) -> dict[str, Any]:
    offer = parsed.offering
    pop = parsed.population_en
    decision = project.get("decision_to_inform") or (
        f"Whether to launch {offer} and at what price" if "pricing" in parsed.intents else f"Whether and how to launch {offer}"
    )
    objectives = []
    if "pricing" in parsed.intents:
        price_txt = fmt_money(parsed.price, parsed.currency) if parsed.price else "the proposed price"
        objectives += [
            f"Estimate the share of {pop} willing to pay {price_txt} for {offer}.",
            f"Identify the acceptable price range and a revenue-maximizing price for {offer}.",
        ]
    objectives.append(f"Identify which perceptions (value, interest, authenticity, price sensitivity) are associated with purchase intention among {pop}.")
    if parsed.tourism:
        objectives.append(f"Compare willingness to pay and preferences between domestic and international {pop}.")
    objectives.append(f"Profile segments of {pop} to guide targeting, packaging and communication.")
    return {
        "business_question": parsed.text,
        "decision_statement": decision,
        "research_problem": (f"Management lacks evidence on how {pop} value {offer}"
                             + (" and how price affects their intention to buy." if "pricing" in parsed.intents else ".")),
        "objectives": objectives,
        "study_type": ("Descriptive and explanatory (correlational) cross-sectional survey with a price-research module. "
                       "Causal claims require a follow-up experiment."),
        "key_unknowns": [
            f"Size of the market segment among {pop} that finds the price acceptable",
            "Which benefits justify the price in the customer's eyes",
            "Differences between customer groups that could justify different packages or prices",
        ],
        "decision_criteria": ([f"At least 50% of qualified {pop} state they would buy at the target price, and the target price lies "
                               "inside the Van Westendorp acceptable range."] if "pricing" in parsed.intents else
                              [f"At least 50% of qualified {pop} state purchase intention (top-two box)."]),
        "intents": parsed.intents,
        "notes": parsed.notes,
    }


def select_constructs(parsed: ParsedQuestion) -> list[str]:
    keys: list[str] = []
    if parsed.cultural:
        keys += ["cultural_interest", "perceived_authenticity"]
    if "satisfaction" in parsed.intents:
        keys += ["service_quality", "satisfaction"]
    if "brand" in parsed.intents:
        keys += ["brand_awareness", "trust"]
    if "channel" in parsed.intents:
        keys += ["social_media_influence"]
    keys += ["perceived_value"]
    if "pricing" in parsed.intents:
        keys += ["price_consciousness"]
    if "loyalty" in parsed.intents or "satisfaction" in parsed.intents:
        keys += ["loyalty_wom"]
    else:
        keys += ["purchase_intention"]
    return list(dict.fromkeys(keys))


def hypotheses_for(keys: list[str], parsed: ParsedQuestion) -> list[dict[str, Any]]:
    names = {k: LIBRARY[k].name.lower() for k in keys}
    codes = {k: LIBRARY[k].code for k in keys}
    outcome = "loyalty_wom" if "loyalty_wom" in keys else "purchase_intention"
    hyps: list[dict[str, Any]] = []

    def add(statement: str, iv: str, dv: str, direction: str = "positive", mediator: str = "", moderator: str = "",
            method: str = "regression_ols", rationale: str = "") -> None:
        hyps.append({"code": f"H{len(hyps) + 1}", "statement": statement, "iv": iv, "dv": dv, "mediator": mediator,
                     "moderator": moderator, "expected_direction": direction, "method": method, "rationale": rationale})

    add(f"Perceived value is positively associated with {names[outcome]}.", codes["perceived_value"], codes[outcome],
        rationale="Value-for-money judgments are a consistent predictor of intention across services (Sweeney and Soutar, 2001).")
    if "cultural_interest" in keys:
        add(f"Cultural interest is positively associated with {names[outcome]}.", codes["cultural_interest"], codes[outcome],
            rationale="Culturally motivated travelers seek and value cultural experiences (McKercher and du Cros, 2002).")
    if "service_quality" in keys and "satisfaction" in keys:
        add("Service quality is positively associated with customer satisfaction.", codes["service_quality"], codes["satisfaction"])
    if "price_consciousness" in keys:
        target = fmt_money(parsed.price, parsed.currency) if parsed.price else "the target price"
        add(f"Price consciousness is negatively associated with willingness to pay {target}.", codes["price_consciousness"],
            "WTP", direction="negative", method="regression_logistic",
            rationale="Price-conscious consumers weigh monetary cost more heavily (Lichtenstein et al., 1993).")
    if "perceived_authenticity" in keys:
        add(f"Perceived authenticity is positively associated with {names[outcome]} through perceived value.",
            codes["perceived_authenticity"], codes[outcome], mediator=codes["perceived_value"], method="mediation",
            rationale="Authenticity raises the perceived benefits side of the value equation (Kolar and Zabkar, 2010).")
    elif "satisfaction" in keys and "loyalty_wom" in keys:
        add("Service quality is positively associated with loyalty through satisfaction.", codes["service_quality"],
            codes["loyalty_wom"], mediator=codes["satisfaction"], method="mediation")
    if parsed.tourism and "pricing" in parsed.intents:
        target = fmt_money(parsed.price, parsed.currency) if parsed.price else "the target price"
        add(f"International visitors are more willing than domestic visitors to pay {target}.", "origin", "WTP",
            direction="difference", method="crosstab",
            rationale="Income and travel-budget differences suggest different price sensitivity by origin.")
    return hyps


def research_design(parsed: ParsedQuestion) -> dict[str, Any]:
    keys = select_constructs(parsed)
    hyps = hypotheses_for(keys, parsed)
    pop = parsed.population_en
    rqs = []
    if "pricing" in parsed.intents:
        rqs.append(f"What share of {pop} would pay {fmt_money(parsed.price, parsed.currency) if parsed.price else 'the target price'} "
                   f"for {parsed.offering}, and what price range do they find acceptable?")
    rqs.append(f"Which perceptions are associated with {pop}'s intention to buy {parsed.offering}?")
    if parsed.tourism:
        rqs.append(f"How do domestic and international {pop} differ in willingness to pay and preferences?")
    rqs.append(f"What distinct segments exist among {pop}, and what would make the offer worth its price to each?")
    constructs = []
    for k in keys:
        c = LIBRARY[k]
        constructs.append({"key": k, "code": c.code, "name": c.name, "definition": c.definition, "source": c.source,
                           "items": [{"variable": f"{c.code.lower()}{i + 1}", "text": t, "text_id": c.items_id[i]}
                                     for i, t in enumerate(c.items_en)]})
    analysis_plan = [{"hypothesis": h["code"], "method": h["method"],
                      "detail": {"regression_ols": "OLS on construct mean scores with controls; assumption checks and robust SE if needed.",
                                 "regression_logistic": "Logistic regression of the target-price yes/no answer.",
                                 "mediation": "PROCESS Model 4 with 5,000 bootstrap resamples.",
                                 "crosstab": "Chi-square test of willingness to pay by visitor origin."}[h["method"]]}
                     for h in hyps]
    analysis_plan += [{"hypothesis": None, "method": "reliability", "detail": "Cronbach's alpha for each construct (0.70 or higher)."}]
    if "pricing" in parsed.intents:
        analysis_plan += [{"hypothesis": None, "method": "van_westendorp", "detail": "Acceptable price range and optimal price point."},
                          {"hypothesis": None, "method": "gabor_granger", "detail": "Demand and revenue across the price ladder."}]
    analysis_plan += [{"hypothesis": None, "method": "segmentation", "detail": "k-means on construct scores; personas."},
                      {"hypothesis": None, "method": "text_themes", "detail": "Themes in the open-ended answers."}]
    return {
        "research_questions": rqs,
        "hypotheses": hyps,
        "constructs": constructs,
        "conceptual_framework": _framework_edges(hyps),
        "method": ("Cross-sectional survey (self-administered, tablet or online) with a price-research module "
                   "(direct target-price question, Van Westendorp and Gabor-Granger) and open-ended questions. "
                   "Optional 8 to 12 qualitative interviews to explain survey findings."),
        "analysis_plan": analysis_plan,
        "design_caveats": [
            "Stated willingness to pay overstates real behavior (hypothetical bias); plan a behavioral validation.",
            "Cross-sectional data supports associations, not causal claims.",
            "Adapted scale items must be pilot-tested for comprehension in both languages.",
        ],
    }


def _framework_edges(hyps: list[dict[str, Any]]) -> list[dict[str, str]]:
    edges = []
    for h in hyps:
        if h["mediator"]:
            edges += [{"from": h["iv"], "to": h["mediator"], "hypothesis": h["code"]},
                      {"from": h["mediator"], "to": h["dv"], "hypothesis": h["code"]}]
        else:
            edges.append({"from": h["iv"], "to": h["dv"], "hypothesis": h["code"]})
    return edges


# ----------------------------------------------------------------------------------------------
# Questionnaire
# ----------------------------------------------------------------------------------------------


def _q(code: str, section: str, qtype: str, text: str, text_id: str, options: list | None = None,
       scale: dict | None = None, logic: dict | None = None, required: bool = True, construct: str = "") -> dict[str, Any]:
    return {"code": code, "section": section, "qtype": qtype, "text": text, "text_id": text_id, "options": options or [],
            "scale": scale or {}, "logic": logic or {}, "required": required, "construct_code": construct}


def _opts(pairs: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"value": en, "label": en, "label_id": idn} for en, idn in pairs]


YES_NO = [{"value": "Ya", "label": "Yes", "label_id": "Ya"}, {"value": "Tidak", "label": "No", "label_id": "Tidak"}]
AGREE_SCALE = {"min": 1, "max": 5, "labels": AGREE5_EN, "labels_id": AGREE5_ID}


def questionnaire(parsed: ParsedQuestion, design: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    offer = parsed.offering
    qs: list[dict[str, Any]] = []
    place = "Lake Toba" if "toba" in parsed.text.lower() else ("the destination" if parsed.tourism else "our business")
    place_id = "Danau Toba" if "toba" in parsed.text.lower() else ("destinasi ini" if parsed.tourism else "usaha kami")
    if parsed.tourism:
        qs.append(_q("screen_visit", "Screening", "single",
                     f"Have you visited {place} in the past 12 months, or do you plan to visit in the next 12 months?",
                     f"Apakah Anda pernah mengunjungi {place_id} dalam 12 bulan terakhir, atau berencana berkunjung dalam 12 bulan ke depan?",
                     YES_NO, logic={"terminate_if": "Tidak"}))
    else:
        qs.append(_q("screen_customer", "Screening", "single", f"Are you a current or potential customer of {place}?",
                     f"Apakah Anda pelanggan atau calon pelanggan {place_id}?", YES_NO, logic={"terminate_if": "Tidak"}))
    qs.append(_q("concept", "Concept", "info",
                 f"Please read this short description of {offer}. [Describe the offer neutrally: what is included, duration, "
                 "where it takes place. Do not mention the price here.]",
                 "Silakan baca deskripsi singkat berikut. [Jelaskan penawaran secara netral: apa yang termasuk, durasi, lokasi. "
                 "Jangan sebutkan harga di sini.]", required=False))
    for c in design["constructs"]:
        for item in c["items"]:
            qs.append(_q(item["variable"], c["name"], "likert", item["text"], item["text_id"], scale=AGREE_SCALE, construct=c["code"]))
        if c["code"] == design["constructs"][len(design["constructs"]) // 2]["code"]:
            qs.append(_q("attention_check", c["name"], "likert", "To show you are reading carefully, please select 'Agree' for this statement.",
                         "Untuk menunjukkan Anda membaca dengan saksama, silakan pilih 'Setuju' untuk pernyataan ini.",
                         scale={**AGREE_SCALE, "expected": 4}))
    if "pricing" in parsed.intents:
        target = parsed.price or 100.0
        cur = parsed.currency
        suffix = price_suffix(target, cur)
        qs.append(_q(f"wtp_{suffix}", "Price", "single", f"Would you book {offer} at {fmt_money(target, cur)} per person?",
                     f"Apakah Anda akan memesan pengalaman ini dengan harga {fmt_money(target, cur)} per orang?", YES_NO))
        vw = [("vw_too_cheap", "At what price would it be so cheap that you would doubt its quality?",
               "Pada harga berapa terlalu murah sehingga Anda meragukan kualitasnya?"),
              ("vw_cheap", "At what price would it be a bargain, a great buy for the money?",
               "Pada harga berapa ini terasa murah, pembelian yang sangat menguntungkan?"),
              ("vw_expensive", "At what price would it start to feel expensive, but you would still consider it?",
               "Pada harga berapa mulai terasa mahal, tetapi masih Anda pertimbangkan?"),
              ("vw_too_expensive", "At what price would it be so expensive that you would not consider it?",
               "Pada harga berapa terlalu mahal sehingga tidak akan Anda pertimbangkan?")]
        for code, en, idn in vw:
            qs.append(_q(code, "Price", "price", f"{en} ({cur})", f"{idn} ({cur})", scale={"currency": cur, "min": 0}))
        for p in price_ladder(target):
            qs.append(_q(f"gg_{price_suffix(p, cur)}", "Price", "single", f"Would you book it at {fmt_money(p, cur)}?",
                         f"Apakah Anda akan memesannya dengan harga {fmt_money(p, cur)}?", YES_NO))
    if parsed.tourism:
        qs += [
            _q("visits_before", "Travel behavior", "single", f"How many times have you visited {place} before?",
               f"Berapa kali Anda pernah mengunjungi {place_id} sebelumnya?",
               _opts([("First visit", "Kunjungan pertama"), ("1 time", "1 kali"), ("2-3 times", "2-3 kali"), ("4+ times", "4 kali atau lebih")])),
            _q("travel_party", "Travel behavior", "single", "Who are you traveling with?", "Anda bepergian dengan siapa?",
               _opts([("Solo", "Sendiri"), ("Couple", "Pasangan"), ("Family", "Keluarga"), ("Friends", "Teman"), ("Tour group", "Rombongan tur")])),
            _q("nights_planned", "Travel behavior", "numeric", "How many nights do you plan to stay?",
               "Berapa malam Anda berencana menginap?", scale={"min": 0, "max": 60}),
            _q("spend_per_day_idr", "Travel behavior", "price", "About how much do you spend per day during this trip (IDR)?",
               "Kira-kira berapa pengeluaran Anda per hari selama perjalanan ini (Rp)?", scale={"currency": "IDR", "min": 0}),
        ]
    qs += [
        _q("discovery_channel", "Travel behavior" if parsed.tourism else "Behavior", "single", f"How did you first hear about {place}?",
           f"Dari mana Anda pertama kali mengetahui {place_id}?",
           _opts([("Instagram", "Instagram"), ("TikTok", "TikTok"), ("Google Search", "Pencarian Google"),
                  ("Friends and family", "Teman dan keluarga"), ("Online travel agent", "Agen perjalanan online"), ("Travel agent", "Agen perjalanan")])),
        _q("recommend_0_10", "Behavior", "numeric", f"How likely are you to recommend {place} to a friend? (0 = not at all, 10 = extremely)",
           f"Seberapa besar kemungkinan Anda merekomendasikan {place_id} kepada teman? (0 = sama sekali tidak, 10 = sangat mungkin)",
           scale={"min": 0, "max": 10}),
    ]
    if parsed.tourism:
        qs.append(_q("origin", "About you", "single", "Where do you live?", "Di mana Anda tinggal?",
                     _opts([("Domestic", "Indonesia"), ("International", "Luar negeri")])))
        qs.append(_q("home_region", "About you", "single", "Which region or country do you live in?", "Di provinsi atau negara mana Anda tinggal?",
                     _opts([("North Sumatra", "Sumatera Utara"), ("Jakarta", "Jakarta"), ("West Java", "Jawa Barat"), ("Riau", "Riau"),
                            ("Other Indonesia", "Indonesia lainnya"), ("Malaysia", "Malaysia"), ("Singapore", "Singapura"),
                            ("Europe", "Eropa"), ("Australia", "Australia"), ("Other Asia", "Asia lainnya")])))
    qs += [
        _q("age_group", "About you", "single", "What is your age group?", "Berapa kelompok usia Anda?",
           _opts([("18-24", "18-24"), ("25-34", "25-34"), ("35-44", "35-44"), ("45-54", "45-54"), ("55+", "55+")])),
        _q("gender", "About you", "single", "What is your gender?", "Apa jenis kelamin Anda?",
           _opts([("Female", "Perempuan"), ("Male", "Laki-laki"), ("Prefer not to say", "Tidak ingin menyebutkan")])),
        _q("income_level", "About you", "single", "How would you describe your household income?",
           "Bagaimana Anda menggambarkan pendapatan rumah tangga Anda?",
           _opts([("Low", "Rendah"), ("Middle", "Menengah"), ("High", "Tinggi")])),
        _q("worth_it_comment", "Open question", "text", f"What would make {offer} worth the price for you?",
           "Apa yang akan membuat pengalaman ini sepadan dengan harganya bagi Anda?", required=False),
        _q("contact_email", "Contact (optional)", "text", "If you would like the results, leave your email (stored separately).",
           "Jika ingin menerima hasilnya, tuliskan email Anda (disimpan terpisah).", required=False),
    ]
    for i, q in enumerate(qs):
        q["position"] = i
    return {
        "title": f"Survey: {project.get('name') or offer}",
        "introduction": (f"Thank you for taking part. This survey asks about your views on {offer}. It takes about 8 minutes."),
        "consent_text": ("Participation is voluntary and anonymous. You may stop at any time. Answers are used only for research "
                         "and reported in aggregate. Partisipasi bersifat sukarela dan anonim; Anda dapat berhenti kapan saja."),
        "languages": ["en", "id"],
        "questions": qs,
        "interview_guide": [
            f"Tell me about the last time you chose a paid activity like {offer}. How did you decide?",
            "What would make this experience feel authentic to you? What would make it feel staged?",
            "How do you judge whether a price is fair for an experience like this?",
            "Where do you look for information and how do you prefer to book and pay?",
            "What almost stopped you from going, or would stop you?",
            "If you could redesign the first 15 minutes of the experience, what would happen?",
        ],
        "estimated_minutes": 8,
    }


# ----------------------------------------------------------------------------------------------
# Sampling and fieldwork
# ----------------------------------------------------------------------------------------------


def sampling_plan(parsed: ParsedQuestion, design: dict[str, Any], population_size: int | None = None) -> dict[str, Any]:
    base = sample_size_proportion(0.5, 0.05, 0.95, population_size)
    n_terms = max(len({h["iv"] for h in design["hypotheses"]}) + 3, 4)
    regression_min = 50 + 8 * n_terms
    recommended = int(math.ceil(max(base["n"], regression_min, 300) / 50.0) * 50)
    quotas = []
    if parsed.tourism:
        quotas = [{"variable": "origin", "group": "Domestic", "share": 0.65, "n": round(recommended * 0.65)},
                  {"variable": "origin", "group": "International", "share": 0.35, "n": round(recommended * 0.35)}]
    moe_table = [{"n": n, "margin_of_error": margin_of_error(n, 0.5, 0.95, population_size)} for n in (200, 300, 400, 600)]
    return {
        "target_population": (f"Adult {parsed.population_en} (18+) who visited or plan to visit within 12 months"
                              if parsed.tourism else f"Adult {parsed.population_en} in the target market"),
        "sampling_frame": (["On-site intercepts at arrival points (ferry ports, hotels, cultural villages)",
                            "Online link shared through tourism community groups and accommodation partners"]
                           if parsed.tourism else ["Customer lists and social media followers", "Online panel (if budget allows)"]),
        "method": "Quota sampling with quotas on key groups; non-probability, so report results as indicative of the sampled groups.",
        "sample_size": {"recommended": recommended, "for_5pct_margin": base["n"], "regression_minimum": regression_min,
                        "subgroup_minimum": 100, "formula": base["formula"]},
        "quotas": quotas,
        "margin_of_error_table": moe_table,
        "assumptions": ["Visitor mix of 65% domestic and 35% international is an assumption; replace it with official statistics."]
        if parsed.tourism else [],
    }


def fieldwork_plan(parsed: ParsedQuestion, sampling: dict[str, Any]) -> dict[str, Any]:
    return {
        "channels": (["Tablet-based intercepts using KoboToolbox or ODK in offline mode (export the XLSForm from MDOS)",
                      "Online survey link via WhatsApp and Instagram for recent visitors"] if parsed.tourism else
                     ["Online survey link (Google Forms, KoboToolbox or Qualtrics) using the XLSForm or questionnaire export"]),
        "timeline": [
            {"week": 1, "activity": "Translate and review wording with a native speaker; pilot with 20 respondents; fix issues"},
            {"week": 2, "activity": "Main fieldwork starts; daily upload; first data-quality check in MDOS"},
            {"week": 3, "activity": "Continue fieldwork; monitor quotas; replace low-quality responses"},
            {"week": 4, "activity": "Close fieldwork; final cleaning plan approved in MDOS; analysis"},
        ],
        "quality_control": [
            "Attention check item must equal 'Agree' (4)",
            "Flag completion times below one third of the median",
            "Flag straight-lining across Likert batteries",
            "Check Van Westendorp answers are in logical order",
            "Keep contact details in a separate, access-restricted file",
        ],
        "target_completes": sampling["sample_size"]["recommended"],
        "incentive": "Small token of appreciation (for example a local snack or a discount voucher); keep it the same for everyone.",
        "ethics": ["Informed consent before the first question", "No personal identifiers in the analysis file",
                   "Store raw data securely and delete contact details after results are shared"],
        "handoff": "Export the questionnaire as XLSForm (KoboToolbox, ODK, SurveyCTO) so variable names match on re-import.",
    }


def generate_all(project: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_question(project["business_question"], project.get("currency", "IDR"), project.get("industry", ""))
    frame = framing(parsed, project)
    design = research_design(parsed)
    survey = questionnaire(parsed, design, project)
    sampling = sampling_plan(parsed, design)
    field = fieldwork_plan(parsed, sampling)
    return {"parsed": parsed.__dict__, "framing": frame, "design": design, "questionnaire": survey,
            "sampling": sampling, "fieldwork": field}
