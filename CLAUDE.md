# Claude Code Configuration for Multi-Supabase Instance Manager

## Project Overview

This project manages multiple, isolated Supabase instances using Docker containerization. It includes a Python instance manager (`setup.py`) and supports various development workflows for docs, studio, and other Supabase services.

## Key Commands

### Instance Management
```bash
# Create a new Supabase instance
make create NAME=myproject

# List all instances
make list

# View connection details
make list-details                    # Show ALL connection details for all instances
make details NAME=myproject          # Show connection details for specific instance
make update-details NAME=myproject   # Update connection details for existing instance

# Start/stop/restart instances
make myproject-start
make myproject-stop  
make myproject-restart

# View logs for an instance
make myproject-logs

# Destroy an instance (with confirmation)
make myproject-destroy

# One-time setup (clone Supabase template)
make setup
```

### Development Workflow
```bash
# Install dependencies
pip install -r requirements.txt

# Setup project initially
make setup

# Create new instance for development
make create NAME=dev-instance

# Access services
# Studio: http://localhost:{STUDIO_PORT}
# API: http://localhost:{KONG_HTTP_PORT}
# Database: postgresql://postgres:{PASSWORD}@localhost:{POSTGRES_PORT}/postgres
```

### Testing Commands
```bash
# For docs testing (if working in apps/docs/)
pnpm supabase status
pnpm supabase start  # if not running
pnpm supabase db reset --local
pnpm run -F docs test:local:unwatch

# For studio testing (if working in apps/studio/)
# Ensure Supabase instance is running first
pnpm run -F studio test
```

### Linting and Type Checking
```bash
# Run linting (if applicable to specific apps)
pnpm run lint
pnpm run typecheck

# For Python components
python -m flake8 setup.py
python -m mypy setup.py --ignore-missing-imports
```

## Project Structure

- `setup.py` - Main Python script for managing Supabase instances
- `instances/` - Directory containing all created instances
- `supabase-template/` - Git submodule with Supabase source code
- `.cursor/rules/` - IDE-specific rules and configurations
- `Makefile` - Make targets for common operations

## Instance Configuration

Each instance gets:
- Unique ports automatically allocated
- Isolated Docker containers with project-specific names
- Secure secrets and JWT tokens
- Complete Supabase stack (Auth, Database, Storage, Edge Functions, etc.)
- Comprehensive connection details stored in instances.json including:
  - URLs for all services (localhost, hostname, and Pi IP)
  - Database connection strings (direct and pooled)
  - Authentication keys and secrets
  - Dashboard credentials
  - System information

## Development Notes

- Instances are completely isolated - no port conflicts
- Each instance has its own `.env` file with unique secrets
- Use `make list` to see all instances and their ports
- Containers use project-specific naming to avoid conflicts
- All data is preserved until explicitly destroyed

## Security

- JWT secrets are cryptographically secure (512-bit)
- Database passwords use secure random generation
- Each instance has unique authentication tokens
- Secrets are stored locally in instance `.env` files

## Multi-Instance Features

- Concurrent instances without conflicts
- Automatic port allocation
- Isolated Docker networks
- Individual instance management
- Registry tracking in `instances/instances.json`

## Claude Code Integration

This project includes comprehensive Claude Code configuration in the `.cursor/rules/` directory:

- `claude-code-instance-management.mdc` - Core instance management patterns
- `claude-code-development-workflow.mdc` - Development workflow guidance
- `claude-code-multi-instance-config.mdc` - Complete multi-instance configuration
- `docs-test-requirements.mdc` - Updated testing procedures for docs
- `unit-integration-testing.mdc` - Updated testing procedures for studio
- `docs-graphql.mdc` - GraphQL development patterns

These files provide Claude Code with context about:
- Multi-instance project structure
- Context-aware command execution
- Testing strategies across instances
- Port management and service access
- Security considerations
- Troubleshooting guidance

## Key Patterns for Claude Code

1. **Always check instance state first**: `make list`
2. **Understand working context**: Template vs specific instance
3. **Use instance-specific ports**: Check `.env` files
4. **Test in appropriate context**: Template for core, instances for integration
5. **Clean up resources**: Destroy unused instances