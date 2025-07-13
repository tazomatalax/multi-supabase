#!/usr/bin/env python3
"""
Supabase Instance Manager (Refactored v5)

Manages isolated Supabase instances, disabling Supavisor and Analytics services
to ensure stability and direct database access.

Author: vanderwt (Refactored by Gemini)
License: MIT
"""

import os
import shutil
import subprocess
import argparse
import logging
import secrets
import time
import json
from pathlib import Path
from typing import List, Dict, Optional

try:
    import jwt
    import yaml
except ImportError:
    print("Required packages are not installed. Please run: pip install pyjwt pyyaml")
    exit(1)

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.resolve()
INSTANCES_ROOT_DIR = BASE_DIR / "instances"
SUPABASE_TEMPLATE_DIR = BASE_DIR / "supabase-template"
REGISTRY_FILE = INSTANCES_ROOT_DIR / "instances.json"

# --- Helper Functions ---

def run_command(cmd: List[str], cwd: str, check: bool = True, capture: bool = False) -> Optional[str]:
    """Execute a shell command with logging."""
    logger.debug(f"Running command: {' '.join(cmd)} in {cwd}")
    try:
        result = subprocess.run(
            cmd, cwd=cwd, check=check, capture_output=True, text=True
        )
        if capture:
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"Stderr: {e.stderr.strip()}")
        if e.stdout:
            logger.error(f"Stdout: {e.stdout.strip()}")
        raise

def load_registry() -> Dict[str, Dict]:
    """Loads the instance registry from a JSON file."""
    if not REGISTRY_FILE.exists():
        return {}
    with open(REGISTRY_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            logger.warning("Registry file is corrupted, starting fresh.")
            return {}

def save_registry(registry: Dict[str, Dict]) -> None:
    """Saves the instance registry to a JSON file."""
    INSTANCES_ROOT_DIR.mkdir(exist_ok=True)
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2)

def get_next_instance_id(registry: Dict[str, Dict]) -> int:
    """Finds the next available integer ID for a new instance."""
    if not registry:
        return 1
    existing_ids = [data['id'] for data in registry.values()]
    return max(existing_ids) + 1 if existing_ids else 1

def generate_secrets() -> Dict[str, str]:
    """Generate all necessary secrets for a Supabase instance."""
    logger.info("Generating secure secrets...")
    jwt_secret = ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(40))

    def create_jwt(role: str) -> str:
        now = int(time.time())
        exp = now + (10 * 365 * 24 * 60 * 60)
        payload = {"role": role, "iss": "supabase", "iat": now, "exp": exp}
        return jwt.encode(payload, jwt_secret, algorithm="HS256")

    return {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "JWT_SECRET": jwt_secret,
        "ANON_KEY": create_jwt("anon"),
        "SERVICE_ROLE_KEY": create_jwt("service_role"),
        "DASHBOARD_USERNAME": "supabase",
        "DASHBOARD_PASSWORD": secrets.token_urlsafe(24),
    }

def clone_supabase_template() -> None:
    """Clones or updates the Supabase repository to be used as a template."""
    if SUPABASE_TEMPLATE_DIR.exists():
        logger.info("Updating Supabase template from git...")
        run_command(["git", "pull"], cwd=str(SUPABASE_TEMPLATE_DIR))
    else:
        logger.info("Cloning Supabase repository for template...")
        run_command([
            "git", "clone", "--depth", "1",
            "https://github.com/supabase/supabase",
            str(SUPABASE_TEMPLATE_DIR)
        ], cwd=str(BASE_DIR))

# --- Main Functions ---

