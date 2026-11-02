# Security policy

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private reporting instead: **Security** tab → **Report a vulnerability**.

Include the affected version, the steps to reproduce, and the impact you expect. Do not include real credentials or the content of real mailboxes.

This project is maintained on a best-effort basis, so there is no guaranteed response time.

## What counts as a vulnerability

The project's main promise is that the server only reads the mailbox and writes only to the Drafts folder. Examples of what we want to hear about:

- any way to send email, or to make the server issue an IMAP command other than `EXAMINE`, `SEARCH`, `LIST`, `STATUS`, `FETCH` (with `BODY.PEEK`) or `APPEND`;
- any way to `APPEND` outside the Drafts folder;
- any way to change a message's flags, including marking it as read;
- injection of IMAP commands or email headers through tool parameters;
- a bypass of `IMAP_DRAFT_ALLOWED_DOMAINS`;
- leaks of credentials.

## Known risk: prompt injection

Text in an email can persuade a model to prepare a draft the user did not want. This is a known limit, not a vulnerability in itself: the draft is not sent, and a person must review it. See the Security section of the [README](README.md).
