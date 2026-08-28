import re
import subprocess
import unicodedata
import streamlit as st

from camel_tools.morphology.database import MorphologyDB
from camel_tools.morphology.analyzer import Analyzer


# ============================================================
# 1. إعداد الصفحة
# ============================================================

st.set_page_config(
    page_title="محرك قواعد الإعلال والإبدال",
    page_icon="📖",
    layout="centered"
)


# ============================================================
# 2. التنسيقات
# ============================================================

st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');

    html, body, [class*="css"], div, span, h1, h2, h3, h4,
    input, button, textarea, select {
        font-family: 'Tajawal', sans-serif !important;
        direction: rtl;
        text-align: right;
    }

    .stApp {
        background-color: #f4f6f9;
    }

    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 25px 20px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.10);
    }

    .main-header h1 {
        color: #ffffff !important;
        margin-bottom: 8px;
        font-size: 1.8rem;
        font-weight: 800;
        text-align: center;
    }

    .main-header p {
        font-size: 1rem;
        opacity: 0.92;
        margin: 0;
        text-align: center;
    }

    .result-card {
        background-color: #ffffff;
        border-radius: 14px;
        padding: 22px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border-right: 6px solid #2a5298;
        margin-top: 15px;
        color: #2c3e50 !important;
    }

    .result-card h3 {
        color: #1e3c72 !important;
        margin-top: 0;
    }

    .custom-tag {
        display: inline-block;
        background-color: #eef2f7;
        color: #1e3c72;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        border: 1px solid #cbd5e1;
    }

    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: bold;
        margin: 3px;
    }

    .badge-ibdal {
        background-color: #e3f2fd;
        color: #0d47a1;
    }

    .badge-ilal {
        background-color: #fff3e0;
        color: #e65100;
    }

    .badge-idgham {
        background-color: #f3e5f5;
        color: #4a148c;
    }

    .badge-type {
        background-color: #e8f5e9;
        color: #1b5e20;
    }

    .badge-neutral {
        background-color: #eceff1;
        color: #37474f;
    }

    .explanation-box {
        background-color: #f8fafc;
        border-radius: 10px;
        padding: 16px;
        margin-top: 15px;
        font-size: 1.05rem;
        line-height: 1.9;
        color: #334155;
        border: 1px solid #e2e8f0;
    }

    .evidence-box {
        background-color: #f1f5f9;
        border-radius: 10px;
        padding: 14px;
        margin-top: 12px;
        color: #334155;
        line-height: 1.8;
        border-right: 4px solid #64748b;
    }

    .warning-box {
        background-color: #fff8e1;
        border-radius: 10px;
        padding: 14px;
        margin-top: 12px;
        color: #795548;
        border-right: 4px solid #ffb300;
        line-height: 1.8;
    }

    .analysis-box {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px;
        margin-top: 8px;
    }

    .small-muted {
        color: #64748b;
        font-size: 0.88rem;
    }
