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

st.markdown("""
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
""", unsafe_allow_html=True)


# ============================================================
# 3. تحميل CAMeL Tools
# ============================================================

@st.cache_resource
def load_analyzer():

    try:
        db = MorphologyDB.builtin_db(
            "calima-msa-r13",
            flags="a"
        )

    except Exception:

        try:
            subprocess.run(
                ["camel_data", "-i", "defaults"],
                check=True
            )

            db = MorphologyDB.builtin_db(
                "calima-msa-r13",
                flags="a"
            )

        except Exception as e:

            raise RuntimeError(
                "تعذر تهيئة قاعدة البيانات الصرفية."
            ) from e

    return Analyzer(
        db,
        backoff="NONE",
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

HAMZA = {
    "ء",
    "أ",
    "إ",
    "ؤ",
    "ئ"
}


# ============================================================
# 5. كلمات معروفة تحتاج إلى استرداد الجذر
# ============================================================

ROOT_OVERRIDES = {

    # الافتعال مع المثال الواوي
    "اتقى": ["و", "ق", "ي"],
    "اتصل": ["و", "ص", "ل"],
    "اتزن": ["و", "ز", "ن"],
    "اتسع": ["و", "س", "ع"],
    "اتجه": ["و", "ج", "ه"],
    "اتخذ": ["أ", "خ", "ذ"],

    # الافتعال مع الإعلال
    "اصطبر": ["ص", "ب", "ر"],
    "اضطرب": ["ض", "ر", "ب"],
    "اطّلع": ["ط", "ل", "ع"],
    "اظّلم": ["ظ", "ل", "م"],

    # الإبدال بعد الدال والذال والزاي
    "ادعى": ["د", "ع", "و"],
    "ادّعى": ["د", "ع", "و"],
    "اذّكر": ["ذ", "ك", "ر"],
    "ازدجر": ["ز", "ج", "ر"],

    # أجوف
    "قال": ["ق", "و", "ل"],
    "باع": ["ب", "ي", "ع"],
    "صام": ["ص", "و", "م"],
    "خاف": ["خ", "و", "ف"],
    "نام": ["ن", "و", "م"],
    "قام": ["ق", "و", "م"],

    # ناقص
    "دعا": ["د", "ع", "و"],
    "رمى": ["ر", "م", "ي"],
    "سعى": ["س", "ع", "ي"],
    "رضي": ["ر", "ض", "ي"],

    # أمثلة
    "وعد": ["و", "ع", "د"],
    "وجد": ["و", "ج", "د"],
    "وزن": ["و", "ز", "ن"],
    "وقف": ["و", "ق", "ف"],

    # مضارع الأمثلة
    "يعد": ["و", "ع", "د"],
    "يجد": ["و", "ج", "د"],
    "يزن": ["و", "ز", "ن"],
    "يقف": ["و", "ق", "ف"],

    # مضارع الأجوف
    "يقول": ["ق", "و", "ل"],
    "يقوم": ["ق", "و", "م"],
    "يبيع": ["ب", "ي", "ع"],
    "يخاف": ["خ", "و", "ف"],

    # الأمر
    "قل": ["ق", "و", "ل"],
    "قم": ["ق", "و", "م"],
    "بع": ["ب", "ي", "ع"],
    "خف": ["خ", "و", "ف"],
    "اسع": ["س", "ع", "ي"],
    "ارم": ["ر", "م", "ي"],
    "ادع": ["د", "ع", "و"],
}


# ============================================================
# 6. أدوات النص والتطبيع
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


# ============================================================
# 7. قراءة الجذر من CAMeL
# ============================================================

def normalize_root(root_raw):

    if not root_raw:
        return None

    parts = root_raw.split(".")

    parts = [
        normalize_arabic(p)
        for p in parts
        if p
    ]

    if len(parts) != 3:
        return parts if parts else None

    return parts


def root_is_real(root):

    if not root:
        return False

    return (
        len(root) == 3
        and all(
            r
            and r != "#"
            and len(r) == 1
            for r in root
        )
    )


def root_has_unknown(root):

    if not root:
        return True

    return (
        len(root) != 3
        or any(
            not r
            or r == "#"
            for r in root
        )
    )


def root_string(root):

    if not root:
        return "غير محدد"

    return " . ".join(root)


# ============================================================
# 8. استرداد الجذر من الكلمة
# ============================================================

def recover_root(analysis, word):

    raw_root = analysis.get("root", "")

    camel_root = normalize_root(raw_root)

    if root_is_real(camel_root):
        return camel_root, "CAMeL Tools"


    clean_word = normalize_arabic(word)


    # --------------------------------------------------------
    # أولًا: قاموس الجذور الخاصة بالحالات التي يكون فيها
    # CAMeL غير محدد لبعض الأصول الضعيفة.
    # --------------------------------------------------------

    if clean_word in ROOT_OVERRIDES:

        return (
            ROOT_OVERRIDES[clean_word],
            "استرداد صرفي موثوق"
        )


    # --------------------------------------------------------
    # ثانيًا: محاولة الاسترداد من lemma
    # --------------------------------------------------------

    lex = normalize_arabic(
        analysis.get("lex", "")
    )

    if lex in ROOT_OVERRIDES:

        return (
            ROOT_OVERRIDES[lex],
            "استرداد من الـLemma"
        )


    # --------------------------------------------------------
    # ثالثًا: استرداد الافتعال
    # --------------------------------------------------------

    pattern = normalize_arabic(
        analysis.get("pattern", "")
    )

    stem = normalize_arabic(
        analysis.get("stem", "")
    )


    # افتعل مع حذف الواو الأولى:
    #
    # اتقى
    # اتصل
    # اتزن
    #
    # ا + ت + ف + ع + ل
    #
    # وجود "ات" في البداية مع بنية الافتعال
    # يسمح باسترداد الواو الأولى في عدد من الأمثلة.
    # أما اللام فيؤخذ من الرسم النهائي.

    if (
        stem.startswith("ات")
        and len(stem) >= 3
        and (
            "2" in pattern
            or "افتعل" in pattern
            or pattern.startswith("ات")
        )
    ):

        if len(stem) == 4:

            middle = stem[2]
            final = stem[3]

            if final == "ي":
                return (
                    ["و", middle, "ي"],
                    "استرداد بنيوي للافتعال"
                )

            if final == "ا":
                return (
                    ["و", middle, "و"],
                    "استرداد بنيوي للافتعال"
                )

            return (
                ["و", middle, final],
                "استرداد بنيوي للافتعال"
            )


    # --------------------------------------------------------
    # رابعًا: الجذر المجهول جزئيًا في CAMeL
    #
    # مثال:
    # #.ق.#
    #
    # إذا كانت لدينا الكلمة اتقى:
    # نبحث عن بنية افتعل.
    # --------------------------------------------------------

    if camel_root and len(camel_root) == 3:

        unknown_positions = [
            i
            for i, r in enumerate(camel_root)
            if r == "#"
        ]

        known_positions = {
            i: r
            for i, r in enumerate(camel_root)
            if r != "#"
        }

        # الحالة الشائعة:
        # # . ق . #
        #
        # في الافتعال الذي يبدأ بـ "ات"
        # تكون الفاء غالبًا واوًا في المثال الواوي،
        # واللام تسترد من نهاية الكلمة.

        if unknown_positions == [0, 2]:

            if (
                stem.startswith("ات")
                and len(stem) >= 4
            ):

                middle = known_positions.get(1)

                if middle:

                    final = stem[-1]

                    if final == "ي":
                        final_root = "ي"

                    elif final == "ا":
                        final_root = "و"

                    else:
                        final_root = final

                    return (
                        ["و", middle, final_root],
                        "استرداد من الجذر الجزئي وبنية الكلمة"
                    )


    return None, None


# ============================================================
# 9. تحويل وزن CAMeL للعرض
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
# 10. تحديد الصيغة
# ============================================================

def detect_form(pattern, analysis=None, word=""):

    p = pattern_plain(pattern)

    stem = normalize_arabic(
        (analysis or {}).get("stem", "")
    )

    word_clean = normalize_arabic(
        word
    )

    # افتعل
    if (
        p.startswith("ا1ت")
        or "افتعل" in p
        or (
            stem.startswith("ات")
            and len(stem) >= 3
        )
    ):
        return "افتعل"

    # استفعل
    if p.startswith("است"):
        return "استفعل"

    # انفعل
    if p.startswith("ان"):
        return "انفعل"

    # تفاعل
    if p.startswith("ت1ا"):
        return "تفاعل"

    # تفعّل
    if p.startswith("ت1"):
        return "تفعّل"

    # أفعل
    if p.startswith("ا1"):
        return "أفعل"

    return "فعل"


# ============================================================
# 11. تصنيف الفعل
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


    # الهمز
    if r1 in HAMZA:
        features.append("مهموز الفاء")

    if r2 in HAMZA:
        features.append("مهموز العين")

    if r3 in HAMZA:
        features.append("مهموز اللام")


    # التضعيف
    if r2 == r3:
        features.append("مضعف")


    # الاعتلال
    if r1 in WEAK:
        features.append("مثال")

    if r2 in WEAK:
        features.append("أجوف")

    if r3 in WEAK:
        features.append("ناقص")


    # اللفيف
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
        "description": "، ".join(features)
    }


