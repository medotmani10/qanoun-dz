#!/usr/bin/env python3
"""
library_service.py
Provides ultra-fast, optimized access to the 59 Algerian Laws (6,012 Articles)
and 89 Supreme Court Jurisprudence decisions in legal_agent_index.db.
Features:
- In-memory caching of high-frequency metadata (overview, law counts).
- Lazy loading & pagination for articles (limit/offset).
- Instant search with fallback matching.
"""

import os
import sqlite3
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "legal_agent_index.db")
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB)

DOMAIN_MAP = {
    '01_Constitutionnel_et_Admin': {'key': 'constitutionnel', 'title_ar': 'القانون الدستوري والوظيفة العمومية', 'icon': '📜', 'color': 'slate', 'desc_ar': 'الدستور، قانون البلدية والولاية، والوظيفة العمومية.'},
    'Jurisprudence et Justice Administrative': {'key': 'constitutionnel', 'title_ar': 'القانون الدستوري والوظيفة العمومية', 'icon': '📜', 'color': 'slate', 'desc_ar': 'الدستور، قانون البلدية والولاية، والوظيفة العمومية.'},
    '02_Civil_et_Justice': {'key': 'civil', 'title_ar': 'القانون المدني والإجراءات القضائية', 'icon': '⚖️', 'color': 'emerald', 'desc_ar': 'قانون الإجراءات المدنية والإدارية CPCA، القانون المدني، والتنظيم القضائي.'},
    'Civil et Justice': {'key': 'civil', 'title_ar': 'القانون المدني والإجراءات القضائية', 'icon': '⚖️', 'color': 'emerald', 'desc_ar': 'قانون الإجراءات المدنية والإدارية CPCA، القانون المدني، والتنظيم القضائي.'},
    '03_Penal_et_Securite': {'key': 'penal', 'title_ar': 'القانون الجزائي ومكافحة الجريمة', 'icon': '🛡️', 'color': 'rose', 'desc_ar': 'إصلاح قانون العقوبات 2024، الإجراءات الجزائية، ومكافحة الفساد.'},
    '04_Affaires_Commerce_Investissement': {'key': 'commerce', 'title_ar': 'التجارة، الشركات والاستثمار', 'icon': '💼', 'color': 'blue', 'desc_ar': 'قانون الاستثمار، الصفقات العمومية، الشركات التجارية، والمقاول الذاتي.'},
    'Affaires, Commerce et Investissement': {'key': 'commerce', 'title_ar': 'التجارة، الشركات والاستثمار', 'icon': '💼', 'color': 'blue', 'desc_ar': 'قانون الاستثمار، الصفقات العمومية، الشركات التجارية، والمقاول الذاتي.'},
    '05_Travail_et_Social': {'key': 'travail', 'title_ar': 'قانون العمل والضمان الاجتماعي', 'icon': '🤝', 'color': 'indigo', 'desc_ar': 'علاقات العمل 90-11، الحق النقابي، الإضراب، وعطلة الأمومة.'},
    '06_Fiscal_et_Douanes': {'key': 'fiscal', 'title_ar': 'المالية، الضرائب والجمارك', 'icon': '📊', 'color': 'cyan', 'desc_ar': 'قوانين المالية 2024-2026، قانون الجمارك، والإعفاءات الضريبية.'},
    'Fiscal et Douanes': {'key': 'fiscal', 'title_ar': 'المالية، الضرائب والجمارك', 'icon': '📊', 'color': 'cyan', 'desc_ar': 'قوانين المالية 2024-2026، قانون الجمارك، والإعفاءات الضريبية.'},
    '07_Famille_et_Etat_Civil': {'key': 'famille', 'title_ar': 'شؤون الأسرة والحالة المدنية', 'icon': '👨‍👩‍👧', 'color': 'violet', 'desc_ar': 'قانون الأسرة، الجنسية الجزائرية، وصندوق النفقة.'},
    '08_Foncier_Urbanisme_Immobilier': {'key': 'foncier', 'title_ar': 'القانون العقاري والتعمير', 'icon': '🏛️', 'color': 'amber', 'desc_ar': 'حماية أراضي الدولة 23-18، مطابقة البنايات 08-15، والعقار الصناعي.'},
    '09_Sante_Route_Environnement': {'key': 'sante_route', 'title_ar': 'الصحة، المرور والبيئة', 'icon': '🚗', 'color': 'teal', 'desc_ar': 'قانون الصحة، قانون المرور الجديد، وحماية البيئة.'},
    'Sante, Route et Environnement': {'key': 'sante_route', 'title_ar': 'الصحة، المرور والبيئة', 'icon': '🚗', 'color': 'teal', 'desc_ar': 'قانون الصحة، قانون المرور الجديد، وحماية البيئة.'}
}

