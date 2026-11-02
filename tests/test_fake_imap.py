"""Test del server contro un finto server IMAP locale.
Esecuzione:  uv run pytest   (oppure: uv run python tests/test_fake_imap.py)
Verifica anche che l'unico comando di scrittura sia APPEND, e solo verso la
cartella Bozze."""
import json
import os
import re
import socket
import socketserver
import subprocess
import sys
import threading
from email import message_from_bytes, policy
from email.message import EmailMessage

COMMANDS = []  # comandi ricevuti dal finto server
APPENDED = []  # (cartella, flag, messaggio) ricevuti con APPEND
# False: \Drafts compare solo con LIST (SPECIAL-USE), come su alcuni server
SERVER = {"plain_list_special_use": True,
          "search_lines": None}  # righe * SEARCH da inviare al posto di quelle vere


def build_messages():
    m1 = EmailMessage()
    m1["From"] = "Mario Rossi <mario@example.com>"
    m1["To"] = "anna@example.org"
    m1["Subject"] = "Preventivo sito web"
    m1["Date"] = "Mon, 05 Oct 2026 09:00:00 +0200"
    m1["Message-ID"] = "<a1@example.com>"
    m1.set_content("Buongiorno, in allegato il preventivo. Ci sentiamo domani.")
    m1.add_attachment("voce;importo\nsito;1200\n".encode(), maintype="text",
                      subtype="csv", filename="preventivo.csv")

    m2 = EmailMessage()
    m2["From"] = "anna@example.org"
    m2["To"] = "Mario Rossi <mario@example.com>"
    m2["Subject"] = "Re: Preventivo sito web"
    m2["Date"] = "Mon, 05 Oct 2026 11:30:00 +0200"
    m2["Message-ID"] = "<b2@example.org>"
    m2["In-Reply-To"] = "<a1@example.com>"
    m2["References"] = "<a1@example.com>"
    m2.set_content("Grazie, lo approviamo.\n\n> Buongiorno, in allegato il preventivo.\n")

    m3 = EmailMessage()
    m3["From"] = "newsletter@example.net"
    m3["To"] = "anna@example.org"
    m3["Subject"] = "Offerte d'autunno è qui"
    m3["Date"] = "Tue, 06 Oct 2026 08:00:00 +0200"
    m3["Message-ID"] = "<c3@example.net>"
    m3.set_content("<html><body><p>Sconti&nbsp;<b>fino al 50%</b></p></body></html>",
                   subtype="html")
    return [m.as_bytes() for m in (m1, m2, m3)]


MSGS = build_messages()  # UID = indice + 1
FLAGS = {1: r"\Seen", 2: r"\Seen", 3: ""}


def hdr_only(raw: bytes) -> bytes:
    head = raw.split(b"\r\n\r\n", 1)[0] if b"\r\n\r\n" in raw else raw.split(b"\n\n", 1)[0]
    return head + b"\r\n\r\n"


