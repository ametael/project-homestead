from datetime import datetime
from html import escape
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import re
import socket
import ssl
import unicodedata
import zlib
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import homestead as core


LIBRARY = "MEMORY/KNOWLEDGEBANK"
REFUSALS = {401, 402, 403, 407, 429, 451}
MAX_WEB_BYTES = 512 * 1024
ARCHIVE_API = "https://archive.org/wayback/available"
CAPTURE_HOST = "web.archive.org"
PRIVATE_QUERY = {"key", "token", "api_key", "apikey", "auth", "signature", "sig", "session", "access_token"}
TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}
SKIP_TAGS = {"script", "style", "template", "noscript", "svg", "nav", "footer"}
INSTRUCTION = re.compile(
    r"ignore (?:all |the )?(?:previous|prior|above) instructions|"
    r"(?:reveal|send|upload|print) (?:your|the) (?:system prompt|password|credentials|api key)|"
    r"you are now (?:in )?(?:developer mode|an? unrestricted)", re.I)
CLICKBAIT = re.compile(r"you won.t believe|one weird trick|what happened next will shock", re.I)
PAYWALL = re.compile(r"subscribe to (?:continue reading|read the full article)|"
                     r"sign in to (?:continue reading|read the full article)", re.I)


def canonical_url(raw):
    core.require(isinstance(raw, str) and 1 <= len(raw) <= 2048 and
                 all(c.isprintable() and not c.isspace() for c in raw) and "\\" not in raw,
                 "Provide one public web URL.")
    url = urlsplit(raw)
    core.require(url.scheme in {"http", "https"} and url.hostname and "." in url.hostname
                 and not url.username and not url.password
                 and url.port in {None, 443 if url.scheme == "https" else 80},
                 "Use a public HTTP or HTTPS URL without credentials or a custom port.")
    try:
        address = ipaddress.ip_address(url.hostname)
    except ValueError:
        address = None
    core.require(address is None or address.is_global, "Private network addresses are refused.")
    host = url.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    core.require(host and host not in {"localhost", "localhost.localdomain"}
                 and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                         for label in host.split(".")), "Use a public DNS name.")
    params = parse_qsl(url.query, keep_blank_values=True, max_num_fields=64)
    core.require(not any(key.casefold() in PRIVATE_QUERY for key, _ in params),
                 "A URL with credentials or a private query token is refused.")
    params = [(key, value) for key, value in params if
              key.casefold() not in TRACKING and not key.casefold().startswith("utm_")]
    path = quote(url.path or "/", safe="/%:@!$&'()*+,;=-._~")
    return urlunsplit((url.scheme, host, path, urlencode(params), ""))


