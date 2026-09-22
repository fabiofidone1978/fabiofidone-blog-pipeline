# -*- coding: utf-8 -*-
"""
Genera un post LinkedIn di annuncio per il nuovo articolo del blog e lo
pubblica sul profilo personale di Fabio Fidone via LinkedIn REST API.

Gira come step del workflow (.github/workflows/publish-blog.yml), SOLO DOPO
che l'upload FTP dell'articolo e' andato a buon fine (stesso motivo per cui
la notifica WhatsApp di successo parte solo a quel punto: non ha senso
annunciare un articolo che non e' ancora online). Nessuna revisione umana —
stessa scelta del resto della pipeline.

Meccanismo LinkedIn (author URN + POST /rest/posts) verificato funzionante
in produzione a maggio 2026 in un progetto precedente (Documents/AI-linkedin
sulla macchina locale di Fabio, non in questo repo).

Variabili d'ambiente richieste:
  ANTHROPIC_API_KEY, LINKEDIN_TOKEN
  ARTICLE_TITOLO, ARTICLE_SLUG, ARTICLE_LEDE, ARTICLE_META_DESCRIPTION
    (questi quattro arrivano dagli output dello step "generate" precedente,
    vedi generate_article.py)
Opzionali:
  BLOG_AI_MODEL (default: claude-haiku-4-5-20251001 — il piu' economico)
  FAKE_AI=1 (dry-run: genera il testo del post ma non chiama LinkedIn)

IMPORTANTE: il LINKEDIN_TOKEN scade ogni ~60 giorni (limite dell'API
LinkedIn per token senza refresh dedicato, non aggirabile lato nostro).
Quando scade, questo step fallisce e basta — la pubblicazione del blog
(gia' avvenuta negli step precedenti del workflow) non ne risente. Il
workflow manda una notifica WhatsApp separata in quel caso, per ricordare
di rigenerare il token.
"""
import os
import re
import json
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STYLE_GUIDE_FILE = os.path.join(BASE_DIR, "linkedin_style_guide.md")

MODEL = os.environ.get("BLOG_AI_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LINKEDIN_TOKEN = os.environ.get("LINKEDIN_TOKEN", "")
FAKE_AI = os.environ.get("FAKE_AI", "") == "1"

TITOLO = os.environ.get("ARTICLE_TITOLO", "")
SLUG = os.environ.get("ARTICLE_SLUG", "")
LEDE = os.environ.get("ARTICLE_LEDE", "")
META_DESCRIPTION = os.environ.get("ARTICLE_META_DESCRIPTION", "")

ARTICLE_URL = f"https://www.fabiofidone.it/blog/{SLUG}/"

LINKEDIN_API_POST = "https://api.linkedin.com/rest/posts"
LINKEDIN_API_USERINFO = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_VERSION = "202603"


def costruisci_prompt():
    with open(STYLE_GUIDE_FILE, "r", encoding="utf-8") as f:
        guida = f.read()

    return f"""{guida}

---

Genera il post LinkedIn per questo articolo, usando SOLO queste informazioni (non inventare altro):

Titolo: {TITOLO}
Lede (introduzione dell'articolo): {LEDE}
Meta description: {META_DESCRIPTION}

Rispondi SOLO con il testo del post (senza il link — lo aggiungo io dopo, non includerlo), nessun blocco markdown/backtick, nessuna spiegazione prima o dopo il testo."""


def chiama_claude(prompt):
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(blocco.get("text", "") for blocco in data.get("content", []))


def pulisci_testo(testo):
    testo = testo.strip()
    testo = re.sub(r"^```\w*\s*", "", testo)
    testo = re.sub(r"\s*```$", "", testo)
    return testo.strip().strip('"').strip()


def get_linkedin_author():
    req = urllib.request.Request(
        LINKEDIN_API_USERINFO,
        headers={"Authorization": f"Bearer {LINKEDIN_TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    sub = data.get("sub")
    if not sub:
        raise RuntimeError(f"Risposta userinfo senza 'sub': {data}")
    return f"urn:li:person:{sub}"


def pubblica_post(author, testo):
    payload = {
        "author": author,
        "commentary": testo,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED"},
        "lifecycleState": "PUBLISHED",
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LINKEDIN_API_POST,
        data=body,
        headers={
            "Authorization": f"Bearer {LINKEDIN_TOKEN}",
            "Content-Type": "application/json",
            "Linkedin-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def main():
    if not SLUG or not TITOLO:
        raise SystemExit("ARTICLE_TITOLO/ARTICLE_SLUG mancanti — nessun articolo da annunciare.")
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY mancante.")

    testo_grezzo = chiama_claude(costruisci_prompt())
    corpo_post = pulisci_testo(testo_grezzo)
    if not corpo_post:
        raise SystemExit("Il modello ha restituito un post vuoto.")

    testo_finale = f"{corpo_post}\n\n{ARTICLE_URL}"
    print(f"--- Post LinkedIn ({len(testo_finale)} caratteri) ---\n{testo_finale}\n---")

    if FAKE_AI:
        print("FAKE_AI=1 — nessuna pubblicazione reale su LinkedIn.")
        return

    if not LINKEDIN_TOKEN:
        raise SystemExit("LINKEDIN_TOKEN mancante.")

    author = get_linkedin_author()
    print(f"Author: {author}")

    status, risposta = pubblica_post(author, testo_finale)
    if status not in (200, 201):
        raise SystemExit(f"Pubblicazione LinkedIn fallita: HTTP {status} — {risposta[:300]}")
    print("Post LinkedIn pubblicato.")


if __name__ == "__main__":
    main()