class Handler(socketserver.StreamRequestHandler):
    def send(self, s):
        self.wfile.write(s if isinstance(s, bytes) else s.encode("utf-8"))

    def handle(self):
        self.send("* OK IMAP4rev1 fake ready\r\n")
        for line in self.rfile:
            line = line.decode("utf-8").rstrip("\r\n")
            tag, _, rest = line.partition(" ")
            COMMANDS.append(rest.split(" ")[0].upper() + (
                " " + rest.split(" ")[1].upper()
                if rest.upper().startswith(("UID", "LIST (SPECIAL-USE)")) else ""))
            up = rest.upper()
            if up.startswith("CAPABILITY"):
                self.send(f"* CAPABILITY IMAP4rev1 SPECIAL-USE\r\n{tag} OK done\r\n")
            elif up.startswith("LOGIN"):
                self.send(f"{tag} OK logged in\r\n")
            elif up.startswith("LIST (SPECIAL-USE)"):
                self.send('* LIST (\\HasNoChildren \\Sent) "/" "Posta inviata"\r\n')
                self.send('* LIST (\\HasNoChildren \\Drafts) "/" "Bozze"\r\n')
                self.send(f"{tag} OK done\r\n")
            elif up.startswith("LIST"):
                drafts = " \\Drafts" if SERVER["plain_list_special_use"] else ""
                self.send('* LIST (\\HasNoChildren) "/" "INBOX"\r\n')
                self.send('* LIST (\\HasNoChildren) "/" "Posta inviata"\r\n')
                self.send('* LIST (\\HasNoChildren) "/" "Archivio &AOk-"\r\n')
                self.send(f'* LIST (\\HasNoChildren{drafts}) "/" "Bozze"\r\n')
                self.send('* LIST (\\Noselect \\HasChildren) "/" "Shared"\r\n')
                self.send(f"{tag} OK done\r\n")
            elif up.startswith(("EXAMINE", "SELECT")):
                self.send(f"* {len(MSGS)} EXISTS\r\n{tag} OK [READ-ONLY] done\r\n")
            elif up.startswith("STATUS"):
                self.send('* STATUS "INBOX" (MESSAGES 3 UNSEEN 1)\r\n')
                self.send(f"{tag} OK done\r\n")
            elif up.startswith("UID SEARCH") and SERVER["search_lines"]:
                for found in SERVER["search_lines"]:
                    self.send("* SEARCH " + found + "\r\n")
                self.send(f"{tag} OK done\r\n")
            elif up.startswith("UID SEARCH"):
                hits = []
                subj = re.search(r'SUBJECT "((?:[^"\\]|\\.)*)"', rest)
                frm = re.search(r'FROM "((?:[^"\\]|\\.)*)"', rest)
                for uid, raw in enumerate(MSGS, 1):
                    text = raw.decode("utf-8", "replace")
                    from email.header import decode_header, make_header
                    dec = lambda v: str(make_header(decode_header(v)))
                    s = dec(re.search(r"^Subject: (.*)$", text, re.M | re.I).group(1))
                    f = dec(re.search(r"^From: (.*)$", text, re.M | re.I).group(1))
                    if subj and subj.group(1).lower() not in s.lower():
                        continue
                    if frm and frm.group(1).lower() not in f.lower():
                        continue
                    hits.append(str(uid))
                self.send("* SEARCH " + " ".join(hits) + "\r\n")
                self.send(f"{tag} OK done\r\n")
            elif up.startswith("UID FETCH"):
                m = re.match(r"UID FETCH (\S+) \((.*)\)$", rest, re.I)
                uids = [int(x) for x in m.group(1).split(",")]
                items = m.group(2).upper()
                for uid in uids:
                    if not 1 <= uid <= len(MSGS):
                        continue
                    raw, fl = MSGS[uid - 1], FLAGS[uid]
                    if "HEADER.FIELDS" in items:
                        h = hdr_only(raw)
                        # UID dopo il literal, come fanno alcuni server
                        self.send(f"* {uid} FETCH (FLAGS ({fl}) RFC822.SIZE {len(raw)} "
                                  f"BODY[HEADER.FIELDS (FROM TO)] {{{len(h)}}}\r\n".encode()
                                  + h + f" UID {uid})\r\n".encode())
                    elif "BODY.PEEK[]" in items:
                        self.send(f"* {uid} FETCH (UID {uid} FLAGS ({fl}) "
                                  f"BODY[] {{{len(raw)}}}\r\n".encode() + raw + b")\r\n")
                    else:
                        self.send(f"* {uid} FETCH (UID {uid} RFC822.SIZE {len(raw)})\r\n")
                self.send(f"{tag} OK done\r\n")
            elif up.startswith("APPEND"):
                m = re.match(r'APPEND ("(?:[^"\\]|\\.)*"|\S+) (?:\(([^)]*)\) )?'
                             r'(?:"[^"]*" )?\{(\d+)\}$', rest, re.I)
                self.send("+ ready\r\n")
                raw = self.rfile.read(int(m.group(3)))
                self.rfile.readline()  # CRLF finale del comando
                APPENDED.append((m.group(1), m.group(2) or "", raw))
                self.send(f"{tag} OK [APPENDUID 1 {len(APPENDED)}] done\r\n")
            elif up.startswith("LOGOUT"):
                self.send(f"* BYE\r\n{tag} OK bye\r\n")
                return
            else:
                self.send(f"{tag} BAD unknown command\r\n")


def mcp_stdio(requests, **env):
    """Parla col server vero via stdio, come un client MCP. Restituisce la
    risposta a initialize e quelle alle richieste [(metodo, parametri)]."""
    p = subprocess.Popen([sys.executable, "-m", "imap_drafts_mcp"], text=True,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         env={**os.environ, **env})

    def send(msg):
        p.stdin.write(json.dumps({"jsonrpc": "2.0", **msg}) + "\n")
        p.stdin.flush()
        return json.loads(p.stdout.readline()) if "id" in msg else None

    try:
        init = send({"id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"}}})
        send({"method": "notifications/initialized"})
        return init["result"], [send({"id": i, "method": method, "params": params})
                                for i, (method, params) in enumerate(requests, 2)]
    finally:
        p.stdin.close()
        p.wait(timeout=20)


