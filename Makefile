# Supabase Instance Manager - Makefile
# Simplified commands for managing multiple Supabase instances

.PHONY: help list create destroy deps setup clean

# Default target
help:
	@echo "🚀 Supabase Instance Manager"
	@echo ""
	@echo "🔧 First Time Setup:"
	@echo "  make setup                    One-time setup (clone template, install deps)"
	@echo ""
	@echo "Quick Commands:"
	@echo "  make create NAME=myproject    Create new instance"
	@echo "  make list                     List all instances"  
	@echo "  make destroy NAME=myproject   Destroy instance"
	@echo ""
	@echo "Instance Management:"
	@echo "  make myproject-start          Start instance"
	@echo "  make myproject-stop           Stop instance"
	@echo "  make myproject-restart        Restart instance"
	@echo "  make myproject-logs           View logs"
	@echo "  make myproject-ps             Show status"
	@echo ""
	@echo "Maintenance:"
	@echo "  make deps                     Install dependencies only"

# One-time setup: dependencies + template
setup:
	@echo "🔧 Setting up Supabase Instance Manager..."
	@$(MAKE) deps
	@.venv/bin/python setup.py setup
	@echo "✅ Setup complete! You can now create instances."

# Install dependencies only
deps:
	@echo "📦 Setting up virtual environment and installing dependencies..."
	@python3 -m venv .venv
	@echo "🔧 Created .venv virtual environment"
	@.venv/bin/pip install -r requirements.txt
	@which docker > /dev/null || (echo "❌ Docker not found. Please install Docker." && exit 1)
	@which git > /dev/null || (echo "❌ Git not found. Please install Git." && exit 1)
	@echo "✅ Dependencies ready in .venv"

# Core instance management
create:
ifndef NAME
	@echo "❌ Usage: make create NAME=myproject"
	@exit 1
endif
	.venv/bin/python setup.py create $(NAME)

list:
	.venv/bin/python setup.py list

destroy:
ifndef NAME
	@echo "❌ Usage: make destroy NAME=myproject"
	@exit 1
endif
	.venv/bin/python setup.py destroy $(NAME)

# Dynamic instance commands - these work for any instance name
%-start:
	.venv/bin/python setup.py start $*

%-stop:
	.venv/bin/python setup.py stop $*

%-restart:
	.venv/bin/python setup.py restart $*

%-logs:
	.venv/bin/python setup.py logs $* -f

%-ps:
	.venv/bin/python setup.py ps $*

# Shortcuts for common instance names
dev-start: 
	.venv/bin/python setup.py start dev

dev-stop:
	.venv/bin/python setup.py stop dev

dev-logs:
	.venv/bin/python setup.py logs dev -f

# Clean up everything
clean:
	@echo "⚠️  This will destroy ALL instances. Continue? [y/N]"
	@read -r confirm && [ "$$confirm" = "y" ] || exit 1
	@for instance in $$(.venv/bin/python setup.py list | tail -n +3 | awk '{print $$1}'); do \
		if [ "$$instance" != "No" ] && [ "$$instance" != "" ]; then \
			echo "Destroying $$instance..."; \
			.venv/bin/python setup.py destroy $$instance; \
		fi \
	done
	@echo "✅ All instances destroyed"