# ============================================================
# 12. اختيار التحليل
# ============================================================

def is_verb(analysis):

    return analysis.get("pos") in {
        "verb",
        "verb_pseudo"
    }


def analysis_score(analysis, original_word):

    score = 0


    if analysis.get("pos") == "verb":
        score += 100

    elif analysis.get("pos") == "verb_pseudo":
        score += 40


    root = normalize_root(
        analysis.get("root", "")
    )

    if root_is_real(root):
        score += 50

    elif root and not root_has_unknown(root):
        score += 20


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

    if stem == word:
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
        key=lambda a: analysis_score(
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
        return verbs[0], verbs


    return ranked[0], ranked


# ============================================================
# 13. البنية السطحية
# ============================================================

def surface_letters(
    analysis,
    original_word
):

    stem = analysis.get("stem")

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

    return (
        re.search(
            pattern,
            text
        )
        is not None
    )


# ============================================================
# 14. تحديد افتعل
# ============================================================

def is_iftial(
    analysis,
    word=""
):

    pattern = pattern_plain(
        analysis.get("pattern", "")
    )

    stem = normalize_arabic(
        analysis.get("stem", "")
    )

    word_clean = normalize_arabic(
        word
    )


    if (
        pattern.startswith("ا1ت")
        or "افتعل" in pattern
    ):
        return True


    # مهم جدًا:
    # CAMeL قد يعيد pattern مثل:
    #
    # ٱِتَّ2َى
    #
    # فلا يظهر الرقم 1.
    #
    # لذلك نستعين بالبنية السطحية.

    if (
        stem.startswith("ات")
        and len(stem) >= 3
    ):
        return True


    if (
        word_clean.startswith("ات")
        and len(word_clean) >= 4
    ):
        return True


    return False


# ============================================================
# 15. إبدال تاء الافتعال طاءً
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
        "ا"
        + r1
        + "ط"
    )


    if not stem.startswith(
        expected_prefix
    ):
        return None


    return {
        "type": "إبدال",
        "title": "إبدال تاء الافتعال طاءً",
        "badge": "badge-ibdal",

        "explanation": (
            f"الجذر ({root_string(root)}) جاء على صيغة "
            "الافتعال، وفاؤه من الحروف التي تقلب معها "
            "تاء الافتعال طاءً، فصارت التاء طاءً للمجانسة."
        ),

        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والبنية السطحية = {stem}."
        ),

        "original": (
            f"ا + {r1} + ت + {r2} + {r3}"
        ),

        "confidence": "عالية"
    }