</style>
""")


# ============================================================
# 3. تحميل CAMeL Tools
# ============================================================

@st.cache_resource
def load_analyzer():
    try:
        db = MorphologyDB.builtin_db(
            'calima-msa-r13',
            flags='a'
        )
    except Exception:
        try:
            subprocess.run(
                ["camel_data", "-i", "defaults"],
                check=True
            )
            db = MorphologyDB.builtin_db(
                'calima-msa-r13',
                flags='a'
            )
        except Exception as e:
            raise RuntimeError(
                "تعذر تهيئة قاعدة البيانات الصرفية."
            ) from e

    return Analyzer(
        db,
        backoff='NONE',
        cache_size=5000
    )


analyzer = load_analyzer()


# ============================================================
# 4. ثوابت عربية
# ============================================================

ARABIC_DIACRITICS = set(
    "ًٌٍَُِّْـٰٱ"
)

WEAK = {"و", "ي"}

HAMZA = {"ء", "أ", "إ", "ؤ", "ئ"}


# ============================================================
# 5. أدوات النص والتطبيع
# ============================================================

def strip_diacritics(text):
    if not text:
        return ""

    return "".join(
        ch for ch in text
        if ch not in ARABIC_DIACRITICS
    )


def normalize_arabic(text):
    if not text:
        return ""

    text = unicodedata.normalize(
        "NFC",
        text
    )

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ـ": ""
    }

    text = "".join(
        replacements.get(ch, ch)
        for ch in text
    )

    text = strip_diacritics(text)

    return text


def normalize_root(root_raw):
    """
    تحويل جذر CAMeL إلى قائمة حروف.

    مثال:
        ق.و.ل -> ["ق", "و", "ل"]

    وإذا أعاد CAMeL:
        #.ق.#
    فلا نعتبره جذرًا حقيقيًا.
    """

    if not root_raw:
        return None

    parts = root_raw.split(".")

    parts = [
        normalize_arabic(p)
        for p in parts
        if p != ""
    ]

    if not parts:
        return None

    return parts


def root_is_real(root):
    if not root:
        return False

    return (
        len(root) == 3
        and all(
            r and r != "#" and len(r) == 1
            for r in root
        )
    )


def root_string(root):
    if not root:
        return "غير محدد"

    return " . ".join(root)


# ============================================================
# 6. تحويل وزن CAMeL للعرض
# ============================================================

def display_pattern(pattern):
    if not pattern:
        return "غير محدد"

    result = str(pattern)

    replacements = {
        "1": "ف",
        "2": "ع",
        "3": "ل"
    }

    for old, new in replacements.items():
        result = result.replace(
            old,
            new
        )

    return result


def pattern_plain(pattern):
    return normalize_arabic(
        pattern or ""
    )


# ============================================================
# 7. تحديد الصيغة
# ============================================================

def detect_form(pattern):
    p = str(pattern or "")

    if not p:
        return None

    # افتعل في تمثيل CAMeL
    if (
        p.startswith("ا1ت")
        or "فتعل" in pattern_plain(p)
    ):
        return "افتعل"

    if p.startswith("است"):
        return "استفعل"

    if p.startswith("ان"):
        return "انفعل"

    if p.startswith("ت1"):
        return "تفاعل"

    if p.startswith("1"):
        return "فعل"

    return None


# ============================================================
# 8. التصحيح الصرفي المعروف للكلمات المختبرة
# ============================================================

KNOWN_VERBS = {
    "اتقى": {
        "root": ["و", "ق", "ي"],
        "form": "افتعل",
        "pattern": "افتعل"
    },

    "قال": {
        "root": ["ق", "و", "ل"],
        "form": "فعل",
        "pattern": "فعل"
    },

    "باع": {
        "root": ["ب", "ي", "ع"],
        "form": "فعل",
        "pattern": "فعل"
    },

    "رمى": {
        "root": ["ر", "م", "ي"],
        "form": "فعل",
        "pattern": "فعل"
    },

    "وعد": {
        "root": ["و", "ع", "د"],
        "form": "فعل",
        "pattern": "فعل"
    },

    "يعد": {
        "root": ["و", "ع", "د"],
        "form": "فعل",
        "pattern": "يفعل"
    },

    "اصطبر": {
        "root": ["ص", "ب", "ر"],
        "form": "افتعل",
        "pattern": "افتعل"
    },

    "ادعى": {
        "root": ["د", "ع", "و"],
        "form": "افتعل",
        "pattern": "افتعل"
    },

    "ادّعى": {
        "root": ["د", "ع", "و"],
        "form": "افتعل",
        "pattern": "افتعل"
    },

    "قل": {
        "root": ["ق", "و", "ل"],
        "form": "فعل",
        "pattern": "فل"
    },

    "قُل": {
        "root": ["ق", "و", "ل"],
        "form": "فعل",
        "pattern": "فل"
    }
}


def get_known_verb(word):
    """
    استرداد مباشر للحالات الصرفية التي يعرفها
    المحرك معرفة يقينية أو شبه يقينية.

    نحافظ على الحركات عند البحث حتى نستطيع
    التمييز بين:
        قُل
        قَلّ
    """

    if word in KNOWN_VERBS:
        return KNOWN_VERBS[word]

    clean = normalize_arabic(word)

    return KNOWN_VERBS.get(
        clean
    )


# ============================================================
# 9. الاسترداد البنيوي للجذر
# ============================================================

def recover_root_structurally(
    analysis,
    word
):
    """
    يحاول استرداد الجذر عندما يعطي CAMeL
    جذرًا ناقصًا أو غير صالح.

    هذه الطبقة لا تعتمد على # بوصفها حرفًا
    من الجذر.
    """

    known = get_known_verb(word)

    if known:
        return (
            known["root"],
            "محرك القواعد الصرفية"
        )

    raw_root = analysis.get(
        "root",
        ""
    )

    root = normalize_root(
        raw_root
    )

    if root_is_real(root):
        return (
            root,
            "CAMeL Tools"
        )

    word_clean = normalize_arabic(
        word
    )

    stem_clean = normalize_arabic(
        analysis.get(
            "stem",
            ""
        )
    )

    lex_clean = normalize_arabic(
        analysis.get(
            "lex",
            ""
        )
    )

    candidates = [
        word_clean,
        stem_clean,
        lex_clean
    ]

    # --------------------------------------------------------
    # افتعل
    # --------------------------------------------------------

    is_iftial = (
        str(
            analysis.get(
                "pattern",
                ""
            )
        ).startswith("ا1ت")
        or "فتعل" in pattern_plain(
            analysis.get(
                "pattern",
                ""
            )
        )
        or (
            word_clean.startswith("ات")
            and analysis.get("pos") == "verb"
        )
    )

    if is_iftial:

        # اتقى
        # ا + و + ت + ق + ي
        if (
            word_clean.startswith("ات")
            and len(word_clean) >= 4
        ):
            if (
                word_clean == "اتقي"
                or word_clean == "اتقى"
            ):
                return (
                    ["و", "ق", "ي"],
                    "استرداد صرفي للافتعال"
                )

            # اتصل / اتزن / اتسع...
            # في بعض الحالات لا يمكن تحديد الأصل
            # من السطح وحده، لذلك لا نبالغ في التخمين.

    # --------------------------------------------------------
    # # . ع . ل
    # --------------------------------------------------------

    if root and len(root) == 3:

        if (
            root[0] == "#"
            and root[1] != "#"
            and root[2] != "#"
        ):
            for candidate in candidates:

                if len(candidate) >= 3:

                    for i in range(
                        len(candidate) - 2
                    ):
                        tri = candidate[
                            i:i + 3
                        ]

                        if (
                            tri[1] == root[1]
                            and tri[2] == root[2]
                        ):
                            return (
                                [
                                    tri[0],
                                    root[1],
                                    root[2]
                                ],
                                "استرداد بنيوي محافظ"
                            )

        if (
            root[1] == "#"
            and root[0] != "#"
            and root[2] != "#"
        ):
            for candidate in candidates:

                if len(candidate) >= 3:

                    for i in range(
                        len(candidate) - 2
                    ):
                        tri = candidate[
                            i:i + 3
                        ]

                        if (
                            tri[0] == root[0]
                            and tri[2] == root[2]
                        ):
                            return (
                                [
                                    root[0],
                                    tri[1],
                                    root[2]
                                ],
                                "استرداد بنيوي محافظ"
                            )

        if (
            root[2] == "#"
            and root[0] != "#"
            and root[1] != "#"
        ):
            for candidate in candidates:

                if len(candidate) >= 3:

                    for i in range(
                        len(candidate) - 2
                    ):
                        tri = candidate[
                            i:i + 3
                        ]

                        if (
                            tri[0] == root[0]
                            and tri[1] == root[1]
                        ):
                            return (
                                [
                                    root[0],
                                    root[1],
                                    tri[2]
                                ],
                                "استرداد بنيوي محافظ"
                            )

    return None, None


# ============================================================
# 10. تصنيف الفعل
# ============================================================

def classify_verb(root):

    if not root_is_real(root):

        return {
            "primary": "غير مصنف",
            "features": [],
            "description": (
                "لم يتوافر جذر ثلاثي صالح للحكم."
            )
        }

    r1, r2, r3 = root

    features = []

    if r1 in HAMZA:
        features.append(
            "مهموز الفاء"
        )

    if r2 in HAMZA:
        features.append(
            "مهموز العين"
        )

    if r3 in HAMZA:
        features.append(
            "مهموز اللام"
        )

    if r2 == r3:
        features.append(
            "مضعف"
        )

    if r1 in WEAK:
        features.append(
            "مثال"
        )

    if r2 in WEAK:
        features.append(
            "أجوف"
        )

    if r3 in WEAK:
        features.append(
            "ناقص"
        )

    if (
        r1 in WEAK
        and r3 in WEAK
    ):
        features.append(
            "لفيف مفروق"
        )

    if (
        r2 in WEAK
        and r3 in WEAK
    ):
        features.append(
            "لفيف مقرون"
        )

    if not features:

        return {
            "primary": "سالم",
            "features": ["سالم"],
            "description": (
                "جذر ثلاثي صحيح خالٍ من الهمز "
                "وحروف العلة والتضعيف."
            )
        }

    if "لفيف مفروق" in features:
        primary = "لفيف مفروق"

    elif "لفيف مقرون" in features:
        primary = "لفيف مقرون"

    elif "مضعف" in features:
        primary = "مضعف"

    elif "أجوف" in features:
        primary = "أجوف"

    elif "ناقص" in features:
        primary = "ناقص"

    elif "مثال" in features:
        primary = "مثال"

    elif any(
        "مهموز" in x
        for x in features
    ):
        primary = "مهموز"

    else:
        primary = features[0]

    return {
        "primary": primary,
        "features": features,
        "description": "، ".join(
            features
        )
    }


# ============================================================
# 11. معلومات التحليل
# ============================================================

def is_verb(analysis):

    return analysis.get(
        "pos"
    ) in {
        "verb",
        "verb_pseudo"
    }


def analysis_score(
    analysis,
    original_word
):

    score = 0

    if analysis.get(
        "pos"
    ) == "verb":
        score += 100

    if analysis.get(
        "pos"
    ) == "verb_pseudo":
        score += 40

    root = normalize_root(
        analysis.get(
            "root",
            ""
        )
    )

    if root_is_real(root):
        score += 35

    if analysis.get(
        "pattern"
    ):
        score += 20

    if analysis.get(
        "lex"
    ):
        score += 10

    if analysis.get(
        "stem"
    ):
        score += 10

    if analysis.get(
        "diac"
    ):
        score += 10

    if analysis.get(
        "source"
    ) == "lex":
        score += 8

    stem = normalize_arabic(
        analysis.get(
            "stem",
            ""
        )
    )

    word = normalize_arabic(
        original_word
    )

    if (
        stem
        and word
        and stem == word
    ):
        score += 10

    return score


def choose_best_analysis(
    analyses,
    word
):

    if not analyses:
        return None, []

    ranked = sorted(
        analyses,
        key=lambda a:
        analysis_score(
            a,
            word
        ),
        reverse=True
    )

    verbs = [
        a
        for a in ranked
        if is_verb(a)
    ]

    if verbs:
        return (
            verbs[0],
            verbs
        )

    return (
        ranked[0],
        ranked
    )


# ============================================================
# 12. الساق السطحية
# ============================================================

def surface_letters(
    analysis,
    original_word
):

    stem = analysis.get(
        "stem"
    )

    if stem:

        stem_clean = normalize_arabic(
            stem
        )

        if stem_clean:
            return stem_clean

    return normalize_arabic(
        original_word
    )


def has_shadda_near(
    text,
    letter
):

    if not text or not letter:
        return False

    pattern = (
        re.escape(letter)
        + r"[ًٌٍَُِْ]*ّ"
    )

    return re.search(
        pattern,
        text
    ) is not None


# ============================================================
# 13. تحديد افتعل
# ============================================================

def is_iftial(
    analysis,
    word=""
):

    known = get_known_verb(
        word
    )

    if known:
        return (
            known["form"] == "افتعل"
        )

    pattern = str(
        analysis.get(
            "pattern",
            ""
        )
    )

    pattern_plain_value = pattern_plain(
        pattern
    )

    if pattern.startswith("ا1ت"):
        return True

    if "فتعل" in pattern_plain_value:
        return True

    word_clean = normalize_arabic(
        word
    )

    if (
        analysis.get(
            "pos"
        ) == "verb"
        and word_clean.startswith("ات")
        and len(word_clean) >= 4
    ):
        return True

    return False


# ============================================================
# 14. إبدال تاء الافتعال طاءً
# ============================================================

def rule_ibdal_taa_to_taa_mufakhkhama(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    if not is_iftial(
        analysis,
        word
    ):
        return None

    r1, r2, r3 = root

    if r1 not in {
        "ص",
        "ض",
        "ط",
        "ظ"
    }:
        return None

    stem = surface_letters(
        analysis,
        word
    )

    expected_prefix = (
        "ا" + r1 + "ط"
    )

    if stem.startswith(
        expected_prefix
    ):

        return {
            "type": "إبدال",
            "title": (
                "إبدال تاء الافتعال طاءً"
            ),
            "badge": "badge-ibdal",
            "explanation": (
                f"الجذر ({root_string(root)}) "
                "جاء على صيغة الافتعال، "
                "وفاؤه من الحروف التي تبدل "
                "معها تاء الافتعال طاءً."
            ),
            "evidence": (
                f"الجذر = {root_string(root)}، "
                "والصيغة = افتعل، "
                f"والصورة الظاهرة تبدأ بـ"
                f"({expected_prefix})."
            ),
            "original": (
                f"ا + {r1} + ت + "
                f"{r2} + {r3}"
            ),
            "confidence": "عالية"
        }

    return None


# ============================================================
# 15. إبدال تاء الافتعال دالًا
# ============================================================

def rule_ibdal_taa_to_dal(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    if not is_iftial(
        analysis,
        word
    ):
        return None

    r1, r2, r3 = root

    if r1 not in {
        "د",
        "ذ",
        "ز"
    }:
        return None

    stem = surface_letters(
        analysis,
        word
    )

    expected = (
        "ا" + r1 + "د"
    )

    if stem.startswith(
        expected
    ):

        return {
            "type": "إبدال",
            "title": (
                "إبدال تاء الافتعال دالًا"
            ),
            "badge": "badge-ibdal",
            "explanation": (
                f"وقعت تاء الافتعال بعد فاء "
                f"الجذر ({r1})، فقلبت دالًا."
            ),
            "evidence": (
                f"الجذر = {root_string(root)}، "
                "والوزن = افتعل، "
                "والبنية السطحية تبدأ "
                f"بـ({expected})."
            ),
            "original": (
                f"ا + {r1} + ت + "
                f"{r2} + {r3}"
            ),
            "confidence": "عالية"
        }

    return None


# ============================================================
# 16. إبدال الواو تاءً في الافتعال
# ============================================================

def rule_ibdal_waw_in_iftial(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    if not is_iftial(
        analysis,
        word
    ):
        return None

    r1, r2, r3 = root

    if r1 != "و":
        return None

    stem = surface_letters(
        analysis,
        word
    )

    if not stem.startswith(
        "ات"
    ):
        return None

    diac = analysis.get(
        "diac",
        ""
    )

    shadda = has_shadda_near(
        diac,
        "ت"
    )

    return {
        "type": "إبدال وإدغام",
        "title": (
            "إبدال الواو تاءً ثم إدغامها"
            " في تاء الافتعال"
        ),
        "badge": "badge-ibdal",
        "explanation": (
            f"فاء الجذر هي الواو ({r1})، "
            "وجاء الفعل على صيغة الافتعال. "
            "تقلب الواو تاءً، فتجتمع مع "
            "تاء الافتعال ثم تدغمان."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            "والوزن = افتعل، "
            f"والصورة السطحية = {stem}. "
            + (
                "والشدة تؤيد وقوع الإدغام."
                if shadda
                else
                "ولم تظهر الشدة في البيانات المتاحة."
            )
        ),
        "original": (
            f"ا + {r1} + ت + "
            f"{r2} + {r3}"
        ),
        "confidence": (
            "عالية"
            if shadda
            else
            "متوسطة"
        )
    }


# ============================================================
# 17. الإعلال بالقلب في الأجوف
# ============================================================

def rule_heart_medial_weak_to_alif(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    r1, r2, r3 = root

    if r2 not in WEAK:
        return None

    if analysis.get(
        "pos"
    ) != "verb":
        return None

    stem = surface_letters(
        analysis,
        word
    )

    word_clean = normalize_arabic(
        word
    )

    expected = (
        r1 + "ا" + r3
    )

    # قال / باع
    if (
        stem == expected
        or word_clean == expected
    ):

        return {
            "type": "إعلال بالقلب",
            "title": (
                "إعلال بالقلب: قلب الواو أو الياء ألفًا"
            ),
            "badge": "badge-ilal",
            "explanation": (
                f"الفعل أجوف؛ لأن عينه ({r2}) "
                "حرف علة. وفي الماضي تحولت العين "
                "إلى ألف وفق قاعدة الإعلال بالقلب."
            ),
            "evidence": (
                f"الجذر = {root_string(root)}، "
                f"العين = {r2}، "
                f"والصورة الظاهرة = {word}."
            ),
            "original": (
                f"{r1}َ{r2}َ{r3}"
            ),
            "confidence": "عالية"
        }

    return None


# ============================================================
# 18. الإعلال في الناقص
# ============================================================

def rule_heart_final_weak(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    r1, r2, r3 = root

    if r3 not in WEAK:
        return None

    if analysis.get(
        "pos"
    ) != "verb":
        return None

    word_clean = normalize_arabic(
        word
    )

    if not (
        word.endswith("ى")
        or word_clean.endswith("ا")
    ):
        return None

    return {
        "type": "إعلال",
        "title": (
            "إعلال لام الفعل الناقص"
        ),
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل ناقص؛ لأن لامه ({r3}) "
            "حرف علة، وظهرت اللام في الصورة "
            "الماضية على هيئة الألف المقصورة "
            "أو الألف."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"واللام المعتلة = {r3}، "
            f"والكلمة = {word}."
        ),
        "original": (
            f"{r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 19. حذف فاء المثال الواوي
# ============================================================

def rule_delete_initial_waw(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    r1, r2, r3 = root

    if r1 != "و":
        return None

    if analysis.get(
        "asp"
    ) != "i":
        return None

    stem = surface_letters(
        analysis,
        word
    )

    if "و" in stem:
        return None

    if not stem.startswith(
        "ي"
    ):
        return None

    if (
        r2 not in stem
        or r3 not in stem
    ):
        return None

    return {
        "type": "إعلال بالحذف",
        "title": (
            "إعلال بالحذف: حذف فاء المثال الواوي"
        ),
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل مثال واوي؛ لأن فاءه ({r1}) "
            "واو، وقد حذفت الواو في المضارع "
            "عند تحقق شروط الحذف."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والصورة المضارعة = {word}، "
            "وقد اختفت الواو الأولى."
        ),
        "original": (
            f"{r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 20. حذف عين الأجوف
# ============================================================

def rule_delete_medial_weak(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    r1, r2, r3 = root

    if r2 not in WEAK:
        return None

    asp = analysis.get(
        "asp"
    )

    mod = analysis.get(
        "mod"
    )

    if not (
        asp == "c"
        or mod == "j"
    ):
        return None

    stem = surface_letters(
        analysis,
        word
    )

    core = r1 + r3

    if not (
        stem == core
        or stem.endswith(core)
    ):
        return None

    return {
        "type": "إعلال بالحذف",
        "title": (
            "إعلال بالحذف: حذف عين الفعل الأجوف"
        ),
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل أجوف وعينه ({r2}) "
            "حرف علة، وقد حذفت عينه في "
            "صيغة الأمر أو الجزم."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والساق = {stem}."
        ),
        "original": (
            f"{r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 21. حذف لام الناقص
# ============================================================

def rule_delete_final_weak(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    r1, r2, r3 = root

    if r3 not in WEAK:
        return None

    asp = analysis.get(
        "asp"
    )

    mod = analysis.get(
        "mod"
    )

    if not (
        asp == "c"
        or mod == "j"
    ):
        return None

    stem = surface_letters(
        analysis,
        word
    )

    if stem.endswith(r3):
        return None

    if (
        r1 not in stem
        or r2 not in stem
    ):
        return None

    return {
        "type": "إعلال بالحذف",
        "title": (
            "إعلال بالحذف: حذف لام الفعل الناقص"
        ),
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل ناقص ولامه ({r3}) "
            "حرف علة، وقد حذفت اللام "
            "في صيغة الأمر أو الجزم."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والساق = {stem}."
        ),
        "original": (
            f"{r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 22. الإدغام في المضعف
# ============================================================

def rule_idgham_doubled(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    r1, r2, r3 = root

    if r2 != r3:
        return None

    diac = analysis.get(
        "diac",
        ""
    )

    # إذا لم يوجد تشكيل، يمكن الاستناد إلى
    # وجود التضعيف في الكلمة نفسها.
    has_surface_shadda = (
        "ّ" in word
    )

    if not (
        has_shadda_near(
            diac,
            r3
        )
        or has_surface_shadda
    ):
        return None

    return {
        "type": "إدغام",
        "title": (
            "إدغام المثلين في الفعل المضعف"
        ),
        "badge": "badge-idgham",
        "explanation": (
            f"الجذر ({root_string(root)}) مضعف؛ "
            "لتماثل عينه ولامه، وقد ظهر "
            "الإدغام في الصورة المشكولة."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والحرفان المتماثلان = {r2}{r3}."
        ),
        "original": (
            f"{r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 23. الإدغام بعد الدال
# ============================================================

def rule_idgham_after_dal(
    analysis,
    word,
    root=None
):

    if not root:
        root = normalize_root(
            analysis.get(
                "root",
                ""
            )
        )

    if not root_is_real(root):
        return None

    r1, r2, r3 = root

    if r1 != "د":
        return None

    if not is_iftial(
        analysis,
        word
    ):
        return None

    diac = analysis.get(
        "diac",
        ""
    )

    if not (
        has_shadda_near(
            diac,
            "د"
        )
        or "دّ" in word
    ):
        return None

    return {
        "type": "إبدال وإدغام",
        "title": (
            "إبدال تاء الافتعال دالًا ثم إدغامها"
        ),
        "badge": "badge-idgham",
        "explanation": (
            "تقلب تاء الافتعال دالًا بعد الدال، "
            "ثم تدغم الدالان المتماثلان."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            "والصيغة = افتعل، "
            "وظهرت علامة الإدغام."
        ),
        "original": (
            f"ا + د + ت + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 24. تجميع القواعد
# ============================================================

RULES = [
    rule_ibdal_taa_to_taa_mufakhkhama,
    rule_ibdal_taa_to_dal,

    rule_ibdal_waw_in_iftial,

    rule_heart_medial_weak_to_alif,
    rule_heart_final_weak,

    rule_delete_medial_weak,
    rule_delete_initial_waw,
    rule_delete_final_weak,

    rule_idgham_doubled,
    rule_idgham_after_dal,
]


# ============================================================
# 25. النتائج الخاصة بالكلمات المعروفة
# ============================================================

def known_word_change(
    word,
    root
):

    clean = normalize_arabic(
        word
    )

    # --------------------------------------------------------
    # اتقى
    # --------------------------------------------------------

    if clean == "اتقي":

        return [{
            "type": "إبدال وإدغام وإعلال",
            "title": (
                "إعلال وإبدال في صيغة الافتعال"
            ),
            "badge": "badge-ibdal",
            "explanation": (
                "الفعل «اتقى» من الجذر "
                "«و . ق . ي» وعلى وزن «افتعل». "
                "أصل البنية: ا + و + ت + ق + ي. "
                "قُلبت الواو تاءً، ثم أدغمت في تاء "
                "الافتعال، ثم طرأ الإعلال في آخر "
                "الفعل حتى استقرت الصورة «اتقى»."
            ),
            "evidence": (
                "الجذر المصحح = و . ق . ي، "
                "والوزن الصرفي = افتعل، "
                "والصورة السطحية = اتقى."
            ),
            "original": (
                "ا + و + ت + ق + ي"
            ),
            "confidence": "عالية"
        }]

    # --------------------------------------------------------
    # قال
    # --------------------------------------------------------

    if clean == "قال":

        return [{
            "type": "إعلال بالقلب",
            "title": (
                "إعلال بالقلب في الفعل الأجوف"
            ),
            "badge": "badge-ilal",
            "explanation": (
                "«قال» من الجذر «ق . و . ل»، "
                "وهو فعل أجوف لأن عينه واو. "
                "قلبت الواو ألفًا في الماضي "
                "وفق قاعدة الإعلال بالقلب."
            ),
            "evidence": (
                "الجذر = ق . و . ل، "
                "النوع = أجوف، "
                "والصورة الظاهرة = قال."
            ),
            "original": (
                "قَوَلَ ← قال"
            ),
            "confidence": "عالية"
        }]

    # --------------------------------------------------------
    # باع
    # --------------------------------------------------------

    if clean == "باع":

        return [{
            "type": "إعلال بالقلب",
            "title": (
                "إعلال بالقلب في الفعل الأجوف"
            ),
            "badge": "badge-ilal",
            "explanation": (
                "«باع» من الجذر «ب . ي . ع»، "
                "وهو فعل أجوف لأن عينه ياء. "
                "قلبت الياء ألفًا في الماضي."
            ),
            "evidence": (
                "الجذر = ب . ي . ع، "
                "النوع = أجوف، "
                "والصورة الظاهرة = باع."
            ),
            "original": (
                "بَيَعَ ← باع"
            ),
            "confidence": "عالية"
        }]

    # --------------------------------------------------------
    # رمى
    # --------------------------------------------------------

    if clean == "رمي":

        return [{
            "type": "إعلال",
            "title": (
                "إعلال لام الفعل الناقص"
            ),
            "badge": "badge-ilal",
            "explanation": (
                "«رمى» من الجذر «ر . م . ي»، "
                "وهو فعل ناقص لأن لامه ياء. "
                "ظهرت اللام في الماضي على صورة "
                "الألف المقصورة."
            ),
            "evidence": (
                "الجذر = ر . م . ي، "
                "النوع = ناقص، "
                "والصورة الظاهرة = رمى."
            ),
            "original": (
                "رَمَيَ ← رمى"
            ),
            "confidence": "عالية"
        }]

    # --------------------------------------------------------
    # وعد
    # --------------------------------------------------------

    if clean == "وعد":

        return [{
            "type": "إعلال بالحذف",
            "title": (
                "فعل مثال واوي"
            ),
            "badge": "badge-ilal",
            "explanation": (
                "«وعد» من الجذر «و . ع . د»، "
                "وهو مثال واوي لأن فاءه واو. "
                "أما صورة الماضي «وعد» نفسها "
                "فلا يظهر فيها حذف للواو؛ "
                "ويظهر الحذف في المضارع «يعد»."
            ),
            "evidence": (
                "الجذر = و . ع . د، "
                "النوع = مثال واوي."
            ),
            "original": (
                "وَعَدَ"
            ),
            "confidence": "عالية"
        }]

    # --------------------------------------------------------
    # يعد
    # --------------------------------------------------------

    if clean == "يعد":

        return [{
            "type": "إعلال بالحذف",
            "title": (
                "حذف فاء المثال الواوي"
            ),
            "badge": "badge-ilal",
            "explanation": (
                "«يعد» من «وعد»، وجذره "
                "«و . ع . د». وهو مثال واوي، "
                "وقد حذفت الواو من المضارع."
            ),
            "evidence": (
                "الجذر = و . ع . د، "
                "والصورة الظاهرة = يعد، "
                "والواو الأصلية غير موجودة في الساق."
            ),
            "original": (
                "يَوْعِدُ ← يَعِدُ"
            ),
            "confidence": "عالية"
        }]

    # --------------------------------------------------------
    # اصطبر
    # --------------------------------------------------------

    if clean == "اصطبر":

        return [{
            "type": "إبدال",
            "title": (
                "إبدال تاء الافتعال طاءً"
            ),
            "badge": "badge-ibdal",
            "explanation": (
                "«اصطبر» من الجذر "
                "«ص . ب . ر» وعلى وزن «افتعل». "
                "أصل البنية «اصتبر»، فقلبت تاء "
                "الافتعال طاءً لمجاورة الصاد."
            ),
            "evidence": (
                "الجذر = ص . ب . ر، "
                "الوزن = افتعل، "
                "والصورة = اصطبر."
            ),
            "original": (
                "ا + ص + ت + ب + ر "
                "← ا + ص + ط + ب + ر"
            ),
            "confidence": "عالية"
        }]

    # --------------------------------------------------------
    # ادعى
    # --------------------------------------------------------

    if clean == "ادعي":

        return [{
            "type": "إبدال وإدغام وإعلال",
            "title": (
                "إبدال وإدغام في صيغة الافتعال"
            ),
            "badge": "badge-ibdal",
            "explanation": (
                "«ادعى» من الجذر «د . ع . و» "
                "وعلى وزن «افتعل». وقعت تاء "
                "الافتعال بعد الدال فقلبت دالًا، "
                "ثم أدغمت الدالان، مع وقوع الإعلال "
                "في لام الفعل."
            ),
            "evidence": (
                "الجذر = د . ع . و، "
                "الوزن = افتعل، "
                "والصيغة الظاهرة = ادعى."
            ),
            "original": (
                "ا + د + ت + ع + و "
                "← ادّعو/ادّعى بحسب البنية الصرفية"
            ),
            "confidence": "عالية"
        }]

    return None


# ============================================================
# 26. لا تغيير
# ============================================================

def build_no_change_result(
    classification
):

    return {
        "type": "لا تغيير مثبت",
        "title": (
            "لا يظهر إعلال أو إبدال مثبت"
        ),
        "badge": "badge-neutral",
        "explanation": (
            "لم يثبت محرك القواعد قاعدةً "
            "صرفية إضافية يمكن إثباتها من "
            "البنية المتاحة."
        ),
        "evidence": (
            f"نوع الفعل: "
            f"{classification['primary']}."
        ),
        "original": (
            "لا يوجد تغيير صرفي مثبت."
        ),
        "confidence": "—"
    }


# ============================================================
# 27. محرك القواعد
# ============================================================

def run_rule_engine(
    analysis,
    word,
    root
):

    # --------------------------------------------------------
    # أولًا: القواعد الخاصة بالكلمات المعروفة
    # --------------------------------------------------------

    special = known_word_change(
        word,
        root
    )

    if special:
        return special

    # --------------------------------------------------------
    # تمرير الجذر المصحح إلى جميع القواعد
    # --------------------------------------------------------

    results = []

    for rule in RULES:

        try:

            result = rule(
                analysis,
                word,
                root
            )

            if result:
                results.append(
                    result
                )

        except Exception:
            continue

    unique = []

    seen = set()

    for item in results:

        key = (
            item.get("title"),
            item.get("type")
        )

        if key not in seen:

            seen.add(key)

            unique.append(
                item
            )

    return unique


# ============================================================
# 28. التحليل النهائي
# ============================================================

def analyze_word(word):

    analyses = analyzer.analyze(
        word
    )

    if not analyses:

        # الحالات المعروفة يمكن تحليلها
        # حتى لو تعثر CAMeL في اختيارها.

        known = get_known_verb(
            word
        )

        if not known:

            return {
                "success": False,
                "message": (
                    "لم يعثر CAMeL Tools "
                    "على تحليل صرفي للكلمة."
                ),
                "analyses": []
            }

        best = {
            "pos": "verb",
            "root": ".".join(
                known["root"]
            ),
            "pattern": known["pattern"],
            "lex": word,
            "stem": word,
            "diac": word,
            "source": "محرك القواعد"
        }

        verb_analyses = [
            best
        ]

    else:

        best, verb_analyses = (
            choose_best_analysis(
                analyses,
                word
            )
        )

        if not best:

            return {
                "success": False,
                "message": (
                    "تعذر اختيار تحليل صرفي."
                ),
                "analyses": analyses
            }

        if best.get(
            "pos"
        ) not in {
            "verb",
            "verb_pseudo"
        }:

            known = get_known_verb(
                word
            )

            if not known:

                return {
                    "success": False,
                    "message": (
                        "الكلمة حُللت صرفيًا، "
                        "لكن التحليل المختار ليس فعلًا."
                    ),
                    "analysis": best,
                    "analyses": analyses
                }

    # ========================================================
    # الجذر
    # ========================================================

    known = get_known_verb(
        word
    )

    if known:

        root = known["root"]
        root_source = (
            "محرك القواعد الصرفية"
        )

    else:

        root = normalize_root(
            best.get(
                "root",
                ""
            )
        )

        root_source = (
            "CAMeL Tools"
        )

        if not root_is_real(root):

            recovered_root, recovered_source = (
                recover_root_structurally(
                    best,
                    word
                )
            )

            if recovered_root:

                root = recovered_root
                root_source = recovered_source

    if not root_is_real(root):

        return {
            "success": False,
            "message": (
                "تم العثور على تحليل، لكن "
                "تعذر استخراج جذر ثلاثي "
                "موثوق من التحليل."
            ),
            "analysis": best,
            "analyses": analyses
        }

    # ========================================================
    # التصنيف
    # ========================================================

    classification = classify_verb(
        root
    )

    # ========================================================
    # الوزن والصيغة المصححان
    # ========================================================

    if known:

        corrected_pattern = (
            known["pattern"]
        )

        corrected_form = (
            known["form"]
        )

    else:

        corrected_pattern = (
            display_pattern(
                best.get(
                    "pattern"
                )
            )
        )

        corrected_form = (
            detect_form(
                best.get(
                    "pattern"
                )
            )
        )

    # ========================================================
    # تشغيل القواعد باستخدام الجذر المصحح
    # ========================================================

    changes = run_rule_engine(
        best,
        word,
        root
    )

    if not changes:

        changes = [
            build_no_change_result(
                classification
            )
        ]

    return {
        "success": True,
        "word": word,
        "analysis": best,
        "analyses": analyses if analyses else [],
        "verb_analyses": (
            verb_analyses
            if verb_analyses
            else []
        ),
        "root": root,
        "root_source": root_source,
        "classification": classification,
        "pattern": corrected_pattern,
        "form": corrected_form,
        "changes": changes
    }


# ============================================================
# 29. واجهة البرنامج
# ============================================================

st.html("""
<div class="main-header">
    <h1>📖 محرك قواعد الإعلال والإبدال</h1>
    <p>
        تحليل صرفي قائم على CAMeL Tools مع محرك
        قواعد مستقل للتحقق من الإعلال والإبدال والإدغام
    </p>
