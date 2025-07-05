import os
import shutil
import subprocess
import json
import argparse
from pathlib import Path
import yaml
from datetime import datetime
import secrets
import base64
import time

def run_command(cmd, cwd=None):
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def generate_secrets():
    """Generate secure secrets for Supabase"""
    # Generate JWT secret (must be at least 32 characters)
    jwt_secret = secrets.token_urlsafe(32)
    
    # Create JWT tokens (using demo format for simplicity)
    anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
    service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
    
    # Generate other secrets
    dashboard_password = secrets.token_urlsafe(16)
    secret_key_base = secrets.token_urlsafe(64)
    vault_enc_key = secrets.token_urlsafe(32)
    postgres_password = secrets.token_urlsafe(24)
    
    return {
        "jwt_secret": jwt_secret,
        "anon_key": anon_key,
        "service_role_key": service_key,
        "dashboard_password": dashboard_password,
        "secret_key_base": secret_key_base,
        "vault_enc_key": vault_enc_key,
        "postgres_password": postgres_password
    }

class SupabaseInstanceManager:
    def __init__(self, base_folder=None):
        self.base_folder = base_folder or os.path.expanduser("~/projects/database")
        self.registry_file = os.path.join(self.base_folder, "instance_registry.json")
        self.docker_client = None
        
        try:
            import docker
            self.docker_client = docker.from_env()
        except Exception as e:
            print(f"Warning: Could not connect to Docker: {e}")
        
        # Ensure base folder exists
        os.makedirs(self.base_folder, exist_ok=True)
        
        # Load or create registry
        self.registry = self.load_registry()
    
    def load_registry(self):
        """Load the instance registry from file"""
        if os.path.exists(self.registry_file):
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        return {"instances": {}, "networks": {}, "last_updated": None}
    
    def save_registry(self):
        """Save the instance registry to file"""
        self.registry["last_updated"] = datetime.now().isoformat()
        with open(self.registry_file, 'w') as f:
            json.dump(self.registry, f, indent=2)
    
    def get_docker_network_name(self, instance_id):
        """Get the Docker network name for an instance"""
        return f"supabase-instance{instance_id}-network"
    
    def create_docker_network(self, instance_id):
        """Create a Docker network for the instance"""
        network_name = self.get_docker_network_name(instance_id)
        if self.docker_client:
            try:
                # Check if network already exists
                networks = self.docker_client.networks.list(names=[network_name])
                if not networks:
                    network = self.docker_client.networks.create(
                        network_name,
                        driver="bridge",
                        options={"com.docker.network.bridge.name": f"supabase-br{instance_id}"}
                    )
                    print(f"Created Docker network: {network_name}")
                    return network_name
                else:
                    print(f"Docker network {network_name} already exists")
                    return network_name
            except Exception as e:
                print(f"Warning: Could not create Docker network: {e}")
        return network_name
    
    def get_instance_info(self, instance_id):
        """Get comprehensive information about an instance"""
        # Use single port increments for each instance
        # Instance 1 should use original ports + 1, Instance 2 should use original ports + 2, etc.
        port_offset = instance_id
        kong_http_port = 8000 + port_offset      # 8001, 8002, 8003, etc.
        postgres_port = 5432 + port_offset       # 5433, 5434, 5435, etc.
        
        return {
            'instance_id': instance_id,
            'kong_http_port': kong_http_port,
            'postgres_port': postgres_port,
            'database_name': f'postgres_instance{instance_id}',
            'supabase_url': f'http://localhost:{kong_http_port}',
            'postgres_url': f'postgresql://postgres:POSTGRES_PASSWORD@localhost:{postgres_port}/postgres_instance{instance_id}',
            'docker_network': self.get_docker_network_name(instance_id),
            'ports': {
                'kong_http': kong_http_port,           # 8001, 8002, 8003, etc.
                'kong_https': 8443 + port_offset,     # 8444, 8445, 8446, etc.
                'postgres': postgres_port,             # 5433, 5434, 5435, etc.
                'studio': 3000 + port_offset,          # 3001, 3002, 3003, etc.
                'analytics': 4000 + port_offset,       # 4001, 4002, 4003, etc.
                'pooler': 6543 + port_offset,          # 6544, 6545, 6546, etc.
            }
        }
    
    def register_instance(self, instance_id, name=None, description=None, tags=None, secrets=None):
        """Register an instance in the registry"""
        info = self.get_instance_info(instance_id)
        instance_key = f"instance{instance_id}"
        
        # Create folder name based on custom name or default
        if name:
            # Sanitize the name for folder usage
            folder_name = name.replace(" ", "-").replace("/", "-").replace("\\", "-")
            folder_name = "".join(c for c in folder_name if c.isalnum() or c in "-_")
            folder_name = f"{folder_name}-instance{instance_id}"
        else:
            folder_name = instance_key
        
        self.registry["instances"][instance_key] = {
            **info,
            'name': name or f"Instance {instance_id}",
            'description': description or f"Supabase instance {instance_id}",
            'tags': tags or [],
            'created_at': datetime.now().isoformat(),
            'status': 'configured',
            'path': os.path.join(self.base_folder, folder_name),
            'folder_name': folder_name,
            'secrets': secrets or {}
        }
        
        # Register network
        network_name = self.get_docker_network_name(instance_id)
        self.registry["networks"][network_name] = {
            'instance_id': instance_id,
            'name': network_name,
            'created_at': datetime.now().isoformat()
        }
        
        self.save_registry()
        return self.registry["instances"][instance_key]
    
    def update_instance_name(self, instance_id, name, description=None):
        """Update the name and description of an instance"""
        instance_key = f"instance{instance_id}"
        if instance_key in self.registry["instances"]:
            self.registry["instances"][instance_key]["name"] = name
            if description:
                self.registry["instances"][instance_key]["description"] = description
            self.registry["instances"][instance_key]["updated_at"] = datetime.now().isoformat()
            self.save_registry()
            return True
        return False
    
    def delete_instance(self, instance_id, remove_files=False):
        """Delete an instance from the registry and optionally remove files"""
        instance_key = f"instance{instance_id}"
        
        if instance_key not in self.registry["instances"]:
            return False, f"Instance {instance_id} not found"
        
        instance = self.registry["instances"][instance_key]
        instance_path = instance.get("path", "")
        network_name = self.get_docker_network_name(instance_id)
        
        # Run docker compose down to properly stop and remove containers
        if instance_path and os.path.exists(instance_path):
            compose_path = os.path.join(instance_path, "supabase", "docker")
            if os.path.exists(compose_path):
                try:
                    print(f"Running docker compose down for instance {instance_id}...")
                    original_cwd = os.getcwd()
                    os.chdir(compose_path)
                    run_command(["docker", "compose", "down", "-v", "--remove-orphans"])
                    os.chdir(original_cwd)
                    print(f"✅ Docker compose down completed for instance {instance_id}")
                except Exception as e:
                    print(f"Warning: Error running docker compose down: {e}")
        
        # Stop containers if running (fallback)
        if self.docker_client:
            try:
                containers = self.docker_client.containers.list(filters={"network": network_name})
                for container in containers:
                    print(f"Stopping container: {container.name}")
                    container.stop()
                    container.remove()
                
                # Remove Docker network
                try:
                    networks = self.docker_client.networks.list(names=[network_name])
                    for network in networks:
                        print(f"Removing Docker network: {network_name}")
                        network.remove()
                except Exception as e:
                    print(f"Warning: Could not remove Docker network {network_name}: {e}")
                        
            except Exception as e:
                print(f"Warning: Error stopping containers: {e}")
        
        # Remove from registry
        del self.registry["instances"][instance_key]
        if network_name in self.registry["networks"]:
            del self.registry["networks"][network_name]
        
        # Remove files if requested
        if remove_files and instance_path and os.path.exists(instance_path):
            try:
                shutil.rmtree(instance_path)
                print(f"Removed instance files: {instance_path}")
            except Exception as e:
                print(f"Warning: Could not remove files {instance_path}: {e}")
        
        self.save_registry()
        return True, f"Instance {instance_id} deleted successfully"
    
    def get_instance_status(self, instance_id):
        """Check if an instance is running"""
        if not self.docker_client:
            return "unknown"
        
        try:
            # Look for containers with the instance network
            network_name = self.get_docker_network_name(instance_id)
            containers = self.docker_client.containers.list(
                filters={"network": network_name}
            )
            if containers:
                return "running"
            else:
                # Check if containers exist but are stopped
                all_containers = self.docker_client.containers.list(all=True)
                instance_containers = [c for c in all_containers if network_name in [n.name for n in c.attrs.get('NetworkSettings', {}).get('Networks', {}).keys()]]
                return "stopped" if instance_containers else "configured"
        except Exception as e:
            print(f"Error checking status: {e}")
            return "unknown"
    
    def list_instances(self):
        """List all registered instances with their status"""
        instances = []
        for key, instance in self.registry["instances"].items():
            instance_id = instance["instance_id"]
            status = self.get_instance_status(instance_id)
            instances.append({
                **instance,
                "current_status": status
            })
        return instances
    
    def export_connection_info(self, instance_id=None, format="json"):
        """Export connection information for external tools"""
        if instance_id:
            # Export single instance
            instance_key = f"instance{instance_id}"
            if instance_key not in self.registry["instances"]:
                return None
            
            instance = self.registry["instances"][instance_key]
            secrets = instance.get("secrets", {})
            
            # Update postgres URL with actual password
            postgres_url = instance["postgres_url"].replace("POSTGRES_PASSWORD", secrets.get("postgres_password", "your-postgres-password"))
            
            connection_info = {
                "name": instance["name"],
                "instance_id": instance_id,
                "folder_name": instance.get("folder_name", f"instance{instance_id}"),
                "database_url": postgres_url,
                "supabase_url": instance["supabase_url"],
                "supabase_anon_key": secrets.get("anon_key", ""),
                "supabase_service_key": secrets.get("service_role_key", ""),
                "docker_network": instance["docker_network"],
                "ports": instance["ports"]
            }
        else:
            # Export all instances
            connection_info = {}
            for key, instance in self.registry["instances"].items():
                instance_id = instance["instance_id"]
                secrets = instance.get("secrets", {})
                postgres_url = instance["postgres_url"].replace("POSTGRES_PASSWORD", secrets.get("postgres_password", "your-postgres-password"))
                
                connection_info[key] = {
                    "name": instance["name"],
                    "instance_id": instance_id,
                    "folder_name": instance.get("folder_name", f"instance{instance_id}"),
                    "database_url": postgres_url,
                    "supabase_url": instance["supabase_url"],
                    "docker_network": instance["docker_network"],
                    "ports": instance["ports"]
                }
        
        if format == "yaml":
            return yaml.dump(connection_info, default_flow_style=False)
        elif format == "env":
            # Environment variable format
            env_vars = []
            if instance_id:
                prefix = f"SUPABASE_INSTANCE_{instance_id}"
                env_vars.append(f"{prefix}_NAME={connection_info['name']}")
                env_vars.append(f"{prefix}_DATABASE_URL={connection_info['database_url']}")
                env_vars.append(f"{prefix}_SUPABASE_URL={connection_info['supabase_url']}")
                env_vars.append(f"{prefix}_SUPABASE_ANON_KEY={connection_info['supabase_anon_key']}")
                env_vars.append(f"{prefix}_SUPABASE_SERVICE_KEY={connection_info['supabase_service_key']}")
                env_vars.append(f"{prefix}_DOCKER_NETWORK={connection_info['docker_network']}")
                env_vars.append(f"{prefix}_POSTGRES_PORT={connection_info['ports']['postgres']}")
            else:
                for key, info in connection_info.items():
                    prefix = f"SUPABASE_{key.upper()}"
                    env_vars.append(f"{prefix}_NAME={info['name']}")
                    env_vars.append(f"{prefix}_DATABASE_URL={info['database_url']}")
                    env_vars.append(f"{prefix}_SUPABASE_URL={info['supabase_url']}")
                    env_vars.append(f"{prefix}_DOCKER_NETWORK={info['docker_network']}")
                    env_vars.append(f"{prefix}_POSTGRES_PORT={info['ports']['postgres']}")
            return "\n".join(env_vars)
        else:
            return json.dumps(connection_info, indent=2)
    
    def generate_external_service_template(self, instance_id, service_name):
        """Generate a docker-compose template for external services to connect to Supabase"""
        instance_info = self.get_instance_info(instance_id)
        network_name = self.get_docker_network_name(instance_id)
        
        # Get secrets if available
        instance_key = f"instance{instance_id}"
        secrets = {}
        if instance_key in self.registry["instances"]:
            secrets = self.registry["instances"][instance_key].get("secrets", {})
        
        postgres_url = instance_info["postgres_url"].replace("POSTGRES_PASSWORD", secrets.get("postgres_password", "your-postgres-password"))
        
        template = {
            "version": "3.8",
            "services": {
                service_name: {
                    "image": "your-service-image:latest",
                    "environment": [
                        f"DATABASE_URL={postgres_url}",
                        f"SUPABASE_URL={instance_info['supabase_url']}",
                        f"SUPABASE_ANON_KEY={secrets.get('anon_key', '')}",
                        f"SUPABASE_SERVICE_KEY={secrets.get('service_role_key', '')}"
                    ],
                    "networks": [network_name],
                    "depends_on": ["supabase-db"]
                }
            },
            "networks": {
                network_name: {
                    "external": True,
                    "name": network_name
                }
            }
        }
        
        return yaml.dump(template, default_flow_style=False)

