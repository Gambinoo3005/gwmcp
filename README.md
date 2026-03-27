# gwmcp

Google Workspace MCP Server with guided setup and seamless auth.

One command to install, authenticate, and start using **114 Google Workspace tools** with Claude Code, Cursor, or any MCP client.

> Derived from [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) (MIT). This project adds a guided setup wizard, simplified configuration, and improved auth flow for local single-user setups.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Step-by-Step Google Cloud Setup](#step-by-step-google-cloud-setup)
- [What You Get](#what-you-get)
- [Configuration](#configuration)
- [CLI Options](#cli-options)
- [How It Improves on the Original](#how-it-improves-on-the-original)
- [Development](#development)
- [License](#license)

---

## Quick Start

If you already have a `client_secret.json` from Google Cloud, you can skip ahead:

```bash
uvx gwmcp setup --email you@gmail.com --client-secret /path/to/client_secret.json
```

If you don't have one yet, follow the step-by-step guide below.

---

## Step-by-Step Google Cloud Setup

This section walks you through everything from scratch. No prior Google Cloud experience needed.

### 1. Install Prerequisites

You need **Python 3.10+** and **uv** (a fast Python package manager).

**Windows (PowerShell):**
```powershell
# Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installing, restart your terminal so the `uvx` command is available.

### 2. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Click the project dropdown at the top of the page (it might say "Select a project")
4. Click **New Project**
5. Give it a name (e.g. "My Workspace MCP") and click **Create**
6. Make sure your new project is selected in the dropdown

### 3. Enable Google APIs

You need to turn on the APIs for the Google services you want to use.

1. In the Google Cloud Console, go to **APIs & Services > Library** (or [click here](https://console.cloud.google.com/apis/library))
2. Search for and enable each API you need by clicking on it and hitting **Enable**:

| API | What it unlocks |
|-----|----------------|
| **Google Drive API** | Search, upload, download, share files |
| **Google Docs API** | Create, read, edit documents |
| **Google Sheets API** | Read, write, format spreadsheets |
| **Gmail API** | Search, read, send, draft emails |
| **Google Calendar API** | Events, availability, calendars |
| **Google Slides API** | Create, edit presentations |
| **Google Forms API** | Create forms, read responses |
| **Tasks API** | Manage task lists and tasks |
| **People API** | Manage contacts |
| **Google Chat API** | Spaces and messages |
| **Apps Script API** | Manage script projects |

You can enable just the ones you need now and add more later.

### 4. Set Up the OAuth Consent Screen

This tells Google what your app is and who can use it.

1. Go to **APIs & Services > OAuth consent screen** (or [click here](https://console.cloud.google.com/apis/credentials/consent))
2. Select **Get started** or **External** as the user type, then click **Create**
3. Fill in the required fields:
   - **App name**: anything (e.g. "gwmcp")
   - **User support email**: your email
   - **Developer contact email**: your email
4. Click **Save and Continue** through the Scopes and Summary steps (defaults are fine)
5. On the **Test users** page or under **Audience**, click **Add Users**
6. Add your own Gmail address (e.g. `you@gmail.com`) and click **Save**

> **Important:** While the app is in "Testing" mode, only the email addresses you add as test users can authenticate. This is fine for personal use.

### 5. Create OAuth Credentials

This generates the `client_secret.json` file you need.

1. Go to **APIs & Services > Credentials** (or [click here](https://console.cloud.google.com/apis/credentials))
2. Click **Create Credentials** at the top
3. Choose **OAuth client ID**
4. For **Application type**, select **Desktop app**
5. Give it a name (e.g. "gwmcp") and click **Create**
6. A dialog will appear with your client ID and secret — click **Download JSON**
7. Save the downloaded file somewhere you can find it (e.g. your Downloads folder)

The file will have a long name like `client_secret_284692452895-xxxxx.apps.googleusercontent.com.json`. That's normal.

### 6. Run the Setup Wizard

Now you have everything you need. Run this in your terminal:

```bash
uvx gwmcp setup --email you@gmail.com --client-secret ~/Downloads/client_secret_*.json
```

Replace `you@gmail.com` with your actual Gmail address, and update the path to wherever you saved the JSON file.

The wizard will:
1. Copy your credentials to a safe location (`~/.google_workspace_mcp/`)
2. Open your browser for Google sign-in
3. Save the authentication token
4. Write the MCP config file for Claude Code

**When the browser opens:**
- Sign in with the same Google account you added as a test user
- You'll see a warning: "Google hasn't verified this app" — click **Advanced**, then **Go to gwmcp (unsafe)**
- Check the permissions and click **Allow**
- You'll see a success page — you can close the browser tab

### 7. Restart Claude Code

Close and reopen Claude Code. The Google Workspace tools will now be available. Try asking:

> "Search my Google Drive for recent documents"

Or if you prefer the interactive setup (prompts you for each step):

```bash
uvx gwmcp setup
```

---

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

---

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

---

## CLI Options

```bash
gwmcp --single-user                    # Single-user mode (recommended)
gwmcp --tools gmail drive docs         # Load specific services only
gwmcp --tool-tier core                 # Load core tools only
gwmcp --read-only                      # Read-only mode
gwmcp --permissions gmail:readonly drive:full  # Granular permissions
gwmcp --cli search_drive_files --args '{"query": "test"}'  # Direct CLI usage
```

---

## How It Improves on the Original

| Pain point | Original | gwmcp |
|-----------|----------|-------|
| Env vars needed | 4 (trial and error) | 1 (`GOOGLE_CLIENT_SECRET_PATH`) |
| Email config | Manual `USER_GOOGLE_EMAIL` required | Auto-detected from stored credentials |
| First-time auth | Print URL, no callback server, state mismatch | Setup wizard handles everything |
| CLI mode auth | Prints dead URL, exits | Opens browser, waits, retries automatically |
| Setup process | Read docs, edit JSON manually | `uvx gwmcp setup` |
| Tool responses | Verbose JSON with raw IDs | Clean, human-readable output |

---

## Troubleshooting

### "Google hasn't verified this app"
This appears because your app is in "Testing" mode. To get past it:

1. Click **Advanced**, then **Go to gwmcp (unsafe)** to continue
2. If you get blocked entirely, make sure your email is added as a test user:
   - Go to [Google Cloud Console](https://console.cloud.google.com/) > **APIs & Services** > **OAuth consent screen**
   - Under **Audience** (or **Test users**), click **Add Users**
   - Add the Gmail address you're trying to sign in with
   - Save and try again

### "Access blocked: This app's request is invalid"
Make sure the **redirect URI** matches. gwmcp uses `http://localhost:8000/oauth2callback`. You don't need to configure this in Google Cloud for Desktop app credentials — it's handled automatically.

### "uvx: command not found"
You need to install uv first. See [Install Prerequisites](#1-install-prerequisites).

### Port 8000 is in use
Another application is using port 8000. Stop it and try again, or set a custom port:
```bash
WORKSPACE_MCP_PORT=9000 uvx gwmcp setup --email you@gmail.com --client-secret /path/to/secret.json
```

### Token expired or revoked
Re-run the setup wizard to re-authenticate:
```bash
uvx gwmcp setup
```

---

## Development

```bash
git clone https://github.com/Gambinoo3005/gwmcp.git
cd gwmcp
pip install -e ".[dev]"
pytest
```

---

## License

MIT License. See [LICENSE](LICENSE).

Based on [google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) by Taylor Wilsdon.
