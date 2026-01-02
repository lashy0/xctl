# xctl - Xray Controller

## Project Structure

```
xctl/
├── config/
│   ├── config.json         # Actual Xray configuration
│   └── config.example.json # Template for configuration
├── src/
│   ├── config/             # Settings & Pydantic validation
│   ├── core/               # Low-level logic (JSON I/O, Docker ops)
│   ├── services/           # Business logic (User management)
│   └── main.py             # CLI Entry point
├── .env                    # Environment variables
├── docker-compose.yml      # Xray Docker service
├── pyproject.toml          # Dependencies
└── README.md
```

## Prerequisites

- **Linux Server** with a public IPv4 address.
- **Docker** and **Docker Compose** installed.
- **uv** installed.

> [!NOTE]
> You do not need to install Python manually. `uv` will automatically download and manage Python 3.13 for this project.

## Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/lashy0/xctl.git

cd xctl
```

### 2. Install dependencies

Using `uv`:

```bash
uv sync
```

### 3. Prepare Configuration Files

Copy the example files to create your actual configuration:

```bash
cp .env.example .env
cp config/config.example.json config/config.json
```

### 4. Generate Keys and IDs

You need to generate secrets for the server. You can use `xctl` to do this.

Generate a ShortId:

```bash
uv run xctl gen-id
```

Generate X25519 Keys:

```bash
uv run xctl gen-keys
```

### 5. Fill Configuration

Open the files and insert the generated values.

1. Edit `config/config.json`:
    - Paste Private Key into "privateKey".
    - Paste ShortId into "shortIds".

2. Edit `.env`:
    - SERVER_IP: Set your server's public IP.
    - XRAY_PUB_KEY: Paste the Public Key.

### 6. Start the Server

Start the Xray container using Docker Compose:

```bash
docker compose up -d
```

## Usage xctl

### Manage Users

**Add a new user**:

```bash
uv run xctl add <name>
```

Returns a vless:// link.

**List all users**:

```bash
uv run xctl list
```

**Remove a user**:

```bash
uv run xctl remove <name>
```

### Helper Commands

**Create a new ShortId**:

```bash
uv run xctl gen-id
```

**Generate new X25519 Keys**:

```bash
uv run xctl gen-keys
```

**Force restart Xray**:

```bash
uv run xctl restart
```