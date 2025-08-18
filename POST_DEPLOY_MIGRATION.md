# Post-Deploy Migration Guide

## Problem
The application is failing with a database error:
```
psycopg.errors.UndefinedColumn: column users.email_verified does not exist
```

This happens because the code expects an `email_verified` column in the `users` table, but it doesn't exist in the production database.

## Solution: Post-Deploy Migration

We've created a safe post-deploy migration approach to avoid deployment timeouts.

### Files Created
- `scripts/run_migration.py` - Python script to add the missing column
- `scripts/run_post_deploy_migration.sh` - Shell script wrapper
- `POST_DEPLOY_MIGRATION.md` - This documentation

### How to Run the Migration

#### Option 1: Using the Shell Script (Recommended)
```bash
# From the project root directory
./scripts/run_post_deploy_migration.sh
```

#### Option 2: Using Python Directly
```bash
# From the project root directory
python scripts/run_migration.py
```

#### Option 3: Manual SQL (if needed)
```sql
-- For PostgreSQL
ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT false;
```

### What the Migration Does

1. **Checks if column exists** - Won't fail if column already exists
2. **Adds the column** - Adds `email_verified BOOLEAN NOT NULL DEFAULT false`
3. **Handles both PostgreSQL and SQLite** - Works in development and production
4. **Provides detailed logging** - Shows exactly what's happening

### Expected Output
```
=== Post-Deploy Migration Script ===
This script will add the missing email_verified column to the users table.

Running migration script...
2025-08-18 16:00:00,000 [INFO] === Starting Post-Deploy Migration ===
2025-08-18 16:00:00,001 [INFO] Connected to database successfully
2025-08-18 16:00:00,002 [INFO] Database dialect: postgresql
2025-08-18 16:00:00,003 [INFO] Column 'email_verified' does not exist. Adding it...
2025-08-18 16:00:00,004 [INFO] Successfully added 'email_verified' column to users table
2025-08-18 16:00:00,005 [INFO] === Migration completed successfully ===

✅ Migration completed successfully!
The email_verified column has been added to the users table.
Login functionality should now work properly.
```

### After Migration
- ✅ Login functionality will work
- ✅ User registration will work
- ✅ Email verification features will work
- ✅ No more 500 errors on `/auth/login`

### Troubleshooting

#### If the script fails:
1. Check database connection
2. Verify you have write permissions to the database
3. Check the logs for specific error messages

#### If column already exists:
The script will detect this and exit successfully without making changes.

### Why Post-Deploy?

- **Avoids deployment timeouts** - No migration during startup
- **Safer** - Can be run manually and verified
- **More reliable** - Won't cause deployment failures
- **Reversible** - Can be undone if needed

### Future Migrations

For future database changes, consider:
1. Creating migrations that can be run post-deploy
2. Using the same pattern for other schema changes
3. Testing migrations in development first
