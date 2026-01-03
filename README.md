# xctl - Xray Controller

## Project Structure

```
xctl/
├── config/
│   ├── config.json         # Actual Xray configuration
│   └── config.example.json # Template for configuration
├── src/
│   ├── config/             # Settings & Validation
│   ├── core/               # Low-level logic (JSON I/O, Docker ops)
│   ├── services/           # Business logic (User management)
│   ├── dependencies.py     # Dependency Injection container
│   └── main.py             # CLI Entry point
├── .env                    # Environment variables
├── docker-compose.yml      # Xray Docker service
├── pyproject.toml
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

### 3. Initialize the Server

Run the initialization command. This will:

- Detect your public IP address.
- Generate X25519 Private/Public keys.
- Generate a secure ShortId.
- Create .env and config/config.json.

```bash
uv run xctl init
```

### 4. Start Xray

Start the container using Docker Compose:

```bash
docker compose up -d
```

## Usage xctl

### Manage Users

**Add a new user**:

Creates a user, restarts the server, and returns a ready-to-use VLESS link.

```bash
uv run xctl add <name>
```

**Get an existing user`s link**:

If you lost the link, you can retrieve it again without regenerating keys.

```bash
uv run xctl link <name>
```

**List all users**:

```bash
uv run xctl list
```

**Remove a user**:

```bash
uv run xctl remove <name>
```

### Traffic Monitoring

**Detailed stats for a user**:

Shows total upload/download bytes for a specific user.

```bash
uv run xctl stats <name>
```

**Live Dashboard (All Users)**:

Shows current internet speed and total traffic for all users in real-time.

```bash
uv run xctl watch
```

**Live Monitor (Single User)**:

Focus on one user to see separate Upload and Download speeds in real-time.

```bash
uv run xctl watch-user <name>
```

### Server Management

**Initial/Reset Configuration**:

> [!WARNING]
> This will overwrite your existing configuration and users.

Use the `--force` flag if you want to overwrite existing configs.

```bash
uv run xctl init --force
```

**Restart Xray**:

Force restarts the Docker container.

```bash
uv run xctl restart
```

**Stop/Start Xray**:

Control the Docker container directly.

```bash
uv run xctl stop/start
```