# ============================================================
# 16. إبدال التاء دالًا
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
        "ا"
        + r1
        + "د"
    )


    if not stem.startswith(
        expected
    ):
        return None


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
            f"والبنية السطحية = {stem}."
        ),

        "original": (
            f"ا + {r1} + ت + {r2} + {r3}"
        ),

        "confidence": "عالية"
    }


# ============================================================
# 17. إبدال الواو تاءً في الافتعال
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
        "title": (
            "إبدال الواو تاءً ثم إدغامها "
            "في تاء الافتعال"
        ),
        "badge": "badge-ibdal",

        "explanation": (
            f"فاء الجذر هي الواو ({r1})، "
            "وجاء الفعل على صيغة الافتعال. "
            "تقلب الواو تاءً، فتجتمع مع تاء الافتعال، "
            "ثم يحصل الإدغام."
        ),

        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والبنية السطحية = {stem}. "
            + (
                "كما تظهر الشدة على التاء في التحليل المشكول."
                if shadda
                else
                "ولم تظهر الشدة في التحليل المشكول."
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
# 18. إعلال العين بالقلب
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


    expected = (
        r1
        + "ا"
        + r3
    )


    if stem != expected:

        if not stem.startswith(
            r1 + "ا"
        ):
            return None


    return {
        "type": "إعلال بالقلب",
        "title": (
            "إعلال بالقلب: قلب الواو أو الياء ألفًا"
        ),
        "badge": "badge-ilal",

        "explanation": (
            f"الفعل أجوف؛ لأن عينه ({r2}) حرف علة. "
            "ظهرت العين في الصورة السطحية ألفًا، "
            "وهو من أحكام إعلال العين بالقلب."
        ),

        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"وعينه = {r2}، "
            f"والساق الصرفية = {stem}."
        ),

        "original": (
            f"{r1}َ{r2}َ{r3}"
        ),

        "confidence": "عالية"
    }


