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

FORM_VIII_PREFIX = "ا1ت"
FORM_X_PREFIX = "است"
FORM_VII_PREFIX = "ان"


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

    text = unicodedata.normalize("NFC", text)

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
    نُبقي # كما هو حتى تتم محاولة الاسترداد البنيوي لاحقًا.
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
        result = result.replace(old, new)

    return result


def pattern_plain(pattern):
    return normalize_arabic(pattern or "")


# ============================================================
# 7. تحديد صيغة الفعل
# ============================================================

def detect_form(pattern):
    p = pattern_plain(pattern)

    if not p:
        return None

    if p.startswith("ا1ت"):
        return "افتعل"

    if p.startswith("است"):
        return "استفعل"

    if p.startswith("ان"):
        return "انفعل"

    if p.startswith("ا") and "ّ" in (pattern or ""):
        if "3" in (pattern or ""):
            return "افعلّ"

    if p.startswith("ا") and "2" in p and "3" in p:
        if p.startswith("ا1"):
            return "أفعل"

    if p.startswith("ت1"):
        if "ا" in p:
            return "تفاعل"
        return "تفعّل"

    if p.startswith("1"):
        return "فعل"

    return None


# ============================================================
# 8. الاسترداد البنيوي للجذر
# ============================================================

def recover_root_structurally(analysis, word):
    """
    CAMeL Tools قد يعطي أحيانًا جذرًا ناقصًا مثل:

        #.ق.#

    مع أن بقية التحليل يدل على بنية معروفة.

    هنا نحاول استرداد الجذر من:
    - الوزن
    - الكلمة
    - lemma
    - stem

    ولا نفعل ذلك إلا في أنماط بنيوية محددة.
    """

    raw_root = analysis.get("root", "")
    root = normalize_root(raw_root)

    if root_is_real(root):
        return root, "CAMeL Tools"

    word_clean = normalize_arabic(word)
    stem_clean = normalize_arabic(
        analysis.get("stem", "")
    )
    lex_clean = normalize_arabic(
        analysis.get("lex", "")
    )

    candidates = [
        word_clean,
        stem_clean,
        lex_clean
    ]

    pattern = str(
        analysis.get("pattern", "")
    )

    pattern_plain_value = pattern_plain(pattern)

    # --------------------------------------------------------
    # الحالة المهمة:
    # افتعل المثال الواوي
    #
    # اتقى = ا + و + ت + ق + ي
    # الجذر = و . ق . ي
    #
    # CAMeL قد يعيد أحيانًا:
    # # . ق . #
    # --------------------------------------------------------

    is_iftial_pattern = (
        pattern.startswith("ا1ت")
        or "فتعل" in pattern_plain_value
        or (
            word_clean.startswith("ات")
            and analysis.get("pos") == "verb"
        )
    )

    if is_iftial_pattern:

        for candidate in candidates:

            if not candidate:
                continue

            # مثال:
            # اتقى -> و ق ي
            if (
                candidate.startswith("ات")
                and len(candidate) >= 4
            ):
                middle = candidate[2]
                final = candidate[-1]

                # النهاية يجب أن تكون حرفًا صالحًا
                if (
                    middle
                    and final
                    and middle not in {"ا", "ت"}
                ):
                    candidate_root = [
                        "و",
                        middle,
                        final
                    ]

                    return (
                        candidate_root,
                        "استرداد بنيوي للافتعال"
                    )

            # حالة أخرى: اتصل / اتزن / اتسع
            if (
                candidate.startswith("ات")
                and len(candidate) == 5
            ):
                r2 = candidate[2]
                r3 = candidate[3]

                if r2 and r3:
                    return (
                        ["و", r2, r3],
                        "استرداد بنيوي للافتعال"
                    )

    # --------------------------------------------------------
    # حالة عامة آمنة نسبيًا:
    # إذا كان الجذر يحتوي # واحدًا فقط وكان التحليل
    # البنيوي واضحًا من الكلمة.
    # --------------------------------------------------------

    if root and len(root) == 3:

        # # . ع . ل
        if root[0] == "#" and root[1] != "#" and root[2] != "#":

            for candidate in candidates:
                if len(candidate) >= 3:
                    if (
                        candidate[1] == root[1]
                        and candidate[-1] == root[2]
                    ):
                        return (
                            [
                                candidate[0],
                                root[1],
                                root[2]
                            ],
                            "استرداد بنيوي محافظ"
                        )

        # ف . # . ل
        if root[1] == "#" and root[0] != "#" and root[2] != "#":

            for candidate in candidates:
                if len(candidate) >= 3:
                    if (
                        candidate[0] == root[0]
                        and candidate[-1] == root[2]
                    ):
                        return (
                            [
                                root[0],
                                candidate[1],
                                root[2]
                            ],
                            "استرداد بنيوي محافظ"
                        )

        # ف . ع . #
        if root[2] == "#" and root[0] != "#" and root[1] != "#":

            for candidate in candidates:
                if len(candidate) >= 3:
                    if candidate[0] == root[0]:
                        return (
                            [
                                root[0],
                                root[1],
                                candidate[-1]
                            ],
                            "استرداد بنيوي محافظ"
                        )

    return None, None


