"""Job URL normalization, applied before every dedup check and to every stored ``jobs.url``."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query parameters that only say where a click came from; matched case-insensitively.
TRACKING_PARAMS = frozenset(
    {
        "gh_src",
        "lever-source",
        "lever-origin",
        "source",
        "src",
        "ref",
        "referrer",
        "refid",
        "trk",
        "trackingid",
        "gclid",
        "fbclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "_hsenc",
        "_hsmi",
    }
)
TRACKING_PARAM_PREFIXES = ("utm_",)
DEFAULT_PORTS = {"http": 80, "https": 443}


def _is_tracking_param(name: str) -> bool:
    lowered = name.lower()
    return lowered in TRACKING_PARAMS or lowered.startswith(TRACKING_PARAM_PREFIXES)


def normalize_url(url: str) -> str | None:
    """The canonical form of a job URL, or ``None`` when it is not an absolute http(s) URL.

    Lowercases the scheme and host, drops the default port, the fragment, tracking parameters
    and a trailing slash. The remaining query parameters keep their order.
    """
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if scheme not in DEFAULT_PORTS or not host:
        return None

    if ":" in host:
        host = f"[{host}]"
    netloc = host if port is None or port == DEFAULT_PORTS[scheme] else f"{host}:{port}"
    path = parts.path.rstrip("/")
    params = parse_qsl(parts.query, keep_blank_values=True)
    kept = [(name, value) for name, value in params if not _is_tracking_param(name)]
    # An untouched query keeps its original encoding.
    query = parts.query if len(kept) == len(params) else urlencode(kept)
    return urlunsplit((scheme, netloc, path, query, ""))
