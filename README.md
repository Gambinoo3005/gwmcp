# gwmcp

Google Workspace MCP Server with guided setup and seamless auth.

One command to install, authenticate, and start using **114 Google Workspace tools** with Claude Code, Cursor, or any MCP client.

> Derived from [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) (MIT). This project adds a guided setup wizard, simplified configuration, and improved auth flow for local single-user setups.

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- A Google Cloud project with OAuth credentials ([setup guide](#google-cloud-setup))

### Install & Authenticate

```bash
uvx gwmcp setup --email you@gmail.com --client-secret /path/to/client_secret.json
```

That's it. The setup wizard will:

1. Copy your credentials to `~/.google_workspace_mcp/`
2. Start a local server and open your browser for Google OAuth
3. Save the auth token
4. Write the MCP config to `~/.claude/mcp.json`

Restart Claude Code and the tools are live.

### Interactive Mode

If you prefer prompts instead of flags:

```bash
uvx gwmcp setup
```

## What You Get

114 tools across 12 Google Workspace services:

| Service | Examples |
|---------|---------|
| **Gmail** | Search, read, send, draft, label, filter |
| **Drive** | Search, upload, download, share, permissions |
| **Docs** | Create, read, edit, find & replace, export to PDF |
| **Sheets** | Read, write, format, conditional formatting |
| **Calendar** | Events, availability, multiple calendars |
| **Slides** | Create, read, edit presentations |
| **Forms** | Create, read responses |
| **Tasks** | Create, manage task lists |
| **Contacts** | Search, create, manage |
| **Chat** | Spaces, messages |
| **Apps Script** | Projects, deployments, versions |
| **Search** | Custom search engine |

## Configuration

After `gwmcp setup`, your `~/.claude/mcp.json` will look like:

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "python",
      "args": ["-m", "uv", "tool", "run", "gwmcp", "--single-user"],
      "env": {
        "GOOGLE_CLIENT_SECRET_PATH": "/path/to/.google_workspace_mcp/client_secret.json"
      }
    }
  }
}
```

Only **one environment variable** needed. The email and OAuth credentials are auto-detected from stored tokens.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_CLIENT_SECRET_PATH` | Yes | Path to your `client_secret.json` |
| `USER_GOOGLE_EMAIL` | No | Auto-detected from stored credentials |
| `GOOGLE_OAUTH_CLIENT_ID` | No | Auto-extracted from `client_secret.json` |
| `GOOGLE_OAUTH_CLIENT_SECRET` | No | Auto-extracted from `client_secret.json` |

### CLI Options

```bash
gwmcp --single-user                    # Single-user mode (recommended)
gwmcp --tools gmail drive docs         # Load specific services only
gwmcp --tool-tier core                 # Load core tools only
gwmcp --read-only                      # Read-only mode
gwmcp --permissions gmail:readonly drive:full  # Granular permissions
gwmcp --cli search_drive_files --args '{"query": "test"}'  # Direct CLI usage
```

## Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the APIs you need:
   - Google Drive API
   - Google Docs API
   - Google Sheets API
   - Gmail API
   - Google Calendar API
   - *(enable others as needed)*
4. Go to **APIs & Services > OAuth consent screen**
   - Choose "External" user type
   - Add your email as a test user
5. Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Choose **Desktop application**
   - Download the JSON file

Then run:

```bash
uvx gwmcp setup --email you@gmail.com --client-secret ~/Downloads/client_secret_*.json
```

## How It Improves on the Original

| Pain point | Original | gwmcp |
|-----------|----------|-------|
| Env vars needed | 4 (trial and error) | 1 (`GOOGLE_CLIENT_SECRET_PATH`) |
| Email config | Manual `USER_GOOGLE_EMAIL` required | Auto-detected from stored credentials |
| First-time auth | Print URL, no callback server, state mismatch | Setup wizard handles everything |
| CLI mode auth | Prints dead URL, exits | Opens browser, waits, retries automatically |
| Setup process | Read docs, edit JSON manually | `uvx gwmcp setup` |

## Development

```bash
git clone https://github.com/Gambinoo3005/gwmcp.git
cd gwmcp
pip install -e ".[dev]"
pytest
```

## License

MIT License. See [LICENSE](LICENSE).

Based on [google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) by Taylor Wilsdon.
