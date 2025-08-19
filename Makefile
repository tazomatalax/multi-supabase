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
	@python3 setup.py setup
	@echo "✅ Setup complete! You can now create instances."

# Install dependencies only
deps:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt
	@which docker > /dev/null || (echo "❌ Docker not found. Please install Docker." && exit 1)
	@which git > /dev/null || (echo "❌ Git not found. Please install Git." && exit 1)
	@echo "✅ Dependencies ready"

# Core instance management
create:
ifndef NAME
	@echo "❌ Usage: make create NAME=myproject"
	@exit 1
endif
	python3 setup.py create $(NAME)

list:
	python3 setup.py list

destroy:
ifndef NAME
	@echo "❌ Usage: make destroy NAME=myproject"
	@exit 1
endif
	python3 setup.py destroy $(NAME)

# Dynamic instance commands - these work for any instance name
%-start:
	python3 setup.py start $*

%-stop:
	python3 setup.py stop $*

%-restart:
	python3 setup.py restart $*

%-logs:
	python3 setup.py logs $* -f

%-ps:
	python3 setup.py ps $*

# Shortcuts for common instance names
dev-start: 
	python3 setup.py start dev

dev-stop:
	python3 setup.py stop dev

dev-logs:
	python3 setup.py logs dev -f

# Clean up everything
clean:
	@echo "⚠️  This will destroy ALL instances. Continue? [y/N]"
	@read -r confirm && [ "$$confirm" = "y" ] || exit 1
	@for instance in $$(python3 setup.py list | tail -n +3 | awk '{print $$1}'); do \
		if [ "$$instance" != "No" ] && [ "$$instance" != "" ]; then \
			echo "Destroying $$instance..."; \
			python3 setup.py destroy $$instance; \
		fi \
	done
	@echo "✅ All instances destroyed"