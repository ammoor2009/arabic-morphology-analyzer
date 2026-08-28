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
    """
    تطبيع محافظ على المعنى الصرفي العام.
    لا نستخدمه لإعادة بناء الجذر،
    بل للمقارنة البنيوية فقط.
    """

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
    CAMeL Tools يعيد الجذر عادة بالشكل:
    ق.و.ل

    وقد يحتوي على # في بعض التحليلات.
    """

    if not root_raw:
        return None

    parts = root_raw.split(".")

    parts = [
        normalize_arabic(p)
        for p in parts
        if p
    ]

    if not parts:
        return None

    return parts


def root_is_real(root):
    """
    لا نخمن أي حرف عند وجود #.
    """

    if not root:
        return False

    return all(
        r and r != "#" and len(r) == 1
        for r in root
    )


def root_string(root):
    if not root:
        return "غير محدد"

    return " . ".join(root)


# ============================================================
# 6. تحويل وزن CAMeL للعرض فقط
# ============================================================

def display_pattern(pattern):
    """
    لا نفترض أن pattern هو وزن عربي تقليدي.
    نعرضه كما أعاده CAMeL، مع تحويل أرقام الجذر
    إلى ف/ع/ل للعرض التعليمي.

    1 = ف
    2 = ع
    3 = ل
    """

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
    """
    استدلال محافظ من قالب CAMeL.
    لا نستخدمه وحده لإثبات الحكم.
    """

    p = pattern_plain(pattern)

    if not p:
        return None

    # افتعل
    if p.startswith("ا1ت"):
        return "افتعل"

    # استفعل
    if p.startswith("است"):
        return "استفعل"

    # انفعل
    if p.startswith("ان"):
        return "انفعل"

    # افعلّ
    if p.startswith("ا") and "ّ" in (pattern or ""):
        if "3" in (pattern or ""):
            return "افعلّ"

    # صيغ مزيدة مشهورة
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
# 8. تصنيف الفعل من حيث الصحة والاعتلال
# ============================================================

def classify_verb(root):
    """
    تصنيف مبني على الجذر الذي أعاده CAMeL Tools.

    يسمح بتعدد الصفات، لأن:
    مهموز + أجوف
    مهموز + ناقص
    إلخ
    يمكن أن تجتمع.
    """

    if not root_is_real(root):
        return {
            "primary": "غير مصنف",
            "features": [],
            "description": "لم يقدم التحليل الصرفي جذرًا ثلاثيًا صالحًا للحكم."
        }

    if len(root) != 3:
        return {
            "primary": "رباعي/غير ثلاثي",
            "features": ["جذر غير ثلاثي"],
            "description": "الجذر ليس ثلاثيًا؛ لذلك لا تُطبق عليه أحكام تصنيف الثلاثي تلقائيًا."
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

    # صحيح سالم
    if not features:
        primary = "سالم"
        description = "جذر ثلاثي صحيح خالٍ من الهمز والتضعيف وحروف العلة."
        return {
            "primary": primary,
            "features": [primary],
            "description": description
        }

    # ترتيب الأولوية التعليمية
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
# 9. معلومات التحليل
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
    """
    اختيار التحليل لا يعتمد على analyses[0].
    نمنح نقاطًا للتحليل الذي:
    - هو فعل
    - له جذر حقيقي
    - له pattern
    - مصدره lex
    - وله stem/lemma/diac
    """

    score = 0

    if analysis.get("pos") == "verb":
        score += 100

    if analysis.get("pos") == "verb_pseudo":
        score += 40

    root = normalize_root(analysis.get("root", ""))

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

    # إذا كان التحليل يعيد الكلمة نفسها تقريبًا
    stem = normalize_arabic(
        analysis.get("stem", "")
    )

    word = normalize_arabic(original_word)

    if stem and word:
        if stem == word:
            score += 10

    return score


def choose_best_analysis(analyses, word):
    """
    لا نأخذ أول تحليل.
    """

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
# 10. مطابقة الجذر مع بنية الكلمة
# ============================================================

def surface_letters(analysis, original_word):
    """
    نفضل stem الذي أعاده CAMeL.
    وإن لم يوجد نستخدم الكلمة بعد التطبيع.
    """

    stem = analysis.get("stem")

    if stem:
        stem_clean = normalize_arabic(stem)
        if stem_clean:
            return stem_clean

    return normalize_arabic(original_word)


def has_letter_sequence(text, sequence):
    return sequence in text


def has_shadda_near(text, letter):
    """
    البحث في النص المشكول عن شدة على حرف معين.
    """

    if not text or not letter:
        return False

    pattern = re.escape(letter) + r"[ًٌٍَُِْ]*ّ"
    return re.search(pattern, text) is not None


def diac_has_sequence(diac, pattern):
    if not diac:
        return False

    return pattern in diac


# ============================================================
# 11. تحديد افتعل بصورة أكثر أمانًا
# ============================================================

def is_iftial(analysis):
    pattern = pattern_plain(
        analysis.get("pattern", "")
    )

    if not pattern:
        return False

    # قالب CAMeL غالبًا يمثل الجذر بالأرقام
    if pattern.startswith("ا1ت"):
        return True

    # احتياطًا لبعض التمثيلات
    if "فتعل" in pattern:
        return True

    return False


# ============================================================
# 12. قاعدة إبدال تاء الافتعال طاءً
# ============================================================

def rule_ibdal_taa_to_taa_mufakhkhama(analysis, word):
    """
    تاء الافتعال تقلب طاءً بعد:
    ص، ض، ط، ظ

    لا نكتفي بوجود الطاء.
    بل نشترط:
    - جذر ثلاثي
    - صيغة افتعل
    - الفاء من المجموعة
    - وجود الطاء في الموضع البنيوي المتوقع.
    """

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    if not is_iftial(analysis):
        return None

    r1, r2, r3 = root

    if r1 not in {"ص", "ض", "ط", "ظ"}:
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
                f"الجذر ({root_string(root)}) جاء على صيغة "
                f"الافتعال، وفاؤه ({r1}) من الحروف التي "
                "تقلب معها تاء الافتعال طاءً، فصارت التاء "
                "طاءً للمجانسة."
            ),
            "evidence": (
                f"CAMeL Tools: الجذر = {root_string(root)}، "
                f"والوزن = {display_pattern(analysis.get('pattern'))}، "
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
# 13. قاعدة إبدال التاء دالًا
# ============================================================

def rule_ibdal_taa_to_dal(analysis, word):
    """
    بعد د، ذ، ز:
    تاء الافتعال تقلب دالًا.
    """

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    if not is_iftial(analysis):
        return None

    r1, r2, r3 = root

    if r1 not in {"د", "ذ", "ز"}:
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
                f"والوزن = {display_pattern(analysis.get('pattern'))}، "
                f"والصورة السطحية تحقق البنية ا + الفاء + د."
            ),
            "original": (
                f"ا + {r1} + ت + {r2} + {r3}"
            ),
            "confidence": "عالية"
        }

    return None


# ============================================================
# 14. إبدال الواو تاءً في الافتعال
# ============================================================

def rule_ibdal_waw_in_iftial(analysis, word):
    """
    المثال الواوي في الافتعال:
    و + تاء الافتعال
    تؤدي إلى تاءين ثم الإدغام.

    مثل:
    اتصل
    اتقى
    اتزن
    """

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    if not is_iftial(analysis):
        return None

    r1, r2, r3 = root

    if r1 != "و":
        return None

    stem = surface_letters(
        analysis,
        word
    )

    diac = analysis.get("diac", "")

    # الصورة السطحية المتوقعة تبدأ غالبًا بـ ات
    if not stem.startswith("ات"):
        return None

    # الشدة دليل إضافي مهم
    shadda = has_shadda_near(diac, "ت")

    return {
        "type": "إبدال وإدغام",
        "title": "إبدال الواو تاءً ثم إدغامها في تاء الافتعال",
        "badge": "badge-ibdal",
        "explanation": (
            f"فاء الجذر هي الواو ({r1})، وجاء الفعل على "
            "صيغة الافتعال. تقلب الواو تاءً، فتجتمع "
            "مع تاء الافتعال، ثم يحصل الإدغام."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"الوزن = {display_pattern(analysis.get('pattern'))}، "
            f"والصورة السطحية تبدأ بـ(ات). "
            + (
                "كما أن CAMeL Tools أثبت الشدة على التاء."
                if shadda
                else
                "ولم تتوافر شدة في المدخل المشكول؛ لذلك خُفّضت الثقة."
            )
        ),
        "original": (
            f"ا + و + ت + {r2} + {r3}"
        ),
        "confidence": "عالية" if shadda else "متوسطة"
    }


# ============================================================
# 15. الإعلال بالقلب: الأجوف إلى ألف
# ============================================================

def rule_heart_medial_weak_to_alif(analysis, word):
    """
    مثل:
    قال ← ق و ل
    باع ← ب ي ع
    صام ← ص و م
    خاف ← خ و ف

    نتحقق من:
    - الجذر
    - كون الفعل أجوفًا
    - صيغة الماضي الفعلية
    - ظهور الألف في الموضع الأوسط.
    """

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

    # الصورة الأساسية للفعل الماضي الأجوف:
    # ف + ا + ل
    expected = r1 + "ا" + r3

    if stem != expected:
        # بعض التحليلات قد تتضمن زيادات؛
        # نتحقق من وجود الصورة الجوهرية.
        if not stem.startswith(r1 + "ا"):
            return None

    return {
        "type": "إعلال بالقلب",
        "title": "إعلال بالقلب: قلب الواو أو الياء ألفًا",
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل أجوف؛ لأن عينه ({r2}) حرف علة. "
            f"ظهرت العين في الصورة السطحية ألفًا، "
            "وذلك من أحكام إعلال العين بالقلب في الموضع "
            "المستوفي لشروط القلب."
        ),
        "evidence": (
            f"CAMeL Tools: الجذر = {root_string(root)}، "
            f"والفعل ماضٍ، وعينه {r2}، "
            f"والساق الصرفية تظهر الألف بعد الفاء."
        ),
        "original": (
            f"الصورة الأصلية التمثيلية: "
            f"{r1}َ{r2}َ{r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 16. الإعلال بالقلب في الناقص
# ============================================================

def rule_heart_final_weak(analysis, word):
    """
    مثل:
    دعا ← د ع و
    رمى ← ر م ي
    سعى ← س ع ي
    """

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

    original_normalized = normalize_arabic(word)

    # نستخدم الرسم الأصلي أيضًا لأن ى مهمة هنا.
    ends_with_alif_maqsura = word.strip().endswith("ى")
    ends_with_alif = original_normalized.endswith("ا")

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
            "ظهرت اللام في الصورة الماضية على صورة ألف "
            "أو ألف مقصورة بحسب أصلها وسياقها الصرفي."
        ),
        "evidence": (
            f"CAMeL Tools: الجذر = {root_string(root)}، "
            f"واللام المعتلة = {r3}، والفعل ماضٍ، "
            f"والكلمة تنتهي بـ({'ألف مقصورة' if ends_with_alif_maqsura else 'ألف'})."
        ),
        "original": (
            f"الجذر قبل التغيير: {r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 17. الإعلال بالنقل
# ============================================================

def rule_transfer_vowel(analysis, word):
    """
    مثل:
    يقول
    يقوم
    يبيع

    الفكرة:
    عين الفعل حرف علة ما زال ظاهرًا،
    وتظهر الحركة على الحرف السابق له.

    نتحقق من الحركة التي أثبتها CAMeL Tools،
    لا من مجرد وجود الواو/الياء.
    """

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

    diac = analysis.get("diac", "")

    if not diac:
        return None

    # نبحث عن:
    # الحرف الأول + حركة مناسبة + حرف العلة
    if r2 == "و":
        regex = (
            re.escape(r1)
            + r"[َُِ]"
            + r"\u0648"
        )

        matches = re.search(regex, diac)

        if not matches:
            return None

        vowel_name = "الضمة"

        # النقل الأشهر في هذا السياق
        if "ُو" not in diac:
            return None

    else:
        regex = (
            re.escape(r1)
            + r"[َُِ]"
            + r"\u064A"
        )

        matches = re.search(regex, diac)

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
            f"وقد أثبت CAMeL Tools ظهور حرف العلة في الصورة "
            f"السطحية مع حركة {vowel_name} على الحرف السابق؛ "
            "وهذه قرينة صرفية على نقل الحركة."
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
# 18. حذف عين الأجوف في الأمر والجزم
# ============================================================

def rule_delete_medial_weak(analysis, word):
    """
    مثل:
    قُلْ
    بِعْ
    خَفْ

    وكذلك بعض صيغ الجزم:
    لم يقل
    لم يبع

    لا نعتمد على طول الكلمة،
    بل نقارن الجذر بالساق الصرفية.
    """

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

    # نبحث عن ف + ل بدون عين الجذر
    # مع السماح بوجود بادئة ي في الجزم.
    core = r1 + r3

    direct = stem == core
    imperfect = stem.endswith(core) and stem.startswith("ي")

    if not (direct or imperfect):
        return None

    return {
        "type": "إعلال بالحذف",
        "title": "إعلال بالحذف: حذف عين الفعل الأجوف",
        "badge": "badge-ilal",
        "explanation": (
            f"الفعل أجوف وعينه ({r2}) حرف علة، "
            "وقد حُذفت عينه في صيغة الأمر أو في موضع الجزم "
            "بحسب البنية الصرفية."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            f"والتحليل يثبت {'الأمر' if asp == 'c' else 'الجزم'}، "
            f"والساق ({stem}) لا تحتوي على العين المعتلة ({r2})."
        ),
        "original": (
            f"الجذر: {r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 19. حذف فاء المثال الواوي
# ============================================================

def rule_delete_initial_waw(analysis, word):
    """
    مثال:
    وَعَدَ → يَعِدُ
    وَزَنَ → يَزِنُ
    وَقَفَ → يَقِفُ

    نتحقق من:
    - الجذر واوي الفاء
    - الفعل مضارع
    - عدم وجود الواو في ساق المضارع
    - كون الوزن/البنية ثلاثية وليست صيغة مزيدة
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

    # لا نطبق القاعدة آليًا على الصيغ المزيدة
    # التي يكون الواو فيها جزءًا من بناء آخر.
    if pattern.startswith(("ا", "است", "ان", "ت")):
        return None

    # يجب أن تكون بنية المضارع قريبة من:
    # ي + عين + لام
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
            "وحُذفت الواو في المضارع في هذا الباب الصرفي "
            "عندما تحققت شروط الحذف."
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
# 20. حذف لام الناقص في الأمر والجزم
# ============================================================

