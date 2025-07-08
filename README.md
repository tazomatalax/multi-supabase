# Supabase Instance Manager

A comprehensive Python tool for managing multiple Supabase instances with Docker isolation. This tool automates the creation, configuration, and management of isolated Supabase environments with proper JWT token generation and unique networking.

## Features

- ✅ **Automated Instance Setup**: Clone Supabase repository and configure instances
- ✅ **JWT Token Generation**: Properly generate and validate JWT tokens for authentication
- ✅ **Port Management**: Automatic port allocation to avoid conflicts
- ✅ **Docker Network Isolation**: Each instance gets its own Docker network
- ✅ **Registry Management**: Track all instances in a JSON registry
- ✅ **Environment Configuration**: Generate proper .env files from templates
- ✅ **Interactive CLI**: User-friendly command-line interface
- ✅ **Connection Export**: Export connection strings in multiple formats
- ✅ **Instance Lifecycle**: Create, update, status check, and delete instances

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Make sure Docker is running:**
   ```bash
   docker --version
   docker compose --version
   ```

## Usage

### Interactive Mode (Recommended)

```bash
python setup.py
```

This launches an interactive menu where you can:
- Setup new instances
- List all instances
- Get connection information
- Update instance metadata
- Generate Docker Compose templates
- Check instance status
- Delete instances
- Update environment files

### Command Line Interface

#### Setup Instances
```bash
# Setup a single instance
python setup.py setup --instances 1 --name "my-app" --description "My application backend"

# Setup multiple instances
python setup.py setup --instances 1 2 3
```

#### List Instances
```bash
# Table format (default)
python setup.py list

# JSON format
python setup.py list --format json

# YAML format
python setup.py list --format yaml
```

#### Get Connection Information
```bash
# Get info for specific instance
python setup.py info --instance 1 --format json

# Get info for all instances as environment variables
python setup.py info --format env

# Save to file
python setup.py info --instance 1 --format json --output instance1.json
```

#### Check Status
```bash
# Check specific instance
python setup.py status --instance 1

# Check all instances
python setup.py status
```

#### Update Instance Metadata
```bash
python setup.py update 1 --name "Updated Name" --description "New description"
```

#### Generate External Service Template
```bash
python setup.py template 1 my-service
```

#### Delete Instance
```bash
# Delete instance but keep files
python setup.py delete 1

# Delete instance and remove files
python setup.py delete 1 --remove-files

# Skip confirmation (use with caution)
python setup.py delete 1 --remove-files --yes
```

#### Update Environment File
```bash
python setup.py update-env --instance 1
```

## Configuration

### Default Locations
- **Base folder**: `~/projects/database`
- **Registry file**: `~/projects/database/instance_registry.json`
- **Instance folders**: `~/projects/database/{folder-name}/supabase/`

### Port Allocation
Each instance gets unique ports based on the instance ID:

| Service | Base Port | Instance 1 | Instance 2 | Instance 3 |
|---------|-----------|------------|------------|------------|
| Kong HTTP | 8000 | 8001 | 8002 | 8003 |
| Kong HTTPS | 8443 | 8444 | 8445 | 8446 |
| PostgreSQL | 5432 | 5433 | 5434 | 5435 |
| Studio | 3000 | 3001 | 3002 | 3003 |
| Analytics | 4000 | 4001 | 4002 | 4003 |
| Pooler | 6543 | 6544 | 6545 | 6546 |

### Docker Networks
Each instance gets its own Docker network:
- `supabase-instance1-network`
- `supabase-instance2-network`
- etc.

## Starting and Stopping Instances

After setup, navigate to the instance directory and use Docker Compose:

```bash
# Navigate to instance directory
cd ~/projects/database/my-app-instance1/supabase/docker

# Start the instance
docker compose up -d

# View logs
docker compose logs -f

# Stop the instance
docker compose down

# Stop and remove volumes (resets data)
docker compose down -v
```

## Connection Information

After setup, you can connect to your Supabase instance:

### Database Connection
```
Host: localhost
Port: 5433 (for instance 1)
Database: postgres
User: postgres
Password: [generated password from registry]
```

### Supabase API
```
URL: http://localhost:8001 (for instance 1)
Anon Key: [generated key from registry]
Service Role Key: [generated key from registry]
```

### Studio Dashboard
```
URL: http://localhost:3001 (for instance 1)
```

## Troubleshooting

### JWT Token Issues
Run the test script to validate token generation:
```bash
python test_jwt.py
```

### Docker Issues
- Make sure Docker is running
- Check for port conflicts: `netstat -tlnp | grep :8001`
- View container logs: `docker compose logs -f`

### Network Issues
- List Docker networks: `docker network ls`
- Inspect network: `docker network inspect supabase-instance1-network`

### Registry Issues
The registry file (`instance_registry.json`) contains all instance information. If corrupted:
1. Backup the current file
2. Delete the file to start fresh
3. Re-register instances if needed

## File Structure

```
~/projects/database/
├── instance_registry.json          # Registry of all instances
├── setup.py                       # Main script
├── requirements.txt                # Python dependencies
├── test_jwt.py                    # JWT validation test
└── my-app-instance1/              # Instance folder
    └── supabase/
        ├── docker/
        │   ├── .env                # Environment configuration
        │   ├── docker-compose.yml  # Docker Compose file
        │   └── ...
        └── ...
```

## Security Notes

- Generated passwords and keys are cryptographically secure
- Each instance has isolated networking
- JWT tokens are properly signed and validated
- Default configurations include security best practices
- Change default passwords before production use

## Contributing

This tool is designed for personal and development use. Feel free to modify and extend it for your needs.

## License

MIT License - feel free to use and modify as needed.