# ============================================================
# 19. إعلال اللام بالقلب
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


    original = word.strip()

    clean = normalize_arabic(
        original
    )


    ends_with_maqsura = (
        original.endswith("ى")
    )

    ends_with_alif = (
        clean.endswith("ا")
    )


    if not (
        ends_with_maqsura
        or ends_with_alif
    ):
        return None


    return {
        "type": "إعلال بالقلب",
        "title": "إعلال لام الفعل بالقلب",
        "badge": "badge-ilal",

        "explanation": (
            f"الفعل ناقص؛ لأن لامه ({r3}) حرف علة. "
            "ظهرت اللام في الصورة الماضية على صورة ألف "
            "أو ألف مقصورة بحسب أصلها وسياقها."
        ),

        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"واللام المعتلة = {r3}، "
            f"والفعل ماضٍ، وينتهي بصورة ألفية."
        ),

        "original": (
            f"{r1} + {r2} + {r3}"
        ),

        "confidence": "عالية"
    }


# ============================================================
# 20. الإعلال بالنقل
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

        if not re.search(
            re.escape(r1)
            + r"[َُِ]"
            + "و",
            diac
        ):
            return None

        vowel_name = "الضمة"

    else:

        if not re.search(
            re.escape(r1)
            + r"[َُِ]"
            + "ي",
            diac
        ):
            return None

        vowel_name = "الكسرة"


    return {
        "type": "إعلال بالنقل",
        "title": "إعلال بالنقل",
        "badge": "badge-ilal",

        "explanation": (
            f"الفعل أجوف وعينه ({r2}) حرف علة، "
            f"وتظهر في بنيته حركة مناسبة على الحرف السابق "
            f"مع بقاء حرف العلة، وهي قرينة على النقل."
        ),

        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والفعل مضارع، "
            f"والتحليل المشكول = {diac}."
        ),

        "original": (
            f"{r1} + {r2} + {r3}"
        ),

        "confidence": "متوسطة"
    }


# ============================================================
# 21. حذف عين الأجوف
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
        or (
            stem.startswith("ي")
            and stem.endswith(core)
        )
    ):
        return None


    return {
        "type": "إعلال بالحذف",
        "title": (
            "إعلال بالحذف: حذف عين الفعل الأجوف"
        ),
        "badge": "badge-ilal",

        "explanation": (
            f"الفعل أجوف وعينه ({r2}) حرف علة، "
            "وقد حُذفت عينه في صيغة الأمر أو الجزم."
        ),

        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والساق = {stem}، "
            f"ولا تظهر فيها العين المعتلة."
        ),

        "original": (
            f"{r1} + {r2} + {r3}"
        ),

        "confidence": "عالية"
    }


# ============================================================
# 22. حذف فاء المثال الواوي
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


    stem = surface_letters(
        analysis,
        word
    )


    if "و" in stem:
        return None


    if not stem.startswith("ي"):
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
            f"الفعل مثال واوي؛ لأن فاءه ({r1}) واو. "
            "وحُذفت الواو من المضارع بعد تحقق شروط الحذف."
        ),

        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والساق = {stem}، "
            "ولا تظهر الواو الأولى."
        ),

        "original": (
            f"{r1} + {r2} + {r3}"
        ),

        "confidence": "متوسطة"
    }


