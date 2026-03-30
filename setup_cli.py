"""
Interactive setup wizard for Google Workspace MCP.

Usage:
    workspace-mcp setup

Walks the user through:
1. Entering their Google email
2. Providing a client_secret.json file
3. Completing OAuth authentication in the browser
4. Generating the MCP config for Claude Code
"""

import json
import os
import platform
import shutil
import sys
import threading
import time
import webbrowser


# --- Paths ---

def _home_dir():
    return os.path.expanduser("~")


def _workspace_mcp_dir():
    return os.path.join(_home_dir(), ".google_workspace_mcp")


def _credentials_dir():
    return os.path.join(_workspace_mcp_dir(), "credentials")


def _client_secret_dest():
    return os.path.join(_workspace_mcp_dir(), "client_secret.json")


def _claude_mcp_json_path():
    return os.path.join(_home_dir(), ".claude", "mcp.json")


# --- Helpers ---

def _print_header():
    print()
    print("gwmcp - Setup")
    print("=" * 40)
    print()


def _detect_email_from_credentials():
    """Auto-detect email from existing credential files.

    If multiple accounts exist, warns and returns the most recently modified.
    """
    creds_dir = _credentials_dir()
    if not os.path.isdir(creds_dir):
        return None
    accounts = []
    for f in os.listdir(creds_dir):
        if f.endswith(".json") and "@" in f:
            accounts.append(f[:-5])  # strip .json
    if not accounts:
        return None
    if len(accounts) > 1:
        # Pick most recently modified credential file
        accounts.sort(
            key=lambda a: os.path.getmtime(os.path.join(creds_dir, a + ".json")),
            reverse=True,
        )
        print(f"  Note: Found {len(accounts)} accounts: {', '.join(accounts)}")
        print(f"  Using most recent: {accounts[0]}")
        print(f"  To use a different account, pass --email explicitly.")
    return accounts[0]


def _validate_client_secret(path):
    """Validate and parse a client_secret.json file. Returns (client_id, client_secret) or raises."""
    with open(path) as f:
        data = json.load(f)
    inner = data.get("web") or data.get("installed")
    if not inner:
        raise ValueError("Invalid client_secret.json: missing 'web' or 'installed' key")
    client_id = inner.get("client_id")
    client_secret = inner.get("client_secret")
    if not client_id or not client_secret:
        raise ValueError("Invalid client_secret.json: missing client_id or client_secret")
    return client_id, client_secret


