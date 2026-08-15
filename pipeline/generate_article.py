# -*- coding: utf-8 -*-
"""
Pipeline di generazione E pubblicazione automatica — blog fabiofidone.it.
Gira dentro GitHub Actions (.github/workflows/publish-blog.yml), pianificata
2 volte a settimana. Scrive direttamente in site/blog/ dentro il repository;
il workflow poi fa commit + upload FTP su Aruba. Nessuna revisione umana nel
mezzo — per scelta esplicita di Fabio, sapendo che significa nessun controllo
di merito sul contenuto prima che vada online (solo i controlli automatici
qui sotto: struttura, tag vietati, marcatori presenti).

Variabili d'ambiente richieste (GitHub Actions Secrets):
  ANTHROPIC_API_KEY, WHATSAPP_PHONE, WHATSAPP_APIKEY
Opzionali:
  BLOG_AI_MODEL (default: claude-haiku-4-5-20251001 — il piu' economico)
  FAKE_AI=1 (dry-run, nessuna chiamata reale, per testare la meccanica)
"""
import os
import re
import json
import html
import urllib.request
import urllib.parse
from datetime import datetime, timezone

from index_updater import aggiorna_indice_blog, aggiorna_nav_articolo_precedente, aggiorna_sitemap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
SITE_DIR = os.path.join(REPO_ROOT, "site")
SITE_BLOG_DIR = os.path.join(SITE_DIR, "blog")

TOPICS_FILE = os.path.join(BASE_DIR, "topics_covered.json")
STYLE_GUIDE_FILE = os.path.join(BASE_DIR, "style_guide.md")
TEMPLATE_FILE = os.path.join(BASE_DIR, "template.html")