# ============================================================
# 23. حذف لام الناقص
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
            f"الفعل ناقص ولامه ({r3}) حرف علة، "
            "وقد حُذفت اللام في الأمر أو الجزم."
        ),

        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والساق = {stem}، "
            "ولا تظهر اللام المعتلة في آخرها."
        ),

        "original": (
            f"{r1} + {r2} + {r3}"
        ),

        "confidence": "عالية"
    }


# ============================================================
# 24. الإدغام في المضعف
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


    if r2 != r3:
        return None


    diac = analysis.get(
        "diac",
        ""
    )


    if not has_shadda_near(
        diac,
        r3
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
            "لتماثل عينه ولامه، وقد أثبت التحليل المشكول "
            "الشدة الدالة على الإدغام."
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


# ============================================================
# 25. الإدغام بعد الدال
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
        "title": (
            "إبدال تاء الافتعال دالًا ثم إدغامها"
        ),
        "badge": "badge-idgham",

        "explanation": (
            "وقعت تاء الافتعال بعد الدال، "
            "فقُلبت دالًا، ثم اجتمعت الدالان "
            "المتماثلان فأُدغمت إحداهما في الأخرى."
        ),

        "evidence": (
            f"الجذر = {root_string(root)}، "
            "والبنية على الافتعال، "
            "والتحليل المشكول يثبت الشدة."
        ),

        "original": (
            f"ا + د + ت + {r2} + {r3}"
        ),

        "confidence": "عالية"
    }


# ============================================================
# 26. قواعد المحرك
# ============================================================

