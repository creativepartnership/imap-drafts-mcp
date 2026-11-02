# Changelog

## 0.2.0 (2026-11-02)

- New `IMAP_READ_ONLY=true` setting: `create_draft` is not registered, so the server is strictly read-only. An unrecognised value stops the server from starting.
- New `latest` tag, moved automatically to each release. The recommended installation now uses `@latest`, and updates arrive when the client restarts. To update by hand, pin a version such as `@v0.2.0`.

## 0.1.0 (2026-11-02)

First public version.

- Read tools: `list_folders`, `search_messages`, `get_message`, `get_attachment_text`, `get_thread`.
- `create_draft`: saves plain-text messages in the Drafts folder only, including replies. It cannot send.
- Optional recipient domain allowlist (`IMAP_DRAFT_ALLOWED_DOMAINS`).
- Packaged for installation with `uvx` from GitHub.