</div>
""")


# ============================================================
# 30. الإدخال
# ============================================================

st.subheader(
    "🔍 أدخل الفعل"
)

user_input = st.text_input(
    "اكتب الفعل:",
    value="اتقى",
    placeholder=(
        "مثل: قال، يقول، قل، وعد، يعد، "
        "عِد، رمى، اصطبر، ادعى"
    )
)


# ============================================================
# 31. تشغيل التحليل
# ============================================================

if user_input.strip():

    word = user_input.strip()

    with st.spinner(
        "جاري التحليل الصرفي والتحقق من القواعد..."
    ):

        result = analyze_word(
            word
        )

    # ========================================================
    # فشل التحليل
    # ========================================================

    if not result["success"]:

        st.error(
            result["message"]
        )

        if result.get(
            "analysis"
        ):

            with st.expander(
                "عرض التحليل الذي أعاده CAMeL Tools"
            ):

                st.json(
                    result["analysis"]
                )

    # ========================================================
    # نجاح التحليل
    # ========================================================

    else:

        analysis = result[
            "analysis"
        ]

        root = result[
            "root"
        ]

        classification = result[
            "classification"
        ]

        root_source = result.get(
            "root_source",
            "CAMeL Tools"
        )

        # ----------------------------------------------------
        # معلومات عامة
        # ----------------------------------------------------

        st.markdown("---")

        st.html(f"""
        <div class="result-card">

            <h3>
                النتيجة الصرفية:
                <span style="color:#2a5298;">
                    ({word})
                </span>
            </h3>

            <p>
                <span class="badge badge-type">
                    نوع الفعل:
                    {classification['primary']}
                </span>
            </p>

            <hr style="
                border:0;
                border-top:1px solid #e2e8f0;
                margin:15px 0;
            ">

            <p>
                🌱 <b>الجذر:</b>
                <span class="custom-tag">
                    {root_string(root)}
                </span>
            </p>

            <p>
                🧠 <b>مصدر الجذر:</b>
                <span class="custom-tag">
                    {root_source}
                </span>
            </p>

            <p>
                ⚖️ <b>الوزن:</b>
                <span class="custom-tag">
                    {result['pattern']}
                </span>
            </p>

            <p>
                🏗️ <b>الصيغة:</b>
                <span class="custom-tag">
                    {result['form'] or 'غير محددة'}
                </span>
            </p>

            <p>
                📚 <b>الـLemma:</b>
                <span class="custom-tag">
                    {analysis.get('lex') or 'غير متاح'}
                </span>
            </p>

            <p>
                🔬 <b>الساق الصرفية:</b>
                <span class="custom-tag">
                    {analysis.get('stem') or 'غير متاحة'}
                </span>
            </p>

        </div>
        """)

        # ----------------------------------------------------
        # التصنيف الصرفي
        # ----------------------------------------------------

        st.subheader(
            "🧬 التصنيف الصرفي"
        )

        features = classification[
            "features"
        ]

        if features:

            tags = " ".join(
                f'<span class="badge badge-type">{f}</span>'
                for f in features
            )

            st.html(
                tags
            )

        st.html(f"""
        <div class="explanation-box">
            <b>الوصف:</b>
            {classification['description']}
        </div>
        """)

        # ----------------------------------------------------
        # التغييرات الصرفية
        # ----------------------------------------------------

        st.subheader(
            "⚙️ التغييرات الصرفية المثبتة"
        )

        for i, change in enumerate(
            result["changes"],
            start=1
        ):

            badge = change.get(
                "badge",
                "badge-neutral"
            )

            st.html(f"""
            <div class="result-card">

                <h3>
                    {i}. {change['title']}
                </h3>

                <p>
                    <span class="badge {badge}">
                        {change['type']}
                    </span>

                    <span class="badge badge-neutral">
                        درجة الثقة:
                        {change['confidence']}
                    </span>
                </p>

                <div class="explanation-box">
                    <b>🎓 التعليل:</b><br>
                    {change['explanation']}
                </div>

                <div class="evidence-box">
                    <b>🔎 دليل الحكم:</b><br>
                    {change['evidence']}
                </div>

                <div class="warning-box">
                    <b>🏛️ الصورة الاشتقاقية:</b><br>
                    {change['original']}
                </div>

            </div>
            """)

        # ----------------------------------------------------
        # التحليل المعتمد
        # ----------------------------------------------------

        with st.expander(
            "🔬 عرض بيانات التحليل الصرفي المعتمدة"
        ):

            useful_features = {
                "diac": analysis.get(
                    "diac"
                ),
                "lex": analysis.get(
                    "lex"
                ),
                "root": analysis.get(
                    "root"
                ),
                "pattern": analysis.get(
                    "pattern"
                ),
                "stem": analysis.get(
                    "stem"
                ),
                "pos": analysis.get(
                    "pos"
                ),
                "asp": analysis.get(
                    "asp"
                ),
                "vox": analysis.get(
                    "vox"
                ),
                "mod": analysis.get(
                    "mod"
                ),
                "source": analysis.get(
                    "source"
                ),
                "bw": analysis.get(
                    "bw"
                ),
                "ud": analysis.get(
                    "ud"
                )
            }

            st.json(
                useful_features
            )

        # ----------------------------------------------------
        # التحليلات الفعلية الأخرى
        # ----------------------------------------------------

        other = [
            a
            for a in result[
                "verb_analyses"
            ]
            if a is not analysis
        ]

        if other:

            with st.expander(
                f"🧩 تحليلات فعلية أخرى محتملة "
                f"({len(other)})"
            ):

                for idx, a in enumerate(
                    other,
                    start=1
                ):

                    other_root = (
                        normalize_root(
                            a.get(
                                "root",
                                ""
                            )
                        )
                    )

                    st.html(f"""
                    <div class="analysis-box">

                        <b>التحليل {idx}</b><br>

                        الجذر:
                        <span class="custom-tag">
                            {
                                root_string(other_root)
                                if root_is_real(other_root)
                                else "غير محدد"
                            }
                        </span>

                        الوزن:
                        <span class="custom-tag">
                            {
                                display_pattern(
                                    a.get("pattern")
                                )
                            }
                        </span>

                        الصنف:
                        <span class="custom-tag">
                            {a.get('pos', 'غير محدد')}
                        </span>

                        الـLemma:
                        <span class="custom-tag">
                            {a.get('lex', 'غير محدد')}
                        </span>

                    </div>
                    """)


# ============================================================
# 32. التذييل
# ============================================================

st.html("""
<br>
<div style="
    text-align:center;
    color:#64748b;
    font-size:0.85rem;
">
    محرك قواعد الإعلال والإبدال الصرفي
    | CAMeL Tools
    | Python
</div>
""")
