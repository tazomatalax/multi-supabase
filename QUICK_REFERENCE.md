# Supabase Instance Manager – Quick Reference

A concise guide for common operations, port mappings, and troubleshooting.

---

## Installation & Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Make shell script executable
chmod +x supabase-manager.sh
```

---

## Common Commands

### Shell Script (Recommended)

```bash
# Set up default instances (1-5)
./supabase-manager.sh setup

# Set up specific instances
./supabase-manager.sh setup 1 2 3

# List all instances
./supabase-manager.sh list

# Get info for instance 1
./supabase-manager.sh info 1

# Start/Stop instance 1
./supabase-manager.sh start 1
./supabase-manager.sh stop 1

# View logs
./supabase-manager.sh logs 1

# Show environment variables
./supabase-manager.sh env 1

# Delete instance 1 (keep files)
./supabase-manager.sh delete 1

# Delete instance 1 and remove files
./supabase-manager.sh delete 1 --files
```

### Python Script (Advanced)

```bash
# Set up with custom name/description
python3 setup.py setup --instances 1 --name "ChatBot-Backend" --description "Backend for main chatbot"

# List instances (table format)
python3 setup.py list --format table

# Export connection info as env file
python3 setup.py info --instance 1 --format env --output chatbot.env

# Generate docker-compose template
python3 setup.py template 1 my-llm-service --output docker-compose.external.yml

# Update instance name/description
python3 setup.py update 1 --name "Main-ChatBot" --description "Primary chatbot backend"

# Delete instance and files
python3 setup.py delete 1 --remove-files
```

---

## Instance Management

- **Create**: `setup`
- **List**: `list`
- **Update**: `update <id> <name> [description]`
- **Delete**: `delete <id> [--files|--remove-files]`

---

## Connection & Info

- **Show info**: `info <id>`
- **Show env**: `env <id>`
- **Export info**: `info --instance <id> --format env --output <file>`

---

## Docker Operations

- **Start**: `start <id>`
- **Stop**: `stop <id>`
- **Logs**: `logs <id>`
- **Status**: `status <id>`

---

## Advanced Usage

- **Generate docker-compose template**:
  - Shell: `./supabase-manager.sh template 1 my-service > docker-compose.yml`
  - Python: `python3 setup.py template 1 my-service --output docker-compose.yml`

---

## Troubleshooting

- **Docker not running**: Start Docker daemon
- **Port conflicts**: Check if ports are in use (`lsof -i :PORT`)
- **Permission errors**: Ensure script has write permissions
- **Network issues**: `docker network ls | grep supabase`
- **Logs**: `./supabase-manager.sh logs <id>`

---

## Port Reference Table

| Instance | Kong HTTP | PostgreSQL | Studio |
|----------|-----------|------------|--------|
| 1        | 8001      | 5433       | 3001   |
| 2        | 8002      | 5434       | 3002   |
| 3        | 8003      | 5435       | 3003   |
| ...      | ...       | ...        | ...    |

---

## Use Case Examples

### LLM Chatbot Development

- **Dev**: `./supabase-manager.sh setup 1`
- **Staging**: `./supabase-manager.sh setup 2`
- **Prod**: `./supabase-manager.sh setup 3`

### Multi-tenant

- `./supabase-manager.sh setup 1 2 3 4 5`
- Each instance = separate tenant

### Microservices

- `./supabase-manager.sh setup 1 2 3`
- Each service gets its own instance/network

---

## Example docker-compose Service

```yaml
version: '3.8'
services:
  my-llm-chatbot:
    image: my-chatbot:latest
    environment:
      - DATABASE_URL=postgresql://postgres:your-super-secret-and-long-postgres-password@localhost:5433/postgres_instance1
      - SUPABASE_URL=http://localhost:8001
      - SUPABASE_ANON_KEY=[see instance .env or info command]
    networks:
      - supabase-instance1-network
    depends_on:
      - supabase-db

networks:
  supabase-instance1-network:
    external: true
    name: supabase-instance1-network
```

---

For more details, see the full README.md.
