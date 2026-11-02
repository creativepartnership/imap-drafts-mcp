# imap-drafts-mcp

*[Leggi in italiano](README.it.md)*

An MCP server that lets Claude (or any MCP client) search and read an IMAP mailbox and prepare new messages **as drafts only**. It cannot send, move, delete or modify messages, and it does not mark them as read. A person reviews and sends every draft from their own mail client.

If you want no writing at all, set `IMAP_READ_ONLY=true`: see [Read-only mode](#read-only-mode).

Developed by [Creative Partnership Srl](https://www.cp-srl.it) for internal use and released to everyone under the MIT license.

## Why this server

An AI assistant that reads email also reads text written by strangers, and that text can try to give it instructions. This server limits what such an attack can achieve:

- There is no SMTP code and it takes no SMTP credentials, so it has no way to send.
- The only write command is IMAP `APPEND`, and its target is the Drafts folder. The folder is not a tool parameter, so the model cannot choose where to write.
- An automated test checks the commands that actually reach the IMAP server: nothing outside the allowed list, and every `APPEND` goes to Drafts.

## Tools

| Tool | What it does |
|---|---|
| `list_folders` | Lists folders, optionally with message and unread counts |
| `search_messages` | Searches by sender, recipient, subject, text, dates, unread status |
| `get_message` | Reads a message: headers, text body, list of attachments |
| `get_attachment_text` | Extracts text from an attachment (PDF, DOCX, XLSX, text/CSV) |
| `get_thread` | Rebuilds a conversation from Message-ID / References, including the Sent folder if you pass it |
| `create_draft` | Saves a plain-text message in Drafts, optionally as a reply (with `In-Reply-To`/`References` and optional quoting). It does not send. Not available in read-only mode |

## Installation

You need [uv](https://docs.astral.sh/uv/) and git. Add this to your MCP client configuration; for Claude Desktop that is `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mail": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/creativepartnership/imap-drafts-mcp@latest",
        "imap-drafts-mcp"
      ],
      "env": {
        "IMAP_HOST": "imap.example.com",
        "IMAP_USER": "name@example.com",
        "IMAP_PASSWORD": "<password>",
        "IMAP_FROM": "Your Name <name@example.com>"
      }
    }
  }
}
```

- `@latest` follows each new release: you get it the next time the client restarts, without changing anything.
- To update by hand instead, pin a version, for example `@v0.2.0`. With `@latest`, new code gets access to your mail without you reviewing it first, so pin a version if that matters to you.
- If the client cannot find `uvx`, use its absolute path as `command` (run `which uvx` to get it).

## Read-only mode

Add `"IMAP_READ_ONLY": "true"` to `env`. The `create_draft` tool is then not registered, so the model does not see it and cannot be persuaded to use it, and the server writes nothing to the mailbox. A value other than true/false (`1`/`0`, `yes`/`no`, `on`/`off` also work) stops the server from starting, so a typo cannot leave drafts enabled.

Two limits to keep in mind:

- The guarantee covers this server, not the account. The password still gives full access to the mailbox, so protect it just the same.
- If you chose this mode for security, pin a version instead of using `@latest`. Otherwise you are also relying on every future release to keep the guarantee.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `IMAP_HOST` | required | IMAP server host |
| `IMAP_USER` | required | Login name |
| `IMAP_PASSWORD` | required | Password, ideally an app-specific one |
| `IMAP_PORT` | `993` | IMAP port |
| `IMAP_SECURITY` | `ssl` | `ssl` or `starttls`; `none` is accepted only on localhost |
| `IMAP_TIMEOUT` | `30` | Timeout in seconds |
| `IMAP_MAX_BODY_CHARS` | `20000` | Maximum characters returned for a body or attachment |
| `IMAP_MAX_MESSAGE_MB` | `25` | Larger messages are not downloaded |
| `IMAP_READ_ONLY` | `false` | `true` disables `create_draft`. See [Read-only mode](#read-only-mode) |
| `IMAP_FROM` | `IMAP_USER` | Sender of drafts. Required if `IMAP_USER` is not an email address |
| `IMAP_DRAFTS_FOLDER` | automatic | Drafts folder name, if the server does not mark it with `\Drafts` |
| `IMAP_DRAFT_ALLOWED_DOMAINS` | no limit | Comma-separated domains allowed as recipients, e.g. `example.com,example.org` |

Get the host and port from your mail provider. Port 993 with SSL/TLS is the most common setup; if your provider specifies 143 with STARTTLS, set `IMAP_SECURITY=starttls` and `IMAP_PORT=143`.

### How the Drafts folder is found

1. `IMAP_DRAFTS_FOLDER`, if set. The folder must exist.
2. Otherwise, the folder the server marks with the SPECIAL-USE attribute `\Drafts` (RFC 6154).

If this does not give exactly one folder, `create_draft` returns an error asking you to set `IMAP_DRAFTS_FOLDER`. The name is never guessed. To check your server, call `list_folders` and look for `\Drafts` in the flags.

### Provider notes

- **Microsoft 365 / Outlook.com:** not supported. Microsoft requires OAuth2 for IMAP, and this server only does password login.
- **Gmail:** requires an [app password](https://support.google.com/accounts/answer/185833), which needs 2-Step Verification enabled.

## Security

- **No sending is possible.** See [Why this server](#why-this-server).
- **Drafts can only be added.** Changing or deleting them would need `STORE`/`EXPUNGE`, which are not used. To correct a draft, create a new one and delete the old one by hand.
- **Fixed sender, no header injection.** `From` comes from the configuration. Subjects and addresses containing line breaks are rejected, and each `to`/`cc` entry must hold one valid address.
- **No IMAP command injection.** Search parameters reject control characters and are quoted.
- **Prompt injection.** An email can contain text that tries to instruct the AI. The server says so in its instructions and tool descriptions, but that is not a real defence. What remains possible is a draft prepared on the instructions of a malicious email, for example with confidential data addressed to a stranger. **Whoever reviews a draft must check the recipients, not just the text.** If the mailbox writes mostly to the same organisations, set `IMAP_DRAFT_ALLOWED_DOMAINS`.
- **Credentials.** The password sits in plain text in the client configuration. Use a dedicated or app-specific password where possible, protect the file (`chmod 600` on Mac/Linux) and change the password if the file is shared.
- **Data.** The content of the emails you read passes through the AI service you use. For mailboxes holding other people's data, check that this is compatible with your policies and legal obligations.

To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Known limitations

- Password login only (no OAuth2).
- Drafts are plain text, without attachments or Bcc.
- If the connection drops during a save, the server retries once, and in rare cases this can create a duplicate draft.
- `text` search runs on the IMAP server and does not look inside attachments. Use `get_attachment_text` on individual messages.
- Scanned PDFs (images only) return no text. Old `.doc` and `.xls` files are not supported.
- Threads are rebuilt by searching on the subject (without `Re:`/`Fwd:`) and linking messages through headers. A reply with a changed subject and no `References` can be missed.
- Searches with non-ASCII characters use `CHARSET UTF-8`, which very old IMAP servers may not support.
- stdio transport only (local use). Do not expose the server on a network without authentication.

## Development

```bash
uv sync
uv run pytest
```

The tests run against a fake local IMAP server, so try a new version on a real mailbox as well before relying on it.

### Releasing

1. Update the version in `pyproject.toml`, `src/imap_drafts_mcp/__init__.py` and `CHANGELOG.md`, then run `uv lock`.
2. Commit and push to `main`.
3. Run `git tag vX.Y.Z && git push origin vX.Y.Z`.

The Release workflow runs the tests and, if they pass, moves the `latest` tag to the new version. Everyone using `@latest` gets it at their next client restart, so try it on a real mailbox before step 3.

## License

[MIT](LICENSE)