def create_instance(name: str) -> None:
    """
    Creates and starts a new, isolated Supabase instance with dynamic port allocation.
    """
    registry = load_registry()
    if name in registry:
        logger.error(f"Instance '{name}' already exists.")
        return

    instance_id = get_next_instance_id(registry)
    instance_path = INSTANCES_ROOT_DIR / name
    project_name = f"supabase-{name}"

    logger.info(f"Creating new instance '{name}' with ID {instance_id}...")
    clone_supabase_template()

    template_docker_path = SUPABASE_TEMPLATE_DIR / "docker"
    shutil.copytree(template_docker_path, instance_path, dirs_exist_ok=True)
    logger.info(f"Copied template to {instance_path}")

    port_offset = instance_id - 1
    ports = {
        "kong_http": 8001 + port_offset,
        "kong_https": 8444 + port_offset,
        "postgres": 5433 + port_offset,
        "studio": 3001 + port_offset,
    }
    secrets = generate_secrets()

    env_example_path = instance_path / ".env.example"
    env_path = instance_path / ".env"
    with open(env_example_path, 'r') as f:
        env_content = f.read()

    replacements = {
        "POSTGRES_PASSWORD=your-super-secret-and-long-postgres-password": f"POSTGRES_PASSWORD={secrets['POSTGRES_PASSWORD']}",
        "JWT_SECRET=your-super-secret-jwt-token-with-at-least-32-characters-long": f"JWT_SECRET={secrets['JWT_SECRET']}",
        "ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9zZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE": f"ANON_KEY={secrets['ANON_KEY']}",
        "SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9zZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwKICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q": f"SERVICE_ROLE_KEY={secrets['SERVICE_ROLE_KEY']}",
        "DASHBOARD_USERNAME=supabase": f"DASHBOARD_USERNAME={secrets['DASHBOARD_USERNAME']}",
        "DASHBOARD_PASSWORD=this_password_is_insecure_and_should_be_updated": f"DASHBOARD_PASSWORD={secrets['DASHBOARD_PASSWORD']}",
        "KONG_HTTP_PORT=8000": f"KONG_HTTP_PORT={ports['kong_http']}",
        "POSTGRES_PORT=5432": f"POSTGRES_PORT={ports['postgres']}",
        "STUDIO_PORT=3000": f"STUDIO_PORT={ports['studio']}",
    }
    for old, new in replacements.items():
        env_content = env_content.replace(old, new)

    with open(env_path, 'w') as f:
        f.write(env_content)
    logger.info("Successfully created and secured .env file.")

    compose_path = instance_path / "docker-compose.yml"
    with open(compose_path, 'r') as f:
        lines = f.readlines()

    with open(compose_path, 'w') as f:
        in_service_to_comment = False
        service_name = ""
        for line in lines:
            stripped_line = line.strip()
            if stripped_line in ["supavisor:", "analytics:"]:
                in_service_to_comment = True
                service_name = stripped_line[:-1]
            elif not line.startswith(" "):
                in_service_to_comment = False

            if in_service_to_comment:
                f.write(f"# {line}")
            else:
                f.write(line)
    logger.info("Commented out Supavisor and Analytics services in docker-compose.yml")

    with open(compose_path, 'r') as f:
        compose_data = yaml.safe_load(f)

    if 'db' in compose_data['services']:
        compose_data['services']['db']['ports'] = [
            f"${{POSTGRES_PORT}}:${{POSTGRES_PORT}}"
        ]
        logger.info("Exposed PostgreSQL port for direct access.")

    with open(compose_path, 'w') as f:
        yaml.dump(compose_data, f, sort_keys=False)

    logger.info(f"Pulling Docker images for project '{project_name}'...")
    run_command(["docker", "compose", "--project-name", project_name, "pull"], cwd=str(instance_path))

    logger.info(f"Starting Supabase instance '{name}'...")
    run_command(["docker", "compose", "--project-name", project_name, "up", "-d"], cwd=str(instance_path))

    registry[name] = {"id": instance_id, "path": str(instance_path), "ports": ports}
    save_registry(registry)

    logger.info("✅ Instance created and started successfully!")
    logger.info(f"Project Name: {project_name}")
    logger.info(f"Studio URL: http://localhost:{ports['studio']}")
    logger.info(f"API URL: http://localhost:{ports['kong_http']}")
    logger.info(f"Postgres Port: {ports['postgres']}")
    logger.info(f"Postgres Connection: postgresql://postgres:{secrets['POSTGRES_PASSWORD']}@localhost:{ports['postgres']}/postgres")

