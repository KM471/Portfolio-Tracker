import json
import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv

from market_symbols import TICKER_MAP


load_dotenv()

CACHE_DIRECTORY = Path.home() / ".portfolio_intelligence_cache"
MAPPING_CACHE_PATH = CACHE_DIRECTORY / "ticker_mappings.json"

DEFAULT_MODEL = "gpt-6-luna"

ALLOWED_QUOTE_TYPES = {
    "EQUITY",
    "ETF",
    "MUTUALFUND",
}


def _get_setting(name, default=None):
    """
    Read a setting from the local .env/environment first,
    then from Streamlit Secrets.
    """

    value = os.getenv(name)

    if value is not None and str(value).strip():
        return str(value).strip()

    try:
        import streamlit as st

        value = st.secrets.get(name)

        if value is not None and str(value).strip():
            return str(value).strip()

    except Exception:
        pass

    return default


# ============================================================
# Mapping cache
# ============================================================

def _load_mapping_cache():
    if not MAPPING_CACHE_PATH.exists():
        return {}

    try:
        with MAPPING_CACHE_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            return data

    except (
        OSError,
        json.JSONDecodeError,
    ):
        pass

    return {}


def _save_mapping_cache(cache):
    try:
        CACHE_DIRECTORY.mkdir(
            parents=True,
            exist_ok=True,
        )

        with MAPPING_CACHE_PATH.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                cache,
                file,
                indent=2,
                sort_keys=True,
            )

    except OSError:
        # Mapping still works for the current request even
        # if the host cannot persist the file.
        pass


def _get_cached_mapping(
    trading212_ticker,
):
    cache = _load_mapping_cache()

    record = cache.get(
        trading212_ticker
    )

    if isinstance(
        record,
        str,
    ):
        value = record.strip()

        if value:
            return value

    if isinstance(
        record,
        dict,
    ):
        value = str(
            record.get(
                "yahoo_ticker"
            )
            or ""
        ).strip()

        if value:
            return value

    return None


def _cache_mapping(
    trading212_ticker,
    yahoo_ticker,
    instrument,
    source,
):
    cache = _load_mapping_cache()

    cache[
        trading212_ticker
    ] = {
        "yahoo_ticker": yahoo_ticker,
        "source": source,
        "instrument_name": (
            instrument.get("name")
            or instrument.get("shortName")
        ),
        "source_currency": instrument.get(
            "currencyCode"
        ),
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    _save_mapping_cache(
        cache
    )


# ============================================================
# Yahoo candidate discovery
# ============================================================

def _normalise_text(value):
    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(
            value
            or ""
        ).lower(),
    )

    removable_words = {
        "plc",
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "company",
        "co",
        "limited",
        "ltd",
        "sa",
        "se",
        "ag",
        "nv",
        "holdings",
    }

    words = [
        word
        for word in value.split()
        if word not in removable_words
    ]

    return " ".join(
        words
    )


def _similarity_score(
    source_name,
    candidate_name,
):
    source = _normalise_text(
        source_name
    )

    candidate = _normalise_text(
        candidate_name
    )

    if not source or not candidate:
        return 0.0

    sequence_score = (
        SequenceMatcher(
            None,
            source,
            candidate,
        ).ratio()
    )

    source_words = set(
        source.split()
    )

    candidate_words = set(
        candidate.split()
    )

    overlap_score = (
        len(
            source_words
            & candidate_words
        )
        /
        max(
            len(source_words),
            1,
        )
    )

    return (
        sequence_score * 0.65
        + overlap_score * 0.35
    )


