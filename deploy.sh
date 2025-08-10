#!/bin/bash

# mdraft Deployment Script
# This script helps set up and deploy the mdraft application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    print_status "Checking Python version..."
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python $PYTHON_VERSION found"
    elif command_exists python; then
        PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python not found. Please install Python 3.8 or higher."
        exit 1
    fi
}

# Function to create virtual environment
create_venv() {
    print_status "Creating virtual environment..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        print_success "Virtual environment created"
    else
        print_warning "Virtual environment already exists"
    fi
}

# Function to activate virtual environment
activate_venv() {
    print_status "Activating virtual environment..."
    source .venv/bin/activate
    print_success "Virtual environment activated"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    print_success "Dependencies installed"
}

# Function to set up environment variables
setup_env() {
    print_status "Setting up environment variables..."
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_warning "Created .env from .env.example"
            print_warning "Please edit .env with your actual configuration"
        else
            print_error ".env.example not found"
            exit 1
        fi
    else
        print_warning ".env already exists"
    fi
}

# Function to initialize database
init_database() {
    print_status "Initializing database..."
    if command_exists flask; then
        flask db init 2>/dev/null || print_warning "Database already initialized"
        flask db migrate -m "Initial migration" 2>/dev/null || print_warning "Migration already exists"
        flask db upgrade
        print_success "Database initialized"
    else
        print_error "Flask not found. Please install dependencies first."
        exit 1
    fi
}

# Function to run tests
run_tests() {
    print_status "Running setup tests..."
    if [ -f "test_setup.py" ]; then
        python test_setup.py
    else
        print_warning "test_setup.py not found, skipping tests"
    fi
}

# Function to start the application
start_app() {
    print_status "Starting the application..."
    print_success "Application will be available at http://localhost:5000"
    print_warning "Press Ctrl+C to stop the application"
    python run.py
}

# Function to show help
show_help() {
    echo "mdraft Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup     - Complete setup (venv, deps, env, db)"
    echo "  install   - Install dependencies only"
    echo "  init-db   - Initialize database only"
    echo "  test      - Run setup tests"
    echo "  start     - Start the application"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 setup    # Complete setup"
    echo "  $0 start    # Start the application"
}

# Main script logic
case "${1:-help}" in
    "setup")
        print_status "Starting complete setup..."
        check_python_version
        create_venv
        activate_venv
        install_dependencies
        setup_env
        init_database
        run_tests
        print_success "Setup complete!"
        print_status "You can now run '$0 start' to start the application"
        ;;
    "install")
        check_python_version
        create_venv
        activate_venv
        install_dependencies
        ;;
    "init-db")
        activate_venv
        init_database
        ;;
    "test")
        activate_venv
        run_tests
        ;;
    "start")
        activate_venv
        start_app
        ;;
    "help"|*)
        show_help
        ;;
esac