def test_fake_imap():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    os.environ.update(IMAP_HOST="127.0.0.1", IMAP_PORT=str(port), IMAP_USER="u",
                      IMAP_PASSWORD="p", IMAP_SECURITY="none",
                      IMAP_FROM="Studio Prova <studio@example.it>")
    from imap_drafts_mcp import server as S

    # cartelle (con decodifica UTF-7 e cartella Noselect esclusa)
    names = [f["name"] for f in S.list_folders()]
    assert names == ["INBOX", "Posta inviata", "Archivio é", "Bozze"], names
    assert S.list_folders(with_counts=True)[0]["messages"] == 3

    # ricerca
    r = S.search_messages(subject="preventivo")
    assert r["total_matches"] == 2 and [m["uid"] for m in r["messages"]] == [2, 1], r
    assert r["messages"][1]["from"].startswith("Mario Rossi")
    assert S.search_messages(sender="newsletter")["messages"][0]["unread"] is True
    assert S.search_messages(subject="è qui")["total_matches"] == 1  # non-ASCII

    # ricerca senza filtri: tutti i messaggi, dal piu' recente
    r = S.search_messages()
    assert r["total_matches"] == 3 and [m["uid"] for m in r["messages"]] == [3, 2, 1], r

    # risultato spezzato su piu' righe * SEARCH: non si perde l'ultima
    SERVER["search_lines"] = ["1", "2 3"]
    r = S.search_messages()
    assert r["total_matches"] == 3 and r["messages"][0]["uid"] == 3, r

    # casella molto grande: la riga * SEARCH supera il limite di 1 MB di imaplib
    SERVER["search_lines"] = [" ".join(map(str, range(1, 200_001)))]
    assert S.search_messages()["total_matches"] == 200_000
    SERVER["search_lines"] = None
    assert S.search_messages()["total_matches"] == 3  # connessione ancora allineata

    # lettura messaggio con allegato
    g = S.get_message("INBOX", 1)
    assert "preventivo" in g["body"] and g["attachments"][0]["filename"] == "preventivo.csv"
    assert "sito;1200" in S.get_attachment_text("INBOX", 1, 0)["text"]
    h = S.get_message("INBOX", 3)
    assert "fino al 50%" in h["body"] and "<" not in h["body"], h["body"]

    # thread: dalla risposta si risale al messaggio originale
    t = S.get_thread("INBOX", 2, include_bodies=True)
    assert t["thread_size"] == 2, t
    assert [m["uid"] for m in t["messages"]] == [1, 2]
    assert "approviamo" in t["messages"][1]["body"] and ">" not in t["messages"][1]["body"]

    # sicurezza: niente iniezione di comandi IMAP
    for bad in ('x"\r\nA1 STORE 1 +FLAGS (\\Deleted)', "x\nfoo"):
        try:
            S.search_messages(subject=bad)
            raise SystemExit("injection not blocked")
        except ValueError:
            pass

    # bozza nuova: finisce in Bozze, con \Draft, mittente dalla configurazione
    d = S.create_draft(to=["Anna Bianchi <anna@example.org>"], subject="Prova è",
                       body="Buongiorno,\necco la bozza.")
    assert d["status"] == "draft_saved_not_sent" and d["folder"] == "Bozze", d
    assert d["uid"] == 1, d
    folder, flags, raw = APPENDED[-1]
    assert folder == '"Bozze"' and "\\Draft" in flags, (folder, flags)
    m = message_from_bytes(raw, policy=policy.default)
    assert m["From"] == "Studio Prova <studio@example.it>", m["From"]
    assert m["To"] == "Anna Bianchi <anna@example.org>" and m["Subject"] == "Prova è"
    assert "ecco la bozza" in m.get_content() and m["Message-ID"] and m["Date"]
    assert m["In-Reply-To"] is None

    # risposta: si aggancia al thread e cita l'originale
    S.create_draft(to=["anna@example.org"], body="Perfetto, procediamo.",
                   reply_to_folder="INBOX", reply_to_uid=2, quote_original=True)
    m = message_from_bytes(APPENDED[-1][2], policy=policy.default)
    assert m["Subject"] == "Re: Preventivo sito web", m["Subject"]
    assert m["In-Reply-To"] == "<b2@example.org>", m["In-Reply-To"]
    assert m["References"] == "<a1@example.com> <b2@example.org>", m["References"]
    assert "procediamo" in m.get_content() and "> Grazie, lo approviamo." in m.get_content()

    # risposta senza citazione, con oggetto esplicito
    S.create_draft(to=["mario@example.com"], body="Ok", subject="Conferma",
                   reply_to_folder="INBOX", reply_to_uid=1)
    m = message_from_bytes(APPENDED[-1][2], policy=policy.default)
    assert m["Subject"] == "Conferma" and m["References"] == "<a1@example.com>"
    assert "> " not in m.get_content()

    # input rifiutati, senza scrivere nulla
    n = len(APPENDED)
    S.ALLOWED_DOMAINS = {"example.org"}
    for kwargs in (
        dict(to=["x@example.org"], body="b", subject="x\r\nBcc: evil@attacker.test"),
        dict(to=["x@example.org\r\nBcc: evil@attacker.test"], body="b"),
        dict(to=["x@example.org, evil@attacker.test"], body="b"),
        dict(to=["non-un-indirizzo"], body="b"),
        dict(to=[], body="b"),
        dict(to=["evil@attacker.test"], body="b"),          # dominio non ammesso
        dict(to=["x@example.org"], cc=["evil@attacker.test"], body="b"),
        dict(to=["x@example.org"], body="b", reply_to_uid=1),  # manca la cartella
    ):
        try:
            S.create_draft(**kwargs)
            raise SystemExit(f"draft not rejected: {kwargs}")
        except ValueError:
            pass
    S.ALLOWED_DOMAINS = set()
    assert len(APPENDED) == n, "a rejected draft was written"

    # cartella Bozze configurata ma inesistente: errore, nessun fallback
    S._drafts_cache, S.DRAFTS_FOLDER = None, "Bozze vecchie"
    try:
        S.create_draft(to=["x@example.org"], body="b")
        raise SystemExit("missing drafts folder not detected")
    except RuntimeError:
        pass
    S._drafts_cache, S.DRAFTS_FOLDER = None, ""
    assert len(APPENDED) == n

    # \Drafts visibile solo con LIST (SPECIAL-USE)
    SERVER["plain_list_special_use"] = False
    assert S.create_draft(to=["x@example.org"], body="b")["folder"] == "Bozze"
    assert "LIST (SPECIAL-USE)" in COMMANDS

    # via MCP il messaggio d'errore arriva al modello (mcp 2.x lo nasconderebbe)
    call_draft = ("tools/call", {"name": "create_draft", "arguments": {
        "to": ["x@example.org"], "body": "b"}})
    _, (r,) = mcp_stdio([("tools/call", {"name": "create_draft", "arguments": {
        "to": ["non-un-indirizzo"], "body": "b"}})])
    r = r["result"]
    assert r["isError"] and "Invalid address" in r["content"][0]["text"], r

    # di default le bozze sono attive
    init, (tools,) = mcp_stdio([("tools/list", {})])
    assert "create_draft" in [t["name"] for t in tools["result"]["tools"]]
    assert "draft" in init["instructions"].lower()

    # sola lettura: create_draft non esiste, la lettura funziona, nessun APPEND
    n = len(APPENDED)
    init, (tools, draft, search) = mcp_stdio(
        [("tools/list", {}), call_draft,
         ("tools/call", {"name": "search_messages", "arguments": {}})],
        IMAP_READ_ONLY="true")
    names = [t["name"] for t in tools["result"]["tools"]]
    assert "create_draft" not in names and "search_messages" in names, names
    assert "draft" not in init["instructions"].lower(), init["instructions"]
    assert "error" in draft or draft["result"].get("isError"), draft
    assert not search["result"].get("isError"), search
    assert len(APPENDED) == n, "read-only mode wrote a message"

    # IMAP_READ_ONLY esplicitamente false: bozze attive
    _, (tools,) = mcp_stdio([("tools/list", {})], IMAP_READ_ONLY="false")
    assert "create_draft" in [t["name"] for t in tools["result"]["tools"]]

    # valore non riconosciuto: il server non parte, non si ripiega sulle bozze
    bad = subprocess.run([sys.executable, "-m", "imap_drafts_mcp"], text=True,
                         stdin=subprocess.DEVNULL, capture_output=True,
                         env={**os.environ, "IMAP_READ_ONLY": "ture"})
    assert bad.returncode != 0 and "IMAP_READ_ONLY" in bad.stderr, bad

    # unico comando di scrittura: APPEND, e solo verso Bozze
    allowed = {"CAPABILITY", "LOGIN", "LIST", "LIST (SPECIAL-USE)", "EXAMINE", "STATUS", "UID SEARCH",
               "UID FETCH", "APPEND", "LOGOUT"}
    used = set(COMMANDS)
    assert used <= allowed, used - allowed
    assert {f for f, _, _ in APPENDED} == {'"Bozze"'}, APPENDED
    print("OK - comandi usati:", sorted(used))


if __name__ == "__main__":
    test_fake_imap()