def _ticker_search_hint(
    trading212_ticker,
):
    value = str(
        trading212_ticker
        or ""
    )

    value = re.sub(
        r"_US_EQ$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"_EQ$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    return value


def _build_search_queries(
    trading212_ticker,
    instrument,
):
    queries = []

    for value in (
        instrument.get("name"),
        instrument.get("shortName"),
        instrument.get("isin"),
        _ticker_search_hint(
            trading212_ticker
        ),
    ):
        value = str(
            value
            or ""
        ).strip()

        if (
            value
            and value not in queries
        ):
            queries.append(
                value
            )

    return queries


def _search_yahoo_candidates(
    trading212_ticker,
    instrument,
    max_candidates=8,
):
    source_name = (
        instrument.get("name")
        or instrument.get("shortName")
        or trading212_ticker
    )

    candidates = {}

    queries = _build_search_queries(
        trading212_ticker,
        instrument,
    )

    for query in queries:

        try:
            search = yf.Search(
                query,
                max_results=max_candidates,
                news_count=0,
                lists_count=0,
                include_cb=False,
                include_nav_links=False,
                include_research=False,
                include_cultural_assets=False,
                enable_fuzzy_query=True,
                recommended=0,
                timeout=15,
                raise_errors=False,
            )

            quotes = (
                search.quotes
                or []
            )

        except Exception:
            continue

        for quote in quotes:

            if not isinstance(
                quote,
                dict,
            ):
                continue

            symbol = str(
                quote.get("symbol")
                or ""
            ).strip()

            quote_type = str(
                quote.get(
                    "quoteType"
                )
                or ""
            ).upper()

            if not symbol:
                continue

            if (
                quote_type
                and quote_type
                not in ALLOWED_QUOTE_TYPES
            ):
                continue

            candidate = {
                "symbol": symbol,
                "shortname": quote.get(
                    "shortname"
                ),
                "longname": quote.get(
                    "longname"
                ),
                "exchange": quote.get(
                    "exchange"
                ),
                "exchange_display": quote.get(
                    "exchDisp"
                ),
                "quote_type": quote_type,
            }

            candidate_name = (
                candidate.get(
                    "longname"
                )
                or candidate.get(
                    "shortname"
                )
                or ""
            )

            candidate[
                "name_similarity"
            ] = round(
                _similarity_score(
                    source_name,
                    candidate_name,
                ),
                4,
            )

            existing = candidates.get(
                symbol
            )

            if (
                existing is None
                or candidate[
                    "name_similarity"
                ]
                > existing[
                    "name_similarity"
                ]
            ):
                candidates[
                    symbol
                ] = candidate

    ordered = sorted(
        candidates.values(),
        key=lambda item: item[
            "name_similarity"
        ],
        reverse=True,
    )

    return ordered[
        :max_candidates
    ]


# ============================================================
# AI candidate selection
# ============================================================

def _build_ai_prompt(
    trading212_ticker,
    instrument,
    candidates,
):
    payload = {
        "trading212_instrument": {
            "ticker": trading212_ticker,
            "name": instrument.get(
                "name"
            ),
            "short_name": instrument.get(
                "shortName"
            ),
            "isin": instrument.get(
                "isin"
            ),
            "currency": instrument.get(
                "currencyCode"
            ),
            "type": instrument.get(
                "type"
            ),
        },
        "yahoo_candidates": (
            candidates
        ),
    }

    return (
        "You map Trading 212 instruments to Yahoo Finance symbols.\n"
        "Choose the Yahoo candidate representing the SAME security and, "
        "where possible, the same listing rather than an ADR or a "
        "different share class.\n\n"
        "Use the company/fund name, ISIN, currency, instrument type, "
        "exchange and ticker conventions.\n\n"
        "You MUST choose only a symbol appearing in yahoo_candidates. "
        "You are not allowed to invent another ticker.\n\n"
        "If none of the candidates clearly match, return NONE.\n\n"
        "Return ONLY the exact Yahoo symbol or NONE. "
        "Do not provide an explanation.\n\n"
        f"Data:\n"
        f"{json.dumps(payload, indent=2)}"
    )


def _extract_candidate_symbol(
    output_text,
    candidates,
):
    candidate_symbols = {
        candidate["symbol"]
        for candidate in candidates
    }

    text = str(
        output_text
        or ""
    ).strip()

    if not text:
        return None

    if text.upper() == "NONE":
        return None

    cleaned = (
        text
        .replace(
            "`",
            "",
        )
        .replace(
            '"',
            "",
        )
        .replace(
            "'",
            "",
        )
        .strip()
    )

    first_line = (
        cleaned
        .splitlines()[0]
    )

    first_token = (
        first_line
        .split()[0]
        .strip(
            " ,.;:"
        )
    )

    if first_token in candidate_symbols:
        return first_token

    for symbol in candidate_symbols:

        if re.search(
            (
                rf"(?<![A-Z0-9.\-])"
                rf"{re.escape(symbol)}"
                rf"(?![A-Z0-9.\-])"
            ),
            cleaned,
            flags=re.IGNORECASE,
        ):
            return symbol

    return None


def _choose_with_ai(
    trading212_ticker,
    instrument,
    candidates,
):
    api_key = _get_setting(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "An unmapped Trading 212 instrument was found, "
            "but OPENAI_API_KEY is not configured."
        )

    model = _get_setting(
        "OPENAI_TICKER_MODEL",
        DEFAULT_MODEL,
    )

    try:
        from openai import OpenAI

    except ImportError as error:
        raise RuntimeError(
            "The 'openai' package is required for "
            "automatic ticker resolution."
        ) from error

    client = OpenAI(
        api_key=api_key,
        timeout=25.0,
        max_retries=1,
    )

    response = (
        client.responses.create(
            model=model,
            input=_build_ai_prompt(
                trading212_ticker,
                instrument,
                candidates,
            ),
        )
    )

    return _extract_candidate_symbol(
        response.output_text,
        candidates,
    )


# ============================================================
# Yahoo verification
# ============================================================

def _normalise_currency_code(
    currency,
):
    value = str(
        currency
        or ""
    ).strip().upper()

    if value == "GBX":
        return "GBP"

    # Yahoo frequently represents UK pence as GBp.
    # Upper-casing GBp gives GBP.
    return value


def _verify_yahoo_symbol(
    yahoo_ticker,
    source_currency=None,
):
    try:
        ticker = yf.Ticker(
            yahoo_ticker
        )

        history = ticker.history(
            period="1mo",
            auto_adjust=False,
            actions=False,
        )

        if (
            history is None
            or history.empty
        ):
            return False

        if (
            "Close"
            not in history.columns
        ):
            return False

        if (
            history[
                "Close"
            ]
            .dropna()
            .empty
        ):
            return False

        yahoo_currency = None

        try:
            yahoo_currency = (
                ticker.fast_info.get(
                    "currency"
                )
            )

        except Exception:
            pass

        source_currency = (
            _normalise_currency_code(
                source_currency
            )
        )

        yahoo_currency = (
            _normalise_currency_code(
                yahoo_currency
            )
        )

        if (
            source_currency
            and yahoo_currency
            and source_currency
            != yahoo_currency
        ):
            return False

        return True

    except Exception:
        return False


# ============================================================
# Public resolver
# ============================================================

def resolve_yahoo_ticker(
    trading212_ticker,
    instrument=None,
    force_ai=False,
):
    """
    Resolve a Trading 212 instrument to a verified Yahoo ticker.

    Resolution order:

    1. Existing manually verified mapping.
    2. Previously verified automatic mapping.
    3. Yahoo Finance candidate search.
    4. AI selection from Yahoo candidates only.
    5. Independent Yahoo market-data/currency verification.
    """

    trading212_ticker = str(
        trading212_ticker
        or ""
    ).strip()

    if not trading212_ticker:
        raise ValueError(
            "Trading 212 ticker is empty."
        )

    instrument = dict(
        instrument
        or {}
    )

    # Existing mappings always have priority.
    if (
        not force_ai
        and trading212_ticker
        in TICKER_MAP
    ):
        return TICKER_MAP[
            trading212_ticker
        ]

    # Then check previously resolved mappings.
    if not force_ai:

        cached = (
            _get_cached_mapping(
                trading212_ticker
            )
        )

        if cached:
            return cached

    # Search Yahoo for real candidate instruments.
    candidates = (
        _search_yahoo_candidates(
            trading212_ticker,
            instrument,
        )
    )

    if not candidates:
        raise KeyError(
            "No Yahoo Finance candidates "
            "were found for "
            f"{trading212_ticker}."
        )

    # AI chooses ONLY from Yahoo's candidate list.
    selected = _choose_with_ai(
        trading212_ticker,
        instrument,
        candidates,
    )

    if not selected:

        candidate_text = ", ".join(
            candidate[
                "symbol"
            ]
            for candidate
            in candidates
        )

        raise KeyError(
            "AI ticker resolver could not "
            "confidently map "
            f"{trading212_ticker}. "
            "Yahoo candidates: "
            f"{candidate_text}"
        )

    # Verify actual Yahoo price history and currency.
    source_currency = (
        instrument.get(
            "currencyCode"
        )
    )

    if not _verify_yahoo_symbol(
        selected,
        source_currency=source_currency,
    ):
        raise ValueError(
            "AI selected Yahoo symbol "
            f"{selected} for "
            f"{trading212_ticker}, but "
            "the symbol failed Yahoo "
            "market-data/currency verification."
        )

    _cache_mapping(
        trading212_ticker,
        selected,
        instrument,
        source=(
            "openai+yahoo-search"
        ),
    )

    return selected