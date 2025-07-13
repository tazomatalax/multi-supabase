# Supabase Instance Manager (v2)

A comprehensive Python tool for managing multiple, concurrent Supabase instances with dynamic port allocation and isolated networking.

## Features

- ✅ **Concurrent Instances**: Run multiple Supabase instances at the same time, each with its own set of ports.
- ✅ **Dynamic Port Allocation**: Automatically assigns unique ports to each new instance to prevent conflicts.
- ✅ **Direct Database Access**: Exposes the PostgreSQL port for each instance, allowing direct connections from any database tool.
- ✅ **Stateful Registry**: Tracks instances and their assigned ports in a simple `instances.json` file.
- ✅ **True Isolation**: Uses Docker Compose projects (`--project-name`) for robust container and network isolation.
- ✅ **Secure by Default**: Automatically generates all required secrets for each instance.
- ✅ **Clean Destruction**: Fully removes all containers and associated data volumes on instance deletion.

## Installation

1.  **Clone or download this repository.**

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Ensure Docker is installed and running.**

## Usage

### Create a New Instance

Creates a new instance with a unique ID and port allocation. The script will modify the instance's `.env` and `docker-compose.yml` files to ensure it uses the correct ports and exposes the database directly.

```bash
# Usage: python3 setup.py create <instance-name>
python3 setup.py create project-alpha
```

### List All Instances

Shows all registered instances, their ID, running status, and key ports.

```bash
python3 setup.py list
```

### Destroy an Instance

Stops the Docker containers and **permanently deletes all associated data volumes** and the instance's directory.

```bash
# Usage: python3 setup.py destroy <instance-name>
python3 setup.py destroy project-alpha
```

### Manage an Instance (start, stop, logs, etc.)

Pass Docker Compose commands directly to a specific instance's services.

```bash
# Stop a running instance
python3 setup.py stop project-alpha

# Start a stopped instance
python3 setup.py start project-alpha

# Follow logs for an instance
python3 setup.py logs project-alpha -f
```

## How It Works

### Port Allocation

The script maintains a simple registry at `instances/instances.json`. When a new instance is created, it is assigned the next available integer ID (e.g., 1, 2, 3...). This ID is used to calculate a port offset.

| Service    | Base Port | Instance 1 | Instance 2 | Instance 3 |
|------------|-----------|------------|------------|------------|
| Kong HTTP  | 8000      | 8000       | 8001       | 8002       |
| PostgreSQL | 5432      | 5432       | 5433       | 5434       |
| Studio     | 3000      | 3000       | 3001       | 3002       |

### Direct Database Access

During instance creation, the script modifies the `docker-compose.yml` file to add a port mapping to the `db` service. This makes the PostgreSQL database accessible on its assigned port from your host machine (`localhost`).

The full connection string is printed to the console after creation.

### Directory Structure

```
/
├── instances/
│   ├── instances.json       # Registry of instances and their ports
│   └── project-alpha/       # Folder for an instance
│       ├── .env             # Secure, generated environment file
│       └── docker-compose.yml # Modified for port mapping
│
├── supabase-template/       # A local clone of the official Supabase repo
│
├── setup.py                 # The main management script
└── requirements.txt
```

## License

MIT License
