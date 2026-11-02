# Changelog

## 0.1.0 (2026-11-02)

First public version.

- Read tools: `list_folders`, `search_messages`, `get_message`, `get_attachment_text`, `get_thread`.
- `create_draft`: saves plain-text messages in the Drafts folder only, including replies. It cannot send.
- Optional recipient domain allowlist (`IMAP_DRAFT_ALLOWED_DOMAINS`).
- Packaged for installation with `uvx` from GitHub.
