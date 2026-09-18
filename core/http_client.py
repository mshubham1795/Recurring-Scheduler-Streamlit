"""
HTTP Client Session -- stdlib replacement for requests.Session.
Direct port from sas_backend.py (zero external dependencies).

Includes Spring Security 6 XOR CSRF token masking -- CLUWE requires
the X-XSRF-TOKEN header to contain a masked version of the raw cookie
value, not the raw value itself.
"""
import os
import json
import ssl
import base64
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar

from config.constants import USER_AGENT


class HttpResponse:
    """Uniform response object wrapping urllib responses."""
    def __init__(self, status_code, text, headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = dict(headers) if headers else {}

    def json(self):
        return json.loads(self.text)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Handler that limits redirects but doesn't follow infinite loops."""
    max_redirections = 10


def mask_csrf_token(raw_token: str) -> str:
    """Implement Spring Security 6's XorCsrfTokenRequestAttributeHandler masking.

    Spring Security 6 expects the X-XSRF-TOKEN header to contain an XOR-masked
    version of the raw CSRF token (stored in the XSRF-TOKEN cookie).

    Algorithm:
        1. Convert raw token to UTF-8 bytes
        2. Generate random bytes of the same length
        3. XOR random bytes with token bytes
        4. Concatenate: random_bytes + xored_bytes
        5. Base64url-encode without padding

    The server reverses this: decodes Base64, splits in half, XORs to recover
    the raw token, and compares with the cookie value.
    """
    token_bytes = raw_token.encode("utf-8")
    random_bytes = os.urandom(len(token_bytes))
    xored = bytes(a ^ b for a, b in zip(random_bytes, token_bytes))
    combined = random_bytes + xored
    return base64.urlsafe_b64encode(combined).decode("ascii").rstrip("=")


class CluweSession:
    """Persistent HTTP session with cookie jar and SSL context for CLUWE.
    Replacement for requests.Session -- uses only Python stdlib.
    """

    def __init__(self):
        self.cookie_jar = http.cookiejar.CookieJar()
        self.ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ssl_ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except Exception:
            pass

        https_handler = urllib.request.HTTPSHandler(context=self.ssl_ctx)
        cookie_handler = urllib.request.HTTPCookieProcessor(self.cookie_jar)
        redirect_handler = NoRedirectHandler()
        self.opener = urllib.request.build_opener(
            https_handler, cookie_handler, redirect_handler
        )
        self.opener.addheaders = [("User-Agent", USER_AGENT)]

    def get(self, url, headers=None, timeout=15):
        """HTTP GET request. Returns HttpResponse."""
        req = urllib.request.Request(url, method="GET")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            resp = self.opener.open(req, timeout=timeout)
            text = resp.read().decode("utf-8", errors="replace")
            return HttpResponse(resp.status, text, resp.headers)
        except urllib.error.HTTPError as e:
            text = ""
            try:
                text = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return HttpResponse(e.code, text, e.headers)
        except Exception:
            raise

    def post(self, url, data=None, json_data=None, headers=None, timeout=30):
        """HTTP POST request. Returns HttpResponse."""
        if json_data is not None:
            body = json.dumps(json_data).encode("utf-8")
        elif data:
            body = urllib.parse.urlencode(data).encode("utf-8")
        else:
            body = b""

        req = urllib.request.Request(url, data=body, method="POST")
        if json_data is not None and (not headers or "Content-Type" not in headers):
            req.add_header("Content-Type", "application/json; charset=UTF-8")
        elif data and (not headers or "Content-Type" not in headers):
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            resp = self.opener.open(req, timeout=timeout)
            text = resp.read().decode("utf-8", errors="replace")
            return HttpResponse(resp.status, text, resp.headers)
        except urllib.error.HTTPError as e:
            text = ""
            try:
                text = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return HttpResponse(e.code, text, e.headers)
        except Exception:
            raise

    def get_cookie(self, name):
        """Get a cookie value by name (URL-decoded)."""
        for cookie in self.cookie_jar:
            if cookie.name == name:
                return urllib.parse.unquote(cookie.value)
        return ""

    def get_masked_xsrf(self):
        """Get the XSRF token masked for Spring Security 6.

        Reads the raw XSRF-TOKEN cookie and applies XOR masking so it can
        be sent as the X-XSRF-TOKEN header value.  Returns empty string
        if no XSRF-TOKEN cookie is present.
        """
        raw = self.get_cookie("XSRF-TOKEN")
        if not raw:
            return ""
        return mask_csrf_token(raw)

    def set_cookie(self, name, value, domain):
        """Manually set a cookie."""
        c = http.cookiejar.Cookie(
            version=0, name=name, value=value,
            port=None, port_specified=False,
            domain=domain, domain_specified=True, domain_initial_dot=False,
            path="/", path_specified=True, secure=True,
            expires=None, discard=True,
            comment=None, comment_url=None, rest={}, rfc2109=False
        )
        self.cookie_jar.set_cookie(c)

    def cookies_dict(self):
        """Get all cookies as a dict."""
        return {c.name: c.value for c in self.cookie_jar}