_thread_local = threading.local()
_cache_lock = threading.Lock()
_overview_cache = None

def get_db():
    if not hasattr(_thread_local, 'conn') or _thread_local.conn is None:
        _thread_local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _thread_local.conn.row_factory = sqlite3.Row
    return _thread_local.conn

def get_library_overview():
    """Returns overall library stats and the 9 verified domains with accurate counts."""
    global _overview_cache
    with _cache_lock:
        if _overview_cache is not None:
            return _overview_cache

    conn = get_db()
    c = conn.cursor()

    rows = c.execute('SELECT domain, title, count(*) FROM consolidated_laws GROUP BY domain, title').fetchall()
    
    cats = {}
    for d_raw, meta in DOMAIN_MAP.items():
        k = meta['key']
        if k not in cats:
            cats[k] = {
                'key': k,
                'title_ar': meta['title_ar'],
                'icon': meta['icon'],
                'color': meta['color'],
                'desc_ar': meta['desc_ar'],
                'laws_count': 0,
                'articles_count': 0,
                'raw_domains': set()
            }
        cats[k]['raw_domains'].add(d_raw)

    for r in rows:
        dom = r[0]
        cnt = r[2]
        cat_meta = DOMAIN_MAP.get(dom)
        if cat_meta:
            k = cat_meta['key']
            cats[k]['laws_count'] += 1
            cats[k]['articles_count'] += cnt

    tot_arts = sum(cat['articles_count'] for cat in cats.values())
    tot_laws = sum(cat['laws_count'] for cat in cats.values())
    tot_juris = c.execute('SELECT count(*) FROM jurisprudence').fetchone()[0]

    categories_list = []
    # Order categories logically
    ordered_keys = ['civil', 'penal', 'foncier', 'commerce', 'travail', 'fiscal', 'constitutionnel', 'famille', 'sante_route']
    for k in ordered_keys:
        if k in cats:
            item = dict(cats[k])
            item['raw_domains'] = list(item['raw_domains'])
            categories_list.append(item)

    data = {
        'status': 'ok',
        'total_articles': tot_arts,
        'total_laws': tot_laws,
        'total_jurisprudence': tot_juris,
        'categories': categories_list
    }

    with _cache_lock:
        _overview_cache = data

    return data

def get_library_laws(domain_key=None, search=None):
    """Returns list of distinct laws with article counts, filtered by domain or search."""
    conn = get_db()
    c = conn.cursor()

    params = []
    where_clauses = []

    if domain_key:
        matched_raw = [d for d, m in DOMAIN_MAP.items() if m['key'] == domain_key]
        if matched_raw:
            placeholders = ','.join(['?'] * len(matched_raw))
            where_clauses.append(f"domain IN ({placeholders})")
            params.extend(matched_raw)

    if search:
        s_clean = search.strip()
        where_clauses.append("(title LIKE ? OR domain LIKE ?)")
        params.extend([f"%{s_clean}%", f"%{s_clean}%"])

    sql = "SELECT title, domain, count(*) as art_count FROM consolidated_laws"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " GROUP BY title ORDER BY art_count DESC"

    rows = c.execute(sql, params).fetchall()
    laws = []
    for r in rows:
        title = r['title']
        dom = r['domain']
        count = r['art_count']
        cat_meta = DOMAIN_MAP.get(dom, {})
        laws.append({
            'title': title,
            'domain_raw': dom,
            'domain_key': cat_meta.get('key', 'autre'),
            'domain_title_ar': cat_meta.get('title_ar', dom),
            'articles_count': count
        })

    return {'status': 'ok', 'count': len(laws), 'laws': laws}

