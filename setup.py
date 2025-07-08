#!/usr/bin/env python3
"""
Supabase Instance Manager

A comprehensive tool for managing multiple Supabase instances with Docker.
This script handles the creation, configuration, and management of isolated
Supabase environments with proper token generation and unique networking.

Author: vanderwt
License: MIT
"""

import os
import re
import shutil
import subprocess
import json
import argparse
import logging
from pathlib import Path
import yaml
from datetime import datetime
import secrets
import base64
import time
from typing import Dict, List, Optional, Tuple, Any
import jwt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def run_command(cmd: List[str], cwd: Optional[str] = None, capture_output: bool = False) -> subprocess.CompletedProcess:
    """
    Execute a shell command with proper error handling.
    
    Args:
        cmd: Command and arguments as a list
        cwd: Working directory for the command
        capture_output: Whether to capture stdout/stderr
        
    Returns:
        CompletedProcess object
        
    Raises:
        subprocess.CalledProcessError: If command fails
    """
    logger.debug(f"Running command: {' '.join(cmd)} in {cwd or 'current directory'}")
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            check=True, 
            capture_output=capture_output,
            text=True if capture_output else None
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}")
        logger.error(f"Error: {e}")
        if capture_output and e.stderr:
            logger.error(f"Stderr: {e.stderr}")
        raise


def generate_secrets() -> Dict[str, str]:
    """
    Generate secure secrets for Supabase with proper JWT token creation.
    
    Returns:
        Dictionary containing all generated secrets
    """
    logger.info("Generating secure secrets...")
    
    # Generate JWT secret (must be at least 32 characters)
    jwt_secret = secrets.token_urlsafe(64)  # Increased length for better security

    # JWT claims
    now = int(time.time())
    # Set expiry to 100 years in the future for practical non-expiry
    exp = now + 60 * 60 * 24 * 365 * 100
    iss = "supabase"

    # Generate anon_key JWT with proper payload structure
    anon_payload = {
        "role": "anon",
        "iss": iss,
        "iat": now,
        "exp": exp
    }
    anon_key = jwt.encode(anon_payload, jwt_secret, algorithm="HS256")
    if isinstance(anon_key, bytes):
        anon_key = anon_key.decode("utf-8")

    # Generate service_role_key JWT with proper payload structure
    service_payload = {
        "role": "service_role",
        "iss": iss,
        "iat": now,
        "exp": exp
    }
    service_key = jwt.encode(service_payload, jwt_secret, algorithm="HS256")
    if isinstance(service_key, bytes):
        service_key = service_key.decode("utf-8")

    # Generate other secrets with appropriate lengths
    dashboard_password = secrets.token_urlsafe(24)
    secret_key_base = secrets.token_urlsafe(64)
    vault_enc_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8")
    postgres_password = secrets.token_urlsafe(32)
    
    # Generate Logflare tokens
    logflare_public_token = secrets.token_urlsafe(32)
    logflare_private_token = secrets.token_urlsafe(32)

    secrets_dict = {
        "jwt_secret": jwt_secret,
        "anon_key": anon_key,
        "service_role_key": service_key,
        "dashboard_password": dashboard_password,
        "secret_key_base": secret_key_base,
        "vault_enc_key": vault_enc_key,
        "postgres_password": postgres_password,
        "logflare_public_token": logflare_public_token,
        "logflare_private_token": logflare_private_token
    }
    
    # Validate generated tokens
    validate_jwt_tokens(secrets_dict)
    
    logger.info("✅ All secrets generated successfully")
    return secrets_dict


def validate_jwt_tokens(secrets: Dict[str, str]) -> None:
    """
    Validate that generated JWT tokens are properly formatted and decodable.
    
    Args:
        secrets: Dictionary containing the secrets to validate
        
    Raises:
        ValidationError: If token validation fails
    """
    try:
        # Validate anon key
        anon_decoded = jwt.decode(
            secrets["anon_key"], 
            secrets["jwt_secret"], 
            algorithms=["HS256"]
        )
        if anon_decoded.get("role") != "anon":
            raise ValidationError("Anon key role validation failed")
        
        # Validate service role key  
        service_decoded = jwt.decode(
            secrets["service_role_key"], 
            secrets["jwt_secret"], 
            algorithms=["HS256"]
        )
        if service_decoded.get("role") != "service_role":
            raise ValidationError("Service role key role validation failed")
            
        logger.debug("JWT token validation successful")
        
    except jwt.InvalidTokenError as e:
        raise ValidationError(f"JWT token validation failed: {e}")