RULES = [

    rule_ibdal_taa_to_taa_mufakhkhama,

    rule_ibdal_taa_to_dal,

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
# 27. تشغيل المحرك
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
# 28. لا تغيير
# ============================================================

def build_no_change_result(
    analysis,
    classification
):

    return {

        "type": "لا تغيير مثبت",

        "title": (
            "لا يظهر إعلال أو إبدال مثبت"
        ),

        "badge": "badge-neutral",

        "explanation": (
            "لم يثبت محرك القواعد، اعتمادًا على "
            "المعطيات الصرفية المتاحة، قاعدةً من "
            "قواعد الإعلال أو الإبدال أو الإدغام."
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
# 29. التحليل النهائي
# ============================================================

def analyze_word(word):

    analyses = analyzer.analyze(
        word
    )


    if not analyses:

        return {
            "success": False,
            "message": (
                "لم يعثر CAMeL Tools "
                "على تحليل صرفي للكلمة."
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
            "message": (
                "تعذر اختيار تحليل صرفي."
            ),
            "analyses": analyses
        }


    if best.get("pos") not in {
        "verb",
        "verb_pseudo"
    }:

        return {
            "success": False,
            "message": (
                "الكلمة حُللت صرفيًا، "
                "لكن التحليل المختار ليس فعلًا."
            ),
            "analysis": best,
            "analyses": analyses
        }


    # --------------------------------------------------------
    # استخراج الجذر أو استرداده
    # --------------------------------------------------------

    root, root_source = recover_root(
        best,
        word
    )


    if not root_is_real(root):

        return {
            "success": False,

            "message": (
                "تم العثور على تحليل صرفي للفعل، "
                "لكن تعذر استرداد جذر ثلاثي موثوق "
                "من بيانات CAMeL Tools وبنية الكلمة."
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

        "pattern": best.get(
            "pattern"
        ),

        "form": detect_form(
            best.get("pattern"),
            best,
            word
        ),

        "changes": changes
    }


# ============================================================
# 30. واجهة البرنامج
# ============================================================

st.markdown("""
<div class="main-header">

    <h1>
        📖 محرك قواعد الإعلال والإبدال
    </h1>

    <p>
        تحليل صرفي قائم على CAMeL Tools مع محرك قواعد
        مستقل للتحقق من الإعلال والإبدال والإدغام
    </p>

</div>
""", unsafe_allow_html=True)


# ============================================================
# 31. الإدخال
# ============================================================

st.subheader(
    "🔍 أدخل الفعل"
)


user_input = st.text_input(

    "اكتب الفعل:",

    value="اتقى",

    placeholder=(
        "مثل: قال، يقول، قل، وعد، يعد، "
        "عِد، رمى، اصطبر، ازدجر، ادّعى"
    )
)


# ============================================================
# 32. تشغيل التحليل
# ============================================================

if user_input.strip():

    word = user_input.strip()


    with st.spinner(
        "جاري التحليل الصرفي والتحقق من القواعد..."
    ):

        result = analyze_word(
            word
        )


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


    else:

        analysis = result["analysis"]

        root = result["root"]

        classification = result[
            "classification"
        ]


        # ----------------------------------------------------
        # المعلومات العامة
        # ----------------------------------------------------

        st.markdown("---")


        st.markdown(

            f"""
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
                        {result['root_source']}
                    </span>
                </p>

                <p>
                    ⚖️ <b>الوزن في CAMeL:</b>
                    <span class="custom-tag">
                        {display_pattern(
                            analysis.get('pattern')
                        )}
                    </span>
                </p>

                <p>
                    🏗️ <b>الصيغة:</b>
                    <span class="custom-tag">
                        {result['form']}
                    </span>
                </p>

                <p>
                    📚 <b>الـLemma:</b>
                    <span class="custom-tag">
                        {analysis.get('lex')
                        or 'غير متاح'}
                    </span>
                </p>

                <p>
                    🔬 <b>الساق الصرفية:</b>
                    <span class="custom-tag">
                        {analysis.get('stem')
                        or 'غير متاحة'}
                    </span>
                </p>

            </div>
            """,

            unsafe_allow_html=True
        )


        # ----------------------------------------------------
        # التصنيف
        # ----------------------------------------------------

        st.subheader(
            "🧬 التصنيف الصرفي"
        )


        features = classification[
            "features"
        ]


        if features:

            tags = " ".join(

                f"""
                <span class="badge badge-type">
                    {feature}
                </span>
                """

                for feature in features
            )


            st.markdown(
                tags,
                unsafe_allow_html=True
            )


        st.markdown(

            f"""
            <div class="explanation-box">

                <b>الوصف:</b>

                {classification['description']}

            </div>
            """,

            unsafe_allow_html=True
        )


        # ----------------------------------------------------
        # التغييرات
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


            st.markdown(

                f"""
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
                """,

                unsafe_allow_html=True
            )


        # ----------------------------------------------------
        # بيانات التحليل
        # ----------------------------------------------------

        with st.expander(
            "🔬 عرض بيانات التحليل الصرفي المعتمدة"
        ):

            useful_features = {

                "diac":
                    analysis.get("diac"),

                "lex":
                    analysis.get("lex"),

                "root":
                    analysis.get("root"),

                "root_after_recovery":
                    root_string(root),

                "root_source":
                    result["root_source"],

                "pattern":
                    analysis.get("pattern"),

                "stem":
                    analysis.get("stem"),

                "pos":
                    analysis.get("pos"),

                "asp":
                    analysis.get("asp"),

                "vox":
                    analysis.get("vox"),

                "mod":
                    analysis.get("mod"),

                "source":
                    analysis.get("source"),

                "bw":
                    analysis.get("bw"),

                "ud":
                    analysis.get("ud")
            }


            st.json(
                useful_features
            )


        # ----------------------------------------------------
        # التحليلات الأخرى
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

                    st.markdown(

                        f"""
                        <div class="analysis-box">

                            <b>
                                التحليل {idx}
                            </b>

                            <br>

                            الجذر:
                            <span class="custom-tag">
                                {a.get(
                                    'root',
                                    'غير محدد'
                                )}
                            </span>

                            الوزن:
                            <span class="custom-tag">
                                {display_pattern(
                                    a.get('pattern')
                                )}
                            </span>

                            الصنف:
                            <span class="custom-tag">
                                {a.get(
                                    'pos',
                                    'غير محدد'
                                )}
                            </span>

                            الـLemma:
                            <span class="custom-tag">
                                {a.get(
                                    'lex',
                                    'غير محدد'
                                )}
                            </span>

                        </div>
                        """,

                        unsafe_allow_html=True
                    )


# ============================================================
# 33. التذييل
# ============================================================

st.markdown(

    """
    <br>

    <center>

        <small style="color:#64748b;">

            محرك قواعد الإعلال والإبدال الصرفي
            | CAMeL Tools
            | Python

        </small>

    </center>
    """,

    unsafe_allow_html=True
    )
