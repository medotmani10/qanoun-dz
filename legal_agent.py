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
if not API_KEY:
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as _ef:
                for _line in _ef:
                    if _line.strip().startswith("GEMINI_API_KEY="):
                        API_KEY = _line.strip().split("=", 1)[1].strip()
                        break
        except Exception:
            pass
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
            "temperature": 0.0,
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

import html

def needs_web_search(query):
    """Detects whether user is asking for practical dossiers, administrative procedures, or portal links."""
    q = query.lower()
    triggers = [
        'dossier', 'ملف', 'وثائق', 'أوراق', 'pieces', 'documents', 'pièces',
        'ijraat', 'ijra2at', 'إجراءات', 'خطوات', 'process', 'procedure', 'procédure',
        'etapes', 'étapes', 'kifech ndir', 'comment faire', 'demarches', 'démarches',
        'site', 'plateforme', 'bawaba', 'موقع', 'بوابة', 'رابط', 'en ligne',
        'ana.dz', 'anae', 'casnos', 'cnas', 'cnrc', 'aapi', 'aadl'
    ]
    return any(t in q for t in triggers)

def search_algerian_web(query, max_results=3):
    """Targeted web search for Algerian administrative procedures, dossiers, and official portal guidelines."""
    try:
        data = urllib.parse.urlencode({'q': query}).encode('utf-8')
        req = urllib.request.Request(
            'https://lite.duckduckgo.com/lite/',
            data=data,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw_html = resp.read().decode('utf-8', errors='ignore')

        results = []
        links = re.findall(r'<a[^>]+href=[\'\"]([^\'\"]+)[\'\"][^>]*class=[\'\"]result-link[\'\"][^>]*>(.*?)</a>', raw_html, re.DOTALL)
        snippets = re.findall(r'<td[^>]+class=[\'\"]result-snippet[\'\"][^>]*>(.*?)</td>', raw_html, re.DOTALL)
        
        for i in range(min(len(links), len(snippets), max_results)):
            link_url, title_raw = links[i]
            snip_raw = snippets[i]
            title = html.unescape(re.sub(r'<[^>]+>', '', title_raw).strip())
            snippet = html.unescape(re.sub(r'<[^>]+>', '', snip_raw).strip())
            results.append({'title': title, 'snippet': snippet, 'url': link_url})
        return results
    except Exception:
        return []

# ========================================================
# USER PERSONAS & PROFILES ARCHITECTURE
# ========================================================
PERSONA_PROFILES = {
    'citoyen': {
        'id': 'citoyen',
        'title': 'مواطن عادي (Particulier)',
        'icon': '👤',
        'instruction': (
            "صفة وهوية المستخدم: مواطن عادي (مستهلك، ساكن، مشتري).\n"
            "- خاطبه بلغة مبسطة وواضحة جداً ومباشرة دون تعقيد أو مصطلحات فقهية غامضة.\n"
            "- ركز على حماية حقوقه اليومية والخطوات الملموسة البسيطة التي يجب أن يقوم بها."
        )
    },
    'commercant': {
        'id': 'commercant',
        'title': 'مقاول / تاجر (Entrepreneur)',
        'icon': '💼',
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
        'instruction': (
            "صفة وهوية المستخدم: محامٍ، قاضٍ، مستشار قانوني، أو طالب وباحث حقوقي متخصص.\n"
            "- تحدث معه بلغة فقهية وقضائية متخصصة ودقيقة جداً تليق بالزملاء في سلك القضاء والمحاماة.\n"
            "- اذكر التفاصيل الإجرائية (المواعيد، الاختصاص، الدفوع الشكلية والموضوعية)، وأرقام القرارات الحديثة للمحكمة العليا ومجلس الدولة، مع الإحالة الدقيقة لنصوص المواد."
        )
    }
}

def ask_legal_agent(user_query, lang="ar", history=None, user_id="default_user", persona="citoyen", current_date=None):
    """
    Main agent pipeline - 100% Dynamic AI (Zero canned or automated responses):
    - Real-time Date & Year Awareness (calculating deadlines and active legislation).
    - User Persona adaptation (citoyen, commercant, salarie, juriste).
    - Natural, intelligent legal consultation powered by Gemini + RAG.
    - Cites official legal source at bottom when legal context applies.
    """
    import datetime

    # 1. Real-time Date Parsing
    now = None
    if current_date:
        try:
            now = datetime.datetime.fromisoformat(current_date.replace('Z', '+00:00'))
        except Exception:
            now = None
    if not now:
        now = datetime.datetime.now()

    arabic_months = ['جانفي', 'فيفري', 'مارس', 'أفريل', 'ماي', 'جوان', 'جويلية', 'أوت', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
    current_date_ar = f"{now.day} {arabic_months[now.month - 1]} {now.year}"
    current_date_iso = now.strftime("%Y-%m-%d")
    current_time_str = now.strftime("%H:%M")
    current_year = now.year

    user_query_clean = user_query.strip()
    persona_key = persona if persona in PERSONA_PROFILES else 'citoyen'
    p_info = PERSONA_PROFILES[persona_key]

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
    articles = []
    jurisprudence = []
    if keywords:
        articles = search_legal_db(keywords, limit=5)
        jurisprudence = search_jurisprudence(keywords, limit=2)

    if not articles and len(search_query) > 5:
        articles = search_legal_db(search_query, limit=5)
    if not jurisprudence and len(search_query) > 5:
        jurisprudence = search_jurisprudence(search_query, limit=2)

    # Targeted Web Search for practical administrative processes, dossiers & official portals
    web_results = []
    web_str = ""
    if needs_web_search(user_query_clean) or (len(articles) == 0 and len(user_query_clean) > 8):
        search_term = keywords if keywords else user_query_clean
        web_query = f"{search_term} algerie dossier procedure"
        web_results = search_algerian_web(web_query, max_results=3)
        if not web_results and len(keywords) > 0:
            web_results = search_algerian_web(f"{keywords} algerie", max_results=3)
        if web_results:
            web_str = "\n".join([f"- **{w['title']}:** {w['snippet']} ({w['url']})" for w in web_results])
        
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

    sys_instruction = f"""أنت مستشار قانوني ومحامي جزائري ذكي وخبير في التشريع الجزائري الساري، تجيب في محادثة مباشرة وحية (Live Chat).

{p_info['instruction']}

📅 التوقيت والتاريخ الفعلي للمحادثة (مرجع أساسي للآجال وسريان القوانين):
- تاريخ اليوم: {current_date_ar} (الموافق لـ {current_date_iso})، التوقيت: {current_time_str}.
- السنة الحالية هي: {current_year}.
- يجب دائماً أن تعي أننا في سنة {current_year} (اليوم هو {current_date_ar}).
- إذا سأل المستخدم عن تاريخ اليوم، أو متى نحن، أو "هذا العام"، أجب بدقة استناداً لهذا التاريخ ({current_date_ar}).
- احسب الآجال الإجرائية (آجال الاستئناف 15 أو 30 يوماً، المعارضة 10 أيام، الطعن بالنقض شهرين، التقادم، مدة عقود العمل والإيجار) انطلاقاً من تاريخ اليوم أو التواريخ المذكورة في سؤاله.
- اعتبر دائماً أن أحدث قانون مالية ساري المفعول حالياً هو قانون المالية لسنة {current_year}، وأن أحدث التعديلات التشريعية (مثل تعديلات {current_year}) هي السارية المفعول.

قواعد صارمة للإجابة والتفاعل ومنع الاختلاق (Strict Anti-Hallucination):
1. الالتزام الصارم بالحقائق ومنع اختلاق أرقام أو نصوص وهمية:
   - ممنوع منعاً باتاً اختراع أرقام مواد، أو نسب مئوية، أو مبالغ جزافية، أو تواريخ مراسيم غير مؤكدة في السند المرفق أو القانون الجزائري الساري.
   - في المسائل التي لم يحدد فيها المشرع مبلغاً ثابتاً (مثل نفقة الأطفال، بدل سكن الحضانة، أو التعويض عن الضرر)، وضّح أن تقديرها متروك للسلطة التقديرية للقاضي بناءً على دخل الأب ومستوى المعيشة (المادة 79 من قانون الأسرة مثلاً)، دون اختراع مبلغ وهمي.
   - إذا سأل المستخدم عن ملف إداري أو وثائق مطلوبة (Dossier / Pièces à fournir / Démarches) أو خطوات عملية وبروسيس: استند إلى معلومات الويب الرسمية والممارسات الإدارية الجزائرية الحقيقية واذكر الوثائق الأساسية بوضوح وترتيب عملي، واذكر المنصة أو الموقع الرسمي المعتمد (مثل ana.dz، cnrc.org.dz، وغيرها).
   - ممنوع الخلط بين القانون الجزائري وقوانين الدول الأخرى (مثل مصر، فرنسا، أو المغرب).

2. التفاعل الطبيعي والحيوي:
   - تفاعل بذكاء، حيوية وبشكل إنساني طبيعي مع رسالة المستخدم.
   - إذا كان كلام المستخدم تحية أو دردشة أو سؤالاً عن الوقت/التاريخ: رد عليه بأسلوب لبق وطبيعي واذكر له التاريخ إذا طلبه.
   - إذا تحدث المستخدم بالدارجة الجزائرية (عربيزي أو أحرف لاتينية) أو الفرنسية أو العربية الفصحى: تفاعل معه بسلاسة بنفس لغته وسياقه الطبيعي.

3. ذكر المصدر الرسمي بدقة في الأسفل:
   ---
   📌 **المصدر:** [اسم القانون أو المرسوم، رقم المادة / الجريدة الرسمية / المنصة الرسمية المعتمدة].
"""

    user_prompt = f"""رسالة واستفسار المستخدم:
"{user_query}"

[التاريخ الحالي للمحادثة: {current_date_ar} ({current_date_iso}) - سنة {current_year}]

{f"النصوص القانونية الرسمية من قاعدة البيانات:\n{context_str}" if context_str else ""}
{f"اجتهادات المحكمة العليا:\n{jurisprudence_str}" if jurisprudence_str else ""}
{f"معلومات إجرائية وملفات إدارية من المواقع والويب الجزائري:\n{web_str}" if web_str else ""}
{f"سياق سابق للمستخدم: {memory_str}" if memory_str else ""}

أجب بذكاء وطبيعية وبشكل مباشر، مع الالتزام التام بالحقائق وتفصيل الوثائق أو الإجراءات المطلوبة إن سأل عنها."""

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
        "web_results": web_results,
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
