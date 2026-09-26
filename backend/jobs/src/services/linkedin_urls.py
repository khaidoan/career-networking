"""The single normalizer for LinkedIn profile URLs (no I/O).

Every stored ``company_networking.linkedin_url`` goes through ``normalize_linkedin_profile_url``,
so the same profile always has one spelling and the ``(company_id, linkedin_url)`` unique index
can catch duplicates. Migration 0012 carries its own copy of these rules; keep them in step.
"""

import re
from urllib.parse import urlsplit

CANONICAL_PREFIX = "https://www.linkedin.com/in/"
LINKEDIN_DOMAIN = "linkedin.com"
# Country and language subdomains such as "uk.linkedin.com" or "www.linkedin.com".
SUBDOMAIN_PATTERN = re.compile(r"[a-z]{2,3}")
SLUG_PATTERN = re.compile(r"[^/\s]+")


def normalize_linkedin_profile_url(url: str) -> str | None:
    """``https://www.linkedin.com/in/<slug>`` for a LinkedIn profile URL, else ``None``.

    Lowercases the URL, forces ``https``, maps ``linkedin.com`` and ``xx.linkedin.com`` to
    ``www.linkedin.com`` and drops the query string, fragment and trailing slash. Anything that is
    not a ``/in/<slug>`` path on a LinkedIn host (company pages, jobs, ``/pub/``) is rejected.
    """
    text = url.strip().lower()
    if not text:
        return None
    if "://" not in text:
        text = f"https://{text}"
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    # A port or user info in the netloc is never part of a real profile link.
    host = parts.netloc
    if host != LINKEDIN_DOMAIN:
        subdomain, dot, domain = host.partition(".")
        if not dot or domain != LINKEDIN_DOMAIN or not SUBDOMAIN_PATTERN.fullmatch(subdomain):
            return None
    segments = parts.path.rstrip("/").split("/")
    if len(segments) != 3 or segments[0] or segments[1] != "in":
        return None
    slug = segments[2]
    if not SLUG_PATTERN.fullmatch(slug):
        return None
    return f"{CANONICAL_PREFIX}{slug}"
