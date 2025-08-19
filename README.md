# Supabase Multi-Instance Manager

Run multiple isolated Supabase instances simultaneously with automatic port management.

## Quick Start

1. **Setup** (one-time):
```bash
make setup
```

2. **Create instance**:
```bash
make create NAME=myproject
```

3. **Access your instance**:
- **Studio**: http://localhost:3001
- **API**: http://localhost:8001  
- **Database**: Connection details shown after creation

## Essential Commands

| Command | What it does |
|---------|--------------|
| `make create NAME=myproject` | Create new Supabase instance |
| `make list` | Show all instances and their ports |
| `make myproject-start` | Start a stopped instance |
| `make myproject-stop` | Stop a running instance |
| `make myproject-logs` | View instance logs |
| `make destroy NAME=myproject` | Delete instance (⚠️ destroys all data) |

## Features

✅ **Multiple instances** - Run several Supabase projects at once  
✅ **No port conflicts** - Automatic port assignment  
✅ **Full isolation** - Each instance is completely separate  
✅ **Secure by default** - Auto-generated secrets and passwords  
✅ **Direct database access** - Connect with any PostgreSQL tool

## Requirements

- Docker & Docker Compose
- Python 3.7+
- Git

## Troubleshooting

**Slow creation?** Use verbose mode:
```bash
make create NAME=myproject VERBOSE=1
```

**Need help?** See [Advanced Documentation](ADVANCED.md) for detailed usage, port management, and troubleshooting.

---

*Each instance runs as an isolated Docker Compose project with unique ports and secrets.*