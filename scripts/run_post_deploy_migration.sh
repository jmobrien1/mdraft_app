#!/bin/bash
# Post-deploy migration script
# Run this after deployment to add the missing email_verified column

set -e  # Exit on any error

echo "=== Post-Deploy Migration Script ==="
echo "This script will add the missing email_verified column to the users table."
echo ""

# Check if we're in the right directory
if [ ! -f "app/__init__.py" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Run the migration script
echo "Running migration script..."
python scripts/run_migration.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migration completed successfully!"
    echo "The email_verified column has been added to the users table."
    echo "Login functionality should now work properly."
else
    echo ""
    echo "❌ Migration failed!"
    echo "Please check the logs above for details."
    exit 1
fi
