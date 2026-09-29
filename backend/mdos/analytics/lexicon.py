"""Bilingual (English and Bahasa Indonesia) word lists for text analytics and sentiment.

Valences use a -3..+3 scale. The lists are curated for hospitality, tourism, retail and services
reviews. They are intentionally transparent: every score can be traced to the words that produced it.
"""

from __future__ import annotations

STOPWORDS_EN = set("""
a about above after again against all am an and any are aren't as at be because been before being below between both
but by can could did do does doing down during each few for from further had has have having he her here hers herself
him himself his how i if in into is it its itself just me more most my myself no nor not now of off on once only or
other our ours ourselves out over own same she should so some such than that the their theirs them themselves then
there these they this those through to too under until up very was we were what when where which while who whom why
will with would you your yours yourself yourselves also get got really one two us im ive dont didnt cant wont its
three four five six seven eight nine ten first second next last took take went go going come came make made
day days time times year years place way lot thing things even still much many every
""".split())

STOPWORDS_ID = set("""
yang dan di ke dari ini itu untuk dengan ada tidak saya kami kita juga sudah akan bisa karena atau pada adalah dalam
lebih sangat banget nya pun lah kah jadi agar supaya oleh sebagai tersebut seperti serta hanya bila jika kalau maka
namun tetapi tapi setelah sebelum saat ketika telah masih belum pernah sering selalu apa siapa mana bagaimana kenapa
mengapa dia mereka kamu anda aku gue gw sy tsb dll dsb yg dgn utk krn tdk sdh blm aja saja lagi kok sih deh dong
nih tuh ya iya oh ah eh wah buat bikin sama para per tiap setiap semua beberapa banyak sedikit sini situ sana
baru sampai akhir akhirnya terus lalu langsung harus hanya pertama kali kalinya satu dua tiga empat lima jam hari
tahun tempat mau ingin bisa jadi ada adanya punya sendiri begitu
""".split())

STOPWORDS = STOPWORDS_EN | STOPWORDS_ID

# Words that carry sentiment. Positive and negative, English and Indonesian.
POSITIVE = {
    # English
    "good": 1.9, "great": 3.1, "excellent": 3.2, "amazing": 3.0, "awesome": 3.0, "wonderful": 3.0, "beautiful": 2.8,
    "stunning": 3.0, "breathtaking": 3.2, "lovely": 2.6, "nice": 1.8, "friendly": 2.2, "helpful": 2.0, "clean": 1.9,
    "comfortable": 2.0, "cozy": 2.0, "peaceful": 2.1, "relaxing": 2.1, "fun": 2.2, "enjoyable": 2.3, "enjoyed": 2.2,
    "enjoy": 2.0, "love": 3.0, "loved": 2.9, "loving": 2.5, "perfect": 3.0, "fantastic": 3.1, "memorable": 2.5,
    "authentic": 2.2, "unique": 1.8, "interesting": 1.7, "informative": 1.8, "knowledgeable": 2.0, "worth": 1.8,
    "worthwhile": 2.1, "recommend": 2.2, "recommended": 2.2, "affordable": 1.6, "reasonable": 1.3, "fair": 1.1,
    "safe": 1.6, "easy": 1.6, "smooth": 1.7, "fast": 1.3, "quick": 1.3, "delicious": 2.8, "tasty": 2.3, "fresh": 1.6,
    "welcoming": 2.2, "warm": 1.4, "hospitable": 2.3, "impressive": 2.4, "impressed": 2.3, "happy": 2.4,
    "satisfied": 2.2, "satisfying": 2.1, "pleasant": 2.0, "spectacular": 3.0, "magical": 2.9, "charming": 2.3,
    "best": 3.0, "better": 1.5, "well": 1.2, "organized": 1.5, "professional": 1.8, "punctual": 1.6, "polite": 1.8,
    "gorgeous": 3.0, "fascinating": 2.6, "inspiring": 2.5, "cool": 1.3,
    # Indonesian
    "bagus": 2.0, "baik": 1.7, "indah": 2.8, "cantik": 2.5, "keren": 2.4, "mantap": 2.6, "mantul": 2.6,
    "hebat": 2.6, "menakjubkan": 3.0, "memukau": 3.0, "takjub": 2.8, "mempesona": 3.0, "memesona": 3.0,
    "ramah": 2.3, "sopan": 1.9, "bersih": 2.0, "rapi": 1.6, "nyaman": 2.2, "sejuk": 1.9, "asri": 2.2, "tenang": 1.8,
    "damai": 2.0, "seru": 2.4, "asyik": 2.3, "asik": 2.3, "menyenangkan": 2.5, "senang": 2.3, "suka": 1.9,
    "puas": 2.4, "memuaskan": 2.5, "rekomendasi": 2.1, "recomended": 2.0, "rekomen": 2.0,
    "terbaik": 3.0, "sempurna": 3.0, "enak": 2.3, "lezat": 2.8, "segar": 1.8, "murah": 1.3, "terjangkau": 1.8,
    "aman": 1.8, "mudah": 1.7, "lancar": 1.8, "cepat": 1.4, "informatif": 1.9, "menarik": 1.9, "unik": 1.9,
    "otentik": 2.2, "autentik": 2.2, "berkesan": 2.5, "istimewa": 2.6, "spesial": 2.2, "juara": 2.8,
    "profesional": 1.9, "tertib": 1.6, "terawat": 1.8, "strategis": 1.3, "megah": 2.2, "eksotis": 2.3, "sip": 1.8,
    "membantu": 1.9, "cinta": 2.8, "betah": 2.4, "lengkap": 1.5, "luas": 1.2, "terkesan": 2.0,
}

