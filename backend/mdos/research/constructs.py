"""Curated construct library (the explicit knowledge layer for research design).

Items are ADAPTED and paraphrased from the cited sources for a 5-point agreement scale, with English and
Bahasa Indonesia wording. Researchers should verify wording against the original publications before
academic use; Indonesian wording is machine-drafted and should be reviewed by a native speaker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

AGREE5_EN = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]
AGREE5_ID = ["Sangat tidak setuju", "Tidak setuju", "Netral", "Setuju", "Sangat setuju"]


@dataclass(frozen=True)
class Construct:
    key: str
    code: str
    name: str
    definition: str
    source: str
    items_en: list[str]
    items_id: list[str]
    tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


LIBRARY: dict[str, Construct] = {
    c.key: c
    for c in [
        Construct(
            "cultural_interest", "CI", "Cultural interest",
            "The degree to which a traveler seeks to learn about and engage with local culture.",
            "Adapted from McKercher and du Cros (2002) cultural tourist typology and Chen and Rahman (2018).",
            ["I am interested in learning about local culture when I travel.",
             "Experiencing traditional arts is an important reason for my trips.",
             "I look for opportunities to interact with local communities."],
            ["Saya tertarik mempelajari budaya lokal saat bepergian.",
             "Menikmati seni tradisional merupakan alasan penting perjalanan saya.",
             "Saya mencari kesempatan untuk berinteraksi dengan masyarakat setempat."],
            ["tourism", "culture"],
        ),
        Construct(
            "perceived_authenticity", "AU", "Perceived authenticity",
            "The extent to which an experience is judged genuine and true to local traditions.",
            "Adapted from Kolar and Zabkar (2010), object-based and existential authenticity.",
            ["This experience would feel genuine rather than staged.",
             "The experience reflects the real traditions of the local people.",
             "I would feel connected to local history and culture."],
            ["Pengalaman ini akan terasa asli, bukan dibuat-buat.",
             "Pengalaman ini mencerminkan tradisi asli masyarakat setempat.",
             "Saya akan merasa terhubung dengan sejarah dan budaya setempat."],
            ["tourism", "culture", "heritage"],
        ),
        Construct(
            "perceived_value", "PV", "Perceived value",
            "The customer's overall assessment of what is received relative to what is given (price, time, effort).",
            "Adapted from Sweeney and Soutar (2001, PERVAL) and Petrick (2002, SERV-PERVAL).",
            ["The experience would be good value for money.",
             "The price would be reasonable for what I receive.",
             "The experience would be worth the time and effort to get there."],
            ["Pengalaman ini sepadan dengan harganya.",
             "Harganya wajar untuk apa yang saya dapatkan.",
             "Pengalaman ini sepadan dengan waktu dan usaha untuk mencapainya."],
            ["general", "pricing"],
        ),
        Construct(
            "price_consciousness", "PC", "Price consciousness",
            "The degree to which a consumer focuses on paying low prices.",
            "Adapted from Lichtenstein, Ridgway and Netemeyer (1993).",
            ["I usually compare prices before I book activities.",
             "I am willing to make an extra effort to find lower prices.",
             "Saving money on activities is important to me."],
            ["Saya biasanya membandingkan harga sebelum memesan aktivitas.",
             "Saya bersedia berusaha lebih untuk mendapatkan harga yang lebih murah.",
             "Menghemat uang untuk aktivitas wisata penting bagi saya."],
            ["general", "pricing"],
        ),
        Construct(
            "purchase_intention", "PI", "Purchase intention",
            "The likelihood that a consumer plans to buy the offer.",
            "Adapted from Dodds, Monroe and Grewal (1991).",
            ["I would consider booking this experience.",
             "It is likely that I would book this experience on my next visit.",
             "I intend to book this experience when it becomes available."],
            ["Saya akan mempertimbangkan untuk memesan pengalaman ini.",
             "Kemungkinan besar saya akan memesan pengalaman ini pada kunjungan berikutnya.",
             "Saya berniat memesan pengalaman ini ketika sudah tersedia."],
            ["general", "concept"],
        ),
        Construct(
            "satisfaction", "SAT", "Customer satisfaction",
            "A post-consumption evaluation of whether the offer met or exceeded expectations.",
            "Adapted from Oliver (1980, 1997).",
            ["Overall, I am satisfied with this experience.",
             "The experience met my expectations.",
             "I am happy with my decision to choose this."],
            ["Secara keseluruhan, saya puas dengan pengalaman ini.",
             "Pengalaman ini sesuai dengan harapan saya.",
             "Saya senang dengan keputusan saya memilih ini."],
            ["general", "satisfaction"],
        ),
        Construct(
            "loyalty_wom", "LOY", "Loyalty and word of mouth",
            "Intentions to repurchase and to recommend the offer to others.",
            "Adapted from Zeithaml, Berry and Parasuraman (1996).",
            ["I would say positive things about this to other people.",
             "I would recommend it to friends and family.",
             "I would choose it again in the future."],
            ["Saya akan menceritakan hal-hal positif tentang ini kepada orang lain.",
             "Saya akan merekomendasikannya kepada teman dan keluarga.",
             "Saya akan memilihnya lagi di masa depan."],
            ["general", "loyalty"],
        ),
        Construct(
            "destination_image", "DI", "Destination image",
            "Cognitive and affective beliefs about a destination.",
            "Adapted from Echtner and Ritchie (1993) and Baloglu and McCleary (1999).",
            ["The destination offers beautiful natural scenery.",
             "The destination is safe and comfortable to visit.",
             "The destination has a pleasant atmosphere."],
            ["Destinasi ini menawarkan pemandangan alam yang indah.",
             "Destinasi ini aman dan nyaman untuk dikunjungi.",
             "Destinasi ini memiliki suasana yang menyenangkan."],
            ["tourism"],
        ),
        Construct(
            "service_quality", "SQ", "Service quality",
            "Customer perceptions of responsiveness, courtesy and reliability of service.",
            "Adapted (abbreviated) from Parasuraman, Zeithaml and Berry (1988, SERVQUAL).",
            ["Staff provide prompt service.",
             "Staff are friendly and courteous.",
             "Services are delivered as promised."],
            ["Petugas memberikan pelayanan yang cepat.",
             "Petugas ramah dan sopan.",
             "Layanan diberikan sesuai yang dijanjikan."],
            ["general", "satisfaction", "service"],
        ),
        Construct(
            "brand_awareness", "BA", "Brand awareness",
            "The ability of consumers to recognize or recall a brand.",
            "Adapted from Yoo and Donthu (2001).",
            ["I can recognize this brand among competing brands.",
             "I am aware of this brand.",
             "Some characteristics of this brand come to my mind quickly."],
            ["Saya dapat mengenali merek ini di antara merek pesaing.",
             "Saya mengetahui merek ini.",
             "Beberapa ciri merek ini cepat muncul di benak saya."],
            ["brand"],
        ),
        Construct(
            "trust", "TR", "Trust",
            "Confidence in the provider's reliability and integrity.",
            "Adapted from Morgan and Hunt (1994) and Chaudhuri and Holbrook (2001).",
            ["I trust this provider.",
             "This provider is reliable.",
             "This provider is honest with customers."],
            ["Saya percaya pada penyedia ini.",
             "Penyedia ini dapat diandalkan.",
             "Penyedia ini jujur kepada pelanggan."],
            ["general", "brand"],
        ),
        Construct(
            "booking_convenience", "BC", "Booking convenience",
            "Perceived time and effort required to find information, book and pay.",
            "Adapted from Berry, Seiders and Grewal (2002), service convenience.",
            ["Booking would be quick and easy.",
             "Paying for it would be convenient.",
             "Information about it is easy to find."],
            ["Pemesanan akan cepat dan mudah.",
             "Pembayarannya akan praktis.",
             "Informasi tentangnya mudah ditemukan."],
            ["tourism", "channel", "journey"],
        ),
        Construct(
            "social_media_influence", "SM", "Social media influence",
            "The degree to which social media content shapes discovery and choice.",
            "Adapted from Xiang and Gretzel (2010) and eWOM literature.",
            ["Social media content influences which activities I choose.",
             "I often discover new places through social media.",
             "Photos and videos from other travelers affect my decisions."],
            ["Konten media sosial memengaruhi aktivitas yang saya pilih.",
             "Saya sering menemukan tempat baru melalui media sosial.",
             "Foto dan video dari wisatawan lain memengaruhi keputusan saya."],
            ["channel", "tourism"],
        ),
        Construct(
            "perceived_risk", "PR", "Perceived risk",
            "Concern that the purchase may not deliver as expected or may waste money.",
            "Adapted from Dowling and Staelin (1994).",
            ["I worry the experience might not match its description.",
             "Paying in advance feels risky.",
             "I am concerned I might waste my money."],
            ["Saya khawatir pengalaman ini tidak sesuai deskripsinya.",
             "Membayar di muka terasa berisiko.",
             "Saya khawatir akan membuang uang."],
            ["general", "pricing", "journey"],
        ),
    ]
}


def search(query: str = "", tags: list[str] | None = None) -> list[dict]:
    q = query.strip().lower()
    tags = [t.lower() for t in (tags or [])]
    out = []
    for c in LIBRARY.values():
        if q and q not in c.name.lower() and q not in c.definition.lower() and q not in c.key:
            continue
        if tags and not set(tags) & set(c.tags):
            continue
        out.append(c.as_dict())
    return out
