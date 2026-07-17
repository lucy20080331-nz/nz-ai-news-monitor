"""
utils.py

Common helper functions for the AI News Monitor project.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


# ----------------------------------------------------
# URL Helpers
# ----------------------------------------------------

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid"
}


def normalize_url(url: str | None) -> str:
    """
    Remove tracking parameters and normalize URLs.

    Returns an empty string if URL is missing.
    """

    if not url:
        return ""

    url = url.strip()

    parsed = urlparse(url)

    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query)
        if k.lower() not in TRACKING_PARAMS
    ]

    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=urlencode(query),
        fragment=""
    )

    return urlunparse(normalized).rstrip("/")


# ----------------------------------------------------
# Text Helpers
# ----------------------------------------------------

def normalize_text(text: str | None) -> str:
    """
    Normalize titles for hashing.
    """

    if not text:
        return ""

    text = text.lower()

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ----------------------------------------------------
# Article Key
# ----------------------------------------------------

def make_article_key(
    article_url: str | None,
    title: str | None,
    source: str | None,
    published_at: str | None,
) -> str:
    """
    Generate a deterministic article key.

    Priority:
        1. Normalized URL
        2. title + source + published date

    Uses SHA256.
    """

    normalized_url = normalize_url(article_url)

    if normalized_url:

        key = normalized_url

    else:

        key = "|".join([
            normalize_text(title),
            normalize_text(source),
            str(published_at)
        ])

    return hashlib.sha256(
        key.encode("utf-8")
    ).hexdigest()


# ----------------------------------------------------
# Batch
# ----------------------------------------------------

def current_batch_id(prefix="INITIAL") -> str:
    """
    Example

    INITIAL_20260713_093015
    """

    now = datetime.now()

    return f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}"


# ----------------------------------------------------
# Timestamp
# ----------------------------------------------------

def current_timestamp():

    return datetime.now(timezone.utc)


# ----------------------------------------------------
# Data Validation
# ----------------------------------------------------

def validate_required_columns(df, required_columns):
    """
    Raise an exception if required columns are missing.
    """

    missing = [
        c
        for c in required_columns
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )


# ----------------------------------------------------
# Duplicate Check
# ----------------------------------------------------

def remove_dataframe_duplicates(df):

    before = len(df)

    df = df.drop_duplicates(
        subset="article_key",
        keep="first"
    )

    removed = before - len(df)

    print(f"Removed {removed} duplicate articles.")

    return df

# ----------------------------------------------------
# normalization function
# ----------------------------------------------------


def normalize_value(value):
    """
    Convert Python objects into Snowflake-friendly values.
    """
    if value is None:
        return None

    if isinstance(value, list):
        return ", ".join(str(v) for v in value)

    if isinstance(value, dict):
        import json
        return json.dumps(value)

    return value

# ----------------------------------------------------
# normalization Unicode
# ----------------------------------------------------


def clean_text(value):
    if value is None:
        return None

    value = str(value)

    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value or None