def clone_supabase_repo(target_dir="supabase"):
    if not os.path.exists(target_dir):
        print(f"Cloning the Supabase repository into {target_dir}...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/supabase/supabase.git", target_dir
        ])
        os.chdir(target_dir)
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "docker"])
        run_command(["git", "checkout", "master"])
        os.chdir("..")
    else:
        print(f"Supabase repository already exists at {target_dir}, updating...")
        os.chdir(target_dir)
        run_command(["git", "pull"])
        os.chdir("..")

def prepare_supabase_env(manager, root_env_path, target_dir="supabase", instance_id=1):
    env_path = os.path.join(target_dir, "docker", ".env")
    compose_path = os.path.join(target_dir, "docker", "docker-compose.yml")
    
    print(f"Customizing {root_env_path} to {env_path} for instance {instance_id}...")
    
    # Read the template file
    with open(root_env_path, 'r') as f:
        env_content = f.read()
    
    # Generate secrets for this instance
    secrets = generate_secrets()
    
    # Get instance info from manager
    instance_info = manager.get_instance_info(instance_id)
    
    # Create Docker network
    network_name = manager.create_docker_network(instance_id)
    
    # Replace critical configuration values based on the .env.example structure
    replacements = {
        # Dashboard credentials
        'DASHBOARD_PASSWORD=this_password_is_insecure_and_should_be_updated':
            f'DASHBOARD_PASSWORD={secrets["dashboard_password"]}',
        
        # Core secrets
        'SECRET_KEY_BASE=UpNVntn3cDxHJpq99YMc1T1AQgQpc8kfYTuRgBiYa15BLrx8etQoXz3gZv1/u2oq':
            f'SECRET_KEY_BASE={secrets["secret_key_base"]}',
        
        'VAULT_ENC_KEY=your-encryption-key-32-chars-min':
            f'VAULT_ENC_KEY={secrets["vault_enc_key"]}',
        
        # Database configuration
        'POSTGRES_DB=postgres': f'POSTGRES_DB={instance_info["database_name"]}',
        'POSTGRES_PORT=5432': f'POSTGRES_PORT={instance_info["postgres_port"]}',
        'POSTGRES_PASSWORD=your-super-secret-and-long-postgres-password': f'POSTGRES_PASSWORD={secrets["postgres_password"]}',
        
        # External facing ports - Kong is the main API gateway
        'KONG_HTTP_PORT=8000': f'KONG_HTTP_PORT={instance_info["ports"]["kong_http"]}',
        'KONG_HTTPS_PORT=8443': f'KONG_HTTPS_PORT={instance_info["ports"]["kong_https"]}',
        
        # External API URL - this is what external services will use
        'API_EXTERNAL_URL=http://localhost:8000': f'API_EXTERNAL_URL={instance_info["supabase_url"]}',
        
        # Site URL for redirects
        'SITE_URL=http://localhost:3000': f'SITE_URL={instance_info["supabase_url"]}',
        
        # Studio port
        'STUDIO_PORT=3000': f'STUDIO_PORT={instance_info["ports"]["studio"]}',
        
        # Pooler port
        'POOLER_PROXY_PORT_TRANSACTION=6543': f'POOLER_PROXY_PORT_TRANSACTION={instance_info["ports"]["pooler"]}',
        
        # JWT keys
        'ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE':
            f'ANON_KEY={secrets["anon_key"]}',
        
        'SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwKICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q':
            f'SERVICE_ROLE_KEY={secrets["service_role_key"]}',
            
        # JWT secret
        'JWT_SECRET=your-super-secret-jwt-token-with-at-least-32-characters-long': f'JWT_SECRET={secrets["jwt_secret"]}',
    }
    
    # Apply replacements
    for old_value, new_value in replacements.items():
        if old_value in env_content:
            env_content = env_content.replace(old_value, new_value)
    
    # Add instance-specific configuration at the end
    env_content += f'\n\n####################\n'
    env_content += f'# Instance {instance_id} Configuration\n'
    env_content += f'####################\n'
    env_content += f'INSTANCE_ID={instance_id}\n'
    env_content += f'DOCKER_NETWORK={network_name}\n'
    env_content += f'INSTANCE_NAME=instance{instance_id}\n'
    env_content += f'ANON_KEY={secrets["anon_key"]}\n'
    env_content += f'SERVICE_ROLE_KEY={secrets["service_role_key"]}\n'
    env_content += f'POSTGRES_PASSWORD={secrets["postgres_password"]}\n'
    env_content += f'\n# External connection information\n'
    env_content += f'# Use these values to connect from external services:\n'
    env_content += f'# DATABASE_URL=postgresql://postgres:{secrets["postgres_password"]}@localhost:{instance_info["postgres_port"]}/{instance_info["database_name"]}\n'
    env_content += f'# SUPABASE_URL={instance_info["supabase_url"]}\n'
    env_content += f'# SUPABASE_ANON_KEY={secrets["anon_key"]}\n'
    env_content += f'# SUPABASE_SERVICE_KEY={secrets["service_role_key"]}\n'
    
    # Write the customized content
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    # Customize docker-compose.yml for unique container names
    customize_docker_compose(compose_path, instance_id, network_name)
    
    # Update instance info with generated secrets
    instance_info['secrets'] = secrets
    
    print(f"✅ Instance {instance_id} configured successfully!")
    print(f"📦 Database: {instance_info['database_name']}")
    print(f"🔌 PostgreSQL Port: {instance_info['postgres_port']}")
    print(f"🌐 Supabase URL: {instance_info['supabase_url']}")
    print(f"🐳 Docker Network: {network_name}")
    print(f"🔐 Dashboard Password: {secrets['dashboard_password']}")
    
    return instance_info

