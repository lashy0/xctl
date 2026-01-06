## v0.4.0 (2026-01-06)

### Feat

- implement Strategy pattern for Xray protocols
- add SNI domain verification and refactor config loading

### Fix

- **reality**: restore packetEncoding=xudp to generated links
- **cli**: improve watch command graph rendering and stability

## v0.3.0 (2026-01-04)

### Feat

- **cli**: add graph display for the watch command

### Refactor

- **cli**: split monolithic main.py into modular structure

## v0.2.0 (2026-01-04)

### Feat

- implement hot-reload, atomic writes and backup system
- **cli**: make stats argument optional for global snapshot
- **cli**: unify ui design for stats and watch commands
- **cli**: add dedicated 'stats' command for user traffic metrics
- **cli**: implement traffic statistics and live monitoring
- **cli**: add init command and relax key validation
- **cli**: add `link` command to retrieve user connection string
- initial release of xctl CLI tool

### Fix

- **core**: update stats parser to handle Xray JSON output
- **docker**: explicitly specify config file path in startup command
- **service**:  VLESS link format
- **cli**: allow key generation without valid .env configuration

### Refactor

- **core**: switch to Docker SDK and implement DI pattern