def rule_delete_final_weak(analysis, word):
    """
    مثل:
    اسعَ
    ارمِ
    ادعُ
    ولم يسعَ
    ولم يرمِ
    ولم يدعُ

    الحكم هنا مبني على كون اللام حرف علة
    وعدم ظهورها في الساق مع الأمر/الجزم.
    """

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

    if not (asp == "c" or mod == "j"):
        return None

    stem = surface_letters(
        analysis,
        word
    )

    # يجب أن تكون اللام غير موجودة في نهاية الساق.
    if stem.endswith(r3):
        return None

    # نتحقق من وجود الفاء والعين
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
            f"والتحليل يثبت {'الأمر' if asp == 'c' else 'الجزم'}، "
            f"والساق ({stem}) لا تنتهي بالحرف المعتل ({r3})."
        ),
        "original": (
            f"{r1} + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 21. الإدغام في المضعف
# ============================================================

def rule_idgham_doubled(analysis, word):
    """
    الإدغام لا يثبت بمجرد وجود الشدة.
    لا بد من أن يكون الجذر مضعفًا
    أو أن تكون هناك قاعدة إبدال أدت إلى التماثل.
    """

    root = normalize_root(
        analysis.get("root", "")
    )

    if not root_is_real(root):
        return None

    if len(root) != 3:
        return None

    r1, r2, r3 = root

    diac = analysis.get("diac", "")

    if not diac:
        return None

    if r2 == r3:
        if not has_shadda_near(diac, r3):
            return None

        return {
            "type": "إدغام",
            "title": "إدغام المثلين في الفعل المضعف",
            "badge": "badge-idgham",
            "explanation": (
                f"الجذر ({root_string(root)}) مضعف؛ "
                "لتماثل عينه ولامه. وقد أثبت التحليل المشكول "
                "الشدة، وهي علامة الإدغام في الصورة الظاهرة."
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
# 22. الإدغام الناتج عن إبدال تاء الافتعال بعد الدال
# ============================================================

def rule_idgham_after_dal(analysis, word):
    """
    مثل:
    ادّعى
    ادّخر
    ونحوها حيث تتولد الدال الثانية
    ثم يحصل الإدغام.
    """

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

    if not is_iftial(analysis):
        return None

    diac = analysis.get("diac", "")

    if not has_shadda_near(diac, "د"):
        return None

    return {
        "type": "إبدال وإدغام",
        "title": "إبدال تاء الافتعال دالًا ثم إدغامها",
        "badge": "badge-idgham",
        "explanation": (
            "وقعت تاء الافتعال بعد الدال، فقُلبت دالًا، "
            "ثم اجتمعت الدالان المتماثلان فأُدغمت إحداهما "
            "في الأخرى، فظهرت الشدة."
        ),
        "evidence": (
            f"الجذر = {root_string(root)}، "
            "والوزن افتعل، وCAMeL Tools أثبت الشدة "
            "على الدال في الصورة المشكولة."
        ),
        "original": (
            f"ا + د + ت + {r2} + {r3}"
        ),
        "confidence": "عالية"
    }


# ============================================================
# 23. تجميع جميع القواعد
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
# 24. محرك القواعد
# ============================================================

def run_rule_engine(analysis, word):
    """
    يشغل كل القواعد.
    يمكن للكلمة أن تجمع أكثر من تغيير.

    مثال:
    إبدال + إدغام
    """

    results = []

    for rule in RULES:
        try:
            result = rule(analysis, word)

            if result:
                results.append(result)

        except Exception:
            # القاعدة الفاشلة لا توقف المحرك كله.
            continue

    # منع التكرار
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
# 25. تحديد ما إذا كان الفعل سالمًا من جهة التغيير الظاهر
# ============================================================

def build_no_change_result(analysis, classification):
    root = normalize_root(
        analysis.get("root", "")
    )

    return {
        "type": "لا تغيير مثبت",
        "title": "لا يظهر إعلال أو إبدال مثبت",
        "badge": "badge-neutral",
        "explanation": (
            "لم يثبت محرك القواعد، اعتمادًا على تحليل CAMeL Tools، "
            "قاعدةً من قواعد الإعلال أو الإبدال أو الإدغام "
            "يمكن إثباتها من البنية المتاحة."
        ),
        "evidence": (
            f"نوع الفعل: {classification['primary']}."
        ),
        "original": "لا يوجد أصل افتراضي مولد آليًا.",
        "confidence": "—"
    }


# ============================================================
# 26. التحليل النهائي
# ============================================================

def analyze_word(word):
    """
    المحرك الكامل:
    1. CAMeL Tools
    2. اختيار التحليل الفعلي
    3. استخراج الجذر
    4. تصنيف الفعل
    5. تشغيل قواعد الإعلال والإبدال
    6. عدم اختراع حكم عند عدم وجود دليل
    """

    analyses = analyzer.analyze(word)

    if not analyses:
        return {
            "success": False,
            "message": "لم يعثر CAMeL Tools على تحليل صرفي للكلمة.",
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

    if best.get("pos") not in {"verb", "verb_pseudo"}:
        return {
            "success": False,
            "message": (
                "الكلمة حُللت صرفيًا، لكن التحليل المختار "
                "ليس فعلًا."
            ),
            "analysis": best,
            "analyses": analyses
        }

    root = normalize_root(
        best.get("root", "")
    )
    st.write("DEBUG ROOT:", best.get("root"))
    st.json(best)
    if not root_is_real(root):
        return {
            "success": False,
            "message": (
                "تم العثور على تحليل، لكن CAMeL Tools "
                "لم يعطِ جذرًا صالحًا لبناء حكم صرفي موثوق."
            ),
            "analysis": best,
            "analyses": analyses
        }

    classification = classify_verb(root)

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
        "classification": classification,
        "pattern": best.get("pattern"),
        "form": detect_form(
            best.get("pattern")
        ),
        "changes": changes
    }


# ============================================================
# 27. واجهة البرنامج
# ============================================================

st.markdown("""
<div class="main-header">
    <h1>📖 محرك قواعد الإعلال والإبدال</h1>
    <p>
        تحليل صرفي قائم على CAMeL Tools مع محرك قواعد
        مستقل للتحقق من الإعلال والإبدال والإدغام
    </p>
</div>
""", unsafe_allow_html=True)


# ============================================================
# 28. الإدخال
# ============================================================

st.subheader("🔍 أدخل الفعل")

user_input = st.text_input(
    "اكتب الفعل:",
    value="اتقى",
    placeholder="مثل: قال، يقول، قل، وعد، يعد، عِد، رمى، اصطبر، ازدجر، ادّعى"
)


# ============================================================
# 29. تشغيل التحليل
# ============================================================

if user_input.strip():

    word = user_input.strip()

    with st.spinner("جاري التحليل الصرفي والتحقق من القواعد..."):
        result = analyze_word(word)

    if not result["success"]:

        st.error(result["message"])

        if result.get("analysis"):
            with st.expander("عرض التحليل الذي أعاده CAMeL Tools"):
                st.json(result["analysis"])

    else:

        analysis = result["analysis"]
        root = result["root"]
        classification = result["classification"]

        # ----------------------------------------------------
        # معلومات عامة
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
                        نوع الفعل: {classification['primary']}
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
                    ⚖️ <b>الوزن في CAMeL:</b>
                    <span class="custom-tag">
                        {display_pattern(analysis.get('pattern'))}
                    </span>
                </p>

                <p>
                    🏗️ <b>الصيغة المحتملة:</b>
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
            """,
            unsafe_allow_html=True
        )


        # ----------------------------------------------------
        # تصنيف الفعل
        # ----------------------------------------------------

        st.subheader("🧬 التصنيف الصرفي")

        features = classification["features"]

        if features:
            tags = " ".join(
                f'<span class="badge badge-type">{f}</span>'
                for f in features
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
        # التغييرات الصرفية
        # ----------------------------------------------------

        st.subheader("⚙️ التغييرات الصرفية المثبتة")

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
                            درجة الثقة: {change['confidence']}
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
        # التحليل الذي اعتمد عليه المحرك
        # ----------------------------------------------------

        with st.expander("🔬 عرض بيانات التحليل الصرفي المعتمدة"):

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

            st.json(useful_features)


        # ----------------------------------------------------
        # التحليلات الأخرى
        # ----------------------------------------------------

        other = [
            a for a in result["verb_analyses"]
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

                    st.markdown(
                        f"""
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

                        الlemma:
                        <span class="custom-tag">
                            {a.get('lex', 'غير محدد')}
                        </span>

                        </div>
                        """,
                        unsafe_allow_html=True
                    )


# ============================================================
# 30. التذييل
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
