"""
Google Custom Search (PSE) MCP Tools

This module provides MCP tools for interacting with Google Programmable Search Engine.
"""

import logging
import asyncio
import os
from typing import Optional, Literal

from auth.service_decorator import require_google_service
from core.server import server
from core.utils import handle_http_errors, StringList

logger = logging.getLogger(__name__)


@server.tool()
@handle_http_errors("search_custom", is_read_only=True, service_type="customsearch")
@require_google_service("customsearch", "customsearch")
async def search_custom(
    service,
    user_google_email: str,
    q: str,
    num: int = 10,
    start: int = 1,
    safe: Literal["active", "moderate", "off"] = "off",
    search_type: Optional[Literal["image"]] = None,
    site_search: Optional[str] = None,
    site_search_filter: Optional[Literal["e", "i"]] = None,
    date_restrict: Optional[str] = None,
    file_type: Optional[str] = None,
    language: Optional[str] = None,
    country: Optional[str] = None,
    sites: Optional[StringList] = None,
) -> str:
    """
    Performs a search using Google Custom Search JSON API.

    Args:
        user_google_email (str): The user's Google email address. Required.
        q (str): The search query. Required.
        num (int): Number of results to return (1-10). Defaults to 10.
        start (int): The index of the first result to return (1-based). Defaults to 1.
        safe (Literal["active", "moderate", "off"]): Safe search level. Defaults to "off".
        search_type (Optional[Literal["image"]]): Search for images if set to "image".
        site_search (Optional[str]): Restrict search to a specific site/domain.
        site_search_filter (Optional[Literal["e", "i"]]): Exclude ("e") or include ("i") site_search results.
        date_restrict (Optional[str]): Restrict results by date (e.g., "d5" for past 5 days, "m3" for past 3 months).
        file_type (Optional[str]): Filter by file type (e.g., "pdf", "doc").
        language (Optional[str]): Language code for results (e.g., "lang_en").
        country (Optional[str]): Country code for results (e.g., "countryUS").
        sites (Optional[List[str]]): List of sites/domains to restrict search to (e.g., ["example.com", "docs.example.com"]). When provided, results are limited to these sites.

    Returns:
        str: Formatted search results including title, link, and snippet for each result.
    """
    # Get API key and search engine ID from environment
    api_key = os.environ.get("GOOGLE_PSE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_PSE_API_KEY environment variable not set. Please set it to your Google Custom Search API key."
        )

    cx = os.environ.get("GOOGLE_PSE_ENGINE_ID")
    if not cx:
        raise ValueError(
            "GOOGLE_PSE_ENGINE_ID environment variable not set. Please set it to your Programmable Search Engine ID."
        )

    logger.info(
        f"[search_custom] Invoked. Email: '{user_google_email}', Query: '{q}', CX: '{cx}'"
    )

    # Apply site restriction if sites are provided
    if sites:
        site_query = " OR ".join([f"site:{site}" for site in sites])
        q = f"{q} ({site_query})"
        logger.info(f"[search_custom] Applied site restriction: {sites}")

    # Build the request parameters
    params = {
        "key": api_key,
        "cx": cx,
        "q": q,
        "num": num,
        "start": start,
        "safe": safe,
    }

    # Add optional parameters
    if search_type:
        params["searchType"] = search_type
    if site_search:
        params["siteSearch"] = site_search
    if site_search_filter:
        params["siteSearchFilter"] = site_search_filter
    if date_restrict:
        params["dateRestrict"] = date_restrict
    if file_type:
        params["fileType"] = file_type
    if language:
        params["lr"] = language
    if country:
        params["cr"] = country

    # Execute the search request
    result = await asyncio.to_thread(service.cse().list(**params).execute)

    # Extract search information
    search_info = result.get("searchInformation", {})
    total_results = search_info.get("totalResults", "0")
    search_time = search_info.get("searchTime", 0)

    # Extract search results
    items = result.get("items", [])

    if not items:
        logger.info(f"Search completed for {user_google_email}")
        return f'No results found for "{q}"'

    # Format the response
    confirmation_message = f'Found {total_results} results for "{q}":'

    for i, item in enumerate(items, start):
        title = item.get("title", "No title")
        link = item.get("link", "No link")
        snippet = item.get("snippet", "No description available").replace("\n", " ")

        confirmation_message += f"\n  {i}. {title}\n     {link}\n     {snippet}"

    # Add information about pagination
    queries = result.get("queries", {})
    if "nextPage" in queries:
        next_start = queries["nextPage"][0].get("startIndex", 0)
        confirmation_message += (
            f"\n\nTo see more results, search again with start={next_start}"
        )

    logger.info(f"Search completed for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors(
    "get_search_engine_info", is_read_only=True, service_type="customsearch"
)
@require_google_service("customsearch", "customsearch")
async def get_search_engine_info(service, user_google_email: str) -> str:
    """
    Retrieves metadata about a Programmable Search Engine.

    Args:
        user_google_email (str): The user's Google email address. Required.

    Returns:
        str: Information about the search engine including its configuration and available refinements.
    """
    # Get API key and search engine ID from environment
    api_key = os.environ.get("GOOGLE_PSE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_PSE_API_KEY environment variable not set. Please set it to your Google Custom Search API key."
        )

    cx = os.environ.get("GOOGLE_PSE_ENGINE_ID")
    if not cx:
        raise ValueError(
            "GOOGLE_PSE_ENGINE_ID environment variable not set. Please set it to your Programmable Search Engine ID."
        )

    logger.info(
        f"[get_search_engine_info] Invoked. Email: '{user_google_email}', CX: '{cx}'"
    )

    # Perform a minimal search to get the search engine context
    params = {
        "key": api_key,
        "cx": cx,
        "q": "test",  # Minimal query to get metadata
        "num": 1,
    }

    result = await asyncio.to_thread(service.cse().list(**params).execute)

    # Extract context information
    context = result.get("context", {})
    title = context.get("title", "Unknown")

    # Count refinements
    refinements = []
    if "facets" in context:
        for facet in context["facets"]:
            for item in facet:
                label = item.get("label", "Unknown")
                anchor = item.get("anchor", "Unknown")
                refinements.append(f"  - {label} (anchor: {anchor})")

    refinement_count = len(refinements)
    confirmation_message = f'Search engine "{title}" \u2014 {refinement_count} refinements available'

    if refinements:
        confirmation_message += "\n" + "\n".join(refinements)

    logger.info(f"Search engine info retrieved for {user_google_email}")
    return confirmation_message
