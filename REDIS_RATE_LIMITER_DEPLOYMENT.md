# Redis Rate Limiter Deployment Guide

## 🎯 Overview

This guide explains how to configure Flask-Limiter to use Redis storage instead of in-memory storage, which will:

- ✅ **Silence the warning**: "Using in-memory storage for tracking rate limits"
- ✅ **Improve reliability**: Rate limits persist across server restarts
- ✅ **Support concurrency**: Multiple server instances share rate limit state
- ✅ **Production ready**: Proper Redis storage for production environments

## 🔧 Configuration

### **Environment Variable**

Set this environment variable on your **Web service** in Render:

```bash
FLASK_LIMITER_STORAGE_URI=redis://<your-internal-valkey-host>:6379/2
```

### **Example Values**

**For Render's internal Redis:**
```bash
FLASK_LIMITER_STORAGE_URI=redis://red-d2gudc7diees73duftog:6379/2
```

**For external Redis:**
```bash
FLASK_LIMITER_STORAGE_URI=redis://your-redis-host:6379/2
```

**For Redis with authentication:**
```bash
FLASK_LIMITER_STORAGE_URI=redis://username:password@your-redis-host:6379/2
```

**For Redis with TLS:**
```bash
FLASK_LIMITER_STORAGE_URI=rediss://your-redis-host:6379/2
```

## 🚀 Deployment Steps

### **1. Set Environment Variable**

In your Render dashboard:

1. Go to your **Web service**
2. Navigate to **Environment** tab
3. Add environment variable:
   - **Key**: `FLASK_LIMITER_STORAGE_URI`
   - **Value**: `redis://<your-redis-host>:6379/2`
4. Click **Save Changes**

### **2. Deploy the Application**

The code changes are already deployed. The application will:

- ✅ Read the `FLASK_LIMITER_STORAGE_URI` environment variable
- ✅ Configure Flask-Limiter to use Redis storage
- ✅ Log the configuration status
- ✅ Fall back to memory storage if Redis is unavailable

### **3. Verify Configuration**

After deployment, check the logs for:

**Success message:**
```
Flask-Limiter configured with Redis storage: redis://your-redis-host:6379/2
Flask-Limiter initialized successfully
```

**Fallback message (if Redis unavailable):**
```
Flask-Limiter initialization failed, using memory storage: [error details]
```

## 🔍 Verification Commands

### **Check Environment Variable**

```bash
# In Render web shell
echo $FLASK_LIMITER_STORAGE_URI
```

### **Test Rate Limiter Configuration**

```bash
# In Render web shell
python3 test_limiter_config.py
```

Expected output:
```
📋 FLASK_LIMITER_STORAGE_URI: redis://your-redis-host:6379/2
✅ Redis storage URI configured
✅ Limiter storage initialized
✅ Rate limiter should work with Redis
```

### **Check Application Logs**

Look for these log messages:

**✅ Success:**
```
Flask-Limiter configured with Redis storage: redis://your-redis-host:6379/2
Flask-Limiter initialized successfully
```

**⚠️ Fallback:**
```
Flask-Limiter using in-memory storage (set FLASK_LIMITER_STORAGE_URI for Redis)
```

**❌ Error:**
```
Flask-Limiter initialization failed, using memory storage: [error details]
```

## 🎯 Expected Results

### **Before Configuration:**
- ❌ Warning: "Using in-memory storage for tracking rate limits"
- ❌ Rate limits reset on server restart
- ❌ No shared state between server instances

### **After Configuration:**
- ✅ No more in-memory storage warnings
- ✅ Rate limits persist across server restarts
- ✅ Shared rate limit state across multiple instances
- ✅ Production-ready rate limiting

## 🔧 Troubleshooting

### **Redis Connection Issues**

If you see initialization errors:

1. **Check Redis URL format:**
   ```bash
   # Should be:
   redis://hostname:6379/database_number
   ```

2. **Verify Redis is reachable:**
   ```bash
   # Test connection
   redis-cli -h your-redis-host -p 6379 ping
   ```

3. **Check firewall/network:**
   - Ensure the web service can reach the Redis host
   - Verify port 6379 is open

### **Fallback Behavior**

If Redis is unavailable, the application will:

- ✅ Continue to function normally
- ✅ Use in-memory storage as fallback
- ✅ Log a warning message
- ✅ Not crash or fail to start

### **Database Selection**

The `/2` in the Redis URL selects database 2:

```bash
redis://hostname:6379/2  # Uses Redis database 2
```

This keeps rate limiting data separate from other Redis data.

## 📋 Summary

1. **Set environment variable**: `FLASK_LIMITER_STORAGE_URI=redis://your-redis-host:6379/2`
2. **Deploy application**: Code changes are already deployed
3. **Verify configuration**: Check logs for success messages
4. **Test functionality**: Rate limits now persist and are shared

The rate limiter will now use Redis storage, eliminating the warning and providing production-ready rate limiting! 🎉