def customize_docker_compose(compose_path, instance_id, network_name):
    """Customize docker-compose.yml file to make container names unique per instance"""
    print(f"Customizing docker-compose.yml for instance {instance_id}...")
    
    # Read the docker-compose.yml file
    with open(compose_path, 'r') as f:
        compose_content = f.read()
    
    # Update the compose project name to be unique per instance
    compose_content = compose_content.replace(
        'name: supabase',
        f'name: supabase-instance{instance_id}'
    )
    
    # Define container name replacements for unique naming
    container_replacements = {
        'container_name: supabase-studio': f'container_name: supabase-instance{instance_id}-studio',
        'container_name: supabase-kong': f'container_name: supabase-instance{instance_id}-kong',
        'container_name: supabase-auth': f'container_name: supabase-instance{instance_id}-auth',
        'container_name: supabase-rest': f'container_name: supabase-instance{instance_id}-rest',
        'container_name: realtime-dev.supabase-realtime': f'container_name: supabase-instance{instance_id}-realtime',
        'container_name: supabase-storage': f'container_name: supabase-instance{instance_id}-storage',
        'container_name: supabase-imgproxy': f'container_name: supabase-instance{instance_id}-imgproxy',
        'container_name: supabase-meta': f'container_name: supabase-instance{instance_id}-meta',
        'container_name: supabase-edge-functions': f'container_name: supabase-instance{instance_id}-edge-functions',
        'container_name: supabase-analytics': f'container_name: supabase-instance{instance_id}-analytics',
        'container_name: supabase-db': f'container_name: supabase-instance{instance_id}-db',
        'container_name: supabase-vector': f'container_name: supabase-instance{instance_id}-vector',
        'container_name: supabase-pooler': f'container_name: supabase-instance{instance_id}-pooler',
    }
    
    # Apply container name replacements
    for old_name, new_name in container_replacements.items():
        compose_content = compose_content.replace(old_name, new_name)
    
    # Update networks section if it exists, otherwise add it
    if 'networks:' in compose_content:
        # Find the networks section and add our custom network
        networks_section = f"""
networks:
  default:
    name: {network_name}
    external: true
"""
        # Replace the existing networks section
        import re
        compose_content = re.sub(r'\nnetworks:.*?(?=\n\S|\Z)', networks_section, compose_content, flags=re.DOTALL)
    else:
        # Add networks section at the end
        compose_content += f"""
networks:
  default:
    name: {network_name}
    external: true
"""
    
    # Write the customized docker-compose.yml
    with open(compose_path, 'w') as f:
        f.write(compose_content)
    
    print(f"✅ Docker Compose customized for instance {instance_id}")

