#!/usr/bin/env python3
"""
Supabase Instance Manager v7

Manages isolated Supabase instances with automatic port allocation and improved reliability.
Creates concurrent Docker-based instances without conflicts.

Author: vanderwt
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
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Check dependencies upfront
def check_dependencies():
    """Verify required dependencies are available."""
    missing = []
    
    try:
        import jwt
    except ImportError:
        missing.append("pyjwt")
    
    # Check for required commands
    commands = ["docker", "git"]
    for cmd in commands:
        if shutil.which(cmd) is None:
            missing.append(cmd)
    
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print("Install with: pip install pyjwt")
        sys.exit(1)

check_dependencies()
import jwt

# Global verbosity flag
VERBOSE = False

# Configure logging
def setup_logging(verbose: bool = False):
    global VERBOSE
    VERBOSE = verbose
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s'
    )

setup_logging()
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.resolve()
INSTANCES_ROOT_DIR = BASE_DIR / "instances"
SUPABASE_TEMPLATE_DIR = BASE_DIR / "supabase-template"
REGISTRY_FILE = INSTANCES_ROOT_DIR / "instances.json"

# --- Helper Functions ---

def run_command(cmd: List[str], cwd: str, check: bool = True, capture: bool = False, show_progress: bool = False) -> Optional[str]:
    """Execute a shell command with logging and optional progress display."""
    logger.debug(f"Running command: {' '.join(cmd)} in {cwd}")
    try:
        if show_progress and not capture:
            # Show real-time output for long operations
            result = subprocess.run(cmd, cwd=cwd, check=check, text=True)
            return None
        else:
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
        logger.debug(f"Registry file {REGISTRY_FILE} does not exist. Returning empty registry.")
        return {}
    with open(REGISTRY_FILE, 'r') as f:
        try:
            registry = json.load(f)
            logger.debug(f"Loaded registry from {REGISTRY_FILE}: {json.dumps(registry, indent=2)}")
            return registry
        except json.JSONDecodeError:
            logger.error(f"Failed to decode registry file {REGISTRY_FILE}. Returning empty registry.")
            return {}

def save_registry(registry: Dict[str, Dict]) -> None:
    INSTANCES_ROOT_DIR.mkdir(exist_ok=True)
    logger.debug(f"Writing registry to {REGISTRY_FILE} with data: {json.dumps(registry, indent=2)}")
    try:
        with open(REGISTRY_FILE, 'w') as f:
            json.dump(registry, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        logger.debug(f"Registry file {REGISTRY_FILE} written and flushed successfully.")
    except Exception as e:
        logger.error(f"Failed to write registry file {REGISTRY_FILE}: {e}")

def get_next_instance_id(registry: Dict[str, Dict]) -> int:
    if not registry:
        return 1
    existing_ids = [data['id'] for data in registry.values()]
    return max(existing_ids) + 1 if existing_ids else 1

def generate_secrets() -> Dict[str, str]:
    """Generate cryptographically secure secrets for Supabase instance."""
    logger.info("Generating secure secrets...")
    
    # Generate a strong JWT secret (64 bytes = 512 bits)
    jwt_secret = secrets.token_hex(64)
    
    def create_jwt(role: str) -> str:
        """Create JWT token with proper claims and long expiration."""
        now = int(time.time())
        exp = now + (10 * 365 * 24 * 60 * 60)  # 10 years expiration
        payload = {
            "role": role,
            "iss": "supabase", 
            "aud": "authenticated" if role == "service_role" else "anon",
            "iat": now,
            "exp": exp
        }
        return jwt.encode(payload, jwt_secret, algorithm="HS256")
    
    return {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "JWT_SECRET": jwt_secret,
        "ANON_KEY": create_jwt("anon"), 
        "SERVICE_ROLE_KEY": create_jwt("service_role"),
        "DASHBOARD_USERNAME": "supabase",
        "DASHBOARD_PASSWORD": secrets.token_urlsafe(24),
    }

def ensure_template_exists() -> bool:
    """Ensure template exists and is valid. Auto-repair if needed."""
    if not SUPABASE_TEMPLATE_DIR.exists():
        print("📥 Cloning Supabase template...")
        return clone_fresh_template()
    
    # Validate existing template
    docker_path = SUPABASE_TEMPLATE_DIR / "docker"
    compose_path = docker_path / "docker-compose.yml"
    
    if not docker_path.exists() or not compose_path.exists():
        print("🔧 Template appears corrupted, re-cloning...")
        shutil.rmtree(SUPABASE_TEMPLATE_DIR)
        return clone_fresh_template()
    
    # Check if it's a valid git repo
    try:
        run_command(["git", "status"], cwd=str(SUPABASE_TEMPLATE_DIR), check=False, capture=True)
        print("✅ Template validated successfully")
        return True
    except:
        print("⚠️  Template directory exists but is not a valid git repo, re-cloning...")
        shutil.rmtree(SUPABASE_TEMPLATE_DIR)
        return clone_fresh_template()

def clone_fresh_template() -> bool:
    """Clone a fresh copy of the Supabase template."""
    try:
        run_command([
            "git", "clone", "--depth", "1", "--single-branch",
            "https://github.com/supabase/supabase",
            str(SUPABASE_TEMPLATE_DIR)
        ], cwd=str(BASE_DIR))
        print("✅ Template cloned successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to clone template: {e}")
        print("   Please check your internet connection and try again.")
        return False

def setup_command() -> None:
    """One-time setup: clone template and validate environment."""
    print("🔧 Setting up Supabase Instance Manager...")
    
    if not ensure_template_exists():
        print("❌ Setup failed: Could not prepare template")
        return
    
    print("🔍 Validating environment...")
    
    # Test Docker
    try:
        result = run_command(["docker", "--version"], cwd=".", capture=True)
        print(f"✅ Docker: {result}")
    except:
        print("❌ Docker not found or not working")
        return
    
    # Test Git
    try:
        result = run_command(["git", "--version"], cwd=".", capture=True)
        print(f"✅ Git: {result}")
    except:
        print("❌ Git not found or not working")
        return
    
    print("✅ Setup complete! You can now create instances with 'make create NAME=yourproject'")


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
    
    logger.debug("Removed container_name directives for better isolation")

def patch_port_mappings(compose_path: Path) -> None:
    """Patch port mappings in docker-compose.yml for dynamic allocation."""
    if not compose_path.exists():
        logger.warning(f"{compose_path} does not exist.")
        return
    
    with open(compose_path, "r") as f:
        content = f.read()
    
    # Simple string replacements for port mappings
    replacements = [
        ("- 4000:4000", "- ${PHX_HTTP_PORT}:4000"),
        ("- 8443:8443", "- ${KONG_HTTPS_PORT}:8443"),
    ]
    
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f"✓ Patched: {old} → {new}")
    
    with open(compose_path, "w") as f:
        f.write(content)

def get_next_available_ports(registry: Dict[str, Dict]) -> Dict[str, int]:
    """Simplified port allocation using sequential assignment."""
    base_ports = {
        "kong_http": 8001,
        "kong_https": 8444,
        "postgres_direct": 5433,
        "supavisor_pooler": 6544,
        "studio": 3001,
        "analytics": 4001,
    }
    
    # Find highest used instance ID and increment
    max_id = 0
    for data in registry.values():
        max_id = max(max_id, data.get('id', 0))
    
    offset = max_id
    return {key: base_port + offset for key, base_port in base_ports.items()}

# --- Main Functions ---

def validate_instance_name(name: str) -> bool:
    """Validate instance name follows naming conventions."""
    import re
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', name) and len(name) > 1:
        if not re.match(r'^[a-z0-9]$', name):
            logger.error(f"Invalid instance name '{name}'. Use lowercase letters, numbers, and hyphens only. Must start and end with alphanumeric.")
            return False
    if len(name) > 50:
        logger.error(f"Instance name '{name}' too long. Maximum 50 characters.")
        return False
    if name in ['test', 'tmp', 'temp', 'staging', 'prod', 'production']:
        logger.warning(f"Instance name '{name}' uses a reserved word. Consider a more specific name.")
    return True

def create_instance(name: str) -> None:
    """Create a new Supabase instance with isolated configuration."""
    if not validate_instance_name(name):
        return
    
    registry = load_registry()
    if name in registry:
        print(f"❌ Instance '{name}' already exists")
        return

    instance_id = get_next_instance_id(registry)
    instance_path = INSTANCES_ROOT_DIR / name
    project_name = f"supabase-{name}"

    print(f"🚀 Creating instance '{name}' (ID: {instance_id})...")
    
    # Ensure template exists and is valid
    if not ensure_template_exists():
        print("❌ Failed to prepare template. Run 'make setup' first.")
        return
    
    template_docker_path = SUPABASE_TEMPLATE_DIR / "docker"
    
    try:
        shutil.copytree(template_docker_path, instance_path, dirs_exist_ok=True)
        logger.info(f"Copied template to {instance_path}")
    except Exception as e:
        logger.error(f"Failed to copy template: {e}")
        return
    
    # Configure docker-compose for isolation
    compose_file_path = instance_path / "docker-compose.yml"
    if not compose_file_path.exists():
        logger.error(f"docker-compose.yml not found in template: {compose_file_path}")
        return
    
    remove_container_names_from_compose(compose_file_path)
    patch_port_mappings(compose_file_path)

    # Allocate ports and generate secrets
    try:
        ports = get_next_available_ports(registry)
        secrets_dict = generate_secrets()
    except Exception as e:
        logger.error(f"Failed to allocate resources: {e}")
        shutil.rmtree(instance_path, ignore_errors=True)
        return

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
        "KONG_HTTPS_PORT": str(ports['kong_https']),
        "POSTGRES_PORT": str(ports['postgres_direct']),
        "POOLER_PROXY_PORT_TRANSACTION": str(ports['supavisor_pooler']),
        "STUDIO_PORT": str(ports['studio']),
        "PHX_HTTP_PORT": str(ports['analytics']),  # Add analytics port
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
        # If PHX_HTTP_PORT is not present in .env.example, append it
        if "PHX_HTTP_PORT" not in [l.strip().split('=')[0] for l in open(env_example_path) if l.strip() and not l.strip().startswith('#')]:
            f_final.write(f"PHX_HTTP_PORT={instance_values['PHX_HTTP_PORT']}\n")
    logger.info("Successfully created and secured .env file with dynamic ports.")

    # Get system information for connection details
    import socket
    hostname = socket.gethostname()
    try:
        pi_ip = subprocess.run(['hostname', '-I'], capture_output=True, text=True).stdout.strip().split()[0]
    except:
        pi_ip = "127.0.0.1"
    
    # Build comprehensive connection details
    connection_details = {
        "urls": {
            "localhost": {
                "studio": f"http://localhost:{ports['studio']}",
                "api": f"http://localhost:{ports['kong_http']}",
                "api_https": f"https://localhost:{ports['kong_https']}",
                "analytics": f"http://localhost:{ports['analytics']}"
            },
            "hostname": {
                "studio": f"http://{hostname}:{ports['studio']}",
                "api": f"http://{hostname}:{ports['kong_http']}",
                "api_https": f"https://{hostname}:{ports['kong_https']}",
                "analytics": f"http://{hostname}:{ports['analytics']}"
            },
            "pi_ip": {
                "studio": f"http://{pi_ip}:{ports['studio']}",
                "api": f"http://{pi_ip}:{ports['kong_http']}",
                "api_https": f"https://{pi_ip}:{ports['kong_https']}",
                "analytics": f"http://{pi_ip}:{ports['analytics']}"
            }
        },
        "database": {
            "connection_strings": {
                "localhost": f"postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD']}@localhost:{ports['postgres_direct']}/postgres",
                "hostname": f"postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD']}@{hostname}:{ports['postgres_direct']}/postgres",
                "pi_ip": f"postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD']}@{pi_ip}:{ports['postgres_direct']}/postgres"
            },
            "pooler_connection_strings": {
                "localhost": f"postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD']}@localhost:{ports['supavisor_pooler']}/postgres",
                "hostname": f"postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD']}@{hostname}:{ports['supavisor_pooler']}/postgres", 
                "pi_ip": f"postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD']}@{pi_ip}:{ports['supavisor_pooler']}/postgres"
            },
            "host": {
                "localhost": "localhost",
                "hostname": hostname,
                "pi_ip": pi_ip
            },
            "port": ports['postgres_direct'],
            "pooler_port": ports['supavisor_pooler'],
            "database": "postgres",
            "username": "postgres",
            "password": secrets_dict['POSTGRES_PASSWORD']
        },
        "auth": {
            "anon_key": secrets_dict['ANON_KEY'],
            "service_role_key": secrets_dict['SERVICE_ROLE_KEY'],
            "jwt_secret": secrets_dict['JWT_SECRET']
        },
        "dashboard": {
            "username": secrets_dict['DASHBOARD_USERNAME'],
            "password": secrets_dict['DASHBOARD_PASSWORD']
        },
        "system_info": {
            "hostname": hostname,
            "pi_ip": pi_ip,
            "project_name": project_name
        }
    }

    # Ensure all required port keys are present
    required_port_keys = ["kong_http", "kong_https", "postgres_direct", "supavisor_pooler", "studio", "analytics"]
    for key in required_port_keys:
        if key not in ports:
            logger.warning(f"Port key '{key}' missing in ports dict for instance '{name}'.")
            ports[key] = None
    
    logger.debug(f"Saving registry entry for instance '{name}': {{'id': {instance_id}, 'path': str(instance_path), 'ports': ports, 'connection_details': connection_details}}")
    registry[name] = {
        "id": instance_id, 
        "path": str(instance_path), 
        "ports": ports,
        "connection_details": connection_details
    }
    try:
        save_registry(registry)
        logger.info(f"Registry updated successfully for instance '{name}'.")
    except Exception as e:
        logger.error(f"Failed to update registry for instance '{name}': {e}")

    print(f"📥 Pulling Docker images for '{name}'...")
    if VERBOSE:
        print("    This may take several minutes for the first time")
    try:
        # Pull images first with progress display
        run_command(["docker", "compose", "--project-name", project_name, "pull"], 
                   cwd=str(instance_path), show_progress=VERBOSE)
        
        # Start the instance
        print(f"🚀 Starting Supabase services for '{name}'...")
        run_command(["docker", "compose", "--project-name", project_name, "up", "-d"], 
                   cwd=str(instance_path), show_progress=VERBOSE)
        
        # Wait for containers to start with progress feedback
        print("⏳ Waiting for services to become healthy...")
        import time
        time.sleep(3)  # Give containers a moment to start
        
        # Check container health with timeout
        max_wait = 60  # seconds
        wait_time = 0
        while wait_time < max_wait:
            result = run_command(
                ["docker", "compose", "--project-name", project_name, "ps", "--format", "json"],
                cwd=str(instance_path), capture=True, check=False
            )
            if result:
                services = [json.loads(line) for line in result.strip().split('\n') if line]
                healthy_services = [s for s in services if 'healthy' in s.get('Status', '')]
                running_services = [s for s in services if s.get('State') == 'running']
                
                if VERBOSE:
                    print(f"    Services running: {len(running_services)}/{len(services)}, healthy: {len(healthy_services)}")
                
                if len(running_services) >= len(services) * 0.8:  # 80% of services running
                    break
            
            time.sleep(5)
            wait_time += 5
            if wait_time % 15 == 0:  # Progress update every 15 seconds
                print(f"    Still waiting... ({wait_time}s elapsed)")
        
        if wait_time >= max_wait:
            print(f"⚠️  Services are taking longer than expected to start ({max_wait}s)")
            print("    This is often normal for first-time setup. Continuing...")
        
        # Verify containers are running
        result = run_command(
            ["docker", "compose", "--project-name", project_name, "ps", "--format", "json"],
            cwd=str(instance_path), capture=True, check=False
        )
        
        # Final status check
        result = run_command(
            ["docker", "compose", "--project-name", project_name, "ps", "--format", "json"],
            cwd=str(instance_path), capture=True, check=False
        )
        
        if result:
            services = [json.loads(line) for line in result.strip().split('\n') if line]
            running_services = [s for s in services if s.get('State') == 'running']
            healthy_services = [s for s in services if 'healthy' in s.get('Status', '')]
            total_services = len(services)
            
            print(f"✅ Services started: {len(running_services)}/{total_services} running, {len(healthy_services)} healthy")
            
            if VERBOSE and len(running_services) < total_services:
                print("⚠️  Some services may still be starting up. This is normal.")
                failing_services = [s for s in services if s.get('State') not in ['running', 'restarting']]
                if failing_services:
                    print(f"    Services not running: {[s.get('Service') for s in failing_services]}")
        else:
            print("✅ Instance created and started!")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create instance '{name}': Command failed")
        if VERBOSE:
            print(f"    Error: {e}")
            print(f"    Command: {' '.join(e.cmd) if hasattr(e, 'cmd') else 'Unknown'}")
        print(f"🔧 Configuration preserved at: {instance_path}")
        print(f"📋 Debug with: cd {instance_path} && docker compose --project-name {project_name} logs")
        return
    except Exception as e:
        print(f"❌ Unexpected error creating instance '{name}': {e}")
        if VERBOSE:
            import traceback
            print("    Full traceback:")
            traceback.print_exc()
        print(f"🔧 Configuration preserved at: {instance_path}")
        return

    # Display connection information
    print(f"\n✅ Instance '{name}' ready!")
    print(f"📊 Studio:      http://localhost:{ports['studio']} | http://{hostname}:{ports['studio']} | http://{pi_ip}:{ports['studio']}")
    print(f"🔌 API:         http://localhost:{ports['kong_http']} | http://{hostname}:{ports['kong_http']} | http://{pi_ip}:{ports['kong_http']}")
    print(f"🗄️  Database:    postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD'][:8]}...@localhost:{ports['postgres_direct']}/postgres")
    print(f"🎯 Pooler:      postgresql://postgres:{secrets_dict['POSTGRES_PASSWORD'][:8]}...@localhost:{ports['supavisor_pooler']}/postgres")
    print(f"📈 Analytics:   http://localhost:{ports['analytics']} | http://{hostname}:{ports['analytics']} | http://{pi_ip}:{ports['analytics']}")
    print(f"\n🔑 Keys & connections: View complete details with 'make list-details' or check instances.json")
    print(f"🔧 Manage:      make {name}-start|stop|logs|destroy")

def destroy_instance(name: str) -> None:
    registry = load_registry()
    if name not in registry:
        print(f"❌ Instance '{name}' not found")
        return

    instance_path = Path(registry[name]["path"])
    project_name = f"supabase-{name}"

    print(f"🗑️  Destroying instance '{name}'...")
    
    # Stop and remove containers/volumes
    try:
        run_command(
            ["docker", "compose", "--project-name", project_name, "down", "--volumes", "--remove-orphans"], 
            cwd=str(instance_path), check=False
        )
    except:
        pass  # Continue even if this fails
    
    # Remove directory (with permission handling)
    try:
        # First try regular removal
        shutil.rmtree(instance_path)
    except PermissionError:
        # If permission denied, try changing permissions first
        try:
            run_command(["chmod", "-R", "755", str(instance_path)], cwd=".", check=False)
            shutil.rmtree(instance_path)
        except:
            print(f"⚠️  Could not remove {instance_path}. You may need to run: sudo rm -rf {instance_path}")
    
    # Remove from registry
    del registry[name]
    save_registry(registry)
    print(f"✅ Instance '{name}' destroyed")

def update_connection_details(name: str) -> None:
    """Update connection details for an existing instance."""
    registry = load_registry()
    if name not in registry:
        print(f"❌ Instance '{name}' not found")
        return
    
    instance_path = Path(registry[name]["path"])
    env_path = instance_path / ".env"
    
    if not env_path.exists():
        print(f"❌ Environment file not found: {env_path}")
        return
    
    # Read secrets from .env file
    secrets_dict = {}
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                if key in ['POSTGRES_PASSWORD', 'JWT_SECRET', 'ANON_KEY', 'SERVICE_ROLE_KEY', 'DASHBOARD_USERNAME', 'DASHBOARD_PASSWORD']:
                    secrets_dict[key] = value
    
    # Get system information
    import socket
    hostname = socket.gethostname()
    try:
        pi_ip = subprocess.run(['hostname', '-I'], capture_output=True, text=True).stdout.strip().split()[0]
    except:
        pi_ip = "127.0.0.1"
    
    ports = registry[name]["ports"]
    project_name = f"supabase-{name}"
    
    # Build comprehensive connection details
    connection_details = {
        "urls": {
            "localhost": {
                "studio": f"http://localhost:{ports['studio']}",
                "api": f"http://localhost:{ports['kong_http']}",
                "api_https": f"https://localhost:{ports['kong_https']}",
                "analytics": f"http://localhost:{ports['analytics']}"
            },
            "hostname": {
                "studio": f"http://{hostname}:{ports['studio']}",
                "api": f"http://{hostname}:{ports['kong_http']}",
                "api_https": f"https://{hostname}:{ports['kong_https']}",
                "analytics": f"http://{hostname}:{ports['analytics']}"
            },
            "pi_ip": {
                "studio": f"http://{pi_ip}:{ports['studio']}",
                "api": f"http://{pi_ip}:{ports['kong_http']}",
                "api_https": f"https://{pi_ip}:{ports['kong_https']}",
                "analytics": f"http://{pi_ip}:{ports['analytics']}"
            }
        },
        "database": {
            "connection_strings": {
                "localhost": f"postgresql://postgres:{secrets_dict.get('POSTGRES_PASSWORD', 'unknown')}@localhost:{ports['postgres_direct']}/postgres",
                "hostname": f"postgresql://postgres:{secrets_dict.get('POSTGRES_PASSWORD', 'unknown')}@{hostname}:{ports['postgres_direct']}/postgres",
                "pi_ip": f"postgresql://postgres:{secrets_dict.get('POSTGRES_PASSWORD', 'unknown')}@{pi_ip}:{ports['postgres_direct']}/postgres"
            },
            "pooler_connection_strings": {
                "localhost": f"postgresql://postgres:{secrets_dict.get('POSTGRES_PASSWORD', 'unknown')}@localhost:{ports['supavisor_pooler']}/postgres",
                "hostname": f"postgresql://postgres:{secrets_dict.get('POSTGRES_PASSWORD', 'unknown')}@{hostname}:{ports['supavisor_pooler']}/postgres", 
                "pi_ip": f"postgresql://postgres:{secrets_dict.get('POSTGRES_PASSWORD', 'unknown')}@{pi_ip}:{ports['supavisor_pooler']}/postgres"
            },
            "host": {
                "localhost": "localhost",
                "hostname": hostname,
                "pi_ip": pi_ip
            },
            "port": ports['postgres_direct'],
            "pooler_port": ports['supavisor_pooler'],
            "database": "postgres",
            "username": "postgres",
            "password": secrets_dict.get('POSTGRES_PASSWORD', 'unknown')
        },
        "auth": {
            "anon_key": secrets_dict.get('ANON_KEY', 'unknown'),
            "service_role_key": secrets_dict.get('SERVICE_ROLE_KEY', 'unknown'),
            "jwt_secret": secrets_dict.get('JWT_SECRET', 'unknown')
        },
        "dashboard": {
            "username": secrets_dict.get('DASHBOARD_USERNAME', 'unknown'),
            "password": secrets_dict.get('DASHBOARD_PASSWORD', 'unknown')
        },
        "system_info": {
            "hostname": hostname,
            "pi_ip": pi_ip,
            "project_name": project_name
        }
    }
    
    # Update registry
    registry[name]["connection_details"] = connection_details
    save_registry(registry)
    print(f"✅ Updated connection details for instance '{name}'")

def show_connection_details(name: str = None) -> None:
    """Display detailed connection information for one or all instances."""
    registry = load_registry()
    if not registry:
        print("No instances found.")
        return
    
    instances_to_show = [name] if name and name in registry else list(registry.keys())
    
    if name and name not in registry:
        print(f"❌ Instance '{name}' not found")
        return
    
    for instance_name in sorted(instances_to_show):
        data = registry[instance_name]
        print(f"\n{'='*80}")
        print(f"🚀 INSTANCE: {instance_name} (ID: {data['id']})")
        print(f"{'='*80}")
        
        # Check if connection_details exists
        if "connection_details" not in data:
            print("⚠️  Connection details not available. Updating...")
            update_connection_details(instance_name)
            registry = load_registry()  # Reload after update
            data = registry[instance_name]
        
        if "connection_details" not in data:
            print("❌ Failed to generate connection details")
            continue
            
        conn = data["connection_details"]
        
        print(f"\n📊 STUDIO URLs:")
        print(f"   Localhost: {conn['urls']['localhost']['studio']}")
        print(f"   Hostname:  {conn['urls']['hostname']['studio']}")
        print(f"   Pi IP:     {conn['urls']['pi_ip']['studio']}")
        
        print(f"\n🔌 API URLs:")
        print(f"   HTTP Localhost: {conn['urls']['localhost']['api']}")
        print(f"   HTTP Hostname:  {conn['urls']['hostname']['api']}")
        print(f"   HTTP Pi IP:     {conn['urls']['pi_ip']['api']}")
        print(f"   HTTPS Localhost: {conn['urls']['localhost']['api_https']}")
        print(f"   HTTPS Hostname:  {conn['urls']['hostname']['api_https']}")
        print(f"   HTTPS Pi IP:     {conn['urls']['pi_ip']['api_https']}")
        
        print(f"\n📈 ANALYTICS URLs:")
        print(f"   Localhost: {conn['urls']['localhost']['analytics']}")
        print(f"   Hostname:  {conn['urls']['hostname']['analytics']}")
        print(f"   Pi IP:     {conn['urls']['pi_ip']['analytics']}")
        
        print(f"\n🗄️  DATABASE CONNECTION STRINGS:")
        print(f"   Direct - Localhost: {conn['database']['connection_strings']['localhost']}")
        print(f"   Direct - Hostname:  {conn['database']['connection_strings']['hostname']}")
        print(f"   Direct - Pi IP:     {conn['database']['connection_strings']['pi_ip']}")
        
        print(f"\n🎯 POOLER CONNECTION STRINGS:")
        print(f"   Pooler - Localhost: {conn['database']['pooler_connection_strings']['localhost']}")
        print(f"   Pooler - Hostname:  {conn['database']['pooler_connection_strings']['hostname']}")
        print(f"   Pooler - Pi IP:     {conn['database']['pooler_connection_strings']['pi_ip']}")
        
        print(f"\n🔐 AUTHENTICATION KEYS:")
        print(f"   Anon Key: {conn['auth']['anon_key']}")
        print(f"   Service Role Key: {conn['auth']['service_role_key']}")
        print(f"   JWT Secret: {conn['auth']['jwt_secret'][:32]}...")
        
        print(f"\n👤 DASHBOARD CREDENTIALS:")
        print(f"   Username: {conn['dashboard']['username']}")
        print(f"   Password: {conn['dashboard']['password']}")
        
        print(f"\n🖥️  SYSTEM INFO:")
        print(f"   Hostname: {conn['system_info']['hostname']}")
        print(f"   Pi IP: {conn['system_info']['pi_ip']}")
        print(f"   Project Name: {conn['system_info']['project_name']}")
        print(f"   Config Path: {data['path']}")

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
    
    print(f"\n💡 Use 'python setup.py details [instance-name]' for complete connection information")

def main():
    INSTANCES_ROOT_DIR.mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(
        description="Manage multiple, concurrent Supabase instances.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create and start a new Supabase instance.")
    create_parser.add_argument("name", help="A unique name for the new instance (e.g., 'my-project').")
    create_parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed progress and debug information.")

    destroy_parser = subparsers.add_parser("destroy", help="Stop and delete a Supabase instance and its data.")
    destroy_parser.add_argument("name", help="The name of the instance to destroy.")

    subparsers.add_parser("list", help="List all managed Supabase instances and their status.")
    
    details_parser = subparsers.add_parser("details", help="Show detailed connection information for instances.")
    details_parser.add_argument("name", nargs='?', help="(Optional) Specific instance name to show details for. Shows all if omitted.")
    
    update_details_parser = subparsers.add_parser("update-details", help="Update connection details for an existing instance.")
    update_details_parser.add_argument("name", help="Instance name to update connection details for.")
    
    subparsers.add_parser("setup", help="One-time setup: clone template and validate environment.")

    pass_through_cmds = ["start", "stop", "restart", "logs", "ps"]
    for cmd in pass_through_cmds:
        cmd_parser = subparsers.add_parser(cmd, help=f"Run 'docker compose {cmd}' on an instance's services.")
        cmd_parser.add_argument("name", help="The name of the instance to target.")
        cmd_parser.add_argument('services', nargs='*', help='(Optional) The service(s) to target.')

    # Add 'recreate' as a special command for 'up -d --force-recreate'
    recreate_parser = subparsers.add_parser("recreate", help="Recreate all containers for an instance (docker compose up -d --force-recreate)")
    recreate_parser.add_argument("name", help="The name of the instance to target.")
    recreate_parser.add_argument('services', nargs='*', help='(Optional) The service(s) to target.')

    args = parser.parse_args()

    if args.command == "create":
        if hasattr(args, 'verbose') and args.verbose:
            setup_logging(verbose=True)
        create_instance(args.name)
    elif args.command == "setup":
        setup_command()
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
    elif args.command == "details":
        show_connection_details(args.name)
    elif args.command == "update-details":
        update_connection_details(args.name)
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
    elif args.command == "recreate":
        registry = load_registry()
        if args.name not in registry:
            logger.error(f"Instance '{args.name}' not found.")
            return
        instance_path = Path(registry[args.name]["path"])
        project_name = f"supabase-{args.name}"
        try:
            cmd = ["docker", "compose", "--project-name", project_name, "up", "-d", "--force-recreate"] + args.services
            subprocess.run(cmd, cwd=str(instance_path))
        except Exception as e:
            logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