MODEL = os.environ.get("BLOG_AI_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FAKE_AI = os.environ.get("FAKE_AI", "") == "1"

WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE", "")
WHATSAPP_APIKEY = os.environ.get("WHATSAPP_APIKEY", "")

MESI_IT = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
           "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

MARCATORI = ["META_DESCRIPTION", "TAG_CATEGORIA", "H1_HTML", "LEDE",
             "READING_TIME_MIN", "BODY_HTML",
             "FAQ1_Q", "FAQ1_A", "FAQ2_Q", "FAQ2_A", "FAQ3_Q", "FAQ3_A"]


def carica_topics():
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def salva_topics(data):
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def scegli_prossimo_argomento(data):
    pubblicati_slug = {p["slug"] for p in data["pubblicati"]}
    for candidato in data["backlog_argomenti"]:
        if candidato["slug"] not in pubblicati_slug:
            return candidato
    return None


def costruisci_prompt(argomento):
    with open(STYLE_GUIDE_FILE, "r", encoding="utf-8") as f:
        guida = f.read()

    schema = """Rispondi usando ESATTAMENTE questo formato, un blocco per marcatore, nessun testo fuori dai marcatori, nessun blocco markdown/backtick:

###META_DESCRIPTION###
(max 155 caratteri, testo semplice)
###TAG_CATEGORIA###
(2-3 parole separate da virgola, es: automazione, WhatsApp)
###H1_HTML###
(titolo H1, puoi usare <br> per andare a capo, NON includere il carattere '>' iniziale)
###LEDE###
(1-2 frasi di introduzione, testo semplice senza HTML)
###READING_TIME_MIN###
(solo un numero, es: 7)
###BODY_HTML###
(corpo completo dell'articolo in HTML: solo tag <p>, <h2><span class="acc">#</span> ...</h2>, <h3>, <ul>, <ol>, <li>, <strong>, <a href="...">, <div class="art-callout"><p>...</p></div>, <table class="art-table">...</table>. NIENTE <script>, <style>, <iframe>, attributi on*)
###FAQ1_Q###
(prima domanda)
###FAQ1_A###
(prima risposta)
###FAQ2_Q###
(seconda domanda)
###FAQ2_A###
(seconda risposta)
###FAQ3_Q###
(terza domanda)
###FAQ3_A###
(terza risposta)"""

    return f"""{guida}

---

Scrivi un articolo del blog con questo argomento esatto:
Titolo di riferimento: {argomento['titolo']}
Categoria: {argomento['categoria']}

{schema}"""


def chiama_claude(prompt):
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 4096,
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(blocco.get("text", "") for blocco in data.get("content", []))


def risposta_finta(argomento):
    return f"""###META_DESCRIPTION###
Bozza di test per '{argomento['titolo']}'. Contenuto segnaposto, nessuna chiamata AI reale eseguita (FAKE_AI=1).
###TAG_CATEGORIA###
test, dry-run
###H1_HTML###
{html.escape(argomento['titolo'])}
###LEDE###
Questo e' un contenuto di prova generato in modalita' FAKE_AI, non e' mai stato scritto da un modello reale.
###READING_TIME_MIN###
5
###BODY_HTML###
<p>Paragrafo di prova per verificare che il template si compili correttamente.</p><h2><span class="acc">#</span> Sezione di test</h2><p>Secondo paragrafo di prova.</p>
###FAQ1_Q###
Questa e' una domanda di test?
###FAQ1_A###
Si', questa risposta e' generata in modalita' dry-run.
###FAQ2_Q###
Serve una seconda domanda di test?
###FAQ2_A###
Si', per verificare che il ciclo FAQ funzioni con piu' voci.
###FAQ3_Q###
Questo contenuto va pubblicato?
###FAQ3_A###
No, MAI: e' solo per verificare la meccanica della pipeline."""


def estrai_contenuto(testo_grezzo):
    testo = testo_grezzo.strip()
    testo = re.sub(r"^```\w*\s*", "", testo)
    testo = re.sub(r"\s*```$", "", testo)

    pezzi = {}
    pattern = re.compile(r"###(" + "|".join(MARCATORI) + r")###\s*\n(.*?)(?=\n###(?:" + "|".join(MARCATORI) + r")###|\Z)", re.S)
    for m in pattern.finditer(testo):
        pezzi[m.group(1)] = m.group(2).strip()

    mancanti = [m for m in MARCATORI if m not in pezzi]
    if mancanti:
        raise ValueError(f"Marcatori mancanti nella risposta AI: {mancanti}")

    return {
        "meta_description": pezzi["META_DESCRIPTION"],
        "tag_categoria": [t.strip() for t in pezzi["TAG_CATEGORIA"].split(",") if t.strip()],
        "h1_html": pezzi["H1_HTML"],
        "lede": pezzi["LEDE"],
        "reading_time_min": int(re.sub(r"\D", "", pezzi["READING_TIME_MIN"]) or "6"),
        "body_html": pezzi["BODY_HTML"],
        "faq": [
            {"q": pezzi["FAQ1_Q"], "a": pezzi["FAQ1_A"]},
            {"q": pezzi["FAQ2_Q"], "a": pezzi["FAQ2_A"]},
            {"q": pezzi["FAQ3_Q"], "a": pezzi["FAQ3_A"]},
        ],
    }


def valida_contenuto(c):
    if not c["body_html"] or len(c["body_html"]) < 100:
        raise ValueError("body_html troppo corto o vuoto — scartato")
    # \b prima di "on" e la virgoletta dopo "=" sono essenziali: senza,
    # la regex intercetta anche parole italiane normali come "condizione="
    # o "posizione=" (contengono "on" seguito da lettere) — capitato
    # davvero in un articolo sui prezzi, falso positivo verificato.
    vietati = re.compile(r"<script|<iframe|<style|\bon\w+\s*=\s*[\"']", re.IGNORECASE)
    if vietati.search(c["body_html"]):
        raise ValueError("body_html contiene tag/attributi non ammessi — scartato per sicurezza")


def costruisci_html(argomento, contenuto, oggi, prev_articolo):
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        tpl = f.read()

    slug = argomento["slug"]
    titolo_piano = re.sub("<[^<]+?>", "", contenuto["h1_html"]).replace("  ", " ").strip()
    url = f"https://www.fabiofidone.it/blog/{slug}/"
    data_iso = oggi.strftime("%Y-%m-%d")
    data_estesa = f"{oggi.day} {MESI_IT[oggi.month]} {oggi.year}"
    mese_anno = f"{MESI_IT[oggi.month]} {oggi.year}"

    article_ld = json.dumps({
        "@context": "https://schema.org", "@type": "Article",
        "headline": titolo_piano, "description": contenuto["meta_description"],
        "author": {"@type": "Person", "name": "Fabio Fidone", "url": "https://www.fabiofidone.it/"},
        "publisher": {"@type": "Person", "name": "Fabio Fidone"},
        "datePublished": data_iso, "url": url, "mainEntityOfPage": url,
    }, ensure_ascii=False)

    faq_ld = json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": item["q"],
             "acceptedAnswer": {"@type": "Answer", "text": item["a"]}}
            for item in contenuto["faq"]
        ],
    }, ensure_ascii=False)

    tag_spans = "\n        ".join(f'<span class="tag">[ {html.escape(t)} ]</span>' for t in contenuto["tag_categoria"])
    faq_html = "\n".join(f'''      <div class="art-faq-item">
        <p class="art-faq-q">{html.escape(item["q"])}</p>
        <p class="art-faq-a">{html.escape(item["a"])}</p>
      </div>''' for item in contenuto["faq"])

    prev_url = f"/blog/{prev_articolo['slug']}/" if prev_articolo else "/blog/"
    prev_titolo = prev_articolo["titolo"] if prev_articolo else "tutti gli articoli"

    sostituzioni = {
        "__TITLE__": titolo_piano, "__META_DESCRIPTION__": contenuto["meta_description"],
        "__SLUG__": slug, "__DATE_ISO__": data_iso,
        "__ARTICLE_JSONLD__": article_ld, "__FAQ_JSONLD__": faq_ld,
        "__MESE_ANNO__": mese_anno, "__READING_TIME__": str(contenuto["reading_time_min"]),
        "__TAG_SPANS__": tag_spans, "__DATA_ESTESA__": data_estesa,
        "__H1_HTML__": contenuto["h1_html"], "__LEDE__": contenuto["lede"],
        "__BODY_HTML__": contenuto["body_html"], "__FAQ_HTML__": faq_html,
        "__PREV_URL__": prev_url, "__PREV_TITOLO__": prev_titolo,
    }
    for chiave, valore in sostituzioni.items():
        tpl = tpl.replace(chiave, valore)
    return tpl, titolo_piano, mese_anno


