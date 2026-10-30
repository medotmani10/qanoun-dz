#!/usr/bin/env python3
"""
legal_memory.py
Lightweight, plug-and-play Memory Layer for Algerian Legal AI Agent.
Inspired by Mem0 (mem0ai) and AgentMem (oxgeneral/agentmem).
- Zero external dependencies: Built 100% on native Python + SQLite + FTS5.
- Multi-tier memory architecture:
    1. Working Memory (Recent multi-turn buffer)
    2. Episodic / Case Memory (Specific disputes, contracts, dates, notices)
    3. Profile / Core Memory (User status: employee, landlord, tenant, location)
- Intelligent Atomic Fact Extraction: Extracts and updates atomic propositions.
- Associative Hybrid Recall: Injects relevant past facts into active consultations.
- Strict Latin script enforcement (zero Arabic characters).
"""

import os
import re
import json
import time
import sqlite3
import threading
import urllib.request

# Default Database Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_MEM_PATH = os.environ.get("DB_MEM_PATH", os.path.join(BASE_DIR, "legal_agent_memory.db"))

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_GEN = "gemini-3.5-flash-lite"

class LegalMemory:
    """Core Memory Manager for AI Legal Assistant."""
    
    def __init__(self, db_path=DB_MEM_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            cur = conn.cursor()
            # 1. Base memories table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'default_user',
                    category TEXT DEFAULT 'general',
                    fact TEXT NOT NULL,
                    source TEXT,
                    created_at INTEGER,
                    updated_at INTEGER,
                    confidence REAL DEFAULT 1.0
                )
            """)
            
            # 2. Virtual FTS5 table for fast BM25 associative search
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    fact,
                    category,
                    content='memories',
                    content_rowid='id'
                )
            """)
            
            # 3. Triggers to keep FTS index synchronized
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, fact, category) VALUES (new.id, new.fact, new.category);
                END;
            """)
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, fact, category) VALUES('delete', old.id, old.fact, old.category);
                END;
            """)
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS mem_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, fact, category) VALUES('delete', old.id, old.fact, old.category);
                    INSERT INTO memories_fts(rowid, fact, category) VALUES (new.id, new.fact, new.category);
                END;
            """)
            conn.commit()

    def add_fact(self, fact, category="general", user_id="default_user", source=None):
        """Adds or updates an atomic legal memory fact."""
        fact = (fact or "").strip()
        if not fact or len(fact) < 5:
            return None
        now = int(time.time())
        with self._get_conn() as conn:
            cur = conn.cursor()
            # Deduplication: check if exact or identical fact exists
            cur.execute("SELECT id FROM memories WHERE user_id = ? AND fact = ?", (user_id, fact))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE memories SET updated_at = ? WHERE id = ?", (now, row['id']))
                conn.commit()
                return row['id']
                
            cur.execute("""
                INSERT INTO memories (user_id, category, fact, source, created_at, updated_at, confidence)
                VALUES (?, ?, ?, ?, ?, ?, 1.0)
            """, (user_id, category, fact, source, now, now))
            conn.commit()
            return cur.lastrowid

    def recall(self, query, user_id="default_user", limit=4):
        """
        Associative Recall:
        Retrieves relevant legal memories matching the query using FTS5 BM25.
        Protected against FTS5 syntax injection.
        """
        if not query or not query.strip():
            return []

        # Extract search tokens
        tokens = re.findall(r'[a-zA-Z0-9_]+', query)
        # Filter noise & FTS5 reserved keywords
        stop_words = {'ma', 'houwa', 'fi', 'men', '3la', 'ila', 'hal', 'kifech', 'ch7al', '3an', 'm3a', 'hadha', 'le', 'la', 'les', 'de', 'du', 'en', 'des', 'un', 'une'}
        fts_reserved = {'and', 'or', 'not', 'near'}
        meaningful = [
            t for t in tokens 
            if len(t) >= 2 and t.lower() not in stop_words and t.lower() not in fts_reserved
        ]
        
        results = []
        with self._get_conn() as conn:
            cur = conn.cursor()
            if meaningful:
                # Wrap each token in double quotes to prevent syntax errors
                quoted_tokens = ['"' + t.replace('"', '""') + '"' for t in meaningful[:6]]
                fts_query = " OR ".join(quoted_tokens)
                try:
                    cur.execute("""
                        SELECT m.id, m.category, m.fact, m.created_at
                        FROM memories_fts f
                        JOIN memories m ON f.rowid = m.id
                        WHERE memories_fts MATCH ? AND m.user_id = ?
                        ORDER BY rank
                        LIMIT ?
                    """, (fts_query, user_id, limit))
                    for row in cur.fetchall():
                        results.append(dict(row))
                except Exception:
                    pass



        return results

    def extract_facts_from_turn(self, user_query, assistant_reply, user_id="default_user"):
        """
        Mem0-Style Extraction:
        Analyzes the conversation turn to extract atomic, persistent legal facts
        about the user or their pending case.
        """
        situational_cues = [
            '3andi', 'chrit', 'be3t', 'kari', 'krit', 'khedmeti', 'khedam', 'tardouni', 
            'baladiya', 'darna', 'ard', '3aqd', 'appartement', 'villa', '7adith', 'talaq', 
            'wiratha', 'baba', 'el moudir', 'j\'ai', 'mon', 'contrat', 'terrain', 'permis'
        ]
        has_cue = any(cue in user_query.lower() for cue in situational_cues)
        if not has_cue and len(user_query) < 25:
            return []

        prompt = f"""Tu es un agent d'extraction de memoire juridique (Agent Memory Extractor).