def get_library_articles(law_title=None, domain_key=None, search=None, limit=25, offset=0):
    """Lazy-loaded pagination for law articles."""
    conn = get_db()
    c = conn.cursor()

    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))

    params = []
    where_clauses = []

    if law_title:
        where_clauses.append("title = ?")
        params.append(law_title.strip())
    elif domain_key:
        matched_raw = [d for d, m in DOMAIN_MAP.items() if m['key'] == domain_key]
        if matched_raw:
            placeholders = ','.join(['?'] * len(matched_raw))
            where_clauses.append(f"domain IN ({placeholders})")
            params.extend(matched_raw)

    if search and search.strip():
        s = search.strip()
        where_clauses.append("(article_num LIKE ? OR content LIKE ?)")
        params.extend([f"%{s}%", f"%{s}%"])

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Total count
    count_sql = f"SELECT count(*) FROM consolidated_laws{where_sql}"
    total = c.execute(count_sql, params).fetchone()[0]

    # Fetch page
    fetch_sql = f"""
        SELECT id, domain, title, article_num, content 
        FROM consolidated_laws{where_sql} 
        ORDER BY id ASC 
        LIMIT ? OFFSET ?
    """
    fetch_params = list(params) + [limit, offset]
    rows = c.execute(fetch_sql, fetch_params).fetchall()

    articles = []
    for r in rows:
        articles.append({
            'id': r['id'],
            'domain': r['domain'],
            'title': r['title'],
            'article_num': r['article_num'],
            'content': r['content']
        })

    return {
        'status': 'ok',
        'total': total,
        'offset': offset,
        'limit': limit,
        'has_more': (offset + len(articles)) < total,
        'articles': articles
    }

def get_library_jurisprudence(search=None, limit=20, offset=0):
    """Returns Supreme Court decisions with lazy loading."""
    conn = get_db()
    c = conn.cursor()

    limit = max(1, min(50, int(limit)))
    offset = max(0, int(offset))

    params = []
    where_clauses = []

    if search and search.strip():
        s = search.strip()
        where_clauses.append("(theme LIKE ? OR principle LIKE ? OR arret_num LIKE ? OR legal_refs LIKE ?)")
        params.extend([f"%{s}%", f"%{s}%", f"%{s}%", f"%{s}%"])

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    total = c.execute(f"SELECT count(*) FROM jurisprudence{where_sql}", params).fetchone()[0]

    fetch_sql = f"""
        SELECT id, arret_num, arret_date, theme, legal_refs, dispositif, principle, full_content 
        FROM jurisprudence{where_sql} 
        ORDER BY id ASC 
        LIMIT ? OFFSET ?
    """
    rows = c.execute(fetch_sql, list(params) + [limit, offset]).fetchall()

    items = []
    for r in rows:
        items.append({
            'id': r['id'],
            'arret_num': r['arret_num'],
            'arret_date': r['arret_date'],
            'theme': r['theme'],
            'legal_refs': r['legal_refs'],
            'dispositif': r['dispositif'],
            'principle': r['principle'],
            'full_content': r['full_content']
        })

    return {
        'status': 'ok',
        'total': total,
        'offset': offset,
        'limit': limit,
        'has_more': (offset + len(items)) < total,
        'items': items
    }
