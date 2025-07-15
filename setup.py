#!/usr/bin/env python3
"""
Supabase Instance Manager (Refactored v6)

Manages isolated Supabase instances by dynamically configuring .env files for port
allocation, leaving the original docker-compose.yml unmodified as intended.

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
except ImportError:
    print("PyJWT is not installed. Please run: pip install pyjwt")
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
    if not REGISTRY_FILE.exists():
        return {}
    with open(REGISTRY_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_registry(registry: Dict[str, Dict]) -> None:
    INSTANCES_ROOT_DIR.mkdir(exist_ok=True)
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2)

def get_next_instance_id(registry: Dict[str, Dict]) -> int:
    if not registry:
        return 1
    existing_ids = [data['id'] for data in registry.values()]
    return max(existing_ids) + 1 if existing_ids else 1

def generate_secrets() -> Dict[str, str]:
    logger.info("Generating secure secrets...")
    jwt_secret = secrets.token_hex(32)  # Simpler and stronger

    def create_jwt(role: str) -> str:
        now = int(time.time())
        exp = now + (5 * 365 * 24 * 60 * 60)
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
    if SUPABASE_TEMPLATE_DIR.exists():
        logger.info("Updating Supabase template from git...")
        run_command(["git", "pull"], cwd=str(SUPABASE_TEMPLATE_DIR))
    else:
        logger.info("Cloning Supabase repository for template...")
        run_command(
            [
                "git", "clone", "--depth", "1",
                "https://github.com/supabase/supabase",
                str(SUPABASE_TEMPLATE_DIR)
            ], cwd=str(BASE_DIR))

def remove_container_names_from_compose(compose_path: Path) -> None:
    """Remove all 'container_name:' lines from the docker-compose.yml file."""
    if not compose_path.exists():
        logger.warning(f"{compose_path} does not exist.")
        return
    with open(compose_path, "r") as f:
        lines = f.readlines()
    with open(compose_path, "w") as f:
        for line in lines:
            if not line.strip().startswith("container_name:"):
                f.write(line)

# --- Port allocation improvement ---
def get_next_available_ports(registry: Dict[str, Dict]) -> Dict[str, int]:
    base_ports = {
        "kong_http": 8001,
        "postgres_direct": 5433,
        "supavisor_pooler": 6544,
        "studio": 3001,
    }
    used_kong_ports = {data['ports']['kong_http'] for data in registry.values()}
    offset = 0
    while True:
        candidate_port = base_ports["kong_http"] + offset
        if candidate_port not in used_kong_ports:
            return {
                "kong_http": base_ports["kong_http"] + offset,
                "postgres_direct": base_ports["postgres_direct"] + offset,
                "supavisor_pooler": base_ports["supavisor_pooler"] + offset,
                "studio": base_ports["studio"] + offset,
            }
        offset += 1

# --- Main Functions ---

def create_instance(name: str) -> None:
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

    # Remove container_name lines from docker-compose.yml
    compose_file_path = instance_path / "docker-compose.yml"
    remove_container_names_from_compose(compose_file_path)

    # Use robust port allocation
    ports = get_next_available_ports(registry)
    secrets_dict = generate_secrets()

    env_example_path = instance_path / ".env.example"
    env_path = instance_path / ".env"

    # --- Robust .env creation ---
    instance_values = {
        "POSTGRES_PASSWORD": secrets_dict['POSTGRES_PASSWORD'],
        "JWT_SECRET": secrets_dict['JWT_SECRET'],
        "ANON_KEY": secrets_dict['ANON_KEY'],
        "SERVICE_ROLE_KEY": secrets_dict['SERVICE_ROLE_KEY'],
        "DASHBOARD_USERNAME": secrets_dict['DASHBOARD_USERNAME'],
        "DASHBOARD_PASSWORD": secrets_dict['DASHBOARD_PASSWORD'],
        "KONG_HTTP_PORT": str(ports['kong_http']),
        "POSTGRES_PORT": str(ports['postgres_direct']),
        "POOLER_PROXY_PORT_TRANSACTION": str(ports['supavisor_pooler']),
        "STUDIO_PORT": str(ports['studio']),
    }
    with open(env_example_path, 'r') as f_template, open(env_path, 'w') as f_final:
        for line in f_template:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                f_final.write(line)
                continue
            key = stripped.split('=', 1)[0]
            if key in instance_values:
                f_final.write(f"{key}={instance_values[key]}\n")
            else:
                f_final.write(line)
    logger.info("Successfully created and secured .env file with dynamic ports.")

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
    logger.info(f"DB (Direct Session): postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD']}@localhost:{ports['postgres_direct']}/postgres")
    logger.info(f"DB (Pooled Transaction): postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD']}@localhost:{ports['supavisor_pooler']}/postgres")

def destroy_instance(name: str) -> None:
    registry = load_registry()
    if name not in registry:
        logger.error(f"Instance '{name}' not found in registry.")
        return

    instance_path = Path(registry[name]["path"])
    project_name = f"supabase-{name}"

    logger.warning(f"Destroying instance '{name}'. This will delete all its data.")
    try:
        run_command(
            [
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

    print(f"{'INSTANCE':<20} {'ID':<5} {'STATUS':<20} {'API':<8} {'DB':<8} {'POOLER'}")
    print("-" * 80)

    for name, data in sorted(registry.items(), key=lambda item: item[1]['id']):
        instance_path = Path(data["path"])
        project_name = f"supabase-{name}"
        status = "Not Running"
        try:
            output = run_command(
                [
                    "docker", "compose", "--project-name", project_name, "ps", "--format", "json"
                ],
                cwd=str(instance_path), capture=True, check=False
            )
            if output:
                services = [json.loads(line) for line in output.strip().split('\n') if line]
                if any(s.get('State') == 'running' for s in services):
                    status = "Running"
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass

        print(f"{name:<20} {data['id']:<5} {status:<20} {data['ports']['kong_http']:<8} {data['ports']['postgres_direct']:<8} {data['ports']['supavisor_pooler']}")

def main():
    INSTANCES_ROOT_DIR.mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(
        description="Manage multiple, concurrent Supabase instances.",
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