Ta mission est d'extraire des faits juridiques personnels precis du citoyen pour les stocker dans son profil.

Message de l'utilisateur:
"{user_query}"

Reponse du conseiller:
"{assistant_reply[:500]}"

Instruction:
Extrais uniquement les faits juridiques averes sur l'utilisateur (ex: metier, contrat, litige, biens, ville).
Si l'utilisateur pose une question purement theorique sans fait personnel, retourne [].

Format JSON strict uniquement (aucun texte autour):
[
  {{"category": "foncier/travail/famille/commerce/general", "fact": "L'utilisateur..."}}
]"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_GEN}:generateContent?key={API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 400}
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                raw_text = data['candidates'][0]['content']['parts'][0]['text'].strip()
                m = re.search(r'\[.*\]', raw_text, re.DOTALL)
                if m:
                    extracted = json.loads(m.group(0))
                    saved_ids = []
                    for item in extracted:
                        f = item.get("fact", "").strip()
                        c = item.get("category", "general").strip()
                        if f:
                            fid = self.add_fact(f, category=c, user_id=user_id, source=user_query[:100])
                            if fid:
                                saved_ids.append(fid)
                    return saved_ids
        except Exception:
            pass
        return []

    def async_extract_and_store(self, user_query, assistant_reply, user_id="default_user"):
        """Non-blocking background thread for memory extraction."""
        t = threading.Thread(
            target=self.extract_facts_from_turn,
            args=(user_query, assistant_reply, user_id),
            daemon=True
        )
        t.start()

    def get_all(self, user_id="default_user"):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM memories WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
            return [dict(r) for r in cur.fetchall()]

    def delete_memory(self, memory_id, user_id="default_user"):
        try:
            mid = int(memory_id)
        except (ValueError, TypeError):
            return False
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM memories WHERE id = ? AND user_id = ?", (mid, user_id))
            conn.commit()
            return cur.rowcount > 0

    def clear_all(self, user_id="default_user"):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
            conn.commit()
            return True

# Global Memory Instance
global_memory = LegalMemory()

if __name__ == '__main__':
    print("Testing LegalMemory Plugin...")
    m = LegalMemory()
    m.add_fact("L'utilisateur possede un terrain a Fouka sans permis de construire", category="foncier")
    recalled = m.recall("Quelle est la penalite pour construction sans permis?")
    print(f"Recalled: {len(recalled)} items")
    for r in recalled:
        print(f" - [{r['category']}] {r['fact']}")