def setup_instance(manager, instance_id, name=None, description=None, tags=None):
    """Set up a single Supabase instance"""
    base_folder = manager.base_folder
    
    # Create folder name based on custom name or default
    if name:
        # Sanitize the name for folder usage
        folder_name = name.replace(" ", "-").replace("/", "-").replace("\\", "-")
        folder_name = "".join(c for c in folder_name if c.isalnum() or c in "-_")
        folder_name = f"{folder_name}-instance{instance_id}"
    else:
        folder_name = f"instance{instance_id}"
    
    instance_dir = os.path.join(base_folder, folder_name)
    os.makedirs(instance_dir, exist_ok=True)
    
    original_cwd = os.getcwd()
    try:
        os.chdir(instance_dir)
        clone_supabase_repo(target_dir="supabase")
        
        env_template = os.path.join("supabase", "docker", ".env.example")
        instance_info = prepare_supabase_env(manager, env_template, "supabase", instance_id)
        
        # Register the instance
        manager.register_instance(instance_id, name=name, description=description, tags=tags, secrets=instance_info.get('secrets'))
        
        # Get the actual postgres connection string with password
        secrets = instance_info.get('secrets', {})
        postgres_password = secrets.get('postgres_password', 'your-postgres-password')
        postgres_connection_string = f"postgresql://postgres:{postgres_password}@localhost:{instance_info['postgres_port']}/{instance_info['database_name']}"
        
        print(f"Instance {instance_id} set up at {instance_dir}/supabase")
        print(f"📁 Folder: {folder_name}")
        print(f"🐳 Network: {instance_info['docker_network']}")
        print(f"🌐 Supabase URL: {instance_info['supabase_url']}")
        print(f"🔌 PostgreSQL Port: {instance_info['postgres_port']}")
        print(f"🗄️  PostgreSQL Connection String: {postgres_connection_string}")
        
        return instance_info
    finally:
        os.chdir(original_cwd)

