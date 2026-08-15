# -*- coding: utf-8 -*-
"""
Aggiorna blog/index.html (nuova card + contatori) e il blocco NAV
dell'articolo precedente, usando marcatori HTML fissi invece di
indovinare "l'ultima card"/"l'ultimo link" — molto piu' robusto quando
gira senza supervisione (GitHub Actions, nessuna revisione umana prima
del commit).

Se un marcatore manca, solleva un errore esplicito invece di scrivere
silenziosamente nel posto sbagliato.
"""
import re


def _sostituisci_tra_marcatori(html, apertura, chiusura, nuovo_contenuto):
    pattern = re.compile(re.escape(apertura) + r".*?" + re.escape(chiusura), re.S)
    if not pattern.search(html):
        raise ValueError(f"Marcatori {apertura} ... {chiusura} non trovati — file non modificato per sicurezza")
    return pattern.sub(apertura + nuovo_contenuto + chiusura, html, count=1)


def aggiorna_indice_blog(index_html, numero_totale, slug, categoria, titolo, excerpt, mese_anno, reading_time_min):
    html = index_html

    html = _sostituisci_tra_marcatori(html, "<!--CONTATORE_A-->", "<!--/CONTATORE_A-->", f"{numero_totale} articoli")
    html = _sostituisci_tra_marcatori(html, "<!--CONTATORE_B-->", "<!--/CONTATORE_B-->", f"{numero_totale} articoli")

    nuova_card = f'''
      <a href="/blog/{slug}/" class="bl-card">
        <div class="bl-cat">{categoria}</div>
        <h2>{titolo}</h2>
        <p>{excerpt}</p>
        <div class="bl-card-foot">
          <span>{mese_anno} · {reading_time_min} min</span>
          <span class="go">leggi.md →</span>
        </div>
      </a>

      '''

    marcatore = "<!--NUOVA_CARD_QUI-->"
    if marcatore not in html:
        raise ValueError("Marcatore <!--NUOVA_CARD_QUI--> non trovato in blog/index.html — file non modificato per sicurezza")
    html = html.replace(marcatore, nuova_card + marcatore, 1)

    return html


def aggiorna_nav_articolo_precedente(prev_html, nuovo_slug, nuovo_titolo):
    """Sostituisce il blocco NAV dell'articolo che finora era 'l'ultimo',
    puntando il link 'successivo' (a destra, colore giallo) al nuovo
    articolo appena pubblicato. Il link 'precedente' (a sinistra) resta
    invariato: e' gia' corretto e non lo tocchiamo."""
    m = re.search(
        r'<!--NAV_BLOCK-->(.*?)<a href="/blog/"[^>]*>tutti gli articoli →</a>\s*</nav>\s*<!--/NAV_BLOCK-->',
        prev_html, re.S,
    )
    if not m:
        raise ValueError("Blocco <!--NAV_BLOCK--> non trovato nell'articolo precedente — nav non modificata per sicurezza")

    prefisso = m.group(1)
    nuovo_blocco = (
        "<!--NAV_BLOCK-->" + prefisso +
        f'<a href="/blog/{nuovo_slug}/" style="color:var(--yellow);text-decoration:none;font-size:12px">{nuovo_titolo} →</a>\n'
        "  </nav>\n  <!--/NAV_BLOCK-->"
    )
    inizio, fine = m.span()
    return prev_html[:inizio] + nuovo_blocco + prev_html[fine:]
