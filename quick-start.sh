#!/bin/bash

# Quick Start Guide for Supabase Instance Manager
# This script demonstrates the key features

echo "🚀 Supabase Instance Manager - Quick Start Demo"
echo "================================================"
echo

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo
echo "🔧 Setting up instances..."

# Setup instances with different purposes
echo "Setting up Development instance..."
python3 setup.py setup --instances 1 --name "Development ChatBot" --description "Development environment for testing new features" --tags development chatbot llm

echo
echo "Setting up Staging instance..."
python3 setup.py setup --instances 2 --name "Staging ChatBot" --description "Staging environment for pre-production testing" --tags staging chatbot llm

echo
echo "Setting up Production instance..."
python3 setup.py setup --instances 3 --name "Production ChatBot" --description "Production environment for live users" --tags production chatbot llm

echo
echo "📋 Listing all instances..."
python3 setup.py list

echo
echo "🔍 Getting connection info for Development instance..."
python3 setup.py info --instance 1

echo
echo "🌐 Environment variables for Development instance..."
python3 setup.py info --instance 1 --format env

echo
echo "🐳 Generating docker-compose template for external service..."
python3 setup.py template 1 my-llm-service

echo
echo "💾 Exporting all connection info to file..."
python3 setup.py info --format json --output all-instances.json
echo "Connection info saved to all-instances.json"

echo
echo "🏷️ Updating instance name..."
python3 setup.py update 1 --name "Dev Environment" --description "Updated development environment"

echo
echo "📋 Final instance list..."
python3 setup.py list

echo
echo "✅ Quick start complete!"
echo
echo "🎯 Next steps:"
echo "1. Start an instance: ./supabase-manager.sh start 1"
echo "2. View logs: ./supabase-manager.sh logs 1"
echo "3. Stop an instance: ./supabase-manager.sh stop 1"
echo "4. Check status: ./supabase-manager.sh status"
echo
echo "📚 For more information, see README.md"
