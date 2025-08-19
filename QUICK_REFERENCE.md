# Supabase Instance Manager – Quick Reference

Simple commands for managing multiple, concurrent Supabase instances using Make.

**⚠️ Important: Run commands from the `multi-supabase/` directory!**

```bash
cd multi-supabase/   # Make sure you're in the right directory
```

## First Time Setup

```bash
# One-time setup (installs deps + clones template)
make setup

# Or just install dependencies
make deps

# Get help
make help
```

## Core Commands

```bash
# Create new instance
make create NAME=myproject

# List all instances  
make list

# Destroy instance (with confirmation)
make destroy NAME=myproject
```

## Instance Management

```bash
# Start/stop any instance
make myproject-start
make myproject-stop
make myproject-restart

# View logs (follows by default)
make myproject-logs

# Check status
make myproject-ps
```

## Common Shortcuts

```bash
# Quick dev instance commands
make dev-start
make dev-stop  
make dev-logs

# Nuclear option - destroy everything
make clean
```

## What You Get

Each instance gets:
- **Unique ports** (no conflicts)
- **Isolated data** (separate Docker volumes)
- **Secure secrets** (generated JWT keys)
- **Easy access** (Studio, API, direct DB)

## Port Assignment

Ports auto-increment by instance ID:

| Instance | Studio | API  | Database |
|----------|--------|------|----------|
| 1st      | 3001   | 8001 | 5433     |
| 2nd      | 3002   | 8002 | 5434     |
| 3rd      | 3003   | 8003 | 5435     |

## Troubleshooting

**Problem: `make: *** No rule to make target 'create'. Stop.`**
- Solution: Make sure you're in the `multi-supabase/` directory!

**Problem: Template issues**
- Run `make setup` to re-clone template and validate

## Direct Python Usage

Still works if you prefer:
```bash
python3 setup.py setup         # One-time setup
python3 setup.py create myproject
python3 setup.py list
python3 setup.py destroy myproject
```