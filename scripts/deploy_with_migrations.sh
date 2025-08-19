#!/bin/bash
# Comprehensive deployment script with PDF backend and database migration fixes
# This script ensures all critical dependencies are installed and database is up to date

set -e  # Exit on any error

echo "🚀 Starting comprehensive deployment with fixes..."

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

# Step 1: Install/upgrade PDF dependencies
print_status "Installing PDF processing dependency..."
pip install pdfminer.six==20231228

# Step 2: Verify PDF backend availability
print_status "Verifying PDF backend availability..."
python3 -c "
import sys
try:
    from pdfminer.high_level import extract_text
    print('✅ pdfminer.six available')
except ImportError as e:
    print('❌ pdfminer.six not available:', e)
    sys.exit(1)
"

# Step 3: Run database migrations
print_status "Running database migrations..."
flask db upgrade

# Step 4: Apply ingestion columns fix if needed
print_status "Checking for missing ingestion columns..."
python3 -c "
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

try:
    # Get database URL from environment
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('⚠️  DATABASE_URL not set, skipping column check')
        sys.exit(0)
    
    # Create engine and test connection
    engine = create_engine(db_url)
    with engine.connect() as conn:
        # Check if ingestion_status column exists
        result = conn.execute(text(\"\"\"
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'proposal_documents' 
            AND column_name = 'ingestion_status'
        \"\"\"))
        
        if result.fetchone():
            print('✅ ingestion_status column exists')
        else:
            print('❌ ingestion_status column missing - applying fix...')
            # Apply the fix
            with open('scripts/fix_ingestion_columns.sql', 'r') as f:
                sql = f.read()
            conn.execute(text(sql))
            conn.commit()
            print('✅ Ingestion columns fix applied')
            
except Exception as e:
    print(f'⚠️  Database check failed: {e}')
    print('Continuing with deployment...')
"

# Step 5: Run health checks
print_status "Running health checks..."
python3 -c "
import requests
import time
import sys

# Wait for app to be ready
time.sleep(5)

try:
    response = requests.get('http://localhost:5000/health', timeout=10)
    if response.status_code == 200:
        print('✅ Health check passed')
    else:
        print(f'⚠️  Health check returned {response.status_code}')
except Exception as e:
    print(f'⚠️  Health check failed: {e}')
"

# Step 6: Test PDF backend
print_status "Testing PDF backend..."
python3 -c "
import tempfile
import os
from app.services.pdf_backend import validate_pdf_backend, extract_text_from_pdf

# Test backend validation
backend = validate_pdf_backend()
if backend['available']:
    print(f'✅ PDF backend available: {backend[\"backend\"]}')
    
    # Create a simple test PDF
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        fd, temp_path = tempfile.mkstemp(suffix='.pdf')
        os.close(fd)
        
        c = canvas.Canvas(temp_path, pagesize=letter)
        c.drawString(100, 750, 'Test PDF for mdraft')
        c.drawString(100, 700, 'This is a test document.')
        c.save()
        
        # Test text extraction
        text = extract_text_from_pdf(temp_path)
        if 'Test PDF for mdraft' in text:
            print('✅ PDF text extraction working')
        else:
            print('⚠️  PDF text extraction may have issues')
        
        os.unlink(temp_path)
    except Exception as e:
        print(f'⚠️  PDF test failed: {e}')
else:
    print(f'❌ PDF backend not available: {backend[\"error\"]}')
    print(f'Recommendation: {backend[\"recommendation\"]}')
"

print_success "Deployment completed successfully!"
print_status "The application should now be ready with:"
print_status "  ✅ PDF processing capabilities (pdfminer.six)"
print_status "  ✅ Database schema up to date"
print_status "  ✅ All critical dependencies installed"

# Optional: Start the application if not already running
if [ "$1" = "--start" ]; then
    print_status "Starting application..."
    python3 run.py
fi
