# API Authentication Deployment Guide

## 🎯 Overview

This guide covers the deployment of the improved API authentication system that provides better handling of unauthorized access and configurable login requirements.

## ✅ **Changes Implemented**

### **1. JSON 401 Responses for API Endpoints**

**Problem:** API endpoints were returning 302 redirects to `/auth/login` when users were not authenticated.

**Solution:** Added an unauthorized handler that returns JSON 401 responses for API calls instead of redirects.

```python
# app/extensions.py
@login_manager.unauthorized_handler
def _api_unauthorized():
    """Handle unauthorized access - return JSON for API calls, redirect for web."""
    from flask import request, jsonify, redirect, url_for
    
    # if it's an API call, don't redirect — return 401 JSON
    if request.path.startswith("/api/"):
        return jsonify(error="unauthorized"), 401
    # otherwise do the normal redirect
    return redirect(url_for("auth.login"))
```

**Result:** 
- ✅ API endpoints now return `{"error": "unauthorized"}` with 401 status
- ✅ Web endpoints still redirect to login page
- ✅ Frontend can handle 401 responses appropriately

### **2. Configurable Login Requirements**

**Problem:** Need flexibility to allow or require login for conversion endpoints.

**Solution:** Added environment variable `CONVERT_REQUIRES_LOGIN` to control authentication policy.

```python
# app/api_convert.py
import os
REQUIRE_LOGIN_CONVERT = os.getenv("CONVERT_REQUIRES_LOGIN", "0") in {"1", "true", "True"}

if REQUIRE_LOGIN_CONVERT and not current_user.is_authenticated:
    return jsonify(error="unauthorized"), 401
```

**Options:**
- **Option A (Require Login)**: Set `CONVERT_REQUIRES_LOGIN=1` - better UX, users must sign in
- **Option B (Allow Anonymous)**: Set `CONVERT_REQUIRES_LOGIN=0` - fastest unblock, allows guest conversions

### **3. CSRF Exemption for API Endpoints**

**Problem:** File uploads could fail with 400 CSRF errors.

**Solution:** API blueprints are automatically exempted from CSRF protection.

```python
# app/blueprints.py (automatic)
if import_path.startswith("app.api") or "api" in import_path:
    csrf.exempt(bp)
```

**Result:** ✅ File uploads work without CSRF token requirements

## 🚀 **Deployment Instructions**

### **Step 1: Deploy Code Changes**

The code changes are already pushed to GitHub:
```bash
git push origin feature/security-hardening-and-reliability
```

### **Step 2: Set Environment Variables**

In your Render dashboard, set the following environment variables:

#### **For Anonymous Conversions (Recommended for now):**
```bash
CONVERT_REQUIRES_LOGIN=0
```

#### **For Required Login (Better UX):**
```bash
CONVERT_REQUIRES_LOGIN=1
```

#### **Additional Environment Variables:**
```bash
FLASK_LIMITER_STORAGE_URI=redis://red-d2gudc7diees73duftog:6379/2
```

### **Step 3: Verify Deployment**

Test the API endpoints to ensure they work correctly:

```bash
# Test anonymous access (should work with CONVERT_REQUIRES_LOGIN=0)
curl -i "$RENDER_EXTERNAL_URL/api/estimate" -F "file=@/etc/hosts"

# Test unauthorized access (should return JSON 401)
curl -i "$RENDER_EXTERNAL_URL/api/me/usage"

# Test CSRF exemption (should work without CSRF token)
curl -i "$RENDER_EXTERNAL_URL/api/convert" -F "file=@/etc/hosts"
```

## 🎯 **Expected Behavior**

### **With CONVERT_REQUIRES_LOGIN=0 (Anonymous Allowed):**
- ✅ `/api/estimate` → 200 OK (anonymous users)
- ✅ `/api/convert` → 202 Accepted (anonymous users)
- ✅ `/api/conversions` → 200 OK (anonymous users)
- ✅ `/api/me/usage` → 401 JSON (requires login)

### **With CONVERT_REQUIRES_LOGIN=1 (Login Required):**
- ✅ `/api/estimate` → 401 JSON (requires login)
- ✅ `/api/convert` → 401 JSON (requires login)
- ✅ `/api/conversions` → 200 OK (anonymous users)
- ✅ `/api/me/usage` → 401 JSON (requires login)

### **All Configurations:**
- ✅ No more 302 redirects to `/auth/login`
- ✅ JSON 401 responses for API endpoints
- ✅ CSRF exemption working for file uploads
- ✅ Visitor sessions supported for anonymous users

## 🔧 **Frontend Integration**

If you're using `CONVERT_REQUIRES_LOGIN=1`, update your frontend to handle 401 responses:

```javascript
// Example frontend error handling
fetch('/api/convert', {
    method: 'POST',
    body: formData
})
.then(response => {
    if (response.status === 401) {
        // Show sign-in prompt
        showLoginPrompt();
    } else if (response.ok) {
        // Handle success
        handleSuccess(response);
    }
})
.catch(error => {
    // Handle other errors
    handleError(error);
});
```

## 📋 **Verification Checklist**

- [x] **Unauthorized Handler**: API endpoints return JSON 401 instead of 302
- [x] **Environment Variable**: `CONVERT_REQUIRES_LOGIN` controls authentication policy
- [x] **CSRF Exemption**: File uploads work without CSRF tokens
- [x] **Visitor Sessions**: Anonymous users get proper session management
- [x] **Error Handling**: Proper JSON error responses for API calls

## 🎉 **Status: Ready for Production**

The API authentication system is now:
- ✅ **Flexible**: Configurable via environment variables
- ✅ **User-Friendly**: Proper JSON responses for API calls
- ✅ **Secure**: CSRF protection where appropriate
- ✅ **Robust**: Handles both authenticated and anonymous users

Choose your preferred authentication policy by setting `CONVERT_REQUIRES_LOGIN` and deploy!