# ============================================================
# 9. تصنيف الفعل
# ============================================================

def classify_verb(root):

    if not root_is_real(root):
        return {
            "primary": "غير مصنف",
            "features": [],
            "description": (
                "لم يقدم التحليل الصرفي جذرًا ثلاثيًا "
                "صالحًا للحكم."
            )
        }

    r1, r2, r3 = root

    features = []

    if r1 in HAMZA:
        features.append("مهموز الفاء")

    if r2 in HAMZA:
        features.append("مهموز العين")

    if r3 in HAMZA:
        features.append("مهموز اللام")

    if r2 == r3:
        features.append("مضعف")

    if r1 in WEAK:
        features.append("مثال")

    if r2 in WEAK:
        features.append("أجوف")

    if r3 in WEAK:
        features.append("ناقص")

    if r1 in WEAK and r3 in WEAK:
        features.append("لفيف مفروق")

    if r2 in WEAK and r3 in WEAK:
        features.append("لفيف مقرون")

    if not features:
        return {
            "primary": "سالم",
            "features": ["سالم"],
            "description": (
                "جذر ثلاثي صحيح خالٍ من الهمز "
                "والتضعيف وحروف العلة."
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
    elif any("مهموز" in x for x in features):
        primary = "مهموز"
    else:
        primary = features[0]

    return {
        "primary": primary,
        "features": features,
        "description": "، ".join(features)
    }


# ============================================================
# 10. معلومات التحليل
# ============================================================

def get_analysis_value(analysis, key):
    value = analysis.get(key)

    if value is None:
        return ""

    return str(value)


def is_verb(analysis):
    return analysis.get("pos") in {
        "verb",
        "verb_pseudo"
    }


def analysis_score(analysis, original_word):

    score = 0

    if analysis.get("pos") == "verb":
        score += 100

    if analysis.get("pos") == "verb_pseudo":
        score += 40

    root = normalize_root(
        analysis.get("root", "")
    )

    if root_is_real(root):
        score += 35

    if analysis.get("pattern"):
        score += 20

    if analysis.get("lex"):
        score += 10

    if analysis.get("stem"):
        score += 10

    if analysis.get("diac"):
        score += 10

    if analysis.get("source") == "lex":
        score += 8

    stem = normalize_arabic(
        analysis.get("stem", "")
    )

    word = normalize_arabic(
        original_word
    )

    if stem and word and stem == word:
        score += 10

    return score


def choose_best_analysis(analyses, word):

    if not analyses:
        return None, []

    ranked = sorted(
        analyses,
        key=lambda a: analysis_score(a, word),
        reverse=True
    )

    verbs = [
        a for a in ranked
        if is_verb(a)
    ]

    if verbs:
        return verbs[0], verbs

    return ranked[0], ranked


# ============================================================
# 11. مطابقة الجذر مع بنية الكلمة
# ============================================================

def surface_letters(analysis, original_word):

    stem = analysis.get("stem")

    if stem:
        stem_clean = normalize_arabic(stem)

        if stem_clean:
            return stem_clean

    return normalize_arabic(
        original_word
    )


def has_letter_sequence(text, sequence):
    return sequence in text


def has_shadda_near(text, letter):

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


def diac_has_sequence(diac, pattern):
    if not diac:
        return False

    return pattern in diac


# ============================================================
# 12. تحديد افتعل
# ============================================================

def is_iftial(analysis, word=""):

    pattern = str(
        analysis.get("pattern", "")
    )

    pattern_plain_value = pattern_plain(
        pattern
    )

    if pattern.startswith("ا1ت"):
        return True

    if "فتعل" in pattern_plain_value:
        return True

    # استرداد بنيوي للأفعال مثل:
    # اتقى، اتصل، اتزن
    word_clean = normalize_arabic(word)

    if (
        analysis.get("pos") == "verb"
        and word_clean.startswith("ات")
        and len(word_clean) >= 4
    ):
        return True

    return False


# ============================================================
# 13. إبدال تاء الافتعال طاءً
# ============================================================

def rule_ibdal_taa_to_taa_mufakhkhama(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    if not is_iftial(analysis, word):
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

    expected_prefix = "ا" + r1 + "ط"

    if stem.startswith(expected_prefix):

        return {
            "type": "إبدال",
            "title": "إبدال تاء الافتعال طاءً",
            "badge": "badge-ibdal",
            "explanation": (
                f"الجذر ({root_string(root)}) جاء على "
                "صيغة الافتعال، وفاؤه من الحروف "
                "التي تقلب معها تاء الافتعال طاءً، "
                "فصارت التاء طاءً للمجانسة."
            ),
            "evidence": (
                f"الجذر = {root_string(root)}، "
                f"والوزن = "
                f"{display_pattern(analysis.get('pattern'))}، "
                f"والبنية السطحية تبدأ بـ({expected_prefix})."
            ),
            "original": (
                f"الصورة الاشتقاقية المجردة: "
                f"ا + {r1} + ت + {r2} + {r3}"
            ),
            "confidence": "عالية"
        }

    return None


# ============================================================
# 14. إبدال التاء دالًا
# ============================================================

def rule_ibdal_taa_to_dal(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    if not is_iftial(analysis, word):
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

    expected = "ا" + r1 + "د"

    if stem.startswith(expected):

        return {
            "type": "إبدال",
            "title": "إبدال تاء الافتعال دالًا",
            "badge": "badge-ibdal",
            "explanation": (
                f"وقعت تاء الافتعال بعد فاء الجذر ({r1})، "
                "وهي من الحروف التي تقلب معها تاء الافتعال "
                "دالًا للمجانسة."
            ),
            "evidence": (
                f"الجذر = {root_string(root)}، "
                f"والوزن = "
                f"{display_pattern(analysis.get('pattern'))}، "
                "والصورة السطحية تحقق البنية "
                "ا + الفاء + د."
            ),
            "original": (
                f"ا + {r1} + ت + {r2} + {r3}"
            ),
            "confidence": "عالية"
        }

    return None


# ============================================================
# 15. إبدال الواو تاءً في الافتعال
# ============================================================

def rule_ibdal_waw_in_iftial(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    if not is_iftial(analysis, word):
        return None

    r1, r2, r3 = root

    if r1 != "و":
        return None

    stem = surface_letters(
        analysis,
        word
    )

    diac = analysis.get(
        "diac",
        ""
    )

    if not stem.startswith("ات"):
        return None

    shadda = has_shadda_near(
        diac,
        "ت"
    )

    return {
        "type": "إبدال وإدغام",
        "title": "إبدال الواو تاءً ثم إدغامها في تاء الافتعال",
        "badge": "badge-ibdal",
        "explanation": (
            f"فاء الجذر هي الواو ({r1})، وجاء الفعل "
            "على صيغة الافتعال. تقلب الواو تاءً، "
            "فتجتمع مع تاء الافتعال، ثم يحصل الإدغام."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"الوزن = "
            f"{display_pattern(analysis.get('pattern'))}، "
            "والصورة السطحية تبدأ بـ(ات). "
            + (
                "كما أثبت CAMeL Tools الشدة على التاء."
                if shadda
                else
                "لم تتوافر الشدة في التحليل المشكول."
            )
        ),
        "original": (
            f"ا + و + ت + {r2} + {r3}"
        ),
        "confidence": (
            "عالية"
            if shadda
            else
            "متوسطة"
        )
    }


# ============================================================
# 16. الإعلال بالقلب في الأجوف
# ============================================================

def rule_heart_medial_weak_to_alif(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    r1, r2, r3 = root

    if r2 not in WEAK:
        return None

    if analysis.get("pos") != "verb":
        return None

    if analysis.get("asp") != "p":
        return None

    stem = surface_letters(
        analysis,
        word
    )

    expected = r1 + "ا" + r3

    if stem != expected:

        if not stem.startswith(
            r1 + "ا"
        ):
            return None

    return {
        "type": "إعلال بالقلب",
        "title": "إعلال بالقلب: قلب الواو أو الياء ألفًا",
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل أجوف؛ لأن عينه ({r2}) حرف علة. "
            "ظهرت العين في الصورة السطحية ألفًا، "
            "وذلك من أحكام إعلال العين بالقلب."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والفعل ماضٍ، وعينه = {r2}، "
            "والساق الصرفية تظهر الألف بعد الفاء."
        ),
        "original": (
            f"الصورة الأصلية التمثيلية: "
            f"{r1}َ{r2}َ{r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 17. الإعلال بالقلب في الناقص
# ============================================================

def rule_heart_final_weak(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    r1, r2, r3 = root

    if r3 not in WEAK:
        return None

    if analysis.get("pos") != "verb":
        return None

    if analysis.get("asp") != "p":
        return None

    original_normalized = normalize_arabic(
        word
    )

    ends_with_alif_maqsura = (
        word.strip().endswith("ى")
    )

    ends_with_alif = (
        original_normalized.endswith("ا")
    )

    if not (
        ends_with_alif_maqsura
        or ends_with_alif
    ):
        return None

    return {
        "type": "إعلال بالقلب",
        "title": "إعلال لام الفعل بالقلب",
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل ناقص؛ لأن لامه ({r3}) حرف علة. "
            "ظهرت اللام في الصورة الماضية على صورة "
            "ألف أو ألف مقصورة بحسب أصلها."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"واللام المعتلة = {r3}، والفعل ماضٍ، "
            f"والكلمة تنتهي بـ("
            f"{'ألف مقصورة' if ends_with_alif_maqsura else 'ألف'})."
        ),
        "original": (
            f"الجذر قبل التغيير: "
            f"{r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 18. الإعلال بالنقل
# ============================================================

def rule_transfer_vowel(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    r1, r2, r3 = root

    if r2 not in WEAK:
        return None

    if analysis.get("pos") != "verb":
        return None

    if analysis.get("asp") != "i":
        return None

    diac = analysis.get(
        "diac",
        ""
    )

    if not diac:
        return None

    if r2 == "و":

        regex = (
            re.escape(r1)
            + r"[َُِ]"
            + r"و"
        )

        matches = re.search(
            regex,
            diac
        )

        if not matches:
            return None

        vowel_name = "الضمة"

        if "ُو" not in diac:
            return None

    else:

        regex = (
            re.escape(r1)
            + r"[َُِ]"
            + r"ي"
        )

        matches = re.search(
            regex,
            diac
        )

        if not matches:
            return None

        vowel_name = "الكسرة"

        if "ِي" not in diac:
            return None

    return {
        "type": "إعلال بالنقل",
        "title": "إعلال بالنقل",
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل أجوف وعينه ({r2}) حرف علة، "
            f"وقد أثبت CAMeL Tools ظهور حرف العلة "
            f"في الصورة السطحية مع حركة {vowel_name} "
            "على الحرف السابق؛ وهذه قرينة على نقل الحركة."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والفعل مضارع، وعينه = {r2}، "
            f"والتحليل المشكول = {diac}."
        ),
        "original": (
            f"الصورة الصرفية التمثيلية قبل النقل: "
            f"يَ{r1}ْ{r2}ُ{r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 19. حذف عين الأجوف
# ============================================================

def rule_delete_medial_weak(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    r1, r2, r3 = root

    if r2 not in WEAK:
        return None

    asp = analysis.get("asp")
    mod = analysis.get("mod")

    command_or_jussive = (
        asp == "c"
        or mod == "j"
    )

    if not command_or_jussive:
        return None

    stem = surface_letters(
        analysis,
        word
    )

    core = r1 + r3

    direct = stem == core

    imperfect = (
        stem.endswith(core)
        and stem.startswith("ي")
    )

    if not (
        direct
        or imperfect
    ):
        return None

    return {
        "type": "إعلال بالحذف",
        "title": "إعلال بالحذف: حذف عين الفعل الأجوف",
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل أجوف وعينه ({r2}) حرف علة، "
            "وقد حُذفت عينه في صيغة الأمر أو "
            "في موضع الجزم بحسب البنية الصرفية."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والتحليل يثبت "
            f"{'الأمر' if asp == 'c' else 'الجزم'}، "
            f"والساق ({stem}) لا تحتوي على العين المعتلة ({r2})."
        ),
        "original": (
            f"الجذر: {r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 20. حذف فاء المثال الواوي
# ============================================================

def rule_delete_initial_waw(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    r1, r2, r3 = root

    if r1 != "و":
        return None

    if analysis.get("asp") != "i":
        return None

    pattern = pattern_plain(
        analysis.get("pattern", "")
    )

    stem = surface_letters(
        analysis,
        word
    )

    if "و" in stem:
        return None

    if pattern.startswith(
        (
            "ا",
            "است",
            "ان",
            "ت"
        )
    ):
        return None

    if not stem.startswith("ي"):
        return None

    if r2 not in stem or r3 not in stem:
        return None

    return {
        "type": "إعلال بالحذف",
        "title": "إعلال بالحذف: حذف فاء المثال الواوي",
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل مثال واوي؛ لأن فاءه ({r1}) واو. "
            "وحُذفت الواو في المضارع عند تحقق شروط الحذف."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والفعل مضارع، والساق الصرفية ({stem}) "
            "خالية من الواو الأولى."
        ),
        "original": (
            f"الأصل الجذري: {r1} + {r2} + {r3}"
        ),
        "confidence": "متوسطة"
    }


# ============================================================
# 21. حذف لام الناقص
# ============================================================

def rule_delete_final_weak(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    r1, r2, r3 = root

    if r3 not in WEAK:
        return None

    asp = analysis.get("asp")
    mod = analysis.get("mod")

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

    if r1 not in stem or r2 not in stem:
        return None

    return {
        "type": "إعلال بالحذف",
        "title": "إعلال بالحذف: حذف لام الفعل الناقص",
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل ناقص ولامه ({r3}) حرف علة، "
            "وقد حُذفت اللام في صيغة الأمر أو في حالة الجزم."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والتحليل يثبت "
            f"{'الأمر' if asp == 'c' else 'الجزم'}، "
            f"والساق ({stem}) لا تنتهي بالحرف المعتل ({r3})."
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
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    r1, r2, r3 = root

    diac = analysis.get(
        "diac",
        ""
    )

    if not diac:
        return None

    if r2 == r3:

        if not has_shadda_near(
            diac,
            r3
        ):
            return None

        return {
            "type": "إدغام",
            "title": "إدغام المثلين في الفعل المضعف",
            "badge": "badge-idgham",
            "explanation": (
                f"الجذر ({root_string(root)}) مضعف؛ "
                "لتماثل عينه ولامه. وقد أثبت التحليل "
                "المشكول الشدة."
            ),
            "evidence": (
                f"الجذر = {root_string(root)}، "
                f"والحرفان المتماثلان = ({r2}{r3})، "
                "والتحليل المشكول يحتوي على شدة."
            ),
            "original": (
                f"{r1} + {r2} + {r3}"
            ),
            "confidence": "عالية"
        }

    return None


# ============================================================
# 23. الإدغام الناتج عن إبدال تاء الافتعال بعد الدال
# ============================================================

def rule_idgham_after_dal(
    analysis,
    word
):

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
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

    if not has_shadda_near(
        diac,
        "د"
    ):
        return None

    return {
        "type": "إبدال وإدغام",
        "title": "إبدال تاء الافتعال دالًا ثم إدغامها",
        "badge": "badge-idgham",
        "explanation": (
            "وقعت تاء الافتعال بعد الدال، "
            "فقُلبت دالًا، ثم اجتمعت الدالان "
            "المتماثلان فأُدغمت إحداهما في الأخرى."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            "والوزن افتعل، وأثبت CAMeL Tools "
            "الشدة على الدال في الصورة المشكولة."
        ),
        "original": (
            f"ا + د + ت + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 24. قاعدة خاصة بالافتعال بعد الواو
# ============================================================

def rule_iftial_initial_waw_combined(
    analysis,
    word
):
    """
    هذه القاعدة مخصصة للحالات التي يكون فيها:

    الجذر:
        و + ع + ل

    والوزن:
        افتعل

    مثل:
        اتقى
        اتصل
        اتزن

    حيث تحذف الواو من الصورة الظاهرة بعد قلبها تاءً
    ثم إدغام التاءين.
    """

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    r1, r2, r3 = root

    if r1 != "و":
        return None

    if not is_iftial(
        analysis,
        word
    ):
        return None

    stem = surface_letters(
        analysis,
        word
    )

    if not stem.startswith("ات"):
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
        "title": "إبدال الواو تاءً ثم إدغام التاءين",
        "badge": "badge-ibdal",
        "explanation": (
            f"الجذر ({root_string(root)}) مثال واوي، "
            "وجاء على صيغة الافتعال. تقلب الواو تاءً، "
            "ثم تجتمع مع تاء الافتعال فتُدغمان، "
            "فتظهر الصورة على نحو (اتـ...)."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            "والصيغة = افتعل، "
            f"والساق الظاهرة = {stem}. "
            + (
                "والشدة على التاء تؤكد الإدغام."
                if shadda
                else
                "ولم تظهر الشدة في البيانات المشكولة."
            )
        ),
        "original": (
            f"ا + {r1} + ت + {r2} + {r3}"
        ),
        "confidence": (
            "عالية"
            if shadda
            else
            "متوسطة"
        )
    }


# ============================================================
# 25. تجميع القواعد
# ============================================================

RULES = [
    rule_ibdal_taa_to_taa_mufakhkhama,
    rule_ibdal_taa_to_dal,

    rule_iftial_initial_waw_combined,
    rule_ibdal_waw_in_iftial,

    rule_heart_medial_weak_to_alif,
    rule_heart_final_weak,

    rule_transfer_vowel,

    rule_delete_medial_weak,
    rule_delete_initial_waw,
    rule_delete_final_weak,

    rule_idgham_doubled,
    rule_idgham_after_dal,
]


# ============================================================
# 26. عدم وجود تغيير
# ============================================================

def build_no_change_result(
    analysis,
    classification
):

    return {
        "type": "لا تغيير مثبت",
        "title": "لا يظهر إعلال أو إبدال مثبت",
        "badge": "badge-neutral",
        "explanation": (
            "لم يثبت محرك القواعد، اعتمادًا على "
            "تحليل CAMeL Tools، قاعدةً من قواعد "
            "الإعلال أو الإبدال أو الإدغام "
            "يمكن إثباتها من البنية المتاحة."
        ),
        "evidence": (
            f"نوع الفعل: {classification['primary']}."
        ),
        "original": (
            "لا يوجد أصل افتراضي مولد آليًا."
        ),
        "confidence": "—"
    }


# ============================================================
# 27. محرك القواعد
# ============================================================

def run_rule_engine(
    analysis,
    word
):

    results = []

    for rule in RULES:

        try:
            result = rule(
                analysis,
                word
            )

            if result:
                results.append(result)

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
            unique.append(item)

    return unique


# ============================================================
# 28. التحليل النهائي
# ============================================================

def analyze_word(word):

    analyses = analyzer.analyze(
        word
    )

    if not analyses:
        return {
            "success": False,
            "message": (
                "لم يعثر CAMeL Tools على "
                "تحليل صرفي للكلمة."
            ),
            "analyses": []
        }

    best, verb_analyses = choose_best_analysis(
        analyses,
        word
    )

    if not best:
        return {
            "success": False,
            "message": "تعذر اختيار تحليل صرفي.",
            "analyses": analyses
        }

    if best.get("pos") not in {
        "verb",
        "verb_pseudo"
    }:
        return {
            "success": False,
            "message": (
                "الكلمة حُللت صرفيًا، لكن "
                "التحليل المختار ليس فعلًا."
            ),
            "analysis": best,
            "analyses": analyses
        }

    # --------------------------------------------------------
    # محاولة أخذ الجذر الأصلي
    # --------------------------------------------------------

    root = normalize_root(
        best.get("root", "")
    )

    root_source = "CAMeL Tools"

    # --------------------------------------------------------
    # إذا كان CAMeL أعاد جذرًا ناقصًا،
    # نحاول الاسترداد البنيوي.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # إذا فشل الاسترداد
    # --------------------------------------------------------

    if not root_is_real(root):

        return {
            "success": False,
            "message": (
                "تم العثور على تحليل، لكن تعذر "
                "استخراج جذر ثلاثي موثوق من التحليل."
            ),
            "analysis": best,
            "analyses": analyses
        }

    # --------------------------------------------------------
    # التصنيف
    # --------------------------------------------------------

    classification = classify_verb(
        root
    )

    # --------------------------------------------------------
    # تشغيل القواعد
    # --------------------------------------------------------

    changes = run_rule_engine(
        best,
        word
    )

    if not changes:

        changes = [
            build_no_change_result(
                best,
                classification
            )
        ]

    return {
        "success": True,
        "word": word,
        "analysis": best,
        "analyses": analyses,
        "verb_analyses": verb_analyses,
        "root": root,
        "root_source": root_source,
        "classification": classification,
        "pattern": best.get("pattern"),
        "form": detect_form(
            best.get("pattern")
        ),
        "changes": changes
    }


# ============================================================
# 29. واجهة البرنامج
# ============================================================

st.html("""
<div class="main-header">
    <h1>📖 محرك قواعد الإعلال والإبدال</h1>
    <p>
        تحليل صرفي قائم على CAMeL Tools مع محرك قواعد
        مستقل للتحقق من الإعلال والإبدال والإدغام
    </p>
</div>
""")


# ============================================================
# 30. الإدخال
# ============================================================

st.subheader("🔍 أدخل الفعل")

user_input = st.text_input(
    "اكتب الفعل:",
    value="اتقى",
    placeholder=(
        "مثل: قال، يقول، قل، وعد، يعد، عِد، "
        "رمى، اصطبر، ازدجر، ادّعى"
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

        if result.get("analysis"):

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

        analysis = result["analysis"]

        root = result["root"]

        classification = result[
            "classification"
        ]

        # ----------------------------------------------------
        # معلومات عامة
        # ----------------------------------------------------

        st.markdown("---")

        root_source = result.get(
            "root_source",
            "CAMeL Tools"
        )

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
                ⚖️ <b>الوزن في CAMeL:</b>
                <span class="custom-tag">
                    {display_pattern(analysis.get('pattern'))}
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
                "diac": analysis.get("diac"),
                "lex": analysis.get("lex"),
                "root": analysis.get("root"),
                "pattern": analysis.get("pattern"),
                "stem": analysis.get("stem"),
                "pos": analysis.get("pos"),
                "asp": analysis.get("asp"),
                "vox": analysis.get("vox"),
                "mod": analysis.get("mod"),
                "source": analysis.get("source"),
                "bw": analysis.get("bw"),
                "ud": analysis.get("ud")
            }

            st.json(
                useful_features
            )

        # ----------------------------------------------------
        # التحليلات الفعلية الأخرى
        # ----------------------------------------------------

        other = [
            a
            for a in result["verb_analyses"]
            if a is not analysis
        ]

        if other:

            with st.expander(
                f"🧩 تحليلات فعلية أخرى محتملة ({len(other)})"
            ):

                for idx, a in enumerate(
                    other,
                    start=1
                ):

                    st.html(f"""
                    <div class="analysis-box">

                        <b>التحليل {idx}</b><br>

                        الجذر:
                        <span class="custom-tag">
                            {a.get('root', 'غير محدد')}
                        </span>

                        الوزن:
                        <span class="custom-tag">
                            {display_pattern(a.get('pattern'))}
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
