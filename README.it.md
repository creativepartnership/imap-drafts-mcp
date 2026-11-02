# imap-drafts-mcp

*[Read in English](README.md)*

Server MCP che permette a Claude (o a un altro client MCP) di cercare e leggere le email di una casella IMAP e di preparare nuovi messaggi **solo come bozze**. Non può inviare, spostare, cancellare o modificare i messaggi e non li segna come letti. Ogni bozza la rilegge e la invia una persona dal proprio client di posta.

Se non vuoi nessuna scrittura, imposta `IMAP_READ_ONLY=true`: vedi [Modalità sola lettura](#modalità-sola-lettura).

Sviluppato da [Creative Partnership Srl](https://www.cp-srl.it) per uso interno e distribuito a tutti con licenza MIT.

## Perché questo server

Un assistente AI che legge la posta legge anche testo scritto da sconosciuti, e quel testo può cercare di dargli istruzioni. Questo server limita ciò che un attacco del genere può ottenere:

- Non contiene codice SMTP e non riceve credenziali SMTP, quindi non ha modo di inviare.
- L'unico comando di scrittura è `APPEND` di IMAP, diretto alla cartella Bozze. La cartella non è un parametro del tool, quindi il modello non può scegliere dove scrivere.
- Un test automatico controlla i comandi che arrivano davvero al server IMAP: nessuno fuori dall'elenco ammesso, e ogni `APPEND` va nelle Bozze.

## Strumenti

| Strumento | Cosa fa |
|---|---|
| `list_folders` | Elenca le cartelle, a richiesta con il numero di messaggi e di non letti |
| `search_messages` | Cerca per mittente, destinatario, oggetto, testo, date, non letti |
| `get_message` | Legge un messaggio: intestazioni, corpo in testo, elenco allegati |
| `get_attachment_text` | Estrae il testo di un allegato (PDF, DOCX, XLSX, testo/CSV) |
| `get_thread` | Ricostruisce la conversazione da Message-ID / References, anche con la Posta inviata se la indichi |
| `create_draft` | Salva un messaggio di testo nelle Bozze, anche come risposta (con `In-Reply-To`/`References` e citazione opzionale). Non invia. Non disponibile in sola lettura |

## Installazione

Servono [uv](https://docs.astral.sh/uv/) e git. Aggiungi questo alla configurazione del tuo client MCP; per Claude Desktop è `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "posta": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/creativepartnership/imap-drafts-mcp@latest",
        "imap-drafts-mcp"
      ],
      "env": {
        "IMAP_HOST": "imap.example.com",
        "IMAP_USER": "nome@example.com",
        "IMAP_PASSWORD": "<password>",
        "IMAP_FROM": "Nome Cognome <nome@example.com>"
      }
    }
  }
}
```

- `@latest` segue ogni nuova versione: la ricevi al successivo riavvio del client, senza cambiare nulla.
- Per aggiornare a mano, fissa una versione, per esempio `@v0.2.0`. Con `@latest` il nuovo codice accede alla tua posta senza che tu lo abbia controllato prima, quindi fissa la versione se per te è importante.
- Se il client non trova `uvx`, usa il suo percorso assoluto come `command` (lo ottieni con `which uvx`).

## Modalità sola lettura

Aggiungi `"IMAP_READ_ONLY": "true"` a `env`. Lo strumento `create_draft` non viene registrato, quindi il modello non lo vede e non può essere convinto a usarlo, e il server non scrive nulla nella casella. Un valore diverso da true/false (valgono anche `1`/`0`, `yes`/`no`, `on`/`off`) impedisce l'avvio del server, così un errore di battitura non può lasciare attive le bozze.

Due limiti da tenere presenti:

- La garanzia riguarda questo server, non l'account. La password dà comunque pieno accesso alla casella, quindi va protetta allo stesso modo.
- Se hai scelto questa modalità per sicurezza, fissa una versione invece di usare `@latest`. Altrimenti affidi la garanzia anche a tutte le versioni future.

## Configurazione

| Variabile | Default | Uso |
|---|---|---|
| `IMAP_HOST` | obbligatoria | Host del server IMAP |
| `IMAP_USER` | obbligatoria | Nome utente |
| `IMAP_PASSWORD` | obbligatoria | Password, meglio se dedicata |
| `IMAP_PORT` | `993` | Porta IMAP |
| `IMAP_SECURITY` | `ssl` | `ssl` o `starttls`; `none` è accettato solo su localhost |
| `IMAP_TIMEOUT` | `30` | Timeout in secondi |
| `IMAP_MAX_BODY_CHARS` | `20000` | Massimo di caratteri restituiti per un corpo o un allegato |
| `IMAP_MAX_MESSAGE_MB` | `25` | I messaggi più grandi non vengono scaricati |
| `IMAP_READ_ONLY` | `false` | `true` disattiva `create_draft`. Vedi [Modalità sola lettura](#modalità-sola-lettura) |
| `IMAP_FROM` | `IMAP_USER` | Mittente delle bozze. Obbligatoria se `IMAP_USER` non è un indirizzo email |
| `IMAP_DRAFTS_FOLDER` | automatico | Nome della cartella Bozze, se il server non la segnala con `\Drafts` |
| `IMAP_DRAFT_ALLOWED_DOMAINS` | nessun limite | Domini ammessi come destinatari, separati da virgola, es. `example.com,example.org` |

Host e porta vanno presi dalle indicazioni del tuo provider di posta. La configurazione più comune è porta 993 con SSL/TLS; se il provider indica 143 con STARTTLS, usa `IMAP_SECURITY=starttls` e `IMAP_PORT=143`.

### Come si trova la cartella Bozze

1. `IMAP_DRAFTS_FOLDER`, se impostata. La cartella deve esistere.
2. Altrimenti, la cartella che il server segnala con l'attributo SPECIAL-USE `\Drafts` (RFC 6154).

Se così non si ottiene esattamente una cartella, `create_draft` dà errore e chiede di impostare `IMAP_DRAFTS_FOLDER`. Il nome non viene mai indovinato. Per controllare il tuo server, lancia `list_folders` e cerca `\Drafts` tra i flag.

### Note sui provider

- **Microsoft 365 / Outlook.com:** non supportati. Microsoft richiede OAuth2 per IMAP e questo server fa solo il login con password.
- **Gmail:** richiede una [password per le app](https://support.google.com/accounts/answer/185833), che a sua volta richiede la verifica in due passaggi.

## Sicurezza

- **Nessun invio possibile.** Vedi [Perché questo server](#perché-questo-server).
- **Le bozze si possono solo aggiungere.** Per modificarle o cancellarle servirebbero `STORE`/`EXPUNGE`, che non vengono usati. Per correggere una bozza, creane una nuova ed elimina a mano la vecchia.
- **Mittente fisso e niente iniezione di header.** Il `From` viene dalla configurazione. Oggetti e indirizzi con a capo vengono rifiutati, e ogni voce di `to`/`cc` deve contenere un solo indirizzo valido.
- **Niente iniezione di comandi IMAP.** I parametri di ricerca rifiutano i caratteri di controllo e vengono quotati.
- **Prompt injection.** Un'email può contenere testo che cerca di dare istruzioni all'AI. Il server lo dichiara nelle istruzioni e nelle descrizioni degli strumenti, ma questa non è una vera difesa. Resta possibile una bozza preparata su istruzione di un'email malevola, per esempio con dati riservati indirizzati a un estraneo. **Chi rivede la bozza deve controllare i destinatari, non solo il testo.** Se la casella scrive quasi sempre alle stesse organizzazioni, imposta `IMAP_DRAFT_ALLOWED_DOMAINS`.
- **Credenziali.** La password sta in chiaro nella configurazione del client. Se possibile usa una password dedicata, proteggi il file (`chmod 600` su Mac/Linux) e cambia la password se il file viene condiviso.
- **Dati.** Il contenuto delle email lette passa attraverso il servizio AI che usi. Per le caselle con dati di altre persone, verifica che sia compatibile con le tue policy e i tuoi obblighi di legge.

Per segnalare una vulnerabilità, vedi [SECURITY.md](SECURITY.md).

## Limiti noti

- Solo login con password (niente OAuth2).
- Le bozze sono solo testo semplice, senza allegati e senza Bcc.
- Se la connessione cade durante il salvataggio, il server ritenta una volta e in rari casi può creare una bozza doppia.
- La ricerca `text` è eseguita dal server IMAP e non guarda dentro gli allegati. Per quelli serve `get_attachment_text` sui singoli messaggi.
- I PDF scansionati (solo immagini) non restituiscono testo; i vecchi `.doc` e `.xls` non sono supportati.
- Il thread è ricostruito cercando per oggetto (senza `Re:`/`Fwd:`) e collegando i messaggi tramite gli header. Una risposta con oggetto cambiato e senza `References` può sfuggire.
- Le ricerche con caratteri non ASCII usano `CHARSET UTF-8`, che i server IMAP molto vecchi potrebbero non supportare.
- Trasporto solo stdio (uso locale). Non esporre il server su rete senza autenticazione.

## Sviluppo

```bash
uv sync
uv run pytest
```

I test girano contro un finto server IMAP locale, quindi prova ogni nuova versione anche su una casella reale prima di farci affidamento.

### Pubblicare una versione

1. Aggiorna la versione in `pyproject.toml`, `src/imap_drafts_mcp/__init__.py` e `CHANGELOG.md`, poi lancia `uv lock`.
2. Fai commit e push su `main`.
3. Lancia `git tag vX.Y.Z && git push origin vX.Y.Z`.

Il workflow Release esegue i test e, se passano, sposta il tag `latest` sulla nuova versione. Chi usa `@latest` la riceve al successivo riavvio del client, quindi provala su una casella reale prima del passo 3.

## Licenza

[MIT](LICENSE)
