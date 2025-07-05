# Supabase Instance Manager

A comprehensive tool for managing multiple Supabase instances for LLM chatbots and other applications. This tool provides easy setup, management, and connection information for multiple isolated Supabase instances.

## Features

- **Multi-instance Management**: Set up and manage multiple Supabase instances with unique ports and databases
- **Docker Network Integration**: Automatic Docker network creation for container communication
- **Instance Registry**: JSON-based registry to track all instances and their metadata
- **Connection Information Export**: Export connection details in multiple formats (JSON, YAML, environment variables)
- **Instance Naming & Tagging**: Assign meaningful names and tags to instances
- **Status Monitoring**: Check if instances are running or stopped
- **Template Generation**: Generate docker-compose templates for external services
- **CLI Interface**: Comprehensive command-line interface for all operations
- **Shell Script Wrapper**: Quick commands for common operations

## Installation

1. Clone or download the scripts to your desired directory
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Make the shell script executable:
   ```bash
   chmod +x supabase-manager.sh
   ```

## Quick Start

### Using the Shell Script (Recommended)

```bash
# Set up instances 1-5 (default)
./supabase-manager.sh setup

# Set up specific instances
./supabase-manager.sh setup 1 2 3

# List all instances
./supabase-manager.sh list

# Get connection info for instance 1
./supabase-manager.sh info 1

# Start instance 1
./supabase-manager.sh start 1

# Stop instance 1
./supabase-manager.sh stop 1

# View logs for instance 1
./supabase-manager.sh logs 1

# Show environment variables for instance 1
./supabase-manager.sh env 1
```

### Using Python Script Directly

```bash
# Set up instances with custom names
python3 setup.py setup --instances 1 --name "ChatBot-Backend" --description "Backend for main chatbot"

# List instances in table format
python3 setup.py list --format table

# Export connection info as environment variables
python3 setup.py info --instance 1 --format env --output chatbot.env

# Generate docker-compose template for external service
python3 setup.py template 1 my-llm-service --output docker-compose.external.yml

# Update instance name
python3 setup.py update 1 --name "Main-ChatBot" --description "Primary chatbot backend"
```

## Instance Configuration

Each instance gets:
- **Unique Ports**: Base port + (instance_id - 1) × 100
- **Dedicated Database**: `postgres_instance{id}`
- **Docker Network**: `supabase-instance{id}-network`
- **Isolated Environment**: Complete separation between instances

### Port Mapping

For instance 1 (base port 54320):
- Supabase API: 54320
- PostgreSQL: 5432
- Supabase Studio: 54322
- Other services: 54321-54328

For instance 2 (base port 54420):
- Supabase API: 54420
- PostgreSQL: 5532
- Supabase Studio: 54422
- Other services: 54421-54428

## Connection Information

### Database Connection
```
postgresql://postgres:your-super-secret-and-long-postgres-password@localhost:PORT/postgres_instanceN
```

### Supabase API
```
URL: http://localhost:BASE_PORT
Anon Key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0
Service Key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU
```

## Docker Integration

### Connecting External Services

1. Generate a docker-compose template:
   ```bash
   ./supabase-manager.sh template 1 my-service > docker-compose.yml
   ```

2. The template includes:
   - Network configuration to connect to Supabase
   - Environment variables for database and API access
   - Proper service dependencies

### Example External Service

```yaml
version: '3.8'
services:
  my-llm-chatbot:
    image: my-chatbot:latest
    environment:
      - DATABASE_URL=postgresql://postgres:your-super-secret-and-long-postgres-password@localhost:5432/postgres_instance1
      - SUPABASE_URL=http://localhost:54320
      - SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0
    networks:
      - supabase-instance1-network
    depends_on:
      - supabase-db

networks:
  supabase-instance1-network:
    external: true
    name: supabase-instance1-network
```

## File Structure

```
~/projects/database/
├── setup.py                    # Main Python script
├── supabase-manager.sh         # Shell script wrapper
├── requirements.txt            # Python dependencies
├── instance_registry.json     # Instance registry (auto-generated)
├── README.md                   # This file
├── instance1/
│   └── supabase/
│       └── docker/
│           ├── .env            # Instance-specific environment
│           └── docker-compose.yml
├── instance2/
│   └── supabase/
│       └── docker/
│           ├── .env
│           └── docker-compose.yml
└── ...
```

## Commands Reference

### Shell Script Commands
- `setup [instance_ids...]` - Set up instances
- `list` - List all instances
- `info [instance_id]` - Show connection info
- `status [instance_id]` - Check instance status
- `update <instance_id> <name>` - Update instance name
- `template <instance_id> <service_name>` - Generate docker-compose template
- `start <instance_id>` - Start instance
- `stop <instance_id>` - Stop instance
- `logs <instance_id>` - View instance logs
- `env <instance_id>` - Show environment variables

### Python Script Commands
- `setup` - Set up instances with advanced options
- `list` - List instances with formatting options
- `info` - Export connection information
- `update` - Update instance metadata
- `template` - Generate service templates
- `status` - Check instance status

## Use Cases

### LLM Chatbot Development
- **Instance 1**: Development chatbot
- **Instance 2**: Staging chatbot
- **Instance 3**: Production chatbot
- **Instance 4**: A/B testing chatbot
- **Instance 5**: Backup/disaster recovery

### Multi-tenant Applications
- Each instance serves a different tenant
- Isolated data and configurations
- Easy scaling and management

### Microservices Architecture
- Each service gets its own Supabase instance
- Clean separation of concerns
- Independent scaling and updates

## Future Enhancements

The script is designed to be easily extensible for:
- **Neo4j Integration**: Add graph database instances
- **Redis Integration**: Add caching layers
- **Monitoring**: Add health checks and metrics
- **Backup Management**: Automated backup and restore
- **Load Balancing**: Distribute traffic across instances
- **SSL/TLS**: Add certificate management
- **Cloud Deployment**: Support for cloud platforms

## Troubleshooting

### Common Issues

1. **Docker connection failed**: Make sure Docker is running
2. **Port conflicts**: Check if ports are already in use
3. **Permission errors**: Ensure the script has write permissions
4. **Git clone fails**: Check internet connection and Git installation

### Logs and Debugging

```bash
# View instance logs
./supabase-manager.sh logs 1

# Check instance status
./supabase-manager.sh status

# Verify network connectivity
docker network ls | grep supabase
```

## Security Considerations

- Change default passwords in production
- Use environment-specific API keys
- Implement proper firewall rules
- Regular security updates
- Monitor access logs

## Contributing

Feel free to contribute improvements:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This tool is provided as-is for educational and development purposes. Ensure compliance with Supabase's terms of service when using their components.
