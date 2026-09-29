"""Journey stage templates.

* ``tourism``: the living journey from the founder vision notes (Discover to Recommend).
* ``generic``: the ten stages from the specification (Awareness to Retention).

Acquisition stages form a funnel; outcome stages (share, return, recommend or advocacy, retention) are
rates applied to customers and feed word of mouth back into discovery.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

TOURISM = {
    "key": "tourism",
    "name": "Tourism experience (Graph1)",
    "entrants": 20_000,
    "stages": [
        {"key": "discover", "name": "Discover", "kind": "funnel", "conversion": 0.30,
         "description": "First exposure through social media, friends or travel content.",
         "keywords": ["tiktok", "instagram", "reel", "video", "saw", "found", "heard", "discovered", "viral", "influencer",
                      "postingan", "lihat", "tahu dari", "penasaran", "konten", "pertama kali tahu"],
         "touchpoints": [{"name": "TikTok and Instagram content", "channel": "Social media"},
                         {"name": "Friends and family stories", "channel": "Word of mouth"}]},
        {"key": "search", "name": "Search", "kind": "funnel", "conversion": 0.60,
         "description": "Looking for information: schedules, prices, access, reviews.",
         "keywords": ["information", "info", "website", "schedule", "opening hours", "search", "google", "find", "hard to find",
                      "informasi", "jadwal", "cari", "website resmi", "internet", "update"],
         "touchpoints": [{"name": "Google Search and Maps", "channel": "Search"}, {"name": "Official website", "channel": "Web"}]},
        {"key": "compare", "name": "Compare", "kind": "funnel", "conversion": 0.35,
         "description": "Comparing options, packages and prices.",
         "keywords": ["compare", "compared", "cheaper", "comparison", "than bali", "package", "packages", "options",
                      "dibanding", "bandingkan", "lebih murah", "paket", "pilihan", "terjangkau"],
         "touchpoints": [{"name": "Online travel agents", "channel": "OTA"}, {"name": "Review sites", "channel": "Reviews"}]},
        {"key": "book", "name": "Book", "kind": "funnel", "conversion": 0.40, "steps": 5,
         "description": "Reservation and payment.",
         "keywords": ["book", "booking", "reservation", "payment", "pay", "transfer", "ticket", "whatsapp", "confirm",
                      "confirmation", "online", "steps", "pesan", "pemesanan", "bayar", "pembayaran", "tiket", "konfirmasi", "qris"],
         "touchpoints": [{"name": "Booking page", "channel": "Web"}, {"name": "WhatsApp confirmation", "channel": "Messaging"}]},
        {"key": "arrive", "name": "Arrive", "kind": "funnel", "conversion": 0.95,
         "description": "Travel to the destination and check-in.",
         "keywords": ["road", "drive", "traffic", "ferry", "boat", "port", "parking", "arrived", "arrival", "journey", "hours",
                      "directions", "shuttle", "jalan", "macet", "kapal", "pelabuhan", "parkir", "perjalanan", "sampai", "jam"],
         "touchpoints": [{"name": "Road from Medan", "channel": "Transport"}, {"name": "Ferry to Samosir", "channel": "Transport"}]},
        {"key": "experience", "name": "Experience", "kind": "funnel", "conversion": 0.98,
         "description": "The core experience on site.",
         "keywords": ["show", "guide", "dance", "weaving", "ulos", "tortor", "culture", "cultural", "history", "village", "story",
                      "stories", "performance", "food", "boring", "explained", "pemandu", "tarian", "tenun", "budaya", "sejarah",
                      "desa", "cerita", "pertunjukan", "makanan", "membosankan", "menjelaskan", "berkesan"],
         "touchpoints": [{"name": "Welcome and first 15 minutes", "channel": "On site"},
                         {"name": "Cultural performance", "channel": "On site"}, {"name": "Guide storytelling", "channel": "On site"}]},
        {"key": "share", "name": "Share", "kind": "outcome", "rate": 0.35,
         "description": "Posting photos, videos and stories.",
         "keywords": ["photo", "photos", "pictures", "upload", "post", "likes", "spot", "foto", "spot foto", "cocok buat instagram",
                      "perfect for instagram"],
         "touchpoints": [{"name": "Photo spots", "channel": "On site"}, {"name": "Social media posts", "channel": "Social media"}]},
        {"key": "return", "name": "Return", "kind": "outcome", "rate": 0.15,
         "description": "Coming back for another visit.",
         "keywords": ["come back", "return", "again", "next year", "revisit", "longer stay", "balik lagi", "kembali", "tahun depan",
                      "menginap lebih lama"],
         "touchpoints": [{"name": "Follow-up message", "channel": "Messaging"}]},
        {"key": "recommend", "name": "Recommend", "kind": "outcome", "rate": 0.40,
         "description": "Recommending to friends and family.",
         "keywords": ["recommend", "must visit", "friends", "highly recommend", "rekomendasi", "wajib", "teman-teman", "sarankan",
                      "wajib dikunjungi"],
         "touchpoints": [{"name": "Reviews on Google Maps and TripAdvisor", "channel": "Reviews"}]},
    ],
    "word_of_mouth": {"views_per_share": 40, "discover_per_view": 0.02, "referrals_per_recommender": 0.5},
}

GENERIC = {
    "key": "generic",
    "name": "Generic customer journey (specification)",
    "entrants": 10_000,
    "stages": [
        {"key": "awareness", "name": "Awareness", "kind": "funnel", "conversion": 0.40, "keywords": ["saw", "heard", "ad", "advert", "iklan", "tahu"]},
        {"key": "discovery", "name": "Discovery", "kind": "funnel", "conversion": 0.60, "keywords": ["found", "website", "search", "info", "cari"]},
        {"key": "consideration", "name": "Consideration", "kind": "funnel", "conversion": 0.50, "keywords": ["consider", "review", "pertimbang"]},
        {"key": "comparison", "name": "Comparison", "kind": "funnel", "conversion": 0.50, "keywords": ["compare", "cheaper", "banding", "murah"]},
        {"key": "purchase", "name": "Purchase", "kind": "funnel", "conversion": 0.60, "steps": 4,
         "keywords": ["buy", "bought", "checkout", "payment", "pay", "order", "beli", "bayar", "pesan"]},
        {"key": "onboarding", "name": "Onboarding", "kind": "funnel", "conversion": 0.90, "keywords": ["setup", "start", "first time", "mulai"]},
        {"key": "usage", "name": "Usage", "kind": "funnel", "conversion": 0.95, "keywords": ["use", "using", "quality", "pakai", "kualitas"]},
        {"key": "support", "name": "Support", "kind": "outcome", "rate": 0.20, "keywords": ["support", "help", "complain", "cs", "bantuan", "keluhan"]},
        {"key": "advocacy", "name": "Advocacy", "kind": "outcome", "rate": 0.30, "keywords": ["recommend", "rekomendasi", "tell friends"]},
        {"key": "retention", "name": "Retention", "kind": "outcome", "rate": 0.40, "keywords": ["again", "repeat", "loyal", "lagi", "langganan"]},
    ],
    "word_of_mouth": {"views_per_share": 10, "discover_per_view": 0.02, "referrals_per_recommender": 0.3},
}

TEMPLATES = {"tourism": TOURISM, "generic": GENERIC}

# Theme dictionary for pain points: keyword -> theme label (bilingual).
PAIN_THEMES = [
    (("macet", "traffic", "congested", "rusak", "damaged", "road", "jalan", "potholes", "berlubang"), "Road access and traffic"),
    (("ferry", "kapal", "pelabuhan", "port", "boat", "menunggu dua jam", "waited"), "Ferry schedule and waiting"),
    (("error", "failed", "gagal", "payment page", "pembayaran online"), "Online payment errors"),
    (("whatsapp", "konfirmasi", "confirmation", "transfer manual", "bank transfer", "transfer"), "Manual transfer and confirmation"),
    (("steps", "hassle", "ribet", "membingungkan", "confusing", "no way to book", "had to call", "bayar di tempat"),
     "Complicated booking process"),
    (("information", "informasi", "info", "website", "jadwal", "schedule", "hard to find", "minim"), "Missing or outdated information"),
    (("boring", "membosankan", "nobody explained", "tidak ada yang menjelaskan", "first hour", "awalnya"), "Weak storytelling at the start"),
    (("mahal", "expensive", "overpriced", "price", "harga"), "Price concerns"),
    (("kotor", "dirty", "toilet", "sampah", "trash", "bau"), "Cleanliness"),
]


def template(key: str) -> dict[str, Any]:
    if key not in TEMPLATES:
        raise ValueError(f"Unknown journey template '{key}'. Use one of {', '.join(TEMPLATES)}.")
    return deepcopy(TEMPLATES[key])


def stages_for(key: str) -> list[dict[str, Any]]:
    """Stage definitions stored on a Journey (keywords stay in the template, not in the database)."""
    t = template(key)
    out = []
    for s in t["stages"]:
        stage = {k: v for k, v in s.items() if k not in ("keywords", "touchpoints")}
        stage.update({"emotion": None, "mentions": 0, "negative_share": None, "assumption_source": "template default",
                      "notes": ""})
        out.append(stage)
    return out
