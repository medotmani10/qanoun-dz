# Qanoun DZ - Cloud & PWA Edition

Plateforme d'assistance juridique et Agent IA conversationnel dédié au droit algérien.
100% autonome, léger (< 15 MB) et prêt pour le déploiement cloud (Render, Docker, Koyeb, Hugging Face).

## Caractéristiques
- **Législation Algérienne Consolidée :** Intègre les réformes majeures de 2024, 2025 et 2026 (Nouveau Code de la Route Loi 26-09, Révision Constitutionnelle Loi 26-04, Code Pénal Loi 26-13, Code de Procédure Pénale Loi 25-14).
- **Interface Mobile-First & PWA :** Conçue spécialement pour smartphones, installable comme une application native avec support hors-ligne (Service Worker).
- **Architecture Zero-Dependency :** Construit exclusivement avec la bibliothèque standard Python 3 (http.server, sqlite3, json, urllib).

## Déploiement Rapide sur Render.com
1. Connectez votre compte GitHub sur [Render.com](https://render.com).
2. Créez un **New Web Service** en sélectionnant ce dépôt.
3. Ajoutez la variable d'environnement :
   - `GEMINI_API_KEY`: Votre clé d'API Google Gemini.
4. Cliquez sur **Deploy**.

## Lancement Local
```bash
python3 app.py
```
Ouvrez `http://localhost:8080`.