def destroy_instance(name: str) -> None:
    registry = load_registry()
    if name not in registry:
        logger.error(f"Instance '{name}' not found in registry.")
        return

    instance_path = Path(registry[name]["path"])
    project_name = f"supabase-{name}"

    logger.warning(f"Destroying instance '{name}'. This will delete all its data.")
    try:
        run_command([
            "docker", "compose", "--project-name", project_name, "down", "--volumes", "--remove-orphans"
        ], cwd=str(instance_path))
    except subprocess.CalledProcessError:
        logger.error("Failed to run 'docker compose down'. The instance may not have been running.")

    shutil.rmtree(instance_path)
    del registry[name]
    save_registry(registry)
    logger.info(f"✅ Instance '{name}' destroyed successfully.")

def list_instances() -> None:
    registry = load_registry()
    if not registry:
        logger.info("No instances found.")
        return

    print(f"{'INSTANCE':<20} {'ID':<5} {'STATUS':<20} {'API PORT':<10} {'DB PORT'}")
    print("-" * 80)

    for name, data in sorted(registry.items(), key=lambda item: item[1]['id']):
        instance_path = Path(data["path"])
        project_name = f"supabase-{name}"
        status = "Not Running"
        try:
            output = run_command(
                ["docker", "compose", "--project-name", project_name, "ps", "--format", "json"],
                cwd=str(instance_path), capture=True, check=False
            )
            if output:
                services = [json.loads(line) for line in output.strip().split('\n') if line]
                if any(s.get('State') == 'running' for s in services):
                    status = "Running"
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass

        print(f"{name:<20} {data['id']:<5} {status:<20} {data['ports']['kong_http']:<10} {data['ports']['postgres']}")

def main():
    INSTANCES_ROOT_DIR.mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(
        description="Manage multiple, concurrent Supabase instances with dynamic port allocation.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create and start a new Supabase instance.")
    create_parser.add_argument("name", help="A unique name for the new instance (e.g., 'my-project').")

    destroy_parser = subparsers.add_parser("destroy", help="Stop and delete a Supabase instance and its data.")
    destroy_parser.add_argument("name", help="The name of the instance to destroy.")

    subparsers.add_parser("list", help="List all managed Supabase instances and their status.")

    pass_through_cmds = ["start", "stop", "restart", "logs", "ps"]
    for cmd in pass_through_cmds:
        cmd_parser = subparsers.add_parser(cmd, help=f"Run 'docker compose {cmd}' on an instance's services.")
        cmd_parser.add_argument("name", help="The name of the instance to target.")
        cmd_parser.add_argument('services', nargs='*', help='(Optional) The service(s) to target.')

    args = parser.parse_args()

    if args.command == "create":
        create_instance(args.name)
    elif args.command == "destroy":
        try:
            confirm = input(f"Are you sure you want to permanently delete instance '{args.name}' and all its data? (y/n): ")
            if confirm.lower() == 'y':
                destroy_instance(args.name)
            else:
                print("Deletion cancelled.")
        except (KeyboardInterrupt, EOFError):
            print("\nDeletion cancelled.")
    elif args.command == "list":
        list_instances()
    elif args.command in pass_through_cmds:
        registry = load_registry()
        if args.name not in registry:
            logger.error(f"Instance '{args.name}' not found.")
            return
        instance_path = Path(registry[args.name]["path"])
        project_name = f"supabase-{args.name}"
        try:
            cmd = ["docker", "compose", "--project-name", project_name, args.command] + args.services
            subprocess.run(cmd, cwd=str(instance_path))
        except Exception as e:
            logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()