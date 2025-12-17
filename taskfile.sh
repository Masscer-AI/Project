#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
check_env_file() {
    if [ ! -f .env ]; then
        print_warn ".env file not found. Creating from .env.example if it exists..."
        if [ -f .env.example ]; then
            cp .env.example .env
            print_info ".env file created from .env.example"
        else
            print_warn ".env.example not found. You may need to create .env manually."
        fi
    fi
}

# Setup environment
setup_env() {
    print_info "Setting up environment..."
    check_env_file
    
    # Create data directories
    mkdir -p data/postgres
    mkdir -p data/redis
    mkdir -p vector_storage
    mkdir -p storage
    
    print_info "Environment setup complete!"
}

# Setup Django (migrations, superuser, etc.)
setup_django() {
    print_info "Setting up Django..."
    
    # Wait for postgres to be ready
    print_info "Waiting for PostgreSQL to be ready..."
    docker compose -f docker-compose.local.yml exec -T postgres bash -c "until pg_isready -U \${POSTGRES_USER:-postgres}; do sleep 1; done" || true
    
    # Run migrations
    print_info "Running migrations..."
    docker compose -f docker-compose.local.yml exec -T django python manage.py migrate
    
    # Create superuser and default organization
    print_info "Creating superuser and default organization..."
    docker compose -f docker-compose.local.yml exec -T django python manage.py shell <<'PYEOF'
from django.contrib.auth import get_user_model
from api.authenticate.models import Organization, UserProfile

User = get_user_model()
username = 'admin'
email = 'admin@localhost.com'
password = 'p'
org_name = 'localhost'

# Create or get superuser
user, user_created = User.objects.get_or_create(
    username=username,
    defaults={
        'email': email,
        'is_staff': True,
        'is_superuser': True,
    }
)
if user_created:
    user.set_password(password)
    user.save()
    print(f'Superuser "{username}" created successfully!')
    print(f'Email: {email}')
    print(f'Password: {password}')
else:
    # Update password in case it changed
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f'Superuser "{username}" already exists, password updated!')

# Create or get default organization
org, org_created = Organization.objects.get_or_create(
    name=org_name,
    defaults={'owner': user, 'description': 'Default organization for localhost'}
)
if org_created:
    print(f'Organization "{org_name}" created successfully!')
else:
    # Update owner if it changed
    if org.owner != user:
        org.owner = user
        org.save()
        print(f'Organization "{org_name}" owner updated!')
    else:
        print(f'Organization "{org_name}" already exists!')

# Create or update user profile and assign to organization
user_profile, profile_created = UserProfile.objects.get_or_create(user=user)
user_profile.organization = org
user_profile.save(update_fields=['organization', 'updated_at'])

if profile_created:
    print(f'UserProfile for "{username}" created and assigned to "{org_name}"!')
else:
    print(f'UserProfile for "{username}" updated and assigned to "{org_name}"!')

PYEOF
    
    print_info "Django setup complete!"
}

# Create superuser
create_superuser() {
    print_info "Creating superuser and default organization..."
    
    docker compose -f docker-compose.local.yml exec -T django python manage.py shell <<'PYEOF'
from django.contrib.auth import get_user_model
from api.authenticate.models import Organization, UserProfile

User = get_user_model()
username = 'admin'
email = 'admin@localhost.com'
password = 'p'
org_name = 'localhost'

# Create or get superuser
user, user_created = User.objects.get_or_create(
    username=username,
    defaults={
        'email': email,
        'is_staff': True,
        'is_superuser': True,
    }
)
if user_created:
    user.set_password(password)
    user.save()
    print(f'Superuser "{username}" created successfully!')
    print(f'Email: {email}')
    print(f'Password: {password}')
else:
    # Update password in case it changed
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f'Superuser "{username}" already exists, password updated!')

# Create or get default organization
org, org_created = Organization.objects.get_or_create(
    name=org_name,
    defaults={'owner': user, 'description': 'Default organization for localhost'}
)
if org_created:
    print(f'Organization "{org_name}" created successfully!')
else:
    # Update owner if it changed
    if org.owner != user:
        org.owner = user
        org.save()
        print(f'Organization "{org_name}" owner updated!')
    else:
        print(f'Organization "{org_name}" already exists!')

# Create or update user profile and assign to organization
user_profile, profile_created = UserProfile.objects.get_or_create(user=user)
user_profile.organization = org
user_profile.save(update_fields=['organization', 'updated_at'])

