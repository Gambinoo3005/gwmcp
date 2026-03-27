"""
Google Forms MCP Tools

This module provides MCP tools for interacting with Google Forms API.
"""

import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any


from auth.service_decorator import require_google_service
from core.server import server
from core.utils import handle_http_errors

logger = logging.getLogger(__name__)


def _extract_option_values(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract valid option objects from Forms choice option objects.

    Returns the full option dicts (preserving fields like ``isOther``,
    ``image``, ``goToAction``, and ``goToSectionId``) while filtering
    out entries that lack a truthy ``value``.
    """
    return [option for option in options if option.get("value")]


def _get_question_type(question: Dict[str, Any]) -> str:
    """Infer a stable question/item type label from a Forms question payload."""
    choice_question = question.get("choiceQuestion")
    if choice_question:
        return choice_question.get("type", "CHOICE")

    text_question = question.get("textQuestion")
    if text_question:
        return "PARAGRAPH" if text_question.get("paragraph") else "TEXT"

    if "rowQuestion" in question:
        return "GRID_ROW"
    if "scaleQuestion" in question:
        return "SCALE"
    if "dateQuestion" in question:
        return "DATE"
    if "timeQuestion" in question:
        return "TIME"
    if "fileUploadQuestion" in question:
        return "FILE_UPLOAD"
    if "ratingQuestion" in question:
        return "RATING"

    return "QUESTION"


def _serialize_form_item(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Serialize a Forms item with the key metadata agents need for edits."""
    serialized_item: Dict[str, Any] = {
        "index": index,
        "itemId": item.get("itemId"),
        "title": item.get("title", f"Question {index}"),
    }

    if item.get("description"):
        serialized_item["description"] = item["description"]

    if "questionItem" in item:
        question = item.get("questionItem", {}).get("question", {})
        serialized_item["type"] = _get_question_type(question)
        serialized_item["required"] = question.get("required", False)

        question_id = question.get("questionId")
        if question_id:
            serialized_item["questionId"] = question_id

        choice_question = question.get("choiceQuestion")
        if choice_question:
            serialized_item["options"] = _extract_option_values(
                choice_question.get("options", [])
            )

        return serialized_item

    if "questionGroupItem" in item:
        question_group = item.get("questionGroupItem", {})
        columns = _extract_option_values(
            question_group.get("grid", {}).get("columns", {}).get("options", [])
        )

        rows = []
        for question in question_group.get("questions", []):
            row: Dict[str, Any] = {
                "title": question.get("rowQuestion", {}).get("title", "")
            }
            row_question_id = question.get("questionId")
            if row_question_id:
                row["questionId"] = row_question_id
            row["required"] = question.get("required", False)
            rows.append(row)

        serialized_item["type"] = "GRID"
        serialized_item["grid"] = {"rows": rows, "columns": columns}
        return serialized_item

    if "pageBreakItem" in item:
        serialized_item["type"] = "PAGE_BREAK"
    elif "textItem" in item:
        serialized_item["type"] = "TEXT_ITEM"
    elif "imageItem" in item:
        serialized_item["type"] = "IMAGE"
    elif "videoItem" in item:
        serialized_item["type"] = "VIDEO"
    else:
        serialized_item["type"] = "UNKNOWN"

    return serialized_item


@server.tool()
@handle_http_errors("create_form", service_type="forms")
@require_google_service("forms", "forms")
async def create_form(
    service,
    user_google_email: str,
    title: str,
    description: Optional[str] = None,
    document_title: Optional[str] = None,
) -> str:
    """
    Create a new form using the title given in the provided form message in the request.

    Args:
        user_google_email (str): The user's Google email address. Required.
        title (str): The title of the form.
        description (Optional[str]): The description of the form.
        document_title (Optional[str]): The document title (shown in browser tab).

    Returns:
        str: Confirmation message with form ID and edit URL.
    """
    logger.info(f"[create_form] Invoked. Email: '{user_google_email}', Title: {title}")

    form_body: Dict[str, Any] = {"info": {"title": title}}

    if description:
        form_body["info"]["description"] = description

    if document_title:
        form_body["info"]["document_title"] = document_title

    created_form = await asyncio.to_thread(
        service.forms().create(body=form_body).execute
    )

    form_id = created_form.get("formId")
    edit_url = f"https://docs.google.com/forms/d/{form_id}/edit"
    responder_url = created_form.get(
        "responderUri", f"https://docs.google.com/forms/d/{form_id}/viewform"
    )

    form_title = created_form.get("info", {}).get("title", title)

    logger.info(f"Form created successfully for {user_google_email}. ID: {form_id}")
    return f'Created form "{form_title}" \u2014 Edit: {edit_url} \u2014 Share: {responder_url}'


@server.tool()
@handle_http_errors("get_form", is_read_only=True, service_type="forms")
@require_google_service("forms", "forms")
async def get_form(service, user_google_email: str, form_id: str) -> str:
    """
    Get a form.

    Args:
        user_google_email (str): The user's Google email address. Required.
        form_id (str): The ID of the form to retrieve.

    Returns:
        str: Form details including title, description, questions, and URLs.
    """
    logger.info(f"[get_form] Invoked. Email: '{user_google_email}', Form ID: {form_id}")

    form = await asyncio.to_thread(service.forms().get(formId=form_id).execute)

    form_info = form.get("info", {})
    title = form_info.get("title", "No Title")
    description = form_info.get("description", "No Description")

    edit_url = f"https://docs.google.com/forms/d/{form_id}/edit"
    responder_url = form.get(
        "responderUri", f"https://docs.google.com/forms/d/{form_id}/viewform"
    )

    items = form.get("items", [])
    serialized_items = [
        _serialize_form_item(item, i) for i, item in enumerate(items, 1)
    ]

    # Build human-friendly question list
    items_summary = []
    for serialized_item in serialized_items:
        item_index = serialized_item["index"]
        item_title = serialized_item.get("title", f"Item {item_index}")
        item_type = serialized_item.get("type", "UNKNOWN")

        # Build type detail string
        type_detail = item_type
        if item_type == "SCALE":
            scale_q = None
            # Try to get scale bounds from original item
            if item_index - 1 < len(items):
                orig_item = items[item_index - 1]
                scale_q = orig_item.get("questionItem", {}).get("question", {}).get("scaleQuestion")
            if scale_q:
                low = scale_q.get("low", 1)
                high = scale_q.get("high", 5)
                type_detail = f"SCALE, {low}\u2013{high}"
        elif item_type in ("RADIO", "CHECKBOX", "DROP_DOWN") and serialized_item.get("options"):
            option_values = [o.get("value", "") for o in serialized_item["options"] if o.get("value")]
            if option_values:
                type_detail = f"{item_type}: {', '.join(option_values)}"

        required_text = ", required" if serialized_item.get("required") else ""
        items_summary.append(f"  {item_index}. {item_title} ({type_detail}{required_text})")

    question_count = sum(1 for s in serialized_items if s.get("type") not in ("PAGE_BREAK", "TEXT_ITEM", "IMAGE", "VIDEO"))

    if items_summary:
        header = f'Form "{title}" \u2014 {question_count} question{"s" if question_count != 1 else ""}:'
        if description and description != "No Description":
            header += f"\n  Description: {description}"
        header += f"\n  Edit: {edit_url} \u2014 Share: {responder_url}"
        items_text = "\n".join(items_summary)
        result = f"{header}\n{items_text}"
    else:
        result = f'Form "{title}" \u2014 0 questions'
        if description and description != "No Description":
            result += f"\n  Description: {description}"
        result += f"\n  Edit: {edit_url} \u2014 Share: {responder_url}"

    logger.info(f"Successfully retrieved form for {user_google_email}. ID: {form_id}")
    return result


@server.tool()
@handle_http_errors("set_publish_settings", service_type="forms")
@require_google_service("forms", "forms")
async def set_publish_settings(
    service,
    user_google_email: str,
    form_id: str,
    publish_as_template: bool = False,
    require_authentication: bool = False,
) -> str:
    """
    Updates the publish settings of a form.

    Args:
        user_google_email (str): The user's Google email address. Required.
        form_id (str): The ID of the form to update publish settings for.
        publish_as_template (bool): Whether to publish as a template. Defaults to False.
        require_authentication (bool): Whether to require authentication to view/submit. Defaults to False.

    Returns:
        str: Confirmation message of the successful publish settings update.
    """
    logger.info(
        f"[set_publish_settings] Invoked. Email: '{user_google_email}', Form ID: {form_id}"
    )

    settings_body = {
        "publishAsTemplate": publish_as_template,
        "requireAuthentication": require_authentication,
    }

    # Fetch form title for human-friendly output
    form = await asyncio.to_thread(service.forms().get(formId=form_id).execute)
    form_title = form.get("info", {}).get("title", "Untitled form")

    await asyncio.to_thread(
        service.forms().setPublishSettings(formId=form_id, body=settings_body).execute
    )

    logger.info(
        f"Publish settings updated successfully for {user_google_email}. Form ID: {form_id}"
    )
    return f'Updated publish settings for "{form_title}"'


@server.tool()
@handle_http_errors("get_form_response", is_read_only=True, service_type="forms")
@require_google_service("forms", "forms")
async def get_form_response(
    service, user_google_email: str, form_id: str, response_id: str
) -> str:
    """
    Get one response from the form.

    Args:
        user_google_email (str): The user's Google email address. Required.
        form_id (str): The ID of the form.
        response_id (str): The ID of the response to retrieve.

    Returns:
        str: Response details including answers and metadata.
    """
    logger.info(
        f"[get_form_response] Invoked. Email: '{user_google_email}', Form ID: {form_id}, Response ID: {response_id}"
    )

    # Fetch form metadata to get title and question labels
    form = await asyncio.to_thread(service.forms().get(formId=form_id).execute)
    form_title = form.get("info", {}).get("title", "Untitled form")

    # Build question_id -> (index, title) mapping from form items
    question_map: Dict[str, tuple] = {}
    q_counter = 0
    for item in form.get("items", []):
        qi = item.get("questionItem", {})
        question = qi.get("question", {})
        qid = question.get("questionId")
        if qid:
            q_counter += 1
            question_map[qid] = (q_counter, item.get("title", f"Question {q_counter}"))
        # Handle question groups (grids)
        qgi = item.get("questionGroupItem", {})
        for sub_q in qgi.get("questions", []):
            sub_qid = sub_q.get("questionId")
            if sub_qid:
                q_counter += 1
                row_title = sub_q.get("rowQuestion", {}).get("title", f"Question {q_counter}")
                question_map[sub_qid] = (q_counter, row_title)

    response = await asyncio.to_thread(
        service.forms().responses().get(formId=form_id, responseId=response_id).execute
    )

    last_submitted_time = response.get("lastSubmittedTime", "")
    formatted_time = last_submitted_time
    if last_submitted_time:
        try:
            dt = datetime.fromisoformat(last_submitted_time.replace("Z", "+00:00"))
            formatted_time = dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
        except (ValueError, AttributeError):
            formatted_time = last_submitted_time

    answers = response.get("answers", {})
    answer_lines = []
    # Sort answers by their question index so they appear in form order
    sorted_answers = sorted(
        answers.items(),
        key=lambda kv: question_map.get(kv[0], (999, ""))[0],
    )
    for question_id, answer_data in sorted_answers:
        idx, q_title = question_map.get(question_id, (None, question_id))
        question_response = answer_data.get("textAnswers", {}).get("answers", [])
        if question_response:
            answer_text = ", ".join(ans.get("value", "") for ans in question_response)
            display_answer = f'"{answer_text}"' if not answer_text.isdigit() else answer_text
        else:
            display_answer = "(no answer)"

        if idx is not None:
            answer_lines.append(f"  {idx}. {q_title} \u2192 {display_answer}")
        else:
            answer_lines.append(f"  - {q_title} \u2192 {display_answer}")

    if answer_lines:
        answers_text = "\n".join(answer_lines)
        result = f'Response to "{form_title}" ({formatted_time}):\n{answers_text}'
    else:
        result = f'Response to "{form_title}" ({formatted_time}):\n  No answers found'

    logger.info(
        f"Successfully retrieved response for {user_google_email}. Response ID: {response_id}"
    )
    return result


@server.tool()
@handle_http_errors("list_form_responses", is_read_only=True, service_type="forms")
@require_google_service("forms", "forms")
async def list_form_responses(
    service,
    user_google_email: str,
    form_id: str,
    page_size: int = 10,
    page_token: Optional[str] = None,
) -> str:
    """
    List a form's responses.

    Args:
        user_google_email (str): The user's Google email address. Required.
        form_id (str): The ID of the form.
        page_size (int): Maximum number of responses to return. Defaults to 10.
        page_token (Optional[str]): Token for retrieving next page of results.

    Returns:
        str: List of responses with basic details and pagination info.
    """
    logger.info(
        f"[list_form_responses] Invoked. Email: '{user_google_email}', Form ID: {form_id}"
    )

    # Fetch form title for human-friendly output
    form = await asyncio.to_thread(service.forms().get(formId=form_id).execute)
    form_title = form.get("info", {}).get("title", "Untitled form")

    params = {"formId": form_id, "pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token

    responses_result = await asyncio.to_thread(
        service.forms().responses().list(**params).execute
    )

    responses = responses_result.get("responses", [])
    next_page_token = responses_result.get("nextPageToken")

    if not responses:
        return f'No responses found for "{form_title}"'

    response_details = []
    for i, response in enumerate(responses, 1):
        last_submitted_time = response.get("lastSubmittedTime", "")
        formatted_time = last_submitted_time
        if last_submitted_time:
            try:
                dt = datetime.fromisoformat(last_submitted_time.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
            except (ValueError, AttributeError):
                formatted_time = last_submitted_time

        answers_count = len(response.get("answers", {}))
        answer_word = "answer" if answers_count == 1 else "answers"
        response_details.append(
            f"  {i}. Response from {formatted_time} \u2014 {answers_count} {answer_word}"
        )

    details_text = "\n".join(response_details)
    result = f'Found {len(responses)} response{"s" if len(responses) != 1 else ""} to "{form_title}":\n{details_text}'

    if next_page_token:
        result += f"\n  (More responses available)"

    logger.info(
        f"Successfully retrieved {len(responses)} responses for {user_google_email}. Form ID: {form_id}"
    )
    return result


# Internal implementation function for testing
async def _batch_update_form_impl(
    service: Any,
    form_id: str,
    requests: List[Dict[str, Any]],
) -> str:
    """Internal implementation for batch_update_form.

    Applies batch updates to a Google Form using the Forms API batchUpdate method.

    Args:
        service: Google Forms API service client.
        form_id: The ID of the form to update.
        requests: List of update request dictionaries.

    Returns:
        Formatted string with batch update results.
    """
    # Fetch form title for human-friendly output
    form = await asyncio.to_thread(service.forms().get(formId=form_id).execute)
    form_title = form.get("info", {}).get("title", "Untitled form")

    body = {"requests": requests}

    result = await asyncio.to_thread(
        service.forms().batchUpdate(formId=form_id, body=body).execute
    )

    change_word = "change" if len(requests) == 1 else "changes"
    return f'Updated form "{form_title}" \u2014 {len(requests)} {change_word} applied'


@server.tool()
@handle_http_errors("batch_update_form", service_type="forms")
@require_google_service("forms", "forms")
async def batch_update_form(
    service,
    user_google_email: str,
    form_id: str,
    requests: List[Dict[str, Any]],
) -> str:
    """
    Apply batch updates to a Google Form.

    Supports adding, updating, and deleting form items, as well as updating
    form metadata and settings. This is the primary method for modifying form
    content after creation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        form_id (str): The ID of the form to update.
        requests (List[Dict[str, Any]]): List of update requests to apply.
            Supported request types:
            - createItem: Add a new question or content item
            - updateItem: Modify an existing item
            - deleteItem: Remove an item
            - moveItem: Reorder an item
            - updateFormInfo: Update form title/description
            - updateSettings: Modify form settings (e.g., quiz mode)

    Returns:
        str: Details about the batch update operation results.
    """
    logger.info(
        f"[batch_update_form] Invoked. Email: '{user_google_email}', "
        f"Form ID: '{form_id}', Requests: {len(requests)}"
    )

    result = await _batch_update_form_impl(service, form_id, requests)

    logger.info(f"Batch update completed successfully for {user_google_email}")
    return result
