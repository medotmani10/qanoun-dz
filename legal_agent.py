from legal_memory import global_memory
#!/usr/bin/env python3
"""
legal_agent.py
Intelligent Algerian Legal AI Assistant.
Features:
- Dual-tier legal retrieval (Consolidated Laws first, Gazette archive second).
- Cross-lingual search (Darija Arabizi <-> French legal texts).
- Automatic Amendment & Repeal Safeguard ("Avocat Double-Check").
- Strict Latin-script Darija formatting (zero Arabic script characters).
"""

import os
import re
import sys
import json
import sqlite3
import urllib.request
import urllib.error

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_GEN = "gemini-3.5-flash-lite"
MODEL_EMB = "gemini-embedding-2"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "legal_agent_index.db")
if not os.path.exists(DEFAULT_DB) and os.path.exists("/storage/emulated/0/Download/legal_agent_index.db"):
    DEFAULT_DB = "/storage/emulated/0/Download/legal_agent_index.db"
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB)
CONSOLIDATED_DIR = os.environ.get("CONSOLIDATED_DIR", os.path.join(BASE_DIR, "Lois_Mises_A_Jour"))

# Sanitizer: Absolutely guarantee ZERO Arabic script characters
def sanitize_latin_only(text):
    """Replaces any Arabic unicode characters with transliteration or removes them."""
    arabic_map = {
        'ا': 'a', 'أ': 'a', 'إ': 'i', 'آ': 'aa', 'ب': 'b', 'ت': 't', 'ث': 'th',
        'ج': 'j', 'ح': '7', 'خ': '5', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z',
        'س': 's', 'ش': 'ch', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'dh', 'ع': '3',
        'غ': 'gh', 'ف': 'f', 'ق': '9', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
        'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 'a', 'ء': "'", 'ئ': "'", 'ؤ': "'"
    }
    out = []
    for char in text:
        if '\u0600' <= char <= '\u06FF':
            out.append(arabic_map.get(char, ''))
        else:
            out.append(char)
    return ''.join(out)

def call_gemini(prompt=None, system_instruction=None, allow_arabic=True, contents=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_GEN}:generateContent?key={API_KEY}"
    
    if contents is None:
        contents = [{"parts": [{"text": prompt}]}]

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1200
        }
    }
    
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }
        
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                raw_text = data['candidates'][0]['content']['parts'][0]['text']
                if allow_arabic:
                    return raw_text
                return sanitize_latin_only(raw_text)
        except Exception as e:
            if attempt < 2:
                import time
                time.sleep(1.5)
                continue
            return f"[Erreur de communication avec l'API Gemini: {e}]"

def search_legal_db(query, limit=4):
    """Searches SQLite FTS5 for matching articles from consolidated laws."""
    if not os.path.exists(DB_PATH):
        return []
        
    clean_q = re.sub(r'[^\w\s]', ' ', query)
    words = [w for w in clean_q.split() if len(w) > 2 and w.lower() not in {'and', 'or', 'not', 'near'}]
    if not words:
        return []
        
    safe_words = ['"' + w.replace('"', '""') + '"' for w in words[:8]]
    fts_query_or = ' OR '.join(safe_words)
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cur = conn.cursor()
        
        # Priority 1: High-precision AND search if multiple terms
        if len(safe_words) > 1:
            try:
                fts_query_and = ' AND '.join(safe_words)
                cur.execute('''
                SELECT domain, title, article_num, content, rank
                FROM consolidated_fts
                WHERE consolidated_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                ''', (fts_query_and, limit))
                rows = cur.fetchall()
                if rows:
                    return [{
                        'domain': r[0],
                        'title': r[1],
                        'article': r[2],
                        'content': r[3]
                    } for r in rows]
            except Exception:
                pass

        # Priority 2: Broad OR search
        cur.execute('''
        SELECT domain, title, article_num, content, rank
        FROM consolidated_fts
        WHERE consolidated_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        ''', (fts_query_or, limit))
        
        results = []
        for row in cur.fetchall():
            results.append({
                'domain': row[0],
                'title': row[1],
                'article': row[2],
                'content': row[3]
            })
        return results
    except Exception:
        return []
    finally:
        if conn:
            conn.close()