def manda_whatsapp(testo):
    if not WHATSAPP_PHONE or not WHATSAPP_APIKEY:
        print("WhatsApp non configurato — notifica saltata.")
        return
    url = ("https://api.callmebot.com/whatsapp.php?phone=" + urllib.parse.quote(WHATSAPP_PHONE)
           + "&text=" + urllib.parse.quote(testo) + "&apikey=" + urllib.parse.quote(WHATSAPP_APIKEY))
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            resp.read()
        print("Notifica WhatsApp inviata.")
    except Exception as e:
        print(f"Notifica WhatsApp fallita (non bloccante): {e}")


def esegui():
    data = carica_topics()
    argomento = scegli_prossimo_argomento(data)
    if argomento is None:
        print("Backlog argomenti esaurito.")
        manda_whatsapp("Blog fabiofidone.it: backlog argomenti esaurito, serve aggiungerne di nuovi su GitHub.")
        return

    print(f"Argomento scelto: {argomento['titolo']} ({argomento['slug']})")

    if FAKE_AI:
        print("FAKE_AI=1 — nessuna chiamata reale al modello.")
        testo_grezzo = risposta_finta(argomento)
    else:
        if not ANTHROPIC_API_KEY:
            raise SystemExit("ANTHROPIC_API_KEY mancante.")
        testo_grezzo = chiama_claude(costruisci_prompt(argomento))

    contenuto = estrai_contenuto(testo_grezzo)
    valida_contenuto(contenuto)

    oggi = datetime.now(timezone.utc)
    prev_articolo = data["pubblicati"][-1] if data["pubblicati"] else None
    html_finale, titolo_piano, mese_anno = costruisci_html(argomento, contenuto, oggi, prev_articolo)

    # 1) scrive il nuovo articolo dentro site/blog/<slug>/index.html
    out_dir = os.path.join(SITE_BLOG_DIR, argomento["slug"])
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_finale)
    print(f"Articolo scritto: site/blog/{argomento['slug']}/index.html ({len(html_finale)} bytes)")

    # 2) aggiorna site/blog/index.html (contatore + nuova card)
    index_path = os.path.join(SITE_BLOG_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        index_html = f.read()
    excerpt = contenuto["lede"][:180]
    categoria_label = "[ " + " · ".join(contenuto["tag_categoria"][:2]) + " ]"
    index_html = aggiorna_indice_blog(
        index_html, len(data["pubblicati"]) + 1, argomento["slug"], categoria_label,
        titolo_piano, excerpt, mese_anno, contenuto["reading_time_min"],
    )
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print("blog/index.html aggiornato.")

    # 3) aggiorna il link 'successivo' nell'articolo che finora era l'ultimo
    if prev_articolo:
        prev_path = os.path.join(SITE_BLOG_DIR, prev_articolo["slug"], "index.html")
        with open(prev_path, "r", encoding="utf-8") as f:
            prev_html = f.read()
        prev_html = aggiorna_nav_articolo_precedente(prev_html, argomento["slug"], titolo_piano)
        with open(prev_path, "w", encoding="utf-8") as f:
            f.write(prev_html)
        print(f"Nav aggiornata su: site/blog/{prev_articolo['slug']}/index.html")

    # 4) aggiunge la URL al sitemap.xml del sito (root, non solo blog/)
    sitemap_path = os.path.join(SITE_DIR, "sitemap.xml")
    with open(sitemap_path, "r", encoding="utf-8") as f:
        sitemap_xml = f.read()
    sitemap_xml = aggiorna_sitemap(sitemap_xml, argomento["slug"])
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write(sitemap_xml)
    print("sitemap.xml aggiornato.")

    if not FAKE_AI:
        data["pubblicati"].append({"slug": argomento["slug"], "titolo": titolo_piano,
                                    "data": oggi.strftime("%Y-%m-%d")})
        salva_topics(data)
        # NOTA: nessuna notifica "pubblicato" qui — a questo punto i file sono
        # solo scritti in locale nel runner. Il commit git e l'upload FTP sono
        # step successivi del workflow, possono ancora fallire (es. permessi,
        # credenziali FTP). La notifica di successo vera parte da un secondo
        # step del workflow, DOPO che l'upload FTP e' andato a buon fine —
        # altrimenti si rischia di dire "pubblicato" quando non lo e' ancora,
        # come e' successo nel primo test reale di questa pipeline.
        print(f'Articolo "{titolo_piano}" pronto — commit e upload FTP gestiti dal workflow.')
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a", encoding="utf-8") as f:
                f.write(f"titolo={titolo_piano}\n")
                f.write(f"slug={argomento['slug']}\n")
    else:
        print("FAKE_AI=1 — topics_covered.json NON modificato, nessuna notifica reale inviata.")


def main():
    if FAKE_AI:
        esegui()
        return
    try:
        esegui()
    except Exception as e:
        messaggio = str(e)
        if len(messaggio) > 200:
            messaggio = messaggio[:200] + "..."
        print(f"ERRORE pipeline blog: {e}")
        manda_whatsapp(f"Blog fabiofidone.it: generazione articolo FALLITA — {messaggio}")
        raise


if __name__ == "__main__":
    main()
