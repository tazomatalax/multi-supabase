#!/bin/bash

# Supabase Instance Manager - Quick Commands

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SETUP_SCRIPT="$SCRIPT_DIR/setup.py"

# Function to check if setup.py exists
check_setup_script() {
    if [ ! -f "$SETUP_SCRIPT" ]; then
        echo "Error: setup.py not found in $SCRIPT_DIR"
        exit 1
    fi
}

# Function to show usage
show_usage() {
    echo "Supabase Instance Manager - Quick Commands"
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  setup [instance_ids...]    - Set up Supabase instances (default: 1-5)"
    echo "  list                       - List all instances"
    echo "  info [instance_id]         - Show connection info"
    echo "  status [instance_id]       - Check instance status"
    echo "  update <instance_id> <name> - Update instance name"
    echo "  template <instance_id> <service_name> - Generate docker-compose template"
    echo "  delete <instance_id>       - Delete an instance (keeps files)"
    echo "  delete <instance_id> --files - Delete an instance and remove files"
    echo "  start <instance_id>        - Start Supabase instance"
    echo "  stop <instance_id>         - Stop Supabase instance"
    echo "  logs <instance_id>         - View instance logs"
    echo "  env <instance_id>          - Show environment variables"
    echo ""
    echo "Examples:"
    echo "  $0 setup 1 2 3            - Set up instances 1, 2, and 3"
    echo "  $0 list                    - List all instances"
    echo "  $0 info 1                 - Show connection info for instance 1"
    echo "  $0 start 1                - Start instance 1"
    echo "  $0 env 1                  - Show environment variables for instance 1"
}

# Function to start a Supabase instance
start_instance() {
    local instance_id=$1
    local base_folder=$(python3 "$SETUP_SCRIPT" list --format json | jq -r '.[] | select(.instance_id == '$instance_id') | .path')
    
    if [ -z "$base_folder" ]; then
        echo "Error: Instance $instance_id not found"
        exit 1
    fi
    
    cd "$base_folder/supabase/docker"
    echo "Starting Supabase instance $instance_id..."
    docker-compose up -d
}

# Function to stop a Supabase instance
stop_instance() {
    local instance_id=$1
    local base_folder=$(python3 "$SETUP_SCRIPT" list --format json | jq -r '.[] | select(.instance_id == '$instance_id') | .path')
    
    if [ -z "$base_folder" ]; then
        echo "Error: Instance $instance_id not found"
        exit 1
    fi
    
    cd "$base_folder/supabase/docker"
    echo "Stopping Supabase instance $instance_id..."
    docker-compose down
}

# Function to view logs
view_logs() {
    local instance_id=$1
    local base_folder=$(python3 "$SETUP_SCRIPT" list --format json | jq -r '.[] | select(.instance_id == '$instance_id') | .path')
    
    if [ -z "$base_folder" ]; then
        echo "Error: Instance $instance_id not found"
        exit 1
    fi
    
    cd "$base_folder/supabase/docker"
    echo "Viewing logs for Supabase instance $instance_id..."
    docker-compose logs -f
}

# Function to show environment variables
show_env() {
    local instance_id=$1
    echo "Environment variables for instance $instance_id:"
    python3 "$SETUP_SCRIPT" info --instance "$instance_id" --format env
}

# Main command processing
check_setup_script

case "$1" in
    setup)
        shift
        if [ $# -eq 0 ]; then
            python3 "$SETUP_SCRIPT" setup
        else
            python3 "$SETUP_SCRIPT" setup --instances "$@"
        fi
        ;;
    list)
        python3 "$SETUP_SCRIPT" list
        ;;
    info)
        if [ -n "$2" ]; then
            python3 "$SETUP_SCRIPT" info --instance "$2"
        else
            python3 "$SETUP_SCRIPT" info
        fi
        ;;
    status)
        if [ -n "$2" ]; then
            python3 "$SETUP_SCRIPT" status --instance "$2"
        else
            python3 "$SETUP_SCRIPT" status
        fi
        ;;
    update)
        if [ $# -lt 3 ]; then
            echo "Usage: $0 update <instance_id> <name> [description]"
            exit 1
        fi
        python3 "$SETUP_SCRIPT" update "$2" --name "$3" ${4:+--description "$4"}
        ;;
    template)
        if [ $# -lt 3 ]; then
            echo "Usage: $0 template <instance_id> <service_name> [output_file]"
            exit 1
        fi
        if [ -n "$4" ]; then
            python3 "$SETUP_SCRIPT" template "$2" "$3" --output "$4"
        else
            python3 "$SETUP_SCRIPT" template "$2" "$3"
        fi
        ;;
    start)
        if [ -z "$2" ]; then
            echo "Usage: $0 start <instance_id>"
            exit 1
        fi
        start_instance "$2"
        ;;
    stop)
        if [ -z "$2" ]; then
            echo "Usage: $0 stop <instance_id>"
            exit 1
        fi
        stop_instance "$2"
        ;;
    logs)
        if [ -z "$2" ]; then
            echo "Usage: $0 logs <instance_id>"
            exit 1
        fi
        view_logs "$2"
        ;;
    env)
        if [ -z "$2" ]; then
            echo "Usage: $0 env <instance_id>"
            exit 1
        fi
        show_env "$2"
        ;;
    delete)
        if [ -z "$2" ]; then
            echo "Usage: $0 delete <instance_id> [--files]"
            exit 1
        fi
        if [ "$3" = "--files" ]; then
            python3 "$SETUP_SCRIPT" delete "$2" --remove-files
        else
            python3 "$SETUP_SCRIPT" delete "$2"
        fi
        ;;
    *)
        show_usage
        ;;
esac
