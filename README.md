# fabiofidone-blog-pipeline

Pipeline automatica di generazione e pubblicazione articoli per il blog di [fabiofidone.it](https://www.fabiofidone.it/blog/).

- **Generazione**: Claude Haiku 4.5 (il piu' economico), guidato da `pipeline/style_guide.md`
- **Cadenza**: lunedi' e giovedi', via GitHub Actions (`.github/workflows/publish-blog.yml`)
- **Pubblicazione**: upload diretto via FTP su Aruba — nessuna revisione umana nel mezzo, per scelta esplicita
- **Notifica**: WhatsApp (CallMeBot) ad ogni articolo pubblicato o in caso di errore

## Secrets richiesti (Settings → Secrets and variables → Actions)

| Secret | Descrizione |
|---|---|
| `ANTHROPIC_API_KEY` | Chiave API Claude, dedicata a questo progetto |
| `WHATSAPP_PHONE` | Numero WhatsApp per le notifiche |
| `WHATSAPP_APIKEY` | Apikey CallMeBot |
| `FTP_SERVER` | Host FTP Aruba (es. `ftp.fabiofidone.it`) |
| `FTP_USERNAME` | Utente FTP Aruba |
| `FTP_PASSWORD` | Password FTP Aruba |

## Struttura

- `pipeline/` — script di generazione (`generate_article.py`), aggiornamento indice/nav (`index_updater.py`), guida di stile, template HTML, elenco argomenti (`topics_covered.json`)
- `site/blog/` — copia live della cartella `blog/` del sito, sincronizzata su Aruba via FTP ad ogni run

## Test manuale

Dalla tab "Actions" del repository, workflow "Pubblica articolo blog fabiofidone.it" → "Run workflow" per lanciare un run fuori dal calendario schedulato.
