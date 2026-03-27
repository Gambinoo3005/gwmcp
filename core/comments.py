"""
Core Comments Module

This module provides reusable comment management functions for Google Workspace applications.
All Google Workspace apps (Docs, Sheets, Slides) use the Drive API for comment operations.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional

from auth.service_decorator import require_google_service
from core.server import server
from core.utils import handle_http_errors

logger = logging.getLogger(__name__)


def _format_timestamp(iso_str: str) -> str:
    """Format an ISO 8601 timestamp into a human-friendly string like 'Mar 26, 10:30 AM'."""
    if not iso_str:
        return "Unknown time"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
    except (ValueError, AttributeError):
        return iso_str


async def _get_file_title(service, file_id: str, app_name: str) -> str:
    """Fetch the human-readable title of a Drive file, falling back to the app_name + ID."""
    try:
        meta = await asyncio.to_thread(
            service.files().get(fileId=file_id, fields="name").execute
        )
        return meta.get("name", f"{app_name} {file_id}")
    except Exception:
        return f"{app_name} {file_id}"


async def _manage_comment_dispatch(
    service,
    app_name: str,
    file_id: str,
    action: str,
    comment_content: Optional[str] = None,
    comment_id: Optional[str] = None,
) -> str:
    """Route comment management actions to the appropriate implementation."""
    action_lower = action.lower().strip()
    if action_lower == "create":
        if not comment_content:
            raise ValueError("comment_content is required for create action")
        return await _create_comment_impl(service, app_name, file_id, comment_content)
    elif action_lower == "reply":
        if not comment_id or not comment_content:
            raise ValueError(
                "comment_id and comment_content are required for reply action"
            )
        return await _reply_to_comment_impl(
            service, app_name, file_id, comment_id, comment_content
        )
    elif action_lower == "resolve":
        if not comment_id:
            raise ValueError("comment_id is required for resolve action")
        return await _resolve_comment_impl(service, app_name, file_id, comment_id)
    else:
        raise ValueError(
            f"Invalid action '{action_lower}'. Must be 'create', 'reply', or 'resolve'."
        )


def create_comment_tools(app_name: str, file_id_param: str):
    """
    Factory function to create comment management tools for a specific Google Workspace app.

    Args:
        app_name: Name of the app (e.g., "document", "spreadsheet", "presentation")
        file_id_param: Parameter name for the file ID (e.g., "document_id", "spreadsheet_id", "presentation_id")

    Returns:
        Dict containing the comment management functions with unique names
    """

    # --- Consolidated tools ---
    list_func_name = f"list_{app_name}_comments"
    manage_func_name = f"manage_{app_name}_comment"

    if file_id_param == "document_id":

        @require_google_service("drive", "drive_read")
        @handle_http_errors(list_func_name, service_type="drive")
        async def list_comments(
            service, user_google_email: str, document_id: str
        ) -> str:
            """List all comments from a Google Document."""
            return await _read_comments_impl(service, app_name, document_id)

        # Use full Drive scope so comment operations remain visible to collaborators.
        @require_google_service("drive", "drive")
        @handle_http_errors(manage_func_name, service_type="drive")
        async def manage_comment(
            service,
            user_google_email: str,
            document_id: str,
            action: str,
            comment_content: Optional[str] = None,
            comment_id: Optional[str] = None,
        ) -> str:
            """Manage comments on a Google Document.

            Actions:
              - create: Create a new document-level comment. Requires comment_content.
                Note: The Drive API cannot anchor comments to specific text; only
                the Google Docs UI can do that.
              - reply: Reply to a comment. Requires comment_id and comment_content.
              - resolve: Resolve a comment. Requires comment_id.
            """
            return await _manage_comment_dispatch(
                service, app_name, document_id, action, comment_content, comment_id
            )

    elif file_id_param == "spreadsheet_id":

        @require_google_service("drive", "drive_read")
        @handle_http_errors(list_func_name, service_type="drive")
        async def list_comments(
            service, user_google_email: str, spreadsheet_id: str
        ) -> str:
            """List all comments from a Google Spreadsheet."""
            return await _read_comments_impl(service, app_name, spreadsheet_id)

        # Use full Drive scope so comment operations remain visible to collaborators.
        @require_google_service("drive", "drive")
        @handle_http_errors(manage_func_name, service_type="drive")
        async def manage_comment(
            service,
            user_google_email: str,
            spreadsheet_id: str,
            action: str,
            comment_content: Optional[str] = None,
            comment_id: Optional[str] = None,
        ) -> str:
            """Manage comments on a Google Spreadsheet.

            Actions:
              - create: Create a new comment. Requires comment_content.
                Note: The Drive API cannot anchor comments to arbitrary text;
                Sheets comments are cell-scoped via the API.
              - reply: Reply to a comment. Requires comment_id and comment_content.
              - resolve: Resolve a comment. Requires comment_id.
            """
            return await _manage_comment_dispatch(
                service, app_name, spreadsheet_id, action, comment_content, comment_id
            )

    elif file_id_param == "presentation_id":

        @require_google_service("drive", "drive_read")
        @handle_http_errors(list_func_name, service_type="drive")
        async def list_comments(
            service, user_google_email: str, presentation_id: str
        ) -> str:
            """List all comments from a Google Presentation."""
            return await _read_comments_impl(service, app_name, presentation_id)

        # Use full Drive scope so comment operations remain visible to collaborators.
        @require_google_service("drive", "drive")
        @handle_http_errors(manage_func_name, service_type="drive")
        async def manage_comment(
            service,
            user_google_email: str,
            presentation_id: str,
            action: str,
            comment_content: Optional[str] = None,
            comment_id: Optional[str] = None,
        ) -> str:
            """Manage comments on a Google Presentation.

            Actions:
              - create: Create a new comment. Requires comment_content.
                Note: The Drive API cannot anchor comments to arbitrary text;
                Slides comments are element-scoped via the API.
              - reply: Reply to a comment. Requires comment_id and comment_content.
              - resolve: Resolve a comment. Requires comment_id.
            """
            return await _manage_comment_dispatch(
                service, app_name, presentation_id, action, comment_content, comment_id
            )

    list_comments.__name__ = list_func_name
    manage_comment.__name__ = manage_func_name
    server.tool()(list_comments)
    server.tool()(manage_comment)

    return {
        "list_comments": list_comments,
        "manage_comment": manage_comment,
    }


async def _read_comments_impl(service, app_name: str, file_id: str) -> str:
    """Implementation for reading comments from any Google Workspace file."""
    logger.info(f"[read_{app_name}_comments] Reading comments for {app_name} {file_id}")

    title = await _get_file_title(service, file_id, app_name)

    response = await asyncio.to_thread(
        service.comments()
        .list(
            fileId=file_id,
            fields="comments(id,content,author,createdTime,modifiedTime,resolved,quotedFileContent,replies(content,author,id,createdTime,modifiedTime))",
        )
        .execute
    )

    comments = response.get("comments", [])

    if not comments:
        return f'No comments found on "{title}"'

    output = [f'Found {len(comments)} comment{"s" if len(comments) != 1 else ""} on "{title}":']

    for idx, comment in enumerate(comments, start=1):
        author = comment.get("author", {}).get("displayName", "Unknown")
        content = comment.get("content", "")
        created = _format_timestamp(comment.get("createdTime", ""))
        resolved = comment.get("resolved", False)
        status = " [RESOLVED]" if resolved else ""

        quoted_text = comment.get("quotedFileContent", {}).get("value", "")
        quoted_part = f' (on "{quoted_text}")' if quoted_text else ""

        line = f'  {idx}. {author} ({created}): "{content}"{quoted_part}{status}'
        output.append(line)

        # Add reply count summary
        replies = comment.get("replies", [])
        if replies:
            reply_count = len(replies)
            output.append(f'     \u2014 {reply_count} repl{"ies" if reply_count != 1 else "y"}')
            for reply in replies:
                reply_author = reply.get("author", {}).get("displayName", "Unknown")
                reply_content = reply.get("content", "")
                reply_created = _format_timestamp(reply.get("createdTime", ""))
                output.append(f'       {reply_author} ({reply_created}): "{reply_content}"')

    return "\n".join(output)


async def _create_comment_impl(
    service, app_name: str, file_id: str, comment_content: str
) -> str:
    """Implementation for creating a comment on any Google Workspace file.

    Note: Comments created via the Drive API appear as document-level comments.
    The Google Drive API does not support anchoring comments to specific text in
    Google Docs; only the Docs UI can create anchored comments.
    """
    logger.info(f"[create_{app_name}_comment] Creating comment in {app_name} {file_id}")

    title = await _get_file_title(service, file_id, app_name)

    body = {"content": comment_content}

    await asyncio.to_thread(
        service.comments()
        .create(
            fileId=file_id,
            body=body,
            fields="id,content,author,createdTime,modifiedTime",
        )
        .execute
    )

    return f'Added comment on "{title}" \u2014 "{comment_content}"'


async def _reply_to_comment_impl(
    service, app_name: str, file_id: str, comment_id: str, reply_content: str
) -> str:
    """Implementation for replying to a comment on any Google Workspace file."""
    logger.info(
        f"[reply_to_{app_name}_comment] Replying to comment {comment_id} in {app_name} {file_id}"
    )

    title = await _get_file_title(service, file_id, app_name)

    body = {"content": reply_content}

    await asyncio.to_thread(
        service.replies()
        .create(
            fileId=file_id,
            commentId=comment_id,
            body=body,
            fields="id,content,author,createdTime,modifiedTime",
        )
        .execute
    )

    return f'Replied to comment on "{title}" \u2014 "{reply_content}"'


async def _resolve_comment_impl(
    service, app_name: str, file_id: str, comment_id: str
) -> str:
    """Implementation for resolving a comment on any Google Workspace file."""
    logger.info(
        f"[resolve_{app_name}_comment] Resolving comment {comment_id} in {app_name} {file_id}"
    )

    title = await _get_file_title(service, file_id, app_name)

    body = {"content": "This comment has been resolved.", "action": "resolve"}

    await asyncio.to_thread(
        service.replies()
        .create(
            fileId=file_id,
            commentId=comment_id,
            body=body,
            fields="id,content,author,createdTime,modifiedTime",
        )
        .execute
    )

    return f'Resolved comment on "{title}"'
