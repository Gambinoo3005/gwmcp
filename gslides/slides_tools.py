"""
Google Slides MCP Tools

This module provides MCP tools for interacting with Google Slides API.
"""

import logging
import asyncio
from typing import List, Dict, Any


from auth.service_decorator import require_google_service
from core.server import server
from core.utils import handle_http_errors
from core.comments import create_comment_tools

logger = logging.getLogger(__name__)


@server.tool()
@handle_http_errors("create_presentation", service_type="slides")
@require_google_service("slides", "slides")
async def create_presentation(
    service, user_google_email: str, title: str = "Untitled Presentation"
) -> str:
    """
    Create a new Google Slides presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        title (str): The title for the new presentation. Defaults to "Untitled Presentation".

    Returns:
        str: Details about the created presentation including ID and URL.
    """
    logger.info(
        f"[create_presentation] Invoked. Email: '{user_google_email}', Title: '{title}'"
    )

    body = {"title": title}

    result = await asyncio.to_thread(service.presentations().create(body=body).execute)

    presentation_id = result.get("presentationId")
    presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"

    slide_count = len(result.get("slides", []))
    slide_word = "slide" if slide_count == 1 else "slides"
    confirmation_message = f'Created presentation "{title}" \u2014 {slide_count} {slide_word} \u2014 {presentation_url}'

    logger.info(f"Presentation created successfully for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors("get_presentation", is_read_only=True, service_type="slides")
@require_google_service("slides", "slides_read")
async def get_presentation(
    service, user_google_email: str, presentation_id: str
) -> str:
    """
    Get details about a Google Slides presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        presentation_id (str): The ID of the presentation to retrieve.

    Returns:
        str: Details about the presentation including title, slides count, and metadata.
    """
    logger.info(
        f"[get_presentation] Invoked. Email: '{user_google_email}', ID: '{presentation_id}'"
    )

    result = await asyncio.to_thread(
        service.presentations().get(presentationId=presentation_id).execute
    )

    title = result.get("title", "Untitled")
    slides = result.get("slides", [])

    slides_info = []
    for i, slide in enumerate(slides, 1):
        slide_id = slide.get("objectId", "Unknown")
        page_elements = slide.get("pageElements", [])
        page_type = slide.get("pageType", "SLIDE")
        element_count = len(page_elements)
        element_word = "element" if element_count == 1 else "elements"

        # Collect text from the slide whose JSON structure is very complicated
        # https://googleapis.github.io/google-api-python-client/docs/dyn/slides_v1.presentations.html#get
        slide_text = ""
        try:
            texts_from_elements = []
            for page_element in slide.get("pageElements", []):
                shape = page_element.get("shape", None)
                if shape and shape.get("text", None):
                    text = shape.get("text", None)
                    if text:
                        text_elements_in_shape = []
                        for text_element in text.get("textElements", []):
                            text_run = text_element.get("textRun", None)
                            if text_run:
                                content = text_run.get("content", None)
                                if content:
                                    start_index = text_element.get("startIndex", 0)
                                    text_elements_in_shape.append(
                                        (start_index, content)
                                    )

                        if text_elements_in_shape:
                            # Sort text elements within a single shape
                            text_elements_in_shape.sort(key=lambda item: item[0])
                            full_text_from_shape = "".join(
                                [item[1] for item in text_elements_in_shape]
                            )
                            texts_from_elements.append(full_text_from_shape)

            # cleanup text we collected
            slide_text = "\n".join(texts_from_elements)
            slide_text_rows = slide_text.split("\n")
            slide_text_rows = [row for row in slide_text_rows if len(row.strip()) > 0]
            if slide_text_rows:
                slide_text = " \u2014 " + "; ".join(slide_text_rows)
            else:
                slide_text = ""
        except Exception as e:
            logger.warning(f"Failed to extract text from the slide {slide_id}: {e}")
            slide_text = ""

        slides_info.append(
            f"  {i}. Slide {i} ({page_type}) \u2014 {element_count} {element_word}{slide_text}"
        )

    slide_count = len(slides)
    slide_word = "slide" if slide_count == 1 else "slides"
    confirmation_message = f'Presentation "{title}" \u2014 {slide_count} {slide_word}:\n' + (
        "\n".join(slides_info) if slides_info else "  No slides found"
    )

    logger.info(f"Presentation retrieved successfully for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors("batch_update_presentation", service_type="slides")
@require_google_service("slides", "slides")
async def batch_update_presentation(
    service,
    user_google_email: str,
    presentation_id: str,
    requests: List[Dict[str, Any]],
) -> str:
    """
    Apply batch updates to a Google Slides presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        presentation_id (str): The ID of the presentation to update.
        requests (List[Dict[str, Any]]): List of update requests to apply.

    Returns:
        str: Details about the batch update operation results.
    """
    logger.info(
        f"[batch_update_presentation] Invoked. Email: '{user_google_email}', ID: '{presentation_id}', Requests: {len(requests)}"
    )

    body = {"requests": requests}

    result = await asyncio.to_thread(
        service.presentations()
        .batchUpdate(presentationId=presentation_id, body=body)
        .execute
    )

    replies = result.get("replies", [])
    presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"

    # We need the presentation title for a human-friendly message
    try:
        pres_result = await asyncio.to_thread(
            service.presentations().get(presentationId=presentation_id).execute
        )
        pres_title = pres_result.get("title", "Untitled")
    except Exception:
        pres_title = "Untitled"

    op_count = len(requests)
    op_word = "operation" if op_count == 1 else "operations"
    confirmation_message = f'Updated presentation "{pres_title}" \u2014 {op_count} {op_word} applied \u2014 {presentation_url}'

    if replies:
        details = []
        for i, reply in enumerate(replies, 1):
            if "createSlide" in reply:
                details.append(f"  {i}. Created slide")
            elif "createShape" in reply:
                details.append(f"  {i}. Created shape")
            else:
                details.append(f"  {i}. Operation completed")
        confirmation_message += "\n" + "\n".join(details)

    logger.info(f"Batch update completed successfully for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors("get_page", is_read_only=True, service_type="slides")
@require_google_service("slides", "slides_read")
async def get_page(
    service, user_google_email: str, presentation_id: str, page_object_id: str
) -> str:
    """
    Get details about a specific page (slide) in a presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        presentation_id (str): The ID of the presentation.
        page_object_id (str): The object ID of the page/slide to retrieve.

    Returns:
        str: Details about the specific page including elements and layout.
    """
    logger.info(
        f"[get_page] Invoked. Email: '{user_google_email}', Presentation: '{presentation_id}', Page: '{page_object_id}'"
    )

    result = await asyncio.to_thread(
        service.presentations()
        .pages()
        .get(presentationId=presentation_id, pageObjectId=page_object_id)
        .execute
    )

    page_type = result.get("pageType", "Unknown")
    page_elements = result.get("pageElements", [])

    elements_info = []
    for i, element in enumerate(page_elements, 1):
        element_id = element.get("objectId", "Unknown")
        if "shape" in element:
            shape_type = element["shape"].get("shapeType", "Unknown")
            elements_info.append(f"  {i}. Shape ({shape_type})")
        elif "table" in element:
            table = element["table"]
            rows = table.get("rows", 0)
            cols = table.get("columns", 0)
            elements_info.append(f"  {i}. Table ({rows}x{cols})")
        elif "line" in element:
            line_type = element["line"].get("lineType", "Unknown")
            elements_info.append(f"  {i}. Line ({line_type})")
        else:
            elements_info.append(f"  {i}. Element (unknown type)")

    element_count = len(page_elements)
    element_word = "element" if element_count == 1 else "elements"
    confirmation_message = f'Slide "{page_object_id}" ({page_type}) \u2014 {element_count} {element_word}:\n' + (
        "\n".join(elements_info) if elements_info else "  No elements found"
    )

    logger.info(f"Page retrieved successfully for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors("get_page_thumbnail", is_read_only=True, service_type="slides")
@require_google_service("slides", "slides_read")
async def get_page_thumbnail(
    service,
    user_google_email: str,
    presentation_id: str,
    page_object_id: str,
    thumbnail_size: str = "MEDIUM",
) -> str:
    """
    Generate a thumbnail URL for a specific page (slide) in a presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        presentation_id (str): The ID of the presentation.
        page_object_id (str): The object ID of the page/slide.
        thumbnail_size (str): Size of thumbnail ("LARGE", "MEDIUM", "SMALL"). Defaults to "MEDIUM".

    Returns:
        str: URL to the generated thumbnail image.
    """
    logger.info(
        f"[get_page_thumbnail] Invoked. Email: '{user_google_email}', Presentation: '{presentation_id}', Page: '{page_object_id}', Size: '{thumbnail_size}'"
    )

    result = await asyncio.to_thread(
        service.presentations()
        .pages()
        .getThumbnail(
            presentationId=presentation_id,
            pageObjectId=page_object_id,
            thumbnailProperties_thumbnailSize=thumbnail_size,
            thumbnailProperties_mimeType="PNG",
        )
        .execute
    )

    thumbnail_url = result.get("contentUrl", "")
    width = result.get("width", "")
    height = result.get("height", "")
    dimensions = f"{width}x{height}" if width and height else thumbnail_size

    confirmation_message = f"Generated thumbnail for slide {page_object_id} \u2014 {dimensions} \u2014 {thumbnail_url}"

    logger.info(f"Thumbnail generated successfully for {user_google_email}")
    return confirmation_message


# Create comment management tools for slides
_comment_tools = create_comment_tools("presentation", "presentation_id")
list_presentation_comments = _comment_tools["list_comments"]
manage_presentation_comment = _comment_tools["manage_comment"]

# Aliases for backwards compatibility and intuitive naming
list_slide_comments = list_presentation_comments
manage_slide_comment = manage_presentation_comment