NEGATIVE = {
    # English
    "bad": -2.5, "terrible": -3.1, "awful": -3.1, "horrible": -3.1, "poor": -2.1, "dirty": -2.3, "filthy": -2.9,
    "smelly": -2.2, "rude": -2.6, "unfriendly": -2.2, "expensive": -1.6, "overpriced": -2.5, "pricey": -1.4,
    "costly": -1.5, "boring": -2.0, "crowded": -1.5, "noisy": -1.6, "slow": -1.5, "late": -1.4, "delay": -1.6,
    "delayed": -1.7, "cancelled": -1.9, "canceled": -1.9, "broken": -2.0, "unsafe": -2.4, "dangerous": -2.5,
    "disappointing": -2.4, "disappointed": -2.4, "disappointment": -2.4, "worst": -3.2, "waste": -2.4, "scam": -3.0,
    "ripoff": -3.0, "confusing": -1.8, "complicated": -1.6, "difficult": -1.5, "hard": -1.0, "far": -0.6,
    "tired": -1.2, "tiring": -1.4, "uncomfortable": -2.0, "trash": -2.2, "garbage": -2.2,
    "litter": -1.8, "queue": -1.0, "waiting": -1.1, "wait": -0.9, "lost": -1.2, "unclear": -1.5, "lack": -1.3,
    "lacking": -1.5, "missing": -1.3, "hassle": -1.8, "problem": -1.7, "problems": -1.7, "issue": -1.2,
    "issues": -1.2, "worse": -2.1, "mediocre": -1.4, "meh": -1.0, "touristy": -1.1, "hate": -3.0, "annoying": -2.0,
    "unprofessional": -2.2, "overcrowded": -2.0, "potholes": -1.8, "bumpy": -1.3, "sad": -1.8, "angry": -2.4,
    "unhelpful": -2.0, "fake": -2.2, "commercial": -0.8, "neglected": -2.0, "damaged": -2.0,
    # Indonesian
    "buruk": -2.6, "jelek": -2.4, "parah": -2.5, "kotor": -2.4, "jorok": -2.8, "bau": -2.2, "kumuh": -2.4,
    "kasar": -2.4, "judes": -2.3, "jutek": -2.3, "mahal": -1.7, "kemahalan": -2.3, "membosankan": -2.1,
    "bosan": -1.8, "sesak": -1.6, "berisik": -1.6, "bising": -1.6, "lambat": -1.6, "lelet": -1.8,
    "lama": -0.6, "telat": -1.6, "terlambat": -1.7, "macet": -1.9, "rusak": -2.1, "berlubang": -1.9,
    "licin": -1.2, "bahaya": -2.3, "berbahaya": -2.5, "kecewa": -2.5, "mengecewakan": -2.6, "terburuk": -3.2,
    "sampah": -2.2, "pungli": -2.9, "calo": -2.3, "penipuan": -3.0, "tipu": -2.8, "menipu": -2.9, "ribet": -1.9,
    "rumit": -1.7, "susah": -1.6, "sulit": -1.6, "jauh": -0.7, "capek": -1.3, "capai": -0.6, "melelahkan": -1.6,
    "antri": -1.1, "antre": -1.1, "antrian": -1.1, "antrean": -1.1, "nunggu": -0.9, "menunggu": -0.9,
    "tersesat": -1.5, "bingung": -1.5, "membingungkan": -1.9, "kurang": -1.0, "minim": -1.4, "masalah": -1.7,
    "kacau": -2.2, "gersang": -1.4, "terbengkalai": -2.1, "mengganggu": -1.9, "kesal": -2.1,
    "marah": -2.4, "sedih": -1.8, "benci": -3.0, "rugi": -2.2, "mubazir": -1.8, "palsu": -2.2, "komersil": -0.8,
    "overprice": -2.4, "kemalingan": -2.8, "kecopetan": -2.8, "gelap": -0.7, "curam": -0.8, "terpencil": -0.5,
}

