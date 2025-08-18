#!/bin/bash
# Test deployment readiness without database connection

set -e

echo "🧪 Testing mdraft deployment readiness..."

# Test 1: Check migration files
echo "📋 Test 1: Checking migration files..."
if [ -f "migrations/versions/a7e06de8f890_merge_heads.py" ]; then
    echo "✅ Merge migration exists"
else
    echo "❌ Merge migration missing"
    exit 1
fi

# Test 2: Check celery exports
echo "🧪 Test 2: Testing Celery configuration..."
python3 -c "
from celery_worker import celery, celery_app

# Verify celery exports
assert celery is celery_app, 'celery and celery_app should be the same object'
assert hasattr(celery, 'conf'), 'celery should have conf attribute'
assert hasattr(celery, 'send_task'), 'celery should have send_task method'

print('✅ Celery configuration verified')
"

# Test 3: Check blueprint imports
echo "🧪 Test 3: Testing blueprint imports..."
python3 -c "
try:
    from app.api_convert import bp as convert_bp
    from app.api_estimate import bp as estimate_bp
    from app.api_queue import bp as queue_bp
    from app.api.agents import bp as agents_bp
    print('✅ All blueprint imports successful')
except Exception as e:
    print(f'❌ Blueprint import failed: {e}')
    exit(1)
"

# Test 4: Check render.yaml configuration
echo "📋 Test 4: Checking render.yaml configuration..."
if grep -q "celery_worker:celery" render.yaml; then
    echo "✅ Celery command correctly configured"
else
    echo "❌ Celery command not correctly configured"
    exit 1
fi

if grep -q "flask.*db upgrade" render.yaml; then
    echo "✅ Migration command included in render.yaml"
else
    echo "❌ Migration command missing from render.yaml"
    exit 1
fi

echo "🎉 All deployment readiness tests passed!"
echo ""
echo "📋 Deployment is ready. Issues fixed:"
echo "✅ Celery startup command corrected (celery_worker:celery)"
echo "✅ Migration heads merged (a7e06de8f890_merge_heads.py)"
echo "✅ Database migration command added to render.yaml"
echo "✅ All blueprint imports working"
echo ""
echo "🚀 Ready to deploy to Render!"
