# Advanced Documentation

## Complete Command Reference

### Setup and Management

```bash
# One-time setup (installs deps + clones template)
make setup

# Install dependencies only
make deps

# Create instance (normal mode)
make create NAME=myproject

# Create instance (verbose mode - shows detailed progress)
make create NAME=myproject VERBOSE=1

# List all instances with status and ports
make list

# Destroy instance and all data
make destroy NAME=myproject
```

### Instance Control

```bash
# Start/stop instances
make myproject-start
make myproject-stop
make myproject-restart

# View logs
make myproject-logs        # View logs once
make myproject-logs -f     # Follow logs continuously

# Check container status
make myproject-ps
```

### Direct Python Commands

All make commands use the Python script internally:

```bash
# Using the virtual environment directly
.venv/bin/python setup.py create myproject --verbose
.venv/bin/python setup.py list
.venv/bin/python setup.py start myproject
.venv/bin/python setup.py logs myproject -f
.venv/bin/python setup.py destroy myproject
```

## Port Management

### How Ports are Allocated

Each instance gets a unique ID (1, 2, 3...) used as an offset:

| Service | Base Port | Instance 1 | Instance 2 | Instance 3 |
|---------|-----------|------------|------------|------------|
| Kong HTTP | 8001 | 8001 | 8002 | 8003 |
| Kong HTTPS | 8444 | 8444 | 8445 | 8446 |
| Studio | 3001 | 3001 | 3002 | 3003 |
| PostgreSQL | 5433 | 5433 | 5434 | 5435 |
| Pooler | 6544 | 6544 | 6545 | 6546 |
| Analytics | 4001 | 4001 | 4002 | 4003 |

### Database Connection

Each instance exposes PostgreSQL directly:

```
Host: localhost
Port: [shown after creation]
Database: postgres
Username: postgres  
Password: [generated, stored in .env]
```

Connect with any PostgreSQL tool using the connection string shown during creation.

## Directory Structure

```
multi-supabase/
├── .venv/                   # Python virtual environment
├── instances/
│   ├── instances.json       # Registry of all instances
│   ├── myproject/           # Instance directory
│   │   ├── .env             # Generated secrets
│   │   ├── docker-compose.yml # Modified for ports
│   │   └── volumes/         # Data volumes
│   └── another-project/
├── supabase-template/       # Cloned Supabase repo
├── setup.py                 # Main management script
├── Makefile                 # Simplified commands
└── requirements.txt
```

## Configuration Files

### instances.json
Tracks all instances and their allocated resources:

```json
{
  "myproject": {
    "id": 1,
    "path": "/path/to/instances/myproject",
    "ports": {
      "kong_http": 8001,
      "kong_https": 8444,
      "postgres_direct": 5433,
      "supavisor_pooler": 6544,
      "studio": 3001,
      "analytics": 4001
    }
  }
}
```

### .env Files
Each instance gets unique generated secrets:

- `POSTGRES_PASSWORD` - Database password
- `JWT_SECRET` - JWT signing secret  
- `ANON_KEY` - Anonymous access key
- `SERVICE_ROLE_KEY` - Service role key
- `DASHBOARD_USERNAME/PASSWORD` - Dashboard credentials

## Troubleshooting

### Creation Issues

**Process seems stuck:**
- Use `VERBOSE=1` to see real-time progress
- Docker pulls can take 5-10 minutes on first run
- Check `docker ps` to see if containers are starting

**Port conflicts:**
- Ports are automatically allocated to avoid conflicts
- If you have services on base ports (8001, 3001, etc), they may conflict
- Stop conflicting services or modify the base ports in `setup.py`

**Permission errors:**
```bash
# Fix Docker permissions (Linux)
sudo usermod -aG docker $USER
# Log out and back in
```

### Runtime Issues

**Instance won't start:**
```bash
# Check detailed logs
make myproject-logs

# Check container status
make myproject-ps

# Debug with Docker directly
cd instances/myproject
docker compose --project-name supabase-myproject logs
```

**Database connection fails:**
- Verify the instance is running: `make list`
- Check the exact port in the output
- Use the password from `.env` file
- Wait a few seconds after starting for DB to be ready

**Services unhealthy:**
- Some services take time to become healthy
- Use `make myproject-logs` to check for errors
- Restart if needed: `make myproject-restart`

### Cleanup

**Remove all instances:**
```bash
make clean  # Interactive - asks for confirmation
```

**Manual cleanup:**
```bash
# Remove instance directories
rm -rf instances/

# Remove Docker volumes (if needed)
docker system prune -a --volumes
```

**Reset everything:**
```bash
# Remove all Docker containers and images
docker system prune -a --volumes

# Remove template and start fresh
rm -rf supabase-template/
make setup
```

## Development

### Modifying the Setup Script

The main logic is in `setup.py`. Key functions:

- `create_instance()` - Main instance creation
- `get_next_available_ports()` - Port allocation logic
- `generate_secrets()` - JWT and password generation
- `run_command()` - Execute Docker commands with progress

### Adding New Services

To add a new service with port mapping:

1. Add base port to `get_next_available_ports()`
2. Update port mapping in `patch_port_mappings()`
3. Add environment variable to instance creation

### Customizing Templates

The script clones the official Supabase repository. To use a custom template:

1. Modify the clone URL in `clone_fresh_template()`
2. Or manually replace `supabase-template/` with your custom version

## Security Notes

- Each instance generates unique secrets automatically
- Database passwords are cryptographically secure (32 bytes)
- JWT secrets are 512-bit for security
- Secrets are stored in instance `.env` files (not committed to git)
- Add `instances/` to `.gitignore` to avoid committing secrets

## Performance

- Each instance uses ~2GB RAM when fully loaded
- Startup time: 30 seconds to 2 minutes depending on Docker cache
- Port allocation is sequential for predictability
- Uses Docker Compose project names for complete isolation

## API Access

Each instance provides the full Supabase API:

```bash
# REST API
curl http://localhost:8001/rest/v1/your-table \
  -H "Authorization: Bearer YOUR_ANON_KEY"

# Auth
curl http://localhost:8001/auth/v1/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

Keys are available in the instance `.env` file or shown during creation.