def main():
    parser = argparse.ArgumentParser(description="Supabase Instance Manager")
    parser.add_argument("--base-folder", default=os.path.expanduser("~/projects/database"), help="Base folder for instances")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up new instances")
    setup_parser.add_argument("--instances", type=int, nargs="+", default=[1, 2, 3, 4, 5], help="Instance IDs to set up")
    setup_parser.add_argument("--name", help="Name for the instance (only works with single instance)")
    setup_parser.add_argument("--description", help="Description for the instance")
    setup_parser.add_argument("--tags", nargs="+", help="Tags for the instance")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all instances")
    list_parser.add_argument("--format", choices=["table", "json", "yaml"], default="table", help="Output format")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Get connection info for instances")
    info_parser.add_argument("--instance", type=int, help="Instance ID (if not specified, shows all)")
    info_parser.add_argument("--format", choices=["json", "yaml", "env"], default="json", help="Output format")
    info_parser.add_argument("--output", help="Output file (if not specified, prints to stdout)")
    
    # Update command
    update_parser = subparsers.add_parser("update", help="Update instance metadata")
    update_parser.add_argument("instance", type=int, help="Instance ID")
    update_parser.add_argument("--name", required=True, help="New name for the instance")
    update_parser.add_argument("--description", help="New description for the instance")
    
    # Template command
    template_parser = subparsers.add_parser("template", help="Generate docker-compose template for external services")
    template_parser.add_argument("instance", type=int, help="Instance ID")
    template_parser.add_argument("service_name", help="Name of the external service")
    template_parser.add_argument("--output", help="Output file (if not specified, prints to stdout)")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check instance status")
    status_parser.add_argument("--instance", type=int, help="Instance ID (if not specified, shows all)")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an instance")
    delete_parser.add_argument("instance", type=int, help="Instance ID")
    delete_parser.add_argument("--remove-files", action="store_true", help="Remove instance files from disk")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = SupabaseInstanceManager(args.base_folder)
    
    if args.command == "setup":
        if len(args.instances) == 1 and args.name:
            setup_instance(manager, args.instances[0], name=args.name, description=args.description, tags=args.tags)
        else:
            for i in args.instances:
                setup_instance(manager, i, description=args.description, tags=args.tags)
    
    elif args.command == "list":
        instances = manager.list_instances()
        if args.format == "table":
            print(f"{'ID':<4} {'Name':<20} {'Folder':<25} {'Status':<12} {'Supabase URL':<30} {'PostgreSQL Port':<6}")
            print("-" * 105)
            for instance in instances:
                folder_name = instance.get('folder_name', f"instance{instance['instance_id']}")
                print(f"{instance['instance_id']:<4} {instance['name']:<20} {folder_name:<25} {instance['current_status']:<12} {instance['supabase_url']:<30} {instance['postgres_port']:<6}")
        elif args.format == "json":
            print(json.dumps(instances, indent=2))
        elif args.format == "yaml":
            print(yaml.dump(instances, default_flow_style=False))
    
    elif args.command == "info":
        info = manager.export_connection_info(args.instance, args.format)
        if info and args.output:
            with open(args.output, 'w') as f:
                f.write(info)
            print(f"Connection info saved to {args.output}")
        elif info:
            print(info)
        else:
            print("No connection info available")
    
    elif args.command == "update":
        if manager.update_instance_name(args.instance, args.name, args.description):
            print(f"Instance {args.instance} updated successfully")
        else:
            print(f"Instance {args.instance} not found")
    
    elif args.command == "template":
        template = manager.generate_external_service_template(args.instance, args.service_name)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(template)
            print(f"Template saved to {args.output}")
        else:
            print(template)
    
    elif args.command == "status":
        if args.instance:
            status = manager.get_instance_status(args.instance)
            print(f"Instance {args.instance}: {status}")
        else:
            instances = manager.list_instances()
            for instance in instances:
                print(f"Instance {instance['instance_id']}: {instance['current_status']}")
    
    elif args.command == "delete":
        success, message = manager.delete_instance(args.instance, args.remove_files)
        print(message)

if __name__ == "__main__":
    main()