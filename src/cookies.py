import os
import re
import logging
import random
import urllib.parse

yt_cookies_pattern = re.compile("^(#.*?)?\.youtube\.com")
consent_pattern = re.compile("(?<=PENDING\+)(\d+)")

logger = logging.getLogger(name=__name__)


def _load_cookies_file(cookies_file: str) -> dict:
    cookies: dict[str, str] = dict()

    if cookies_file and os.path.isfile(cookies_file):
        with open(cookies_file) as f:
            content = f.read()

        lines = [
            line for line in content.splitlines() if yt_cookies_pattern.match(line)
        ]

        for line in lines:
            parts = re.split("\s+", line)
            key = parts[5]
            value = ""
            if len(parts) >= 7:
                value = parts[6]
            cookies[key] = value
    elif cookies_file:
        logger.warning(f"given cookie file '{cookies_file}' could not be found")

    return cookies


def _init_consent(user_consent: str) -> str:
    if "YES" in user_consent:
        return user_consent

    consent_id_match = consent_pattern.search(user_consent)

    consent_id = (
        consent_id_match.group(0) if consent_id_match else random.randint(100, 999)
    )

    return f"YES+{consent_id}"


def initialize_cookies(cookies_file: str) -> dict:
    cookies: dict[str, str] = dict()

    loaded_cookies = _load_cookies_file(cookies_file=cookies_file)

    cookies["PREF"] = urllib.parse.urlencode({"hl": "en", "tz": "UTC"})

    if "__Secure-3PSID" in loaded_cookies.keys():
        cookies["__Secure-3PSID"] = loaded_cookies["__Secure-3PSID"]

    cookies["CONSENT"] = _init_consent(user_consent=loaded_cookies.get("CONSENT", ""))

    threepapisid = loaded_cookies.get("__Secure-3PAPISID")
    sapisid = loaded_cookies.get("SAPISID")

    if not sapisid and threepapisid:
        sapisid = threepapisid

    if sapisid:
        cookies["SAPISID"] = sapisid

    if not threepapisid and sapisid:
        threepapisid = sapisid

    if threepapisid:
        cookies["__Secure-3PAPISID"] = threepapisid

    return cookies