def _write_mcp_json(client_secret_path, user_email):
    """Write or merge the Claude Code mcp.json config."""
    mcp_path = _claude_mcp_json_path()

    # Ensure .claude directory exists
    claude_dir = os.path.dirname(mcp_path)
    os.makedirs(claude_dir, exist_ok=True)

    # Load existing config if present
    existing = {}
    if os.path.exists(mcp_path):
        try:
            with open(mcp_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    if "mcpServers" not in existing:
        existing["mcpServers"] = {}

    # Build env block - only GOOGLE_CLIENT_SECRET_PATH is needed
    # (main.py auto-extracts client_id/secret from the JSON file)
    env = {
        "GOOGLE_CLIENT_SECRET_PATH": client_secret_path,
    }
    # Only add email if we have it (it will be auto-detected from credentials otherwise)
    if user_email:
        env["USER_GOOGLE_EMAIL"] = user_email

    # Use uvx directly — stable across all directories and uv cache states.
    # Previous approach detected a Python path and used `python -m uv tool run`,
    # which could resolve to a fragile uv cache path that breaks when the cache shifts.
    existing["mcpServers"]["google-workspace"] = {
        "command": "uvx",
        "args": ["gwmcp", "--single-user"],
        "env": env,
    }

    with open(mcp_path, "w") as f:
        json.dump(existing, f, indent=2)

    return mcp_path


def _run_oauth_flow(client_id, client_secret, user_email):
    """
    Run the OAuth flow: start callback server, open browser, wait for auth.
    Returns the authenticated email or None on failure.
    """
    # Set required env vars for the auth modules
    os.environ["GOOGLE_OAUTH_CLIENT_ID"] = client_id
    os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = client_secret
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

    # Import auth modules (after env vars are set)
    from auth.oauth_callback_server import (
        MinimalOAuthServer,
        auth_completed_event,
    )
    from auth.google_auth import start_auth_flow
    from auth.scopes import get_current_scopes, set_enabled_tools

    # Enable all tools so we get full scopes
    set_enabled_tools([
        "gmail", "drive", "calendar", "docs", "sheets", "chat",
        "forms", "slides", "tasks", "contacts", "search", "appscript",
    ])

    port = int(os.environ.get("PORT", os.environ.get("WORKSPACE_MCP_PORT", 8000)))
    base_uri = os.environ.get("WORKSPACE_MCP_BASE_URI", "http://localhost")

    # Start the callback server
    print(f"  Starting OAuth callback server on port {port}...")
    oauth_server = MinimalOAuthServer(port, base_uri)
    success, error_msg = oauth_server.start()
    if not success:
        print(f"  ERROR: Could not start callback server: {error_msg}")
        print(f"  Make sure port {port} is not in use by another application.")
        return None

    try:
        # Generate the auth URL
        import asyncio

        redirect_uri = f"{base_uri}:{port}/oauth2callback"

        async def _get_auth_url():
            return await start_auth_flow(
                user_google_email=user_email,
                service_name="Google Workspace",
                redirect_uri=redirect_uri,
            )

        auth_response = asyncio.run(_get_auth_url())

        # Extract the URL from the response text
        import re
        url_match = re.search(
            r"Authorization URL: (https://accounts\.google\.com\S+)",
            auth_response,
        )
        if not url_match:
            print("  ERROR: Could not generate authorization URL.")
            print(f"  Response: {auth_response[:200]}")
            return None

        auth_url = url_match.group(1)

        # Open browser
        print("  Opening browser for Google sign-in...")
        webbrowser.open(auth_url)
        print()
        print("  Waiting for you to complete authentication in the browser...")
        print("  (timeout: 3 minutes)")
        print()

        # Wait for the callback
        auth_completed_event.clear()
        if auth_completed_event.wait(timeout=180):
            # Find the authenticated email from credentials
            authenticated_email = _detect_email_from_credentials()
            return authenticated_email or user_email
        else:
            print("  Authentication timed out.")
            return None

    finally:
        oauth_server.stop()


# --- Main ---

def setup_command():
    """
    Setup wizard. Supports both interactive and non-interactive modes.

    Non-interactive usage:
        gwmcp setup --email user@gmail.com --client-secret /path/to/client_secret.json
    Interactive usage:
        gwmcp setup
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="gwmcp setup",
        description="Set up gwmcp with guided authentication",
    )
    parser.add_argument(
        "--email", "-e",
        help="Google email address",
    )
    parser.add_argument(
        "--client-secret", "-c",
        help="Path to client_secret.json file from Google Cloud Console",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Skip OAuth authentication (configure only)",
    )

    # Parse only the args after "setup"
    args = parser.parse_args(sys.argv[2:])

    interactive = sys.stdin.isatty()

    _print_header()

    # -------------------------------------------------------
    # Step 1: Google Email
    # -------------------------------------------------------
    print("Step 1: Google Email")
    print("-" * 30)

    existing_email = _detect_email_from_credentials()

    if args.email:
        user_email = args.email
    elif interactive:
        if existing_email:
            email_input = input(f"  Email [{existing_email}]: ").strip()
            user_email = email_input if email_input else existing_email
        else:
            user_email = input("  Your Google email: ").strip()
    else:
        user_email = existing_email

    if not user_email or "@" not in user_email:
        print("  ERROR: Please provide a valid email address.")
        print("  Use: gwmcp setup --email your@gmail.com --client-secret /path/to/client_secret.json")
        return 1

    print(f"  Using: {user_email}")
    print()

    # -------------------------------------------------------
    # Step 2: Client Credentials
    # -------------------------------------------------------
    print("Step 2: Client Credentials")
    print("-" * 30)

    # Check if we already have one
    dest = _client_secret_dest()
    if os.path.exists(dest):
        try:
            client_id, client_secret = _validate_client_secret(dest)
            print(f"  Found existing credentials at: {dest}")
            if interactive and not args.client_secret:
                reuse = input("  Use these? [Y/n]: ").strip().lower()
                if reuse in ("", "y", "yes"):
                    print(f"  Using existing client_secret.json")
                    print()
                else:
                    raise ValueError("User wants new credentials")
            else:
                print(f"  Using existing client_secret.json")
                print()
        except (ValueError, json.JSONDecodeError):
            os.remove(dest)
            client_id, client_secret = None, None
    else:
        client_id, client_secret = None, None

    if not client_id:
        if args.client_secret:
            secret_path = args.client_secret
        elif interactive:
            print("  You need a client_secret.json from Google Cloud Console.")
            print("  (APIs & Services > Credentials > OAuth 2.0 Client ID > Desktop app)")
            print()
            secret_path = input("  Path to client_secret.json: ").strip().strip('"').strip("'")
        else:
            print("  ERROR: No client_secret.json found.")
            print("  Use: gwmcp setup --email your@gmail.com --client-secret /path/to/client_secret.json")
            return 1

        if not secret_path or not os.path.exists(secret_path):
            print(f"  ERROR: File not found: {secret_path}")
            return 1

        try:
            client_id, client_secret = _validate_client_secret(secret_path)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"  ERROR: {e}")
            return 1

        # Copy to standard location
        os.makedirs(_workspace_mcp_dir(), exist_ok=True)
        shutil.copy2(secret_path, dest)
        print(f"  Copied to: {dest}")
        print()

    # -------------------------------------------------------
    # Step 3: Check if already authenticated
    # -------------------------------------------------------
    creds_dir = _credentials_dir()
    creds_file = os.path.join(creds_dir, f"{user_email}.json")
    already_authed = os.path.exists(creds_file)

    if already_authed:
        print("Step 3: OAuth Authentication")
        print("-" * 30)
        print(f"  Already authenticated as {user_email}")
        if interactive and not args.no_auth:
            reauth = input("  Re-authenticate? [y/N]: ").strip().lower()
            if reauth not in ("y", "yes"):
                print("  Skipping authentication.")
                print()
            else:
                already_authed = False
        else:
            print("  Skipping authentication.")
            print()

    if not already_authed and not args.no_auth:
        print("Step 3: OAuth Authentication")
        print("-" * 30)
        os.makedirs(creds_dir, exist_ok=True)

        authenticated_email = _run_oauth_flow(client_id, client_secret, user_email)
        if authenticated_email:
            print(f"  Authenticated as: {authenticated_email}")
            user_email = authenticated_email
            print()
        else:
            print("  WARNING: Authentication did not complete.")
            print("  You can authenticate later when using the MCP tools.")
            print()

    # -------------------------------------------------------
    # Step 4: Write MCP config
    # -------------------------------------------------------
    print("Step 4: MCP Configuration")
    print("-" * 30)

    # Use the platform-native path separator for the mcp.json env value
    client_secret_path_for_config = os.path.abspath(dest)

    mcp_path = _write_mcp_json(client_secret_path_for_config, user_email)
    print(f"  Wrote config to: {mcp_path}")
    print()

    # -------------------------------------------------------
    # Done
    # -------------------------------------------------------
    print("=" * 40)
    print("Setup complete!")
    print()
    print("Next steps:")
    print("  1. Restart Claude Code (exit and relaunch)")
    print("  2. The google-workspace MCP tools will be available automatically")
    print()

    return 0