# Multi-word expressions checked before single tokens.
PHRASES = {
    "luar biasa": 3.0, "worth it": 2.2, "must visit": 2.6, "must see": 2.6, "highly recommend": 3.0,
    "highly recommended": 3.0, "sangat direkomendasikan": 3.0, "wajib dikunjungi": 2.7, "wajib datang": 2.4,
    "tidak rugi": 2.0, "gak rugi": 2.0, "nggak rugi": 2.0, "biasa saja": -0.6, "biasa aja": -0.6,
    "waste of money": -3.0, "waste of time": -2.8, "rip off": -3.0, "buang uang": -2.8, "buang waktu": -2.5,
    "tidak sesuai": -2.0, "tidak worth": -2.0, "not worth": -2.0, "kurang terawat": -2.0, "never again": -2.8,
    "tidak akan kembali": -2.6, "gak lagi": -1.8, "bikin kecewa": -2.6, "kurang informasi": -1.6,
}

NEGATORS = {
    "not", "no", "never", "none", "nothing", "without", "cannot", "cant", "dont", "didnt", "doesnt", "isnt", "wasnt",
    "arent", "werent", "wont", "hardly", "tidak", "tak", "bukan", "belum", "jangan", "nggak", "gak", "ga", "enggak",
    "engga", "ngga", "tdk", "blm", "kagak",
}

INTENSIFIERS = {
    "very": 1.3, "really": 1.3, "so": 1.2, "extremely": 1.5, "super": 1.4, "incredibly": 1.5, "absolutely": 1.4,
    "totally": 1.3, "truly": 1.2, "quite": 1.1, "too": 1.2, "sangat": 1.4, "amat": 1.3, "sungguh": 1.3,
    "benar-benar": 1.4, "terlalu": 1.3, "paling": 1.4,
}

# Indonesian intensifiers that follow the word they intensify ("bagus banget", "indah sekali").
POST_INTENSIFIERS = {"banget": 1.4, "sekali": 1.3, "bgt": 1.4, "pol": 1.3, "abis": 1.3}

CONTRAST = {"but", "however", "although", "tapi", "tetapi", "namun", "meskipun", "walaupun", "sayangnya"}