if profile_created:
    print(f'UserProfile for "{username}" created and assigned to "{org_name}"!')
else:
    print(f'UserProfile for "{username}" updated and assigned to "{org_name}"!')

PYEOF
    
    print_info "Superuser and organization creation complete!"
}

# Build frontend
build_frontend() {
    print_info "Building frontend..."
    docker compose -f docker-compose.local.yml exec -T fastapi npm run build || {
        print_warn "Frontend build failed, continuing..."
    }
}

# Watch frontend (runs in background)
watch_frontend() {
    print_info "Starting frontend watch mode..."
    docker compose -f docker-compose.local.yml exec -d fastapi npm run watch
}

# Development mode - starts all services
dev() {
    print_info "Starting development environment..."
    
    # Setup environment
    setup_env
    
    # Start services
    print_info "Starting Docker Compose services..."
    docker compose -f docker-compose.local.yml up -d
    
    # Wait for services to be ready
    print_info "Waiting for services to be ready..."
    sleep 10
    
    # Setup Django
    setup_django
    
    # Build frontend
    build_frontend
    
    # Start frontend watch
    watch_frontend
    
    print_info "Development environment is ready!"
    print_info "Django: http://localhost:8000"
    print_info "FastAPI: http://localhost:8001"
    print_info "Flower: http://localhost:5555"
    print_info ""
    print_info "To view logs: ./taskfile.sh logs"
    print_info "To stop: ./taskfile.sh stop"
}

# Run migrations
migrate() {
    print_info "Running migrations..."
    docker compose -f docker-compose.local.yml exec django python manage.py migrate
}

# Show logs
logs() {
    if [ -z "$1" ]; then
        docker compose -f docker-compose.local.yml logs -f
    else
        docker compose -f docker-compose.local.yml logs -f "$1"
    fi
}

# Stop all services
stop() {
    print_info "Stopping all services..."
    docker compose -f docker-compose.local.yml down
}

# Clean up (stop and remove volumes)
clean() {
    print_warn "This will stop all services and remove volumes. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_info "Cleaning up..."
        docker compose -f docker-compose.local.yml down -v
        print_info "Cleanup complete!"
    else
        print_info "Cleanup cancelled."
    fi
}

# Clean PostgreSQL data (useful when database is corrupted)
clean_postgres() {
    if [ "$2" != "--yes" ]; then
        print_warn "This will remove PostgreSQL data directory. Are you sure? (y/N)"
        read -r response
        if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            print_info "Cleanup cancelled."
            return
        fi
    fi
    print_info "Cleaning PostgreSQL data..."
    docker compose -f docker-compose.local.yml stop postgres 2>/dev/null || true
    docker compose -f docker-compose.local.yml rm -f postgres 2>/dev/null || true
    if [ -d "./data/postgres" ]; then
        rm -rf ./data/postgres/* ./data/postgres/.[^.]* 2>/dev/null || true
        print_info "PostgreSQL data directory cleaned!"
    fi
    print_info "You can now run './taskfile.sh dev' again."
}

# Main command handler
case "$1" in
    setup-env)
        setup_env
        ;;
    setup-django)
        setup_django
        ;;
    dev)
        dev
        ;;
    migrate)
        migrate
        ;;
    build-frontend)
        build_frontend
        ;;
    watch-frontend)
        watch_frontend
        ;;
    logs)
        logs "$2"
        ;;
    stop)
        stop
        ;;
    clean)
        clean
        ;;
    clean-postgres)
        clean_postgres
        ;;
    create-superuser)
        create_superuser
        ;;
    *)
        echo "Usage: $0 {setup-env|setup-django|dev|migrate|build-frontend|watch-frontend|logs|stop|clean|clean-postgres|create-superuser}"
        echo ""
        echo "Commands:"
        echo "  setup-env       - Setup environment (create directories, check .env)"
        echo "  setup-django    - Setup Django (run migrations)"
        echo "  dev             - Start all services in development mode"
        echo "  migrate         - Run Django migrations"
        echo "  build-frontend  - Build frontend assets"
        echo "  watch-frontend  - Start frontend watch mode"
        echo "  logs [service]  - Show logs (optionally for a specific service)"
        echo "  stop            - Stop all services"
        echo "  clean           - Stop all services and remove volumes"
        echo "  clean-postgres  - Clean PostgreSQL data directory (fixes corruption issues)"
        echo "  create-superuser - Create Django superuser (admin@localhost.com / p)"
        exit 1
        ;;
esac

