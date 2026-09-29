"""Generate the SYNTHETIC Lake Toba demo datasets used by the demo project, tests and tutorials.

Nothing in these files is real data. The data-generating process is documented below so that the
analyses have known, sensible answers, and a few data-quality problems are planted on purpose so the
Data Quality agent has something to find.

Run:  python scripts/generate_sample_data.py
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260928
OUT = Path(__file__).resolve().parents[1] / "samples"
DEMO_DATA = Path(__file__).resolve().parents[1] / "backend" / "mdos" / "demo_data"
N_SURVEY = 320
N_REVIEWS = 240


def likert(latent: np.ndarray, rng: np.random.Generator, noise: float = 0.65) -> np.ndarray:
    raw = 3 + 0.9 * latent + rng.normal(0, noise, latent.shape)
    return np.clip(np.rint(raw), 1, 5).astype(int)


def round_price(x: np.ndarray, step: int = 5000) -> np.ndarray:
    return (np.rint(x / step) * step).astype(int)


COMMENTS_ID = {
    "story": ["Kalau ada cerita sejarah Batak yang dibawakan pemandu lokal, saya mau bayar segitu.",
              "Pertunjukan tortor dan cerita tentang ulos akan membuat pengalaman ini berharga.",
              "Yang penting pemandunya bisa bercerita dengan menarik, bukan hanya jalan-jalan."],
    "price": ["Harga 150 ribu agak mahal untuk kami sekeluarga, mungkin ada paket keluarga.",
              "Terlalu mahal kalau tidak termasuk makan dan transportasi.",
              "Kalau harganya 100 ribu saya pasti ikut."],
    "transport": ["Jalan ke sana macet dan rusak, harus ada antar jemput dari Parapat.",
                  "Jadwal kapal tidak jelas, perlu info yang lebih pasti."],
    "booking": ["Pesan online harus mudah, jangan transfer manual lalu konfirmasi lewat WhatsApp.",
                "Booking ribet sekali di tempat wisata lain, semoga yang ini bisa bayar pakai QRIS."],
    "food": ["Tambahkan makanan khas seperti arsik dan mie gomak, pasti lebih menarik.",
             "Makan siang khas Batak akan membuat harganya masuk akal."],
}
COMMENTS_EN = {
    "story": ["A local guide telling the stories behind the Batak houses would make it worth it.",
              "I would pay for an authentic cultural show and hands-on ulos weaving.",
              "Storytelling from the villagers themselves, not a scripted tour."],
    "price": ["The price is fine if transport from Parapat is included.",
              "Rp 150,000 is reasonable compared with Bali, but not for a short visit."],
    "transport": ["Getting there from Medan took too long; a shuttle would help a lot.",
                  "The ferry schedule was confusing and nobody could tell us the times."],
    "booking": ["Online booking in English with card payment, please.",
                "I want to book and pay online in two steps, not by WhatsApp."],
    "food": ["Include a traditional Batak lunch and I am in.",
             "Local food tasting would make it a full experience."],
}


def generate_survey(rng: np.random.Generator) -> pd.DataFrame:
    n = N_SURVEY
    origin = rng.choice(["Domestic", "International"], n, p=[0.65, 0.35])
    intl = (origin == "International").astype(float)
    age_group = rng.choice(["18-24", "25-34", "35-44", "45-54", "55+"], n, p=[0.24, 0.32, 0.2, 0.14, 0.10])
    genz = (age_group == "18-24").astype(float)
    gender = rng.choice(["Female", "Male"], n, p=[0.52, 0.48])
    income = np.where(intl == 1, rng.choice(["Middle", "High"], n, p=[0.45, 0.55]),
                      rng.choice(["Low", "Middle", "High"], n, p=[0.35, 0.45, 0.20]))
    low_income = (income == "Low").astype(float)
    high_income = (income == "High").astype(float)
    region = np.where(intl == 1, rng.choice(["Malaysia", "Singapore", "Europe", "Australia", "Other Asia"], n,
                                            p=[0.3, 0.2, 0.25, 0.1, 0.15]),
                      rng.choice(["North Sumatra", "Jakarta", "West Java", "Riau", "Other Indonesia"], n,
                                 p=[0.4, 0.25, 0.12, 0.1, 0.13]))
    party = rng.choice(["Solo", "Couple", "Family", "Friends", "Tour group"], n, p=[0.12, 0.24, 0.3, 0.26, 0.08])
    channel = np.empty(n, dtype=object)
    for i in range(n):
        if genz[i]:
            channel[i] = rng.choice(["TikTok", "Instagram", "Friends and family", "Google Search"], p=[0.45, 0.35, 0.1, 0.1])
        elif intl[i]:
            channel[i] = rng.choice(["Google Search", "Online travel agent", "Instagram", "Friends and family"], p=[0.35, 0.3, 0.2, 0.15])
        else:
            channel[i] = rng.choice(["Instagram", "Friends and family", "TikTok", "Google Search", "Travel agent"],
                                    p=[0.32, 0.28, 0.15, 0.15, 0.10])

    # Latent constructs (documented data-generating process).
    ci = rng.normal(0, 1, n) + 0.4 * intl
    pc = rng.normal(0, 1, n) + 0.5 * (1 - intl) + 0.6 * low_income + 0.3 * genz - 0.4 * high_income
    au = 0.5 * ci + rng.normal(0, 0.85, n)
    pv = 0.45 * au + 0.25 * ci - 0.30 * pc + rng.normal(0, 0.75, n)
    pi = 0.50 * pv + 0.20 * ci - 0.15 * pc + rng.normal(0, 0.7, n)

    df = pd.DataFrame({"respondent_id": [f"R{i + 1:04d}" for i in range(n)]})
    start = datetime(2026, 8, 3, 8, 0)
    df["submitted_at"] = [(start + timedelta(minutes=int(m))).isoformat() for m in np.sort(rng.integers(0, 60 * 24 * 21, n))]
    df["duration_sec"] = np.rint(rng.lognormal(np.log(560), 0.3, n)).astype(int)
    df["screen_visit"] = "Ya"
    df["origin"] = origin
    df["home_region"] = region
    df["age_group"] = age_group
    df["gender"] = gender
    df["income_level"] = income
    df["travel_party"] = party
    df["discovery_channel"] = channel
    for prefix, latent in (("ci", ci), ("au", au), ("pv", pv), ("pc", pc), ("pi", pi)):
        for j in range(1, 4):
            df[f"{prefix}{j}"] = likert(latent / max(latent.std(), 1e-9), rng)
    df.insert(df.columns.get_loc("pc1"), "attention_check", 4)

    # Willingness to pay (IDR): log-normal around the target price, driven by value, interest and price consciousness.
    wtp_max = 150_000 * np.exp(0.22 * pv + 0.12 * ci - 0.22 * pc + 0.30 * intl + 0.15 * high_income
                               - 0.10 * low_income + rng.normal(0, 0.22, n))
    # Stated answers carry optimism (hypothetical bias) of about 10%.
    stated = wtp_max * 1.10
    df["wtp_150k"] = np.where(stated * np.exp(rng.normal(0, 0.05, n)) >= 150_000, "Ya", "Tidak")
    for price in (100_000, 125_000, 175_000, 200_000):
        df[f"gg_{price // 1000}k"] = np.where(stated >= price, "Ya", "Tidak")
    df["vw_too_cheap"] = round_price(stated * rng.uniform(0.30, 0.45, n))
    df["vw_cheap"] = round_price(stated * rng.uniform(0.55, 0.75, n))
    df["vw_expensive"] = round_price(stated * rng.uniform(0.95, 1.15, n))
    df["vw_too_expensive"] = round_price(stated * rng.uniform(1.30, 1.60, n))
    df["visits_before"] = rng.choice(["First visit", "1 time", "2-3 times", "4+ times"], n, p=[0.45, 0.25, 0.2, 0.1])
    df["nights_planned"] = np.clip(np.rint(rng.gamma(2.2, 1.1, n) + intl), 1, 10).astype(int)
    daily = np.where(intl == 1, rng.lognormal(np.log(1_200_000), 0.35, n), rng.lognormal(np.log(520_000), 0.4, n))
    df["spend_per_day_idr"] = round_price(daily, 10_000)
    df["recommend_0_10"] = np.clip(np.rint(6.8 + 1.4 * pi / pi.std() + rng.normal(0, 1.2, n)), 0, 10).astype(int)

    comments = []
    for i in range(n):
        pools = COMMENTS_EN if intl[i] else COMMENTS_ID
        weights = np.array([0.35 + 0.2 * max(ci[i], 0), 0.2 + 0.25 * max(pc[i], 0), 0.15, 0.15, 0.1])
        topic = rng.choice(list(pools), p=weights / weights.sum())
        comments.append(rng.choice(pools[topic]) if rng.uniform() > 0.08 else "")
    df["worth_it_comment"] = comments
    df["contact_email"] = [f"respondent{i + 1:04d}@example.com" if rng.uniform() < 0.3 else "" for i in range(n)]

    # ---- Planted data-quality problems ----------------------------------------------------------
    likert_cols = [c for c in df.columns if c[:2] in ("ci", "au", "pv", "pc", "pi") and c[-1].isdigit()]
    straight = rng.choice(n, 8, replace=False)
    for r in straight:
        df.loc[r, likert_cols] = int(rng.choice([3, 4]))
    speeders = rng.choice(np.setdiff1d(np.arange(n), straight), 5, replace=False)
    df.loc[speeders, "duration_sec"] = rng.integers(60, 140, 5)
    attn = rng.choice(np.setdiff1d(np.arange(n), np.concatenate([straight, speeders])), 6, replace=False)
    df.loc[attn, "attention_check"] = rng.choice([1, 2, 5], 6)
    vw_bad = rng.choice(n, 7, replace=False)
    df.loc[vw_bad, "vw_too_cheap"] = df.loc[vw_bad, "vw_expensive"] + 20_000
    oor = rng.choice(n, 3, replace=False)
    df.loc[oor[0], "pv2"] = 6
    df.loc[oor[1], "ci3"] = 0
    df.loc[oor[2], "pi1"] = 7
    for col in ("au2", "pc3", "pi2"):
        miss = rng.choice(n, 5, replace=False)
        df[col] = df[col].astype("object")
        df.loc[miss, col] = None
    dup = df.sample(6, random_state=SEED)
    df = pd.concat([df, dup], ignore_index=True)
    return df


REVIEW_SENTENCES = {
    "discover": {
        "en": ["We first saw Lake Toba on TikTok and knew we had to go.", "Found this place through an Instagram reel."],
        "id": ["Pertama kali tahu dari video TikTok, langsung penasaran.", "Lihat postingan di Instagram, akhirnya ke sini juga."],
        "tone": 1,
    },
    "search": {
        "en": ["Information online about opening hours and schedules was hard to find.", "Very little information on the official website."],
        "id": ["Info jadwal di internet minim sekali, susah cari informasi.", "Website resminya kurang informasi dan jarang update."],
        "tone": -1,
    },
    "compare": {
        "en": ["Compared with Bali the prices are reasonable.", "We compared several tour packages and this one looked cheaper."],
        "id": ["Dibanding Bali harganya lebih terjangkau.", "Sudah bandingkan beberapa paket, yang ini lebih murah."],
        "tone": 1,
    },
    "book": {
        "en": ["Booking was a hassle: five steps, a bank transfer and a WhatsApp confirmation.",
               "The online payment page failed twice before we could book.", "There was no way to book online, we had to call."],
        "id": ["Booking ribet, harus transfer manual lalu konfirmasi lewat WhatsApp.",
               "Pemesanan online error terus, akhirnya bayar di tempat.", "Proses pesan tiket lama dan membingungkan."],
        "tone": -1,
    },
    "arrive": {
        "en": ["The road from Medan was congested and damaged, it took five hours.", "The ferry schedule was unclear and we waited two hours at the port."],
        "id": ["Perjalanan dari Medan macet dan jalannya rusak, lima jam baru sampai.", "Jadwal kapal tidak jelas, menunggu dua jam di pelabuhan."],
        "tone": -1,
    },
    "experience": {
        "en": ["The Batak cultural show and the ulos weaving were amazing.", "Our guide told wonderful stories about the history of the village.",
               "The first hour was boring, nobody explained what we were looking at."],
        "id": ["Pertunjukan tortor dan tenun ulos luar biasa, sangat berkesan.", "Pemandunya ramah dan menjelaskan sejarah dengan menarik.",
               "Awalnya membosankan, tidak ada yang menjelaskan apa-apa."],
        "tone": 1,
    },
    "share": {
        "en": ["Great spot for photos, our pictures got so many likes.", "The views are perfect for Instagram."],
        "id": ["Spot fotonya keren banget, cocok buat Instagram.", "Foto-foto di sini bagus sekali, langsung upload."],
        "tone": 1,
    },
    "return": {
        "en": ["We will definitely come back next year.", "Would return for a longer stay."],
        "id": ["Pasti balik lagi tahun depan.", "Ingin kembali lagi dan menginap lebih lama."],
        "tone": 1,
    },
    "recommend": {
        "en": ["Highly recommend this to friends visiting Sumatra.", "Must visit if you come to North Sumatra."],
        "id": ["Rekomendasi banget buat teman-teman.", "Wajib dikunjungi kalau ke Sumatera Utara."],
        "tone": 1,
    },
}


def generate_reviews(rng: np.random.Generator) -> pd.DataFrame:
    stages = list(REVIEW_SENTENCES)
    weights = np.array([0.07, 0.09, 0.06, 0.18, 0.16, 0.22, 0.08, 0.06, 0.08])
    rows = []
    start = datetime(2025, 10, 1)
    for i in range(N_REVIEWS):
        visitor = rng.choice(["domestic", "international"], p=[0.6, 0.4])
        lang = "en" if (visitor == "international" or rng.uniform() < 0.15) else "id"
        k = int(rng.choice([1, 2, 3], p=[0.35, 0.45, 0.2]))
        chosen = rng.choice(stages, k, replace=False, p=weights / weights.sum())
        sentences = [str(rng.choice(REVIEW_SENTENCES[s][lang])) for s in chosen]
        tone = np.mean([REVIEW_SENTENCES[s]["tone"] for s in chosen])
        if any("boring" in s or "membosankan" in s for s in sentences):
            tone -= 0.8
        rating = int(np.clip(np.rint(3.6 + 1.2 * tone + rng.normal(0, 0.6)), 1, 5))
        rows.append({
            "review_id": f"V{i + 1:04d}",
            "date": (start + timedelta(days=int(rng.integers(0, 330)))).date().isoformat(),
            "platform": rng.choice(["Google Maps", "TripAdvisor", "Instagram", "TikTok"], p=[0.45, 0.25, 0.18, 0.12]),
            "visitor_type": visitor,
            "language": lang,
            "rating": rating,
            "review_text": " ".join(sentences),
        })
    return pd.DataFrame(rows)


def main() -> None:
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    survey = generate_survey(rng)
    survey.to_csv(OUT / "lake_toba_survey.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    survey.head(80).to_excel(OUT / "lake_toba_survey_sample.xlsx", index=False)
    reviews = generate_reviews(rng)
    reviews.to_csv(OUT / "lake_toba_reviews.csv", index=False)
    # The desktop and cloud builds ship a copy inside the package for the one-click demo.
    DEMO_DATA.mkdir(parents=True, exist_ok=True)
    survey.to_csv(DEMO_DATA / "lake_toba_survey.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    reviews.to_csv(DEMO_DATA / "lake_toba_reviews.csv", index=False)
    print(f"survey: {survey.shape}, reviews: {reviews.shape} -> {OUT} and {DEMO_DATA}")


if __name__ == "__main__":
    main()