class SupabaseInstanceManager:
    """
    Manages multiple Supabase instances with Docker isolation.
    
    Provides functionality for creating, configuring, monitoring, and destroying
    Supabase instances with unique ports and networking.
    """
    
    def __init__(self, base_folder: Optional[str] = None):
        """
        Initialize the instance manager.
        
        Args:
            base_folder: Base directory for storing instances
        """
        self.base_folder = base_folder or os.path.expanduser("~/projects/database")
        self.registry_file = os.path.join(self.base_folder, "instance_registry.json")
        self.docker_client = None
        
        # Initialize Docker client with error handling
        try:
            import docker
            self.docker_client = docker.from_env()
            # Test Docker connection
            self.docker_client.ping()
            logger.debug("Docker client connected successfully")
        except Exception as e:
            logger.warning(f"Could not connect to Docker: {e}")
            self.docker_client = None
        
        # Ensure base folder exists
        os.makedirs(self.base_folder, exist_ok=True)
        
        # Load or create registry
        self.registry = self.load_registry()
    
    def load_registry(self) -> Dict[str, Any]:
        """
        Load the instance registry from file.
        
        Returns:
            Dictionary containing the registry data
        """
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r') as f:
                    registry = json.load(f)
                logger.debug(f"Loaded registry with {len(registry.get('instances', {}))} instances")
                return registry
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading registry: {e}")
                logger.info("Creating new registry")
        
        return {
            "instances": {}, 
            "networks": {}, 
            "last_updated": None,
            "version": "1.0"
        }
    
    def save_registry(self) -> None:
        """Save the instance registry to file with error handling."""
        try:
            self.registry["last_updated"] = datetime.now().isoformat()
            # Create backup before saving
            if os.path.exists(self.registry_file):
                backup_file = f"{self.registry_file}.backup"
                shutil.copy2(self.registry_file, backup_file)
            
            with open(self.registry_file, 'w') as f:
                json.dump(self.registry, f, indent=2)
            logger.debug("Registry saved successfully")
        except IOError as e:
            logger.error(f"Error saving registry: {e}")
            raise
    
    def get_docker_network_name(self, instance_id: int) -> str:
        """
        Get the Docker network name for an instance.
        
        Args:
            instance_id: The instance identifier
            
        Returns:
            Network name string
        """
        return f"supabase-instance{instance_id}-network"
    
    def create_docker_network(self, instance_id: int) -> str:
        """
        Create a Docker network for the instance with proper error handling.
        
        Args:
            instance_id: The instance identifier
            
        Returns:
            Network name string
        """
        network_name = self.get_docker_network_name(instance_id)
        
        if not self.docker_client:
            logger.warning("Docker client not available, network creation skipped")
            return network_name
            
        try:
            # Check if network already exists
            existing_networks = self.docker_client.networks.list(names=[network_name])
            if existing_networks:
                logger.info(f"Docker network {network_name} already exists")
                return network_name
            
            # Create new network
            network = self.docker_client.networks.create(
                network_name,
                driver="bridge",
                options={
                    "com.docker.network.bridge.name": f"supabase-br{instance_id}"
                }
            )
            logger.info(f"✅ Created Docker network: {network_name}")
            return network_name
            
        except Exception as e:
            logger.error(f"Error creating Docker network {network_name}: {e}")
            return network_name
    
    def get_instance_info(self, instance_id: int) -> Dict[str, Any]:
        """
        Get comprehensive information about an instance.
        
        Args:
            instance_id: The instance identifier
            
        Returns:
            Dictionary containing instance information
        """
        # Use single port increments for each instance
        port_offset = instance_id
        kong_http_port = 8000 + port_offset      # 8001, 8002, 8003, etc.
        postgres_port = 5432 + port_offset       # 5433, 5434, 5435, etc.
        
        return {
            'instance_id': instance_id,
            'kong_http_port': kong_http_port,
            'postgres_port': postgres_port,
            'database_name': f'postgres',  # Keep database name as 'postgres' for simplicity
            'supabase_url': f'http://localhost:{kong_http_port}',
            'postgres_url': f'postgresql://postgres:{{POSTGRES_PASSWORD}}@localhost:{postgres_port}/postgres',
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
    
    def register_instance(
        self, 
        instance_id: int, 
        name: Optional[str] = None, 
        description: Optional[str] = None, 
        tags: Optional[List[str]] = None, 
        secrets: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Register an instance in the registry.
        
        Args:
            instance_id: The instance identifier
            name: Human-readable name for the instance
            description: Description of the instance
            tags: List of tags for categorization
            secrets: Generated secrets for the instance
            
        Returns:
            Dictionary containing the registered instance information
        """
        info = self.get_instance_info(instance_id)
        instance_key = f"instance{instance_id}"
        
        # Create folder name based on custom name or default
        if name:
            # Sanitize the name for folder usage
            folder_name = re.sub(r'[^\w\-_]', '-', name.lower())
            folder_name = re.sub(r'-+', '-', folder_name).strip('-')
            folder_name = f"{folder_name}-instance{instance_id}"
        else:
            folder_name = instance_key
        
        instance_data = {
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
        
        self.registry["instances"][instance_key] = instance_data
        
        # Register network
        network_name = self.get_docker_network_name(instance_id)
        self.registry["networks"][network_name] = {
            'instance_id': instance_id,
            'name': network_name,
            'created_at': datetime.now().isoformat()
        }
        
        self.save_registry()
        logger.info(f"✅ Instance {instance_id} registered successfully")
        return instance_data
    
    def update_instance_name(
        self, 
        instance_id: int, 
        name: str, 
        description: Optional[str] = None
    ) -> bool:
        """
        Update the name and description of an instance.
        
        Args:
            instance_id: The instance identifier
            name: New name for the instance
            description: New description for the instance
            
        Returns:
            True if successful, False if instance not found
        """
        instance_key = f"instance{instance_id}"
        if instance_key in self.registry["instances"]:
            self.registry["instances"][instance_key]["name"] = name
            if description:
                self.registry["instances"][instance_key]["description"] = description
            self.registry["instances"][instance_key]["updated_at"] = datetime.now().isoformat()
            self.save_registry()
            logger.info(f"✅ Instance {instance_id} updated successfully")
            return True
        logger.error(f"Instance {instance_id} not found")
        return False
    
    def delete_instance(self, instance_id: int, remove_files: bool = False) -> Tuple[bool, str]:
        """
        Delete an instance from the registry and optionally remove files.
        
        Args:
            instance_id: The instance identifier
            remove_files: Whether to remove instance files from disk
            
        Returns:
            Tuple of (success, message)
        """
        instance_key = f"instance{instance_id}"
        
        if instance_key not in self.registry["instances"]:
            return False, f"Instance {instance_id} not found"
        
        instance = self.registry["instances"][instance_key]
        instance_path = instance.get("path", "")
        network_name = self.get_docker_network_name(instance_id)
        
        # Stop Docker containers if running
        try:
            self._stop_instance_containers(instance_id, instance_path)
        except Exception as e:
            logger.error(f"Error stopping containers for instance {instance_id}: {e}")
            return False, f"Failed to stop containers: {e}"

        # Remove Docker network
        try:
            self._remove_docker_network(network_name)
        except Exception as e:
            logger.warning(f"Could not remove Docker network {network_name}: {e}")

        # Remove from registry
        if instance_key in self.registry["instances"]:
            del self.registry["instances"][instance_key]
            logger.info(f"Removed {instance_key} from registry")
        if network_name in self.registry.get("networks", {}):
            del self.registry["networks"][network_name]
            logger.info(f"Removed {network_name} from registry")

        # Save registry after removal
        self.save_registry()
        logger.debug(f"Registry saved after deleting {instance_key}")

        # Remove files if requested
        if remove_files and instance_path:
            try:
                self._remove_instance_files(instance_path)
            except Exception as e:
                logger.error(f"Could not remove files: {e}")
                return False, f"Could not remove files: {e}"

        logger.info(f"✅ Instance {instance_id} deleted successfully")
        return True, f"Instance {instance_id} deleted successfully"
    
    def _stop_instance_containers(self, instance_id: int, instance_path: str) -> None:
        """
        Stop Docker containers for an instance.
        
        Args:
            instance_id: The instance identifier
            instance_path: Path to the instance directory
        """
        # Try docker compose down first
        if instance_path and os.path.exists(instance_path):
            compose_path = os.path.join(instance_path, "supabase", "docker")
            if os.path.exists(compose_path):
                logger.info(f"Running docker compose down for instance {instance_id}...")
                original_cwd = os.getcwd()
                try:
                    os.chdir(compose_path)
                    run_command(
                        ["docker", "compose", "down", "-v", "--remove-orphans"],
                        capture_output=True
                    )
                    logger.info(f"✅ Docker compose down completed for instance {instance_id}")
                finally:
                    os.chdir(original_cwd)

        # Fallback: stop containers manually
        if self.docker_client:
            network_name = self.get_docker_network_name(instance_id)
            try:
                containers = self.docker_client.containers.list(
                    filters={"network": network_name}
                )
                for container in containers:
                    logger.info(f"Stopping container: {container.name}")
                    try:
                        container.stop(timeout=10)
                        container.remove()
                    except Exception as e:
                        logger.warning(f"Could not stop/remove container {container.name}: {e}")
            except Exception as e:
                logger.warning(f"Error stopping containers manually: {e}")
    
    def _remove_docker_network(self, network_name: str) -> None:
        """
        Remove a Docker network.
        
        Args:
            network_name: Name of the network to remove
        """
        if not self.docker_client:
            return
            
        try:
            networks = self.docker_client.networks.list(names=[network_name])
            for network in networks:
                logger.info(f"Removing Docker network: {network_name}")
                network.remove()
        except Exception as e:
            logger.warning(f"Could not remove Docker network {network_name}: {e}")
    
    def _remove_instance_files(self, instance_path: str) -> None:
        """
        Remove instance files with safety checks.
        
        Args:
            instance_path: Path to the instance directory
        """
        # Safety: Only allow removal if path is within base_folder and follows naming convention
        base_folder = os.path.abspath(self.base_folder)
        abs_instance_path = os.path.abspath(instance_path)
        
        if not abs_instance_path.startswith(base_folder):
            raise ValueError(f"Refusing to delete files outside managed directory: {abs_instance_path}")
        
        folder_name = os.path.basename(abs_instance_path)
        if not (folder_name.startswith("instance") or "instance" in folder_name):
            raise ValueError(f"Refusing to delete non-instance directory: {abs_instance_path}")
        
        if os.path.exists(abs_instance_path):
            shutil.rmtree(abs_instance_path)
            logger.info(f"Removed instance files: {abs_instance_path}")
    
    def get_instance_status(self, instance_id: int) -> str:
        """
        Check if an instance is running.
        
        Args:
            instance_id: The instance identifier
            
        Returns:
            Status string: 'running', 'stopped', 'configured', or 'unknown'
        """
        if not self.docker_client:
            return "unknown"
        
        try:
            network_name = self.get_docker_network_name(instance_id)
            
            # Check for running containers
            running_containers = self.docker_client.containers.list(
                filters={"network": network_name}
            )
            if running_containers:
                return "running"
            
            # Check for stopped containers
            all_containers = self.docker_client.containers.list(
                all=True, 
                filters={"network": network_name}
            )
            if all_containers:
                return "stopped"
            
            return "configured"
            
        except Exception as e:
            logger.error(f"Error checking status for instance {instance_id}: {e}")
            return "unknown"
    
    def list_instances(self) -> List[Dict[str, Any]]:
        """
        List all registered instances with their status.
        
        Returns:
            List of instance dictionaries with current status
        """
        instances = []
        for key, instance in self.registry["instances"].items():
            instance_id = instance["instance_id"]
            status = self.get_instance_status(instance_id)
            instances.append({
                **instance,
                "current_status": status
            })
        return instances
    
    def export_connection_info(
        self, 
        instance_id: Optional[int] = None, 
        format: str = "json"
    ) -> Optional[str]:
        """
        Export connection information for external tools.
        
        Args:
            instance_id: Specific instance ID, or None for all instances
            format: Output format ('json', 'yaml', 'env')
            
        Returns:
            Formatted connection information string
        """
        if instance_id:
            # Export single instance
            instance_key = f"instance{instance_id}"
            if instance_key not in self.registry["instances"]:
                return None
            
            instance = self.registry["instances"][instance_key]
            secrets = instance.get("secrets", {})
            
            connection_info = self._build_connection_info(instance, secrets)
        else:
            # Export all instances
            connection_info = {}
            for key, instance in self.registry["instances"].items():
                secrets = instance.get("secrets", {})
                connection_info[key] = self._build_connection_info(instance, secrets)
        
        # Format output
        if format == "yaml":
            return yaml.dump(connection_info, default_flow_style=False)
        elif format == "env":
            return self._format_as_env_vars(connection_info, instance_id)
        else:
            return json.dumps(connection_info, indent=2)
    
    def _build_connection_info(self, instance: Dict[str, Any], secrets: Dict[str, str]) -> Dict[str, Any]:
        """
        Build connection information dictionary for an instance.
        
        Args:
            instance: Instance data from registry
            secrets: Secrets data for the instance
            
        Returns:
            Connection information dictionary
        """
        postgres_password = secrets.get("postgres_password", "your-postgres-password")
        postgres_url = instance["postgres_url"].replace("{POSTGRES_PASSWORD}", postgres_password)
        
        return {
            "name": instance["name"],
            "instance_id": instance["instance_id"],
            "folder_name": instance.get("folder_name", f"instance{instance['instance_id']}"),
            "database_url": postgres_url,
            "supabase_url": instance["supabase_url"],
            "supabase_anon_key": secrets.get("anon_key", ""),
            "supabase_service_key": secrets.get("service_role_key", ""),
            "docker_network": instance["docker_network"],
            "ports": instance["ports"]
        }
    
    def _format_as_env_vars(
        self, 
        connection_info: Dict[str, Any], 
        instance_id: Optional[int]
    ) -> str:
        """
        Format connection information as environment variables.
        
        Args:
            connection_info: Connection information to format
            instance_id: Instance ID for single instance, None for all
            
        Returns:
            Environment variables as a string
        """
        env_vars = []
        
        if instance_id:
            # Single instance
            prefix = f"SUPABASE_INSTANCE_{instance_id}"
            info = connection_info
            env_vars.extend([
                f"{prefix}_NAME={info['name']}",
                f"{prefix}_DATABASE_URL={info['database_url']}",
                f"{prefix}_SUPABASE_URL={info['supabase_url']}",
                f"{prefix}_SUPABASE_ANON_KEY={info['supabase_anon_key']}",
                f"{prefix}_SUPABASE_SERVICE_KEY={info['supabase_service_key']}",
                f"{prefix}_DOCKER_NETWORK={info['docker_network']}",
                f"{prefix}_POSTGRES_PORT={info['ports']['postgres']}"
            ])
        else:
            # All instances
            for key, info in connection_info.items():
                prefix = f"SUPABASE_{key.upper()}"
                env_vars.extend([
                    f"{prefix}_NAME={info['name']}",
                    f"{prefix}_DATABASE_URL={info['database_url']}",
                    f"{prefix}_SUPABASE_URL={info['supabase_url']}",
                    f"{prefix}_DOCKER_NETWORK={info['docker_network']}",
                    f"{prefix}_POSTGRES_PORT={info['ports']['postgres']}"
                ])
        
        return "\n".join(env_vars)
    
    def generate_external_service_template(self, instance_id: int, service_name: str) -> str:
        """
        Generate a docker-compose template for external services.
        
        Args:
            instance_id: The instance identifier
            service_name: Name of the external service
            
        Returns:
            YAML string containing the docker-compose template
        """
        instance_info = self.get_instance_info(instance_id)
        network_name = self.get_docker_network_name(instance_id)
        
        # Get secrets if available
        instance_key = f"instance{instance_id}"
        secrets = {}
        if instance_key in self.registry["instances"]:
            secrets = self.registry["instances"][instance_key].get("secrets", {})
        
        postgres_password = secrets.get("postgres_password", "your-postgres-password")
        postgres_url = instance_info["postgres_url"].replace("{POSTGRES_PASSWORD}", postgres_password)
        
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

def clone_supabase_repo(target_dir: str = "supabase") -> None:
    """
    Clone the Supabase repository with sparse checkout for docker files only.
    
    Args:
        target_dir: Directory to clone the repository into
    """
    if not os.path.exists(target_dir):
        logger.info(f"Cloning Supabase repository into {target_dir}...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/supabase/supabase.git", target_dir
        ])
        
        original_cwd = os.getcwd()
        try:
            os.chdir(target_dir)
            run_command(["git", "sparse-checkout", "init", "--cone"])
            run_command(["git", "sparse-checkout", "set", "docker"])
            run_command(["git", "checkout", "master"])
            logger.info("✅ Supabase repository cloned successfully")
        finally:
            os.chdir(original_cwd)
    else:
        logger.info(f"Supabase repository already exists at {target_dir}, updating...")
        original_cwd_update = os.getcwd()
        try:
            os.chdir(target_dir)
            run_command(["git", "pull"], capture_output=True)
            logger.info("✅ Supabase repository updated")
        except Exception as e:
            logger.warning(f"Could not update repository: {e}")
        finally:
            os.chdir(original_cwd_update)


def prepare_supabase_env(
    manager: SupabaseInstanceManager, 
    root_env_path: str, 
    target_dir: str = "supabase", 
    instance_id: int = 1
) -> Dict[str, Any]:
    """
    Prepare and customize the Supabase environment configuration.
    
    Args:
        manager: The SupabaseInstanceManager instance
        root_env_path: Path to the .env.example template
        target_dir: Supabase directory name
        instance_id: The instance identifier
        
    Returns:
        Dictionary containing instance information and secrets
    """
    env_path = os.path.join(target_dir, "docker", ".env")
    compose_path = os.path.join(target_dir, "docker", "docker-compose.yml")
    
    logger.info(f"Customizing environment for instance {instance_id}...")
    
    # Read the template file
    try:
        with open(root_env_path, 'r') as f:
            env_content = f.read()
    except IOError as e:
        raise IOError(f"Could not read template file {root_env_path}: {e}")
    
    # Generate secrets for this instance
    secrets = generate_secrets()
    
    # Get instance info from manager
    instance_info = manager.get_instance_info(instance_id)
    
    # Create Docker network
    network_name = manager.create_docker_network(instance_id)
    
    # Apply environment variable replacements
    env_content = apply_env_replacements(env_content, instance_info, secrets)
    
    # Write the customized content
    try:
        with open(env_path, 'w') as f:
            f.write(env_content)
        logger.info(f"✅ Environment file created: {env_path}")
    except IOError as e:
        raise IOError(f"Could not write environment file {env_path}: {e}")
    
    # Customize docker-compose.yml for unique container names
    customize_docker_compose(compose_path, instance_id, network_name)
    
    # Update instance info with generated secrets
    instance_info['secrets'] = secrets
    
    # Log success information
    postgres_connection_string = instance_info['postgres_url'].replace(
        '{POSTGRES_PASSWORD}', secrets['postgres_password']
    )
    
    logger.info(f"✅ Instance {instance_id} configured successfully!")
    logger.info(f"📦 Database: {instance_info['database_name']}")
    logger.info(f"🔌 PostgreSQL Port: {instance_info['postgres_port']}")
    logger.info(f"🌐 Supabase URL: {instance_info['supabase_url']}")
    logger.info(f"🐳 Docker Network: {network_name}")
    logger.info(f"🔐 Dashboard Password: {secrets['dashboard_password']}")
    
    return instance_info


def apply_env_replacements(
    env_content: str, 
    instance_info: Dict[str, Any], 
    secrets: Dict[str, str]
) -> str:
    """
    Apply all environment variable replacements to the template content.
    
    Args:
        env_content: Original environment file content
        instance_info: Instance configuration information
        secrets: Generated secrets
        
    Returns:
        Modified environment file content
    """
    # Define all replacements based on the .env.example structure
    replacements = {
        # Core secrets
        'POSTGRES_PASSWORD=your-super-secret-and-long-postgres-password':
            f'POSTGRES_PASSWORD={secrets["postgres_password"]}',
        'JWT_SECRET=your-super-secret-jwt-token-with-at-least-32-characters-long':
            f'JWT_SECRET={secrets["jwt_secret"]}',
        'DASHBOARD_PASSWORD=this_password_is_insecure_and_should_be_updated':
            f'DASHBOARD_PASSWORD={secrets["dashboard_password"]}',
        'SECRET_KEY_BASE=UpNVntn3cDxHJpq99YMc1T1AQgQpc8kfYTuRgBiYa15BLrx8etQoXz3gZv1/u2oq':
            f'SECRET_KEY_BASE={secrets["secret_key_base"]}',
        'VAULT_ENC_KEY=your-encryption-key-32-chars-min':
            f'VAULT_ENC_KEY={secrets["vault_enc_key"]}',
        
        # JWT tokens - replace the example tokens with our generated ones
        'ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9zZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE':
            f'ANON_KEY={secrets["anon_key"]}',
        'SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9zZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwKICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q':
            f'SERVICE_ROLE_KEY={secrets["service_role_key"]}',
        
        # Database configuration
        'POSTGRES_DB=postgres': f'POSTGRES_DB={instance_info["database_name"]}',
        'POSTGRES_PORT=5432': f'POSTGRES_PORT={instance_info["postgres_port"]}',
        
        # Kong ports
        'KONG_HTTP_PORT=8000': f'KONG_HTTP_PORT={instance_info["ports"]["kong_http"]}',
        'KONG_HTTPS_PORT=8443': f'KONG_HTTPS_PORT={instance_info["ports"]["kong_https"]}',
        
        # Studio port
        'STUDIO_PORT=3000': f'STUDIO_PORT={instance_info["ports"]["studio"]}',
        
        # Pooler port
        'POOLER_PROXY_PORT_TRANSACTION=6543': 
            f'POOLER_PROXY_PORT_TRANSACTION={instance_info["ports"]["pooler"]}',
        
        # URLs that need to use the correct port
        'API_EXTERNAL_URL=http://localhost:8000': f'API_EXTERNAL_URL={instance_info["supabase_url"]}',
        'SITE_URL=http://localhost:3000': f'SITE_URL={instance_info["supabase_url"]}',
        
        # Logflare tokens
        'LOGFLARE_PUBLIC_ACCESS_TOKEN=your-super-secret-and-long-logflare-key-public':
            f'LOGFLARE_PUBLIC_ACCESS_TOKEN={secrets["logflare_public_token"]}',
        'LOGFLARE_PRIVATE_ACCESS_TOKEN=your-super-secret-and-long-logflare-key-private':
            f'LOGFLARE_PRIVATE_ACCESS_TOKEN={secrets["logflare_private_token"]}',
    }
    
    # Apply replacements
    for old_value, new_value in replacements.items():
        if old_value in env_content:
            env_content = env_content.replace(old_value, new_value)
        else:
            logger.warning(f"Template replacement not found: {old_value[:50]}...")
    
    # Add instance-specific configuration at the end
    env_content += f'\n\n####################\n'
    env_content += f'# Instance {instance_info["instance_id"]} Configuration\n'
    env_content += f'####################\n'
    env_content += f'INSTANCE_ID={instance_info["instance_id"]}\n'
    env_content += f'DOCKER_NETWORK={instance_info["docker_network"]}\n'
    env_content += f'INSTANCE_NAME=instance{instance_info["instance_id"]}\n'
    env_content += f'\n# External connection information\n'
    env_content += f'# Use these values to connect from external services:\n'
    postgres_url = instance_info["postgres_url"].replace(
        '{POSTGRES_PASSWORD}', secrets["postgres_password"]
    )
    env_content += f'# DATABASE_URL={postgres_url}\n'
    env_content += f'# SUPABASE_URL={instance_info["supabase_url"]}\n'
    env_content += f'# SUPABASE_ANON_KEY={secrets["anon_key"]}\n'
    env_content += f'# SUPABASE_SERVICE_KEY={secrets["service_role_key"]}\n'
    
    return env_content


def customize_docker_compose(compose_path: str, instance_id: int, network_name: str) -> None:
    """
    Customize docker-compose.yml file for unique container names and networking.
    
    Args:
        compose_path: Path to the docker-compose.yml file
        instance_id: The instance identifier
        network_name: Name of the Docker network
    """
    logger.info(f"Customizing docker-compose.yml for instance {instance_id}...")
    
    try:
        # Read the docker-compose.yml file
        with open(compose_path, 'r') as f:
            compose_content = f.read()
    except IOError as e:
        raise IOError(f"Could not read docker-compose file {compose_path}: {e}")
    
    # Update the compose project name to be unique per instance
    compose_content = re.sub(
        r'^name:\s*supabase.*$',
        f'name: supabase-instance{instance_id}',
        compose_content,
        flags=re.MULTILINE
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
    
    # Apply container name replacements only if not already applied
    for old_name, new_name in container_replacements.items():
        if old_name in compose_content and new_name not in compose_content:
            compose_content = compose_content.replace(old_name, new_name)
    
    # Update networks section - replace or add
    networks_section = f"""
networks:
  default:
    name: {network_name}
    external: true
"""
    
    # Remove existing networks section and add our custom one
    compose_content = re.sub(
        r'\nnetworks:.*?(?=\n\S|\Z)', 
        networks_section, 
        compose_content, 
        flags=re.DOTALL
    )
    
    # If no networks section was found, add it at the end
    if 'networks:' not in compose_content:
        compose_content += networks_section
    
    # Write the customized docker-compose.yml
    try:
        with open(compose_path, 'w') as f:
            f.write(compose_content)
        logger.info(f"✅ Docker Compose customized for instance {instance_id}")
    except IOError as e:
        raise IOError(f"Could not write docker-compose file {compose_path}: {e}")


def setup_instance(
    manager: SupabaseInstanceManager, 
    instance_id: int, 
    name: Optional[str] = None, 
    description: Optional[str] = None, 
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Set up a single Supabase instance with complete configuration.
    
    Args:
        manager: The SupabaseInstanceManager instance
        instance_id: The instance identifier
        name: Human-readable name for the instance
        description: Description of the instance
        tags: List of tags for categorization
        
    Returns:
        Dictionary containing instance information and secrets
    """
    base_folder = manager.base_folder
    
    # Create folder name based on custom name or default
    if name:
        # Sanitize the name for folder usage
        folder_name = re.sub(r'[^\w\-_]', '-', name.lower())
        folder_name = re.sub(r'-+', '-', folder_name).strip('-')
        folder_name = f"{folder_name}-instance{instance_id}"
    else:
        folder_name = f"instance{instance_id}"
    
    instance_dir = os.path.join(base_folder, folder_name)
    os.makedirs(instance_dir, exist_ok=True)
    
    original_cwd = os.getcwd()
    try:
        os.chdir(instance_dir)
        
        # Clone or update Supabase repository
        clone_supabase_repo(target_dir="supabase")
        
        # Prepare environment configuration
        env_template = os.path.join("supabase", "docker", ".env.example")
        if not os.path.exists(env_template):
            raise FileNotFoundError(f"Template file not found: {env_template}")
        
        instance_info = prepare_supabase_env(manager, env_template, "supabase", instance_id)
        
        # Register the instance in the manager
        manager.register_instance(
            instance_id, 
            name=name, 
            description=description, 
            tags=tags, 
            secrets=instance_info.get('secrets')
        )
        
        # Log success information
        secrets = instance_info.get('secrets', {})
        postgres_connection_string = instance_info['postgres_url'].replace(
            '{POSTGRES_PASSWORD}', secrets.get('postgres_password', 'unknown')
        )
        
        logger.info(f"✅ Instance {instance_id} set up successfully!")
        logger.info(f"📁 Folder: {folder_name}")
        logger.info(f"🐳 Network: {instance_info['docker_network']}")
        logger.info(f"🌐 Supabase URL: {instance_info['supabase_url']}")
        logger.info(f"🔌 PostgreSQL Port: {instance_info['postgres_port']}")
        logger.info(f"🗄️  PostgreSQL Connection: {postgres_connection_string}")
        
        return instance_info
        
    except Exception as e:
        logger.error(f"Error setting up instance {instance_id}: {e}")
        raise
    finally:
        os.chdir(original_cwd)


def update_env_for_instance(manager: SupabaseInstanceManager, instance_id: int) -> None:
    """
    Regenerate and update only the .env file for a specific instance.
    
    Args:
        manager: The SupabaseInstanceManager instance
        instance_id: The instance identifier
    """
    instance_key = f"instance{instance_id}"
    if instance_key not in manager.registry["instances"]:
        logger.error(f"Instance {instance_id} not found in registry")
        return

    original_cwd = os.getcwd()
    instance = manager.registry["instances"][instance_key]
    instance_dir = instance["path"]
    env_template = os.path.join(instance_dir, "supabase", "docker", ".env.example")
    env_path = os.path.join(instance_dir, "supabase", "docker", ".env")

    if not os.path.exists(env_template):
        logger.error(f".env.example not found for instance {instance_id} at {env_template}")
        return

    try:
        # Read the template file
        with open(env_template, 'r') as f:
            env_content = f.read()

        # Generate new secrets for this instance
        secrets = generate_secrets()
        instance_info = manager.get_instance_info(instance_id)

        # Apply environment variable replacements
        env_content = apply_env_replacements(env_content, instance_info, secrets)

        # Write the updated environment file
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        # Update registry with new secrets
        manager.registry["instances"][instance_key]["secrets"] = secrets
        manager.registry["instances"][instance_key]["updated_at"] = datetime.now().isoformat()
        manager.save_registry()
        
        logger.info(f"✅ Environment file updated for instance {instance_id}")
        
    except Exception as e:
        logger.error(f"Error updating environment for instance {instance_id}: {e}")
        raise
    finally:
        os.chdir(original_cwd)


def interactive_menu(manager: SupabaseInstanceManager) -> None:
    """
    Interactive command-line menu for managing Supabase instances.
    
    Args:
        manager: The SupabaseInstanceManager instance
    """
    while True:
        print("\n" + "="*60)
        print("🚀 Supabase Instance Manager - Interactive Menu")
        print("="*60)
        print("1. 🔧 Setup new instance(s)")
        print("2. 📋 List all instances")
        print("3. 🔗 Get connection info")
        print("4. ✏️  Update instance metadata")
        print("5. 📦 Generate docker-compose template for external service")
        print("6. 📊 Check instance status")
        print("7. 🗑️  Delete an instance")
        print("8. 🔄 Update only .env for an instance")
        print("9. 🚪 Quit")
        print("="*60)
        
        try:
            choice = input("Select an option (1-9): ").strip()
            
            if choice == "1":
                _handle_setup_instances(manager)
            elif choice == "2":
                _handle_list_instances(manager)
            elif choice == "3":
                _handle_connection_info(manager)
            elif choice == "4":
                _handle_update_metadata(manager)
            elif choice == "5":
                _handle_generate_template(manager)
            elif choice == "6":
                _handle_check_status(manager)
            elif choice == "7":
                _handle_delete_instance(manager)
            elif choice == "8":
                _handle_update_env(manager)
            elif choice == "9":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid option. Please try again.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in interactive menu: {e}")
            print(f"❌ An error occurred: {e}")


def _handle_setup_instances(manager: SupabaseInstanceManager) -> None:
    """Handle the setup instances menu option."""
    try:
        ids_input = input("Instance IDs to set up (comma separated, e.g. 1,2,3): ").strip()
        if not ids_input:
            print("❌ No instance IDs provided")
            return
            
        ids = []
        for i in ids_input.split(","):
            try:
                ids.append(int(i.strip()))
            except ValueError:
                print(f"❌ Invalid instance ID: {i.strip()}")
                return
        
        # Get optional metadata
        name = None
        if len(ids) == 1:
            name = input("Name for the instance (optional): ").strip() or None
        
        description = input("Description (optional): ").strip() or None
        tags_input = input("Tags (space separated, optional): ").strip()
        tags = tags_input.split() if tags_input else None
        
        # Setup instances
        for instance_id in ids:
            try:
                current_name = name if len(ids) == 1 else None
                setup_instance(manager, instance_id, name=current_name, description=description, tags=tags)
                print(f"✅ Instance {instance_id} setup completed")
            except Exception as e:
                logger.error(f"Error setting up instance {instance_id}: {e}")
                print(f"❌ Failed to setup instance {instance_id}: {e}")
                
    except Exception as e:
        print(f"❌ Error in setup: {e}")


def _handle_list_instances(manager: SupabaseInstanceManager) -> None:
    """Handle the list instances menu option."""
    try:
        instances = manager.list_instances()
        if not instances:
            print("📭 No instances found")
            return
            
        # Table header
        print(f"\n{'ID':<4} {'Name':<20} {'Folder':<25} {'Status':<12} {'Supabase URL':<30} {'PostgreSQL Port':<6}")
        print("-" * 105)
        
        # Table rows
        for instance in instances:
            folder_name = instance.get('folder_name', f"instance{instance['instance_id']}")
            print(f"{instance['instance_id']:<4} {instance['name']:<20} {folder_name:<25} "
                  f"{instance['current_status']:<12} {instance['supabase_url']:<30} {instance['postgres_port']:<6}")
                  
    except Exception as e:
        print(f"❌ Error listing instances: {e}")


def _handle_connection_info(manager: SupabaseInstanceManager) -> None:
    """Handle the connection info menu option."""
    try:
        iid_input = input("Instance ID (leave blank for all): ").strip()
        instance_id = int(iid_input) if iid_input else None
        
        fmt = input("Format (json/yaml/env) [json]: ").strip() or "json"
        if fmt not in ["json", "yaml", "env"]:
            print("❌ Invalid format. Using json.")
            fmt = "json"
        
        info = manager.export_connection_info(instance_id, fmt)
        if info:
            print("\n" + "="*60)
            print("🔗 Connection Information")
            print("="*60)
            print(info)
        else:
            print("❌ No connection info available")
            
    except ValueError:
        print("❌ Invalid instance ID")
    except Exception as e:
        print(f"❌ Error getting connection info: {e}")


def _handle_update_metadata(manager: SupabaseInstanceManager) -> None:
    """Handle the update metadata menu option."""
    try:
        iid_input = input("Instance ID: ").strip()
        if not iid_input:
            print("❌ Instance ID is required")
            return
            
        instance_id = int(iid_input)
        name = input("New name: ").strip()
        if not name:
            print("❌ Name is required")
            return
            
        description = input("New description (optional): ").strip() or None
        
        if manager.update_instance_name(instance_id, name, description):
            print(f"✅ Instance {instance_id} updated successfully")
        else:
            print(f"❌ Instance {instance_id} not found")
            
    except ValueError:
        print("❌ Invalid instance ID")
    except Exception as e:
        print(f"❌ Error updating metadata: {e}")


def _handle_generate_template(manager: SupabaseInstanceManager) -> None:
    """Handle the generate template menu option."""
    try:
        iid_input = input("Instance ID: ").strip()
        if not iid_input:
            print("❌ Instance ID is required")
            return
            
        instance_id = int(iid_input)
        service_name = input("Service name: ").strip()
        if not service_name:
            print("❌ Service name is required")
            return
        
        template = manager.generate_external_service_template(instance_id, service_name)
        print("\n" + "="*60)
        print("📦 Docker Compose Template")
        print("="*60)
        print(template)
        
    except ValueError:
        print("❌ Invalid instance ID")
    except Exception as e:
        print(f"❌ Error generating template: {e}")


def _handle_check_status(manager: SupabaseInstanceManager) -> None:
    """Handle the check status menu option."""
    try:
        iid_input = input("Instance ID (leave blank for all): ").strip()
        
        if iid_input:
            instance_id = int(iid_input)
            status = manager.get_instance_status(instance_id)
            print(f"📊 Instance {instance_id}: {status}")
        else:
            instances = manager.list_instances()
            if not instances:
                print("📭 No instances found")
                return
                
            print("\n📊 Instance Status:")
            print("-" * 30)
            for instance in instances:
                print(f"Instance {instance['instance_id']}: {instance['current_status']}")
                
    except ValueError:
        print("❌ Invalid instance ID")
    except Exception as e:
        print(f"❌ Error checking status: {e}")


def _handle_delete_instance(manager: SupabaseInstanceManager) -> None:
    """Handle the delete instance menu option."""
    try:
        iid_input = input("Instance ID: ").strip()
        if not iid_input:
            print("❌ Instance ID is required")
            return
            
        instance_id = int(iid_input)
        
        # Confirm deletion
        print(f"⚠️  You are about to delete instance {instance_id}")
        confirm = input("Type 'DELETE' to confirm: ").strip()
        if confirm != 'DELETE':
            print("❌ Deletion cancelled")
            return
        
        remove_files = input("Remove files from disk? (y/N): ").strip().lower() == 'y'
        
        success, message = manager.delete_instance(instance_id, remove_files)
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
            
    except ValueError:
        print("❌ Invalid instance ID")
    except Exception as e:
        print(f"❌ Error deleting instance: {e}")


def _handle_update_env(manager: SupabaseInstanceManager) -> None:
    """Handle the update env menu option."""
    try:
        iid_input = input("Instance ID to update .env for: ").strip()
        if not iid_input:
            print("❌ Instance ID is required")
            return
            
        instance_id = int(iid_input)
        update_env_for_instance(manager, instance_id)
        
    except ValueError:
        print("❌ Invalid instance ID")
    except Exception as e:
        print(f"❌ Error updating environment: {e}")


def main() -> int:
    """
    Main entry point for the Supabase Instance Manager.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Supabase Instance Manager - Manage multiple Supabase instances with Docker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup.py                                    # Interactive mode
  python setup.py setup --instances 1 2 3           # Setup instances 1, 2, 3
  python setup.py list --format table               # List all instances
  python setup.py info --instance 1 --format json  # Get connection info for instance 1
  python setup.py delete 1 --remove-files          # Delete instance 1 and files
        """
    )
    
    parser.add_argument(
        "--base-folder", 
        default=os.path.expanduser("~/projects/database"), 
        help="Base folder for instances (default: ~/projects/database)"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Enable verbose logging"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up new instances")
    setup_parser.add_argument(
        "--instances", 
        type=int, 
        nargs="+", 
        default=[1], 
        help="Instance IDs to set up (default: [1])"
    )
    setup_parser.add_argument("--name", help="Name for the instance (only works with single instance)")
    setup_parser.add_argument("--description", help="Description for the instance")
    setup_parser.add_argument("--tags", nargs="+", help="Tags for the instance")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all instances")
    list_parser.add_argument(
        "--format", 
        choices=["table", "json", "yaml"], 
        default="table", 
        help="Output format (default: table)"
    )
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Get connection info for instances")
    info_parser.add_argument("--instance", type=int, help="Instance ID (if not specified, shows all)")
    info_parser.add_argument(
        "--format", 
        choices=["json", "yaml", "env"], 
        default="json", 
        help="Output format (default: json)"
    )
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
    delete_parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    
    # Update env command
    update_env_parser = subparsers.add_parser("update-env", help="Regenerate and update only the .env file for an instance")
    update_env_parser.add_argument("--instance", type=int, required=True, help="Instance ID to update .env for")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize manager
    try:
        manager = SupabaseInstanceManager(args.base_folder)
    except Exception as e:
        logger.error(f"Failed to initialize manager: {e}")
        return 1
    
    # Handle commands
    try:
        if not args.command:
            # Interactive mode
            interactive_menu(manager)
            return 0
        
        if args.command == "setup":
            if len(args.instances) == 1 and args.name:
                setup_instance(manager, args.instances[0], name=args.name, description=args.description, tags=args.tags)
            else:
                for instance_id in args.instances:
                    setup_instance(manager, instance_id, description=args.description, tags=args.tags)
        
        elif args.command == "list":
            instances = manager.list_instances()
            if args.format == "table":
                if not instances:
                    print("📭 No instances found")
                else:
                    print(f"{'ID':<4} {'Name':<20} {'Folder':<25} {'Status':<12} {'Supabase URL':<30} {'PostgreSQL Port':<6}")
                    print("-" * 105)
                    for instance in instances:
                        folder_name = instance.get('folder_name', f"instance{instance['instance_id']}")
                        print(f"{instance['instance_id']:<4} {instance['name']:<20} {folder_name:<25} "
                              f"{instance['current_status']:<12} {instance['supabase_url']:<30} {instance['postgres_port']:<6}")
            elif args.format == "json":
                print(json.dumps(instances, indent=2))
            elif args.format == "yaml":
                print(yaml.dump(instances, default_flow_style=False))
        
        elif args.command == "info":
            info = manager.export_connection_info(args.instance, args.format)
            if info and args.output:
                with open(args.output, 'w') as f:
                    f.write(info)
                print(f"✅ Connection info saved to {args.output}")
            elif info:
                print(info)
            else:
                print("❌ No connection info available")
        
        elif args.command == "update":
            if manager.update_instance_name(args.instance, args.name, args.description):
                print(f"✅ Instance {args.instance} updated successfully")
            else:
                print(f"❌ Instance {args.instance} not found")
        
        elif args.command == "template":
            template = manager.generate_external_service_template(args.instance, args.service_name)
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(template)
                print(f"✅ Template saved to {args.output}")
            else:
                print(template)
        
        elif args.command == "status":
            if args.instance:
                status = manager.get_instance_status(args.instance)
                print(f"📊 Instance {args.instance}: {status}")
            else:
                instances = manager.list_instances()
                if not instances:
                    print("📭 No instances found")
                else:
                    print("📊 Instance Status:")
                    print("-" * 30)
                    for instance in instances:
                        print(f"Instance {instance['instance_id']}: {instance['current_status']}")
        
        elif args.command == "delete":
            if not args.yes:
                print(f"⚠️  You are about to delete instance {args.instance}")
                confirm = input("Type 'DELETE' to confirm: ").strip()
                if confirm != 'DELETE':
                    print("❌ Deletion cancelled")
                    return 1
            
            success, message = manager.delete_instance(args.instance, args.remove_files)
            if success:
                print(f"✅ {message}")
            else:
                print(f"❌ {message}")
                return 1
        
        elif args.command == "update-env":
            update_env_for_instance(manager, args.instance)
        
        return 0
        
    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())