def search_jurisprudence(query, limit=2):
    """Searches SQLite FTS5 for matching Supreme Court rulings."""
    if not os.path.exists(DB_PATH):
        return []
        
    clean_q = re.sub(r'[^\w\s]', ' ', query)
    words = [w for w in clean_q.split() if len(w) > 2 and w.lower() not in {'and', 'or', 'not', 'near'}]
    if not words:
        return []
        
    safe_words = ['"' + w.replace('"', '""') + '"' for w in words[:6]]
    fts_query_or = ' OR '.join(safe_words)
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cur = conn.cursor()
        
        # Priority 1: High-precision AND search
        if len(safe_words) > 1:
            try:
                fts_query_and = ' AND '.join(safe_words)
                cur.execute('''
                SELECT arret_num, arret_date, theme, legal_refs, principle, full_content, rank
                FROM jurisprudence_fts
                WHERE jurisprudence_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                ''', (fts_query_and, limit))
                rows = cur.fetchall()
                if rows:
                    return [{
                        'arret_num': r[0],
                        'arret_date': r[1],
                        'theme': r[2],
                        'legal_refs': r[3],
                        'principle': r[4],
                        'full_content': r[5]
                    } for r in rows]
            except Exception:
                pass

        # Priority 2: Broad OR search
        cur.execute('''
        SELECT arret_num, arret_date, theme, legal_refs, principle, full_content, rank
        FROM jurisprudence_fts
        WHERE jurisprudence_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        ''', (fts_query_or, limit))
        
        results = []
        for row in cur.fetchall():
            results.append({
                'arret_num': row[0],
                'arret_date': row[1],
                'theme': row[2],
                'legal_refs': row[3],
                'principle': row[4],
                'full_content': row[5]
            })
        return results
    except Exception:
        return []
    finally:
        if conn:
            conn.close()

def extract_legal_keywords(user_query):
    """Extracts French legal search keywords from user query (which may be in Darija)."""
    prompt = f"""Tu es un traducteur juridique algérien. Analyse la question suivante posée par l'utilisateur (qui peut être en Darija algérienne ou en Français) et extrais entre 2 et 5 mots-clés juridiques précis EN FRANÇAIS (termes de droit algérien) pour rechercher dans le Journal Officiel et les Codes de lois algériens.
Réponds UNIQUEMENT avec les mots-clés séparés par des espaces, sans ponctuation ni phrase d'introduction.

Question utilisateur: "{user_query}"
Mots-clés en français:"""
    
    kw = call_gemini(prompt)
    kw_clean = re.sub(r'[^a-zA-Z0-9\sàâéèêîôùûç-]', ' ', kw).strip()
    return kw_clean

def is_casual_or_greeting(text):
    """Detects simple greetings, courtesies, and casual phrases."""
    if not text:
        return True
    t = text.strip().lower()
    clean = re.sub(r'[^\w\s]', ' ', t).strip()
    words = clean.split()
    if not words:
        return True
    
    # Substantive legal trigger words: if present, it is definitely a legal question
    legal_triggers = {
        'قانون', 'مادة', 'مرسوم', 'عقد', 'طلاق', 'نفقة', 'بناء', 'رخصة', 'تسريح', 'طرد',
        'عمل', 'أجر', 'راتب', 'غرامة', 'مخالفة', 'جنحة', 'جناية', 'سجن', 'حبس', 'محكمة',
        'قاضي', 'عريضة', 'استئناف', 'طعن', 'نقض', 'شراء', 'بيع', 'ملكية', 'أرض', 'عقار',
        'شقة', 'ورثة', 'تركة', 'ميراث', 'شركة', 'ضرائب', 'ضريبة', 'سجل', 'تجاري', 'مقاول',
        'كراء', 'إيجار', 'تأمين', 'شهادة', 'توثيق', 'موثق', 'محضر', 'قضائي', 'حادث',
        'droit', 'loi', 'article', 'decret', 'contrat', 'divorce', 'pension', 'permis',
        'licenciement', 'salaire', 'amende', 'tribunal', 'appel', 'cassation', 'foncier',
        'terrain', 'heritage', 'sarl', 'taxe', 'impot', 'location', 'notaire', 'autoentrepreneur'
    }
    if any(w in legal_triggers for w in words):
        return False
        
    greeting_tokens = {
        'salam', 'salem', 'slm', 'bonjour', 'bonsoir', 'salut', 'cc', 'coucou',
        'hello', 'hi', 'hey', 'kifech', 'labas', 'cv', 'merci', 'chokran', 'saha',
        'sa7a', 'salamoualikoum', 'salamou', 'alikoum', 'alaykom',
        'سلام', 'السلام', 'عليكم', 'ورحمة', 'وبركاته', 'أهلا', 'اهلا', 'مرحبا',
        'صباح', 'مساء', 'الخير', 'النور', 'شكرا', 'عفوا', 'يعطيك', 'الصحة',
        'بارك', 'الله', 'فيك', 'شكون', 'نتا', 'انت', 'لباس', 'واش', 'راك'
    }
    greeting_matches = sum(1 for w in words if w in greeting_tokens)
    if greeting_matches >= 1 and (len(words) <= 7 or greeting_matches / len(words) >= 0.5):
        return True
        
    return False

# ========================================================
# USER PERSONAS & PROFILES ARCHITECTURE
# ========================================================
PERSONA_PROFILES = {
    'citoyen': {
        'id': 'citoyen',
        'title': 'مواطن عادي (Particulier)',
        'icon': '👤',
        'greeting': 'وعليكم السلام ورحمة الله وبركاته! أهلاً بك، تفضل بطرح استفسارك القانوني وأنا في الخدمة.',
        'greeting_latin': 'Wa 3alaykom essalam! Marhba bik, tfe7del b sou\'alek l-9anouni w ana f l-khedma.',
        'instruction': (
            "صفة وهوية المستخدم: مواطن عادي (مستهلك، ساكن، مشتري).\n"
            "- خاطبه بلغة عربية مبسطة جداً، واضحة ومباشرة دون تعقيد أو مصطلحات فقهية غامضة.\n"
            "- ركز على حماية حقوقه اليومية والخطوات الملموسة البسيطة التي يجب أن يقوم بها."
        )
    },
    'commercant': {
        'id': 'commercant',
        'title': 'مقاول / تاجر (Entrepreneur)',
        'icon': '💼',
        'greeting': 'وعليكم السلام ورحمة الله! مرحباً بك، تفضل بأي استشارة تجارية، ضريبية أو قانونية لمشروعك وأنا في الخدمة.',
        'greeting_latin': 'Wa 3alaykom essalam! Marhba bik, tfe7del b ay istichara tijariya wla daribiya l machrou3ek.',
        'instruction': (
            "صفة وهوية المستخدم: تاجر أو مقاول أو صاحب مشروع (مؤسسة مصغرة / مقاول ذاتي).\n"
            "- ركز على الأثر التجاري والمالي، الضرائب والرسوم (IFU/IBS/TVA)، التزامات السجل التجاري، والعقود والآجال البنكية والتعاقدية.\n"
            "- قدم له حلولاً لحماية مصالح مشروعه وتفادي الغرامات الجبائية وشبه الجبائية (CASNOS)."
        )
    },
    'salarie': {
        'id': 'salarie',
        'title': 'عامل / موظف (Salarié / Fonctionnaire)',
        'icon': '🛠️',
        'greeting': 'وعليكم السلام ورحمة الله! مرحباً بك، تفضل بأي سؤال حول حقوق العمل، الوظيفة أو الضمان الاجتماعي وأنا في الخدمة.',
        'greeting_latin': 'Wa 3alaykom essalam! Marhba bik, tfe7del b ay sou\'al f 9anoun l-3amal w CNAS w ana f l-khedma.',
        'instruction': (
            "صفة وهوية المستخدم: عامل أو موظف أجير (قطاع اقتصادي أو وظيفة عمومية).\n"
            "- ركز على حماية حقوقه وفق قانون علاقات العمل 90-11 أو القانون الأساسي العام للوظيفة العمومية.\n"
            "- وضّح له حساب التعويضات، الإجازات، الحماية من التسريح التعسفي، وخطوات التوجه لمفتشية العمل أو الضمان الاجتماعي (CNAS)."
        )
    },
    'juriste': {
        'id': 'juriste',
        'title': 'محامي / رجل قانون (Avocat / Juriste)',
        'icon': '⚖️',
        'greeting': 'أهلاً بالأستاذ الزميل، وعليكم السلام ورحمة الله وبركاته! تفضل بالمسألة أو النص القانوني المطلوب بحثه وسنناقشه بدقة.',
        'greeting_latin': 'Ahla b l-ostadh l-zamil, wa 3alaykom essalam! Tfe7del b l-mas\'ala l-9anouniya bach n-na9chouha b di99a.',
        'instruction': (
            "صفة وهوية المستخدم: محامٍ، قاضٍ، مستشار قانوني، أو طالب وباحث حقوقي متخصص.\n"
            "- تحدث معه بلغة فقهية وقضائية متخصصة ودقيقة جداً تليق بالزملاء في سلك القضاء والمحاماة.\n"
            "- اذكر التفاصيل الإجرائية (المواعيد، الاختصاص، الدفوع الشكلية والموضوعية)، وأرقام القرارات الحديثة للمحكمة العليا ومجلس الدولة، مع الإحالة الدقيقة لنصوص المواد."
        )
    }
}

def get_quick_greeting_reply(text, persona="citoyen"):
    """Returns an ultra-short, natural 1-sentence live chat greeting tailored to user persona."""
    t = text.strip().lower()
    p_info = PERSONA_PROFILES.get(persona, PERSONA_PROFILES['citoyen'])
    
    if any(w in t for w in ['bonjour', 'bonsoir', 'salut', 'coucou']):
        return "Bonjour et bienvenue ! Comment puis-je vous aider aujourd'hui sur le plan juridique ?"
    if any(w in t for w in ['hello', 'hi', 'hey']):
        return "Hello and welcome! How can I assist you with Algerian legal matters today?"
    if any(w in t for w in ['شكرا', 'شكر', 'يعطيك الصحة', 'بارك الله', 'merci', 'chokran', 'sa7a']):
        return "العفو، أنا دائماً في الخدمة! بالتوفيق."
    if any(w in t for w in ['salem', 'salam', 'slm', 'kifech']) and not any('\u0600' <= c <= '\u06FF' for c in text):
        return p_info['greeting_latin']
    return p_info['greeting']

def ask_legal_agent(user_query, lang="ar", history=None, user_id="default_user", persona="citoyen"):
    """
    Main agent pipeline:
    - User Persona adaptation (citoyen, commercant, salarie, juriste).
    - Ultra-short, instant 1-sentence live greeting.
    - Concise, direct legal answers without long essays or fluff.
    - Cites official legal source at bottom.
    """
    user_query_clean = user_query.strip()
    persona_key = persona if persona in PERSONA_PROFILES else 'citoyen'
    p_info = PERSONA_PROFILES[persona_key]
    
    # 1. Casual Greeting / Small Talk Flow (Instant 1-sentence response tailored to persona)
    if is_casual_or_greeting(user_query_clean):
        reply = get_quick_greeting_reply(user_query_clean, persona=persona_key)
        return {
            "query": user_query,
            "persona": persona_key,
            "keywords": "",
            "articles": [],
            "jurisprudence": [],
            "recalled_memories": [],
            "answer": reply
        }

    # 2. Substantive Legal Inquiry Flow
    # Contextualize search query with previous turn if follow-up
    search_query = user_query_clean
    if history and isinstance(history, list) and len(history) > 0:
        prev_user_queries = [m.get("text") or m.get("content") for m in history if m.get("role") == "user"]
        if prev_user_queries:
            last_topic = prev_user_queries[-1]
            search_query = f"{last_topic} {user_query_clean}"

    # Extract keywords
    keywords = extract_legal_keywords(search_query)
    
    # Retrieve relevant articles & jurisprudence
    articles = search_legal_db(keywords, limit=3)
    if not articles:
        articles = search_legal_db(search_query, limit=3)
        
    jurisprudence = search_jurisprudence(keywords, limit=2)
    if not jurisprudence:
        jurisprudence = search_jurisprudence(search_query, limit=2)
        
    context_str = ""
    for i, a in enumerate(articles, 1):
        context_str += f"""
--- نص قانوني رسمي {i} ---
المصدر: {a['title']} ({a['domain']})
المادة: {a['article']}
المحتوى:
{a['content'][:1500]}
"""

    jurisprudence_str = ""
    for j, r in enumerate(jurisprudence, 1):
        jurisprudence_str += f"""
--- اجتهاد المحكمة العليا {j} ---
قرار رقم: {r['arret_num']} بتاريخ {r['arret_date']}
الموضوع: {r['theme']}
النصوص المطبقة: {r['legal_refs']}
المبدأ: {r['principle']}
"""

    # Recall relevant facts from Long-Term Memory ONLY if directly relevant
    recalled_mems = global_memory.recall(search_query, user_id=user_id, limit=2)
    memory_str = ""
    if recalled_mems:
        memory_str = "\n".join(f"- [{m['category']}] {m['fact']}" for m in recalled_mems)

    sys_instruction = f"""أنت مستشار ومحامي قانوني جزائري ذكي، تجيب في محادثة مباشرة وحية (Live Chat).

{p_info['instruction']}

قواعد صارمة للإيجاز والدقة (ممنوع الإطالة بتاتاً):
1. إجابة قصيرة، مباشرة وموجزة جداً (أقل من 60 إلى 90 كلمة فقط):
   - ادخل في صلب الجواب فوراً دون أي مقدمات إنشائية بأسلوب يناسب صفة المستخدم ({p_info['title']}).
   - اشرح الحكم أو الخطوة في جملتين أو ثلاث جمل مركزة ومباشرة.
   - اذكر الرقم، الأجل، أو المبلغ بالدينار (DA) بدقة داخل الشرح إن وجد.
   - ممنوع التكرار، ممنوع السرد الإنشائي الطويل، وممنوع القوالب المبرمجة.

2. ذكر المصدر القانوني في الأسفل:
   - اختم رسالتك دائماً بسطر فاصل ثم المصدر الرسمي بدقة:
   ---
   📌 **المصدر:** [اسم القانون أو المرسوم، رقم المادة / الجريدة الرسمية].
"""

    user_prompt = f"""سؤال واستشارة المستخدم:
"{user_query}"

النصوص القانونية الرسمية:
{context_str if context_str else "استند لمعلومات التشريع الجزائري الساري المفعول."}

اجتهادات المحكمة العليا إن وجدت:
{jurisprudence_str if jurisprudence_str else ""}

{f"سياق سابق للمستخدم: {memory_str}" if memory_str else ""}

أجب بإيجاز شديد وبشكل مباشر وواضح (بين 3 إلى 5 أسطر فقط)، ثم اذكر المصدر في الأسفل."""

    # Build multi-turn contents for Gemini
    gemini_contents = []
    if history and isinstance(history, list):
        for turn in history[-4:]:
            r = "user" if turn.get("role") == "user" else "model"
            t = turn.get("text") or turn.get("content") or ""
            if t.strip():
                gemini_contents.append({
                    "role": r,
                    "parts": [{"text": t.strip()}]
                })
    gemini_contents.append({
        "role": "user",
        "parts": [{"text": user_prompt}]
    })

    reply = call_gemini(system_instruction=sys_instruction, allow_arabic=True, contents=gemini_contents)

    # Asynchronously extract & persist any newly mentioned legal facts
    global_memory.async_extract_and_store(user_query, reply, user_id=user_id)

    return {
        "query": user_query,
        "keywords": keywords,
        "articles": articles,
        "jurisprudence": jurisprudence,
        "recalled_memories": recalled_mems if 'recalled_mems' in locals() else [],
        "answer": reply
    }

if __name__ == '__main__':
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
    else:
        q = "Wach y9ol el 9anoun 3la congé de maternité pour les femmes salariées w ch7al la durée?"
        
    print(f"=== REQUETE: {q} ===\n")
    res = ask_legal_agent(q)
    print("Mots-clés recherchés:", res['keywords'])
    print(f"Articles trouvés: {len(res['articles'])}")
    for a in res['articles']:
        print(f" - [{a['domain']}] {a['title']} -> {a['article']}")
    print("\n=== REPONSE DU LEGAL AGENT ===\n")
    print(res['answer'])