class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        answers = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)
        core.require(answers and all(ipaddress.ip_address(row[4][0]).is_global for row in answers),
                     "The destination did not resolve only to public addresses.")
        sock = socket.create_connection((answers[0][4][0], self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def decoded_response(data, encoding, limit):
    encoding = encoding.strip().casefold()
    if encoding in {"", "identity"} and not data.startswith(b"\x1f\x8b"):
        return data
    if encoding == "gzip" or data.startswith(b"\x1f\x8b"):
        window = zlib.MAX_WBITS | 16
    elif encoding == "deflate":
        window = zlib.MAX_WBITS
    else:
        raise core.SafetyError("The source used an unsupported response encoding.")
    try:
        decoder = zlib.decompressobj(window)
        decoded = decoder.decompress(data, limit + 1)
    except zlib.error as error:
        raise core.SafetyError("The compressed source was unreadable.") from error
    core.require(len(decoded) <= limit and decoder.eof and not decoder.unused_data,
                 "The compressed source is incomplete or exceeds the size limit.")
    return decoded


def request(url, *, method="GET", body=None, headers=None, max_bytes=MAX_WEB_BYTES):
    parsed = urlsplit(url)
    core.require(parsed.scheme == "https", "Only HTTPS downloads are supported.")
    conn = PinnedHTTPS(parsed.hostname, timeout=8, context=ssl.create_default_context())
    try:
        target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        request_headers = {"User-Agent": "Project-Homestead/1.0", "Accept-Encoding": "identity", **(headers or {})}
        conn.request(method, target, body=body, headers=request_headers)
        response = conn.getresponse()
        if response.status != 200:
            return response.status, b"", ""
        rules = response.headers.get("X-Robots-Tag", "")
        if method == "GET" and re.search(r"\bnoai\b", rules, re.I):
            return 403, b"", ""
        data = response.read(max_bytes + 1)
        core.require(len(data) <= max_bytes, "The response exceeds the configured size limit.")
        decoded = decoded_response(data, response.headers.get("Content-Encoding", ""), max_bytes)
        return response.status, decoded, response.headers.get_content_type()
    except (OSError, http.client.HTTPException):
        return 0, b"", ""
    finally:
        conn.close()


def plain(value):
    return " ".join("".join(char for char in value
                            if char.isspace() or unicodedata.category(char) not in {"Cc", "Cf"}).split())


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = []
        self.body = []
        self.skipped = []
        self.in_title = False
        self.paywall = False

    def handle_starttag(self, tag, attrs):
        info = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag in SKIP_TAGS:
            self.skipped.append(tag)
        if tag == "meta" and str(info.get("name", "")).casefold() in {"robots", "googlebot"}:
            self.paywall |= "noai" in str(info.get("content", "")).casefold()

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if self.skipped and self.skipped[-1] == tag:
            self.skipped.pop()

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        elif not self.skipped:
            self.body.append(data)


def assess(payload, media_type, title=None):
    core.require(media_type in {"text/html", "text/plain", "application/xhtml+xml"},
                 "Use an HTML or plain-text source.")
    text = payload.decode("utf-8", errors="replace")
    if text.count("\ufffd") > max(5, len(text) // 25) or "\0" in text:
        return "UNAVAILABLE", None, None, "response did not contain readable text"
    if media_type != "text/plain":
        page = Document()
        page.feed(text)
        title = " ".join(page.title)
        body = plain(" ".join(page.body))
        if page.paywall or PAYWALL.search(body):
            return "REFUSED", None, None, "publisher access restriction"
    else:
        body = plain(text)
    title = plain(title or "Untitled source")[:240]
    if INSTRUCTION.search(title + " " + body):
        return "BLOCKED", None, None, "source tried to direct the companion"
    if CLICKBAIT.search(title):
        return "BLOCKED", None, None, "headline matched a clickbait pattern"
    if len(body) < 35:
        return "UNAVAILABLE", None, None, "no usable source text"
    return "UNVERIFIED", title, body[:12000], None


def archive_snapshot(url, fetch):
    api_status, api_body, _ = fetch(ARCHIVE_API + "?" + urlencode({"url": url}))
    if api_status != 200:
        return None
    try:
        closest = json.loads(api_body).get("archived_snapshots", {}).get("closest", {})
        if closest.get("available") is not True or str(closest.get("status")) != "200":
            return None
        date = closest["timestamp"]
        datetime.strptime(date, "%Y%m%d%H%M%S")
        archived = urlsplit(closest["url"])
        match = re.match(r"^/web/([0-9]{14})(?:[a-z]+_)?/(https?://.+)", archived.path)
        source = match[2] + ("?" + archived.query if archived.query else "") if match else ""
        if archived.hostname != CAPTURE_HOST or archived.username or archived.password or not match or match[1] != date:
            return None
        captured = canonical_url(source)
        upgraded = url.startswith("http://") and captured == "https://" + url[7:]
        if captured != url and not upgraded:
            return None
    except (KeyError, AttributeError, TypeError, ValueError, core.SafetyError):
        return None
    return f"https://{CAPTURE_HOST}/web/{date}id_/{captured}", date


def library_state(home):
    path = home.path(LIBRARY + "/library.json")
    if not path.exists():
        return {}
    core.require(path.is_file() and path.stat().st_size <= 2 * 1024 * 1024, "KnowledgeBank index is oversized.")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=core.unique_json_object)
    core.require(isinstance(value, dict), "KnowledgeBank index is invalid.")
    return value


def list_pages(home, sources):
    lines = ["# Bibliography", ""]
    blocks = ["# Hoax and source blocklist", ""]
    for url, record in sorted(sources.items()):
        shown = escape(url)
        if record["status"] == "BLOCKED":
            blocks.append(f"- {shown} · {escape(record['reason'])} · {record['checked']}")
        else:
            detail = f" · archived {record['capture']}" if record.get("capture") else ""
            lines.append(f"- {shown} · {record['status']} · {record['checked']}{detail}")
    for name, contents in (("BIBLIOGRAPHY.md", lines), ("BLOCKLIST.md", blocks)):
        core.install_bytes(home.path(f"{LIBRARY}/{name}"), ("\n".join(contents) + "\n").encode())


def store(home, url, record, body=None):
    with home.lock():
        sources = library_state(home)
        if record["status"] != "BLOCKED" and sources.get(url, {}).get("status") == "BLOCKED":
            return sources[url]
        base = home.path(LIBRARY)
        base.mkdir(parents=True, exist_ok=True)
        if body is not None:
            card = core.digest(url.encode())[:24]
            record["path"] = f"{LIBRARY}/{card}.json"
            core.record_state(home.path(record["path"]), {**record, "evidence_text": body})
        sources[url] = record
        core.require(len(core.packed(sources)) <= 2 * 1024 * 1024, "KnowledgeBank index reached its size limit.")
        core.record_state(home.path(LIBRARY + "/library.json"), sources)
        list_pages(home, sources)
    return record


def ingest(home, raw, topic, *, allow_archive=False, pasted=None, title=None, fetch=request):
    url = canonical_url(raw)
    core.require(1 <= len(topic) <= 80 and all(char.isprintable() for char in topic),
                 "Provide a short topic.")
    old = library_state(home).get(url)
    retry_archive = allow_archive and old and old.get("status") == "UNAVAILABLE" and not old.get("archive_attempted")
    if old and not retry_archive and (old["status"] == "BLOCKED" or pasted is None):
        return {**old, "reused": True}
    record = {"url": url, "topic": topic, "checked": core.stamp(), "source": "pasted" if pasted else "live"}
    if pasted is not None:
        http_status, payload, mime = 200, pasted, "text/plain"
    else:
        http_status, payload, mime = fetch(url) if url.startswith("https://") else (0, b"", "")
        if http_status not in REFUSALS and http_status != 200 and allow_archive:
            record["archive_attempted"] = True
            snapshot = archive_snapshot(url, fetch)
            if snapshot:
                capture_url, record["capture"] = snapshot
                http_status, payload, mime = fetch(capture_url)
                record.update(source="archive", archive_url=capture_url)
    if http_status in REFUSALS:
        record.update(status="REFUSED", reason="This source refuses automated reading. Please paste content you may share.")
        return store(home, url, record)
    if http_status != 200:
        record.update(status="UNAVAILABLE", reason="No readable copy was found.")
        return store(home, url, record)
    if mime not in {"text/html", "text/plain", "application/xhtml+xml"}:
        record.update(status="UNAVAILABLE", reason="This file type needs a manual source.")
        return store(home, url, record)
    status, title, evidence, reason = assess(payload, mime, title)
    record.update(status=status, title=title, reason=reason)
    return store(home, url, record, evidence)


def find(home, query, limit):
    terms = set(core.tokens_of(query))
    core.require(terms and 1 <= limit <= 50, "Provide search words and a limit from 1 to 50.")
    hits = []
    for record in library_state(home).values():
        if record["status"] not in {"UNVERIFIED", "VERIFIED"}:
            continue
        searchable = " ".join(record.get(key, "") or "" for key in ("title", "topic", "url"))
        matches = terms & set(core.tokens_of(searchable))
        if matches:
            hits.append((len(matches), record["url"], record))
    hits.sort(key=lambda item: (-item[0], item[1]))
    return {"results": [item[2] for item in hits[:limit]], "matches": len(hits)}


def block(home, raw, reason):
    core.require(isinstance(reason, str) and 1 <= len(reason) <= 160
                 and all(char.isprintable() for char in reason), "Provide a one-line reason.")
    url = canonical_url(raw)
    record = {"url": url, "status": "BLOCKED", "source": "owner review",
              "reason": reason, "checked": core.stamp()}
    return store(home, url, record)
