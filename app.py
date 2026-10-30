#!/usr/bin/env python3
"""
legal_web_server.py
Lightweight, mobile-first web interface for the Algerian Legal AI Agent.
Runs locally on Android Termux at http://localhost:8080 (or 0.0.0.0:8080).
Adheres strictly to Mobile-First & Light Mode UI guidelines.
"""

import http.server
import socketserver
import json
import urllib.parse
import os
import sys
from legal_agent import ask_legal_agent
from legal_memory import global_memory
import library_service

PORT = int(os.environ.get("PORT", 8080))

HTML_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Qanoun DZ - Agent Juridique IA</title>
    <style>
        :root {
            --bg-color: #FFFFFF;
            --surface-color: #F8FAFC;
            --card-bg: #FFFFFF;
            --border-color: #E2E8F0;
            --text-primary: #0F172A;
            --text-secondary: #475569;
            --accent-green: #0D9488;
            --accent-blue: #2563EB;
            --badge-bg: #F0FDF4;
            --badge-border: #BBF7D0;
            --badge-text: #166534;
            --radius-md: 12px;
            --radius-lg: 16px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.5;
            overflow-x: hidden;
            padding-bottom: env(safe-area-inset-bottom, 24px);
        }

        .container {
            width: 100%;
            max-width: 480px;
            margin: 0 auto;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            padding: 16px;
        }

        /* Top Header */
        header {
            padding: 12px 0 16px 0;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .logo-area {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .logo-icon {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, #0D9488, #059669);
            color: #FFFFFF;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
        }

        .logo-title {
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.2;
        }

        .logo-subtitle {
            font-size: 11px;
            color: var(--text-secondary);
            font-weight: 500;
        }

        .status-badge {
            background-color: var(--badge-bg);
            border: 1px solid var(--badge-border);
            color: var(--badge-text);
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 20px;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #16A34A;
        }

        /* Hero / Stats Banner */
        .stats-banner {
            margin: 16px 0;
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            display: flex;
            justify-content: space-around;
            text-align: center;
        }

        .stat-item .val {
            font-size: 16px;
            font-weight: 700;
            color: var(--accent-green);
        }

        .stat-item .lbl {
            font-size: 11px;
            color: var(--text-secondary);
        }

        /* Suggestions chips */
        .chips-scroll {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding-bottom: 8px;
            margin-bottom: 12px;
            scrollbar-width: none;
        }
        .chips-scroll::-webkit-scrollbar {
            display: none;
        }

        .chip {
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-secondary);
            white-space: nowrap;
            cursor: pointer;
            transition: all 0.2s;
        }

        .chip:active {
            background: #E2E8F0;
            transform: scale(0.97);
        }

        /* Search input card */
        .search-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.03);
            margin-bottom: 16px;
        }

        .input-box {
            width: 100%;
            min-height: 80px;
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 12px;
            font-size: 14px;
            color: var(--text-primary);
            resize: none;
            outline: none;
            font-family: inherit;
            background: #FAFAFA;
        }

        .input-box:focus {
            border-color: var(--accent-green);
            background: #FFFFFF;
        }

        .search-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 10px;
        }

        .lang-hint {
            font-size: 11px;
            color: var(--text-secondary);
        }

        .submit-btn {
            background: var(--accent-green);
            color: #FFFFFF;
            border: none;
            border-radius: var(--radius-md);
            min-height: 44px;
            padding: 0 20px;
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            cursor: pointer;
            transition: opacity 0.2s;
        }

        .submit-btn:active {
            opacity: 0.85;
        }

        /* Results Area */
        #loadingSpinner {
            display: none;
            text-align: center;
            padding: 30px 0;
            color: var(--text-secondary);
            font-size: 13px;
        }

        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid var(--border-color);
            border-top: 3px solid var(--accent-green);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 12px auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        #resultArea {
            display: none;
            flex-direction: column;
            gap: 14px;
            margin-top: 8px;
        }

        .answer-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 16px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.04);
        }

        .answer-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border-color);
        }

        .badge-doublecheck {
            background: #ECFDF5;
            border: 1px solid #A7F3D0;
            color: #065F46;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 6px;
        }

        .answer-content {
            font-size: 14px;
            line-height: 1.6;
            color: var(--text-primary);
            white-space: pre-wrap;
            word-break: break-word;
        }

        .copy-btn {
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            cursor: pointer;
            margin-top: 12px;
            width: 100%;
            min-height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }

        .sources-card {
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 14px;
        }

        .sources-title {
            font-size: 12px;
            font-weight: 700;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .source-item {
            background: #FFFFFF;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 8px 10px;
            margin-bottom: 6px;
            font-size: 12px;
        }

        .source-name {
            font-weight: 600;
            color: var(--text-primary);
        }

        .source-art {
            color: var(--accent-green);
            font-weight: 500;
            font-size: 11px;
        }

        footer {
            margin-top: auto;
            padding-top: 24px;
            text-align: center;
            font-size: 11px;
            color: var(--text-secondary);
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="logo-area">
                <div class="logo-icon">&#9878;</div>
                <div>
                    <div class="logo-title">Qanoun DZ</div>
                    <div class="logo-subtitle">Agent Juridique Algérien 2026</div>
                </div>
            </div>
            <div class="status-badge">
                <span class="status-dot"></span> 37 Lois Mises à Jour
            </div>
        </header>

        <!-- Stats Banner -->
        <div class="stats-banner">
            <div class="stat-item">
                <div class="val">59 Ans</div>
                <div class="lbl">1968-2026</div>
            </div>
            <div class="stat-item">
                <div class="val">4,588</div>
                <div class="lbl">JORADP MD</div>
            </div>
            <div class="stat-item">
                <div class="val">5,490</div>
                <div class="lbl">Articles Indexés</div>
            </div>
        </div>

        <!-- Suggestion Chips -->
        <div class="chips-scroll">
            <div class="chip" onclick="setQuery('Wach y9ol el 9anoun 3la congé de maternité pour les femmes salariées?')">Congé Maternité</div>
            <div class="chip" onclick="setQuery('Kifech ndir statut auto-entrepreneur w wach hiya l imtiyazat?')">Auto-Entrepreneur</div>
            <div class="chip" onclick="setQuery('Ch7al la peine te3 chèque sans provision f code pénal 2024?')">Chèque Sans Provision</div>
            <div class="chip" onclick="setQuery('Wach houma chourout l istithmar w l foncier économique f la loi 23-17?')">Foncier Économique</div>
            <div class="chip" onclick="setQuery('Wach houwa délai de préavis f la démission selon loi 90-11?')">Délai Démission</div>
        </div>

        <!-- Query Form -->
        <div class="search-card">
            <textarea id="queryInput" class="input-box" placeholder="Saqsi l'Agent Juridique en Darija (Arabizi) wla Français..."></textarea>
            <div class="search-actions">
                <span class="lang-hint">&#127760; Darija / Français / English</span>
                <button id="sendBtn" class="submit-btn" onclick="submitQuery()">
                    <span>Ba3ath</span> &#10148;
                </button>
            </div>
        </div>

        <!-- Loading -->
        <div id="loadingSpinner">
            <div class="spinner"></div>
            <div>Rani nverifi f les codes w l Journal Officiel...</div>
        </div>

        <!-- Results -->
        <div id="resultArea">
            <div class="answer-card">
                <div class="answer-header">
                    <span style="font-size: 13px; font-weight: 700;">Jawab L Agent</span>
                    <span class="badge-doublecheck">&#10003; Avocat Double-Check 2026</span>
                </div>
                <div id="answerText" class="answer-content"></div>
                <button class="copy-btn" onclick="copyAnswer()">
                    <span>&#128203; Copier la Réponse</span>
                </button>
            </div>

            <div id="jurisprudenceCard" class="sources-card" style="display: none; background: #FEF3C7; border-color: #FDE68A;">
                <div class="sources-title" style="color: #92400E;">&#9878; Ijtihad Qada'i (Cour Suprême)</div>
                <div id="jurisprudenceList"></div>
            </div>

            <div class="sources-card">
                <div class="sources-title">Mawad & Maraji3 Juridiques</div>
                <div id="sourcesList"></div>
            </div>
        </div>

        <!-- Footer -->
        <footer>
            Qanoun DZ &bull; Base Officielle Secrétariat Général du Gouvernement Algérien &bull; Mode Mobile &bull; Strict Latin Script
        </footer>
    </div>

    <script>
        function setQuery(text) {
            document.getElementById('queryInput').value = text;
            submitQuery();
        }

        async function submitQuery() {
            const input = document.getElementById('queryInput');
            const query = input.value.trim();
            if (!query) return;

            const sendBtn = document.getElementById('sendBtn');
            const spinner = document.getElementById('loadingSpinner');
            const resultArea = document.getElementById('resultArea');
            const answerText = document.getElementById('answerText');
            const sourcesList = document.getElementById('sourcesList');

            sendBtn.disabled = true;
            spinner.style.display = 'block';
            resultArea.style.display = 'none';

            try {
                const resp = await fetch('/api/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query})
                });
                const data = await resp.json();

                answerText.textContent = data.answer || 'Ma lqit walou.';

                // Jurisprudence Cour Supreme
                const jurCard = document.getElementById('jurisprudenceCard');
                const jurList = document.getElementById('jurisprudenceList');
                jurList.innerHTML = '';
                if (data.jurisprudence && data.jurisprudence.length > 0) {
                    jurCard.style.display = 'block';
                    data.jurisprudence.forEach(j => {
                        const div = document.createElement('div');
                        div.className = 'source-item';
                        div.style.borderColor = '#FCD34D';
                        div.innerHTML = `<div class="source-name">Arrêt N° ${j.arret_num} (${j.arret_date})</div><div class="source-art" style="color:#B45309;">${j.theme}</div><div style="font-size:11px;color:#4B5563;margin-top:4px;"><b>Al-Mabda':</b> ${j.principle ? j.principle.substring(0, 160) + '...' : ''}</div>`;
                        jurList.appendChild(div);
                    });
                } else {
                    jurCard.style.display = 'none';
                }

                // Sources Lois
                sourcesList.innerHTML = '';
                if (data.articles && data.articles.length > 0) {
                    data.articles.forEach(a => {
                        const div = document.createElement('div');
                        div.className = 'source-item';
                        div.innerHTML = `<div class="source-name">${a.title}</div><div class="source-art">${a.article} &bull; ${a.domain}</div>`;
                        sourcesList.appendChild(div);
                    });
                } else {
                    sourcesList.innerHTML = '<div style="font-size:12px;color:#64748B;">Lois générales en vigueur appliquées.</div>';
                }

                resultArea.style.display = 'flex';
                resultArea.scrollIntoView({behavior: 'smooth'});
            } catch (err) {
                alert('Erreur: ' + err.message);
            } finally {
                sendBtn.disabled = false;
                spinner.style.display = 'none';
            }
        }

        function copyAnswer() {
            const text = document.getElementById('answerText').textContent;
            navigator.clipboard.writeText(text).then(() => {
                alert('Reponse copiee avec succes!');
            });
        }
    </script>
</body>
</html>
"""

class LegalRequestHandler(http.server.BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def send_json_response(self, status_code, data):
        try:
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def read_json_body(self, max_bytes=1048576):
        try:
            raw_len = self.headers.get('Content-Length', '0')
            content_length = int(raw_len)
        except (ValueError, TypeError):
            return None, 'Invalid Content-Length header'

        if content_length < 0 or content_length > max_bytes:
            return None, 'Request payload exceeds allowed limit'

        try:
            raw_bytes = self.rfile.read(content_length)
            return json.loads(raw_bytes.decode('utf-8')), None
        except Exception as e:
            return None, f'Malformed JSON: {e}'

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        clean_path = urllib.parse.unquote(self.path.split('?')[0]).lstrip('/')
        base_dir = os.path.dirname(os.path.abspath(__file__))
        local_asset_path = os.path.realpath(os.path.join(base_dir, clean_path))

        # Path Traversal Prevention: Ensure target stays strictly inside base_dir
        if not local_asset_path.startswith(base_dir + os.sep) and local_asset_path != base_dir:
            self.send_response(403)
            self.send_cors_headers()
            self.end_headers()
            return

        if (clean_path.startswith('assets/') or clean_path.startswith('images/') or clean_path in ('manifest.json', 'service-worker.js')) and os.path.isfile(local_asset_path):
            ext = os.path.splitext(local_asset_path)[1].lower()
            mime_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.webp': 'image/webp',
                '.svg': 'image/svg+xml',
                '.css': 'text/css',
                '.js': 'application/javascript',
                '.json': 'application/manifest+json',
            }
            content_type = mime_types.get(ext, 'application/octet-stream')
            try:
                with open(local_asset_path, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_cors_headers()
                if clean_path == 'service-worker.js':
                    self.send_header('Service-Worker-Allowed', '/')
                    self.send_header('Cache-Control', 'no-cache')
                else:
                    self.send_header('Cache-Control', 'public, max-age=86400')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                self.send_response(500)
                self.send_cors_headers()
                self.end_headers()
                return

        parsed_url = urllib.parse.urlparse(self.path)
        path_only = parsed_url.path
        qs = urllib.parse.parse_qs(parsed_url.query)

        if path_only == '/' or path_only == '/index.html':
            app_file = os.path.join(base_dir, 'index.html')
            if os.path.exists(app_file):
                with open(app_file, 'rb') as fp:
                    content_html = fp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Content-Length', str(len(content_html)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(content_html)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif path_only == '/preview':
            preview_file = os.path.join(base_dir, 'index.html')
            if os.path.exists(preview_file):
                with open(preview_file, 'rb') as fp:
                    content_prev = fp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content_prev)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(content_prev)
            else:
                self.send_response(404)
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(b'Aucun apercu genere pour le moment.')
        elif path_only.startswith('/api/memory'):
            mems = global_memory.get_all('default_user')
            self.send_json_response(200, {'status': 'ok', 'memories': mems})
        elif path_only == '/api/status':
            self.send_json_response(200, {'status': 'ok', 'laws_count': 59, 'articles_count': 6012, 'jurisprudence_count': 89})
        elif path_only == '/api/library/overview':
            ov = library_service.get_library_overview()
            self.send_json_response(200, ov)
        elif path_only == '/api/library/laws':
            dom = qs.get('domain', [None])[0]
            search = qs.get('search', [None])[0]
            laws_data = library_service.get_library_laws(dom, search)
            self.send_json_response(200, laws_data)
        elif path_only == '/api/library/articles':
            law_title = qs.get('law_title', [None])[0]
            dom = qs.get('domain', [None])[0]
            search = qs.get('search', [None])[0]
            limit = int(qs.get('limit', ['25'])[0])
            offset = int(qs.get('offset', ['0'])[0])
            arts_data = library_service.get_library_articles(law_title, dom, search, limit, offset)
            self.send_json_response(200, arts_data)
        elif path_only == '/api/library/jurisprudence':
            search = qs.get('search', [None])[0]
            limit = int(qs.get('limit', ['20'])[0])
            offset = int(qs.get('offset', ['0'])[0])
            juris_data = library_service.get_library_jurisprudence(search, limit, offset)
            self.send_json_response(200, juris_data)
        else:
            self.send_response(404)
            self.send_cors_headers()
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/ask':
            req_json, err = self.read_json_body()
            if err:
                self.send_json_response(400, {'error': err})
                return
            try:
                q = req_json.get('query', '')
                lang = req_json.get('lang', 'ar')
                history = req_json.get('history', [])
                user_id = req_json.get('user_id', 'default_user')
                persona = req_json.get('persona', 'citoyen')
                current_date = req_json.get('current_date', None)
                res = ask_legal_agent(q, lang=lang, history=history, user_id=user_id, persona=persona, current_date=current_date)
                self.send_json_response(200, res)
            except Exception as e:
                self.send_json_response(500, {'error': str(e)})
        elif self.path == '/api/memory/delete':
            req_json, err = self.read_json_body()
            if err:
                self.send_json_response(400, {'error': err})
                return
            try:
                mem_id = req_json.get('id')
                success = global_memory.delete_memory(mem_id, 'default_user')
                self.send_json_response(200, {'status': 'ok', 'deleted': success})
            except Exception as e:
                self.send_json_response(500, {'error': str(e)})
        elif self.path == '/api/memory/clear':
            try:
                global_memory.clear_all('default_user')
                self.send_json_response(200, {'status': 'ok'})
            except Exception as e:
                self.send_json_response(500, {'error': str(e)})
        else:
            self.send_response(404)
            self.send_cors_headers()
            self.end_headers()

    def log_message(self, format, *args):
        # Silent logger for performance
        return

def run_server():
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PORT), LegalRequestHandler) as httpd:
        print(f"=== Qanoun DZ Web Server Running on http://localhost:{PORT} ===")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == '__main__':
    run_server()
