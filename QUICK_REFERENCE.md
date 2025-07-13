# Supabase Instance Manager – Quick Reference (v3)

A concise guide for managing multiple, concurrent Supabase instances.

---

## Core Commands

```bash
# Create and start a new instance named 'project-alpha'
# Ports will be assigned automatically, starting from 5433, 8001, etc.
python3 setup.py create project-alpha

# Create a second instance, which will get the next set of ports.
python3 setup.py create project-beta

# List all existing instances and their running status
python3 setup.py list

# Stop and completely delete an instance and its data
python3 setup.py destroy project-alpha
```

---

## Instance Lifecycle Management

```bash
# Start a stopped instance
python3 setup.py start project-alpha

# Stop a running instance
python3 setup.py stop project-alpha

# Follow logs from an instance
python3 setup.py logs project-alpha -f

# Check the status of services within an instance
python3 setup.py ps project-alpha
```

---

## Key Concepts

-   **No Port Conflicts**: The script starts allocating ports from a higher, non-standard range (`5433`, `8001`, etc.) to avoid conflicts with default services on your machine.
-   **Concurrent Instances**: You can run multiple instances at the same time. The script handles all port assignments to prevent conflicts.
-   **Direct DB Access**: The PostgreSQL port is always exposed to `localhost`. The connection string is provided when you create the instance.
-   **Instance Registry**: A file at `instances/instances.json` keeps track of your instances, their IDs, and their assigned ports.

---

## Port Reference Table

Ports are assigned based on instance ID. The first instance gets ID 1, the second gets ID 2, and so on.

| Instance ID | Kong HTTP Port | PostgreSQL Port | Studio Port |
|-------------|----------------|-----------------|-------------|
| 1           | 8001           | 5433            | 3001        |
| 2           | 8002           | 5434            | 3002        |
| 3           | 8003           | 5435            | 3003        |
| ...         | ...            | ...             | ...         |

---

## Accessing an Instance

When you create an instance, its unique connection details are printed. You can also find them in the output of `python3 setup.py list`.

**Example for Instance ID 1 (`project-alpha`):**

-   **Supabase Studio**: `http://localhost:3001`
-   **Postgres**: `postgresql://postgres:<password>@localhost:5433/postgres`
-   **API URL**: `http://localhost:8001`

---

For more details, see the full `README.md`.