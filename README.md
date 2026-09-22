# fabiofidone-blog-pipeline

Pipeline automatica di generazione e pubblicazione articoli per il blog di [fabiofidone.it](https://www.fabiofidone.it/blog/).

- **Generazione**: Claude Haiku 4.5 (il piu' economico), guidato da `pipeline/style_guide.md`
- **Cadenza**: lunedi' e giovedi', via GitHub Actions (`.github/workflows/publish-blog.yml`)
- **Pubblicazione**: upload diretto via FTP su Aruba — nessuna revisione umana nel mezzo, per scelta esplicita
- **LinkedIn**: dopo ogni articolo pubblicato con successo, genera (Claude Haiku 4.5, guidato da `pipeline/linkedin_style_guide.md`) e pubblica un post di annuncio sul profilo personale — stesso principio "zero revisione umana", ma isolato: se fallisce (es. token scaduto) non blocca ne' marca come fallita la pubblicazione del blog
- **Notifica**: WhatsApp (CallMeBot) ad ogni articolo pubblicato, ad ogni fallimento (blog o LinkedIn separatamente)

## Secrets richiesti (Settings → Secrets and variables → Actions)

| Secret | Descrizione |
|---|---|
| `ANTHROPIC_API_KEY` | Chiave API Claude, dedicata a questo progetto |
| `WHATSAPP_PHONE` | Numero WhatsApp per le notifiche |
| `WHATSAPP_APIKEY` | Apikey CallMeBot |
| `FTP_SERVER` | Host FTP Aruba (es. `ftp.fabiofidone.it`) |
| `FTP_USERNAME` | Utente FTP Aruba |
| `FTP_PASSWORD` | Password FTP Aruba |
| `LINKEDIN_TOKEN` | Access token OAuth LinkedIn (scope `w_member_social`), scade ogni ~60 giorni — va rigenerato manualmente (vedi sotto) |

### Rigenerare LINKEDIN_TOKEN quando scade

Non e' automatizzabile: LinkedIn richiede un'autorizzazione interattiva nel browser ogni volta (nessun refresh token disponibile su questa app). Serve Client ID/Secret dell'app su [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps) → tab Auth, poi:

1. Apri l'URL di autorizzazione: `https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=<CLIENT_ID>&redirect_uri=https%3A%2F%2Fwww.linkedin.com%2Fdevelopers%2Ftools%2Foauth%2Fredirect&scope=openid%20profile%20email%20w_member_social&state=<qualsiasi_stringa>`
2. Fai login/consenso, copia il parametro `code` dalla pagina di redirect (scade in pochi minuti)
3. Scambialo per il token: `POST https://www.linkedin.com/oauth/v2/accessToken` con `grant_type=authorization_code`, `code`, `client_id`, `client_secret`, `redirect_uri` (uguale a quello usato sopra)
4. Aggiorna il secret `LINKEDIN_TOKEN` su GitHub con il nuovo `access_token`

## Struttura

- `pipeline/` — script di generazione (`generate_article.py`), post LinkedIn (`generate_linkedin_post.py`), aggiornamento indice/nav (`index_updater.py`), guide di stile (blog + LinkedIn), template HTML, elenco argomenti (`topics_covered.json`)
- `site/blog/` — copia live della cartella `blog/` del sito, sincronizzata su Aruba via FTP ad ogni run

## Test manuale

Dalla tab "Actions" del repository, workflow "Pubblica articolo blog fabiofidone.it" → "Run workflow" per lanciare un run fuori dal calendario schedulato.
