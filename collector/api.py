import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from psycopg.types.json import Jsonb


log = logging.getLogger(__name__)


class ChessAPI:
    def __init__(self, connection, user_agent, opener=urlopen, sleeper=time.sleep):
        self.connection = connection
        self.user_agent = user_agent
        self.opener = opener
        self.sleeper = sleeper

    def get(self, url):
        cached = self.connection.execute(
            "SELECT etag, modified, payload FROM chess.http_cache WHERE url = %s", (url,)
        ).fetchone()
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if cached:
            if cached[0]:
                headers["If-None-Match"] = cached[0]
            if cached[1]:
                headers["If-Modified-Since"] = cached[1]
        for attempt in range(4):
            try:
                with self.opener(Request(url, headers=headers), timeout=30) as response:
                    payload = json.load(response)
                    self.connection.execute(
                        """INSERT INTO chess.http_cache (url, etag, modified, payload)
                           VALUES (%s, %s, %s, %s) ON CONFLICT (url) DO UPDATE SET
                           etag = EXCLUDED.etag, modified = EXCLUDED.modified,
                           payload = EXCLUDED.payload, checked_at = now()""",
                        (url, response.headers.get("ETag"), response.headers.get("Last-Modified"), Jsonb(payload)),
                    )
                    return payload
            except HTTPError as error:
                if error.code == 304 and cached:
                    self.connection.execute("UPDATE chess.http_cache SET checked_at = now() WHERE url = %s", (url,))
                    return cached[2]
                if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                    raise
                retry_after = error.headers.get("Retry-After", "") if error.headers else ""
                delay = min(int(retry_after), 60) if retry_after.isdigit() else 2 ** (attempt + 1)
            except (URLError, TimeoutError, ConnectionError):
                if attempt == 3:
                    raise
                delay = 2 ** (attempt + 1)
            log.warning("Retrying %s in %ss", url, delay)
            self.sleeper(delay)
