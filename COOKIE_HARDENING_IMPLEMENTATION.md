# Session & Visitor Cookie Hardening Implementation

## Overview

This document describes the implementation of session and visitor cookie hardening for the mdraft application. The changes improve security by implementing shorter TTLs, proper cookie attributes, visitor session rotation, and optional Redis session storage.

## Security Improvements Implemented

### 1. Visitor Session TTL Reduction
- **Before**: 30 days
- **After**: 7 days (configurable via `VISITOR_SESSION_TTL_DAYS`)
- **Rationale**: Shorter TTL reduces the window of opportunity for session hijacking

### 2. Cookie Security Attributes
All cookies now have hardened security attributes:

```python
# Visitor session cookies
httponly=True      # Prevents XSS access
secure=True        # HTTPS only
samesite="Lax"     # CSRF protection
```

### 3. Visitor Session Rotation
- Visitor session IDs are rotated when users log in
- Invalidates previous anonymous sessions
- Prevents session fixation attacks

### 4. Flask-Login Session Hardening
- Session lifetime reduced to 7 days
- All session cookies use secure attributes
- Remember me cookies also hardened

### 5. Optional Redis Session Storage
- Server-side session storage when `SESSION_BACKEND=redis`
- Improved security and scalability
- Falls back to filesystem storage

## Implementation Details

### Files Modified

#### `app/auth/visitor.py`
- Reduced TTL from 30 to 7 days
- Added `rotate_visitor_session()` function
- Hardened cookie attributes (always Secure, HttpOnly, SameSite=Lax)
- Added configurable TTL via environment variable

#### `app/auth/routes.py`
- Added visitor session rotation on login/register
- Updated response handling to include rotated cookies
- Added last login timestamp tracking

#### `app/__init__.py`
- Added Flask-Session extension
- Configured Redis session backend support
- Hardened all session cookie attributes
- Added environment variable configuration

#### `requirements.txt`
- Added Flask-Session dependency

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VISITOR_SESSION_TTL_DAYS` | `7` | Visitor session TTL in days |
| `SESSION_BACKEND` | `filesystem` | Session storage backend (`redis` or `filesystem`) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL (when using Redis backend) |
| `SECRET_KEY` | `changeme` | Application secret key (must be set in production) |

## Configuration Examples

### Development (Filesystem Sessions)
```bash
export VISITOR_SESSION_TTL_DAYS=7
export SESSION_BACKEND=filesystem
export SECRET_KEY=your-secret-key-here
```

### Production (Redis Sessions)
```bash
export VISITOR_SESSION_TTL_DAYS=7
export SESSION_BACKEND=redis
export REDIS_URL=redis://your-redis-instance:6379/0
export SECRET_KEY=your-production-secret-key
```

## Security Benefits

### 1. Reduced Attack Surface
- Shorter session lifetimes limit exposure
- Secure cookies prevent man-in-the-middle attacks
- HttpOnly prevents XSS cookie theft

### 2. Session Fixation Protection
- Visitor session rotation on login
- Invalidates anonymous sessions when users authenticate
- Prevents attackers from pre-setting session IDs

### 3. CSRF Protection
- SameSite=Lax provides CSRF protection
- Balances security with functionality
- Can be upgraded to "Strict" if needed

### 4. Server-Side Session Storage
- Redis backend moves sessions to server
- Reduces client-side session data exposure
- Enables session invalidation and management

## Testing

### Manual Testing
1. Start the application
2. Visit any page to get a visitor session cookie
3. Check cookie attributes in browser dev tools
4. Log in and verify visitor session is rotated
5. Verify session cookies have proper attributes

### Automated Testing
Run the test script:
```bash
python test_cookie_hardening.py
```

### Cookie Attribute Verification
Expected cookie attributes:
```
visitor_session_id:
  - HttpOnly: true
  - Secure: true (in HTTPS)
  - SameSite: Lax
  - Max-Age: 604800 (7 days)

session:
  - HttpOnly: true
  - Secure: true (in HTTPS)
  - SameSite: Lax
  - Max-Age: 604800 (7 days)
```

## Migration Guide

### For Existing Deployments
1. Update environment variables
2. Deploy new code
3. Existing sessions will continue to work
4. New sessions will use hardened attributes
5. Consider Redis migration for production

### Redis Migration Steps
1. Set up Redis instance
2. Configure `REDIS_URL` environment variable
3. Set `SESSION_BACKEND=redis`
4. Deploy application
5. Monitor session behavior

## Monitoring and Maintenance

### Key Metrics to Monitor
- Session creation rates
- Redis connection health (if using Redis)
- Cookie-related errors
- Authentication success rates

### Regular Maintenance
- Rotate `SECRET_KEY` periodically
- Monitor Redis memory usage
- Review session TTL settings
- Update security headers as needed

## Troubleshooting

### Common Issues

#### Cookies Not Setting
- Check HTTPS requirement (Secure flag)
- Verify domain configuration
- Check browser cookie policies

#### Redis Connection Issues
- Verify `REDIS_URL` format
- Check Redis service status
- Review network connectivity

#### Session Persistence Issues
- Verify `SECRET_KEY` consistency
- Check session storage permissions
- Review session configuration

### Debug Commands
```bash
# Test cookie attributes
python test_cookie_hardening.py

# Check Redis connection
redis-cli -u $REDIS_URL ping

# Verify environment variables
env | grep -E "(SESSION|REDIS|SECRET)"
```

## Future Enhancements

### Potential Improvements
1. **SameSite=Strict**: If cross-site functionality allows
2. **Session Fingerprinting**: Additional session validation
3. **Rate Limiting**: Session creation rate limits
4. **Audit Logging**: Session creation/destruction logs
5. **Automatic Rotation**: Periodic session rotation

### Security Considerations
- Monitor for new cookie security standards
- Stay updated on session management best practices
- Consider implementing session analytics
- Plan for session migration strategies

## Compliance Notes

### GDPR Considerations
- Session data retention policies
- User consent for session storage
- Right to be forgotten implementation

### Security Standards
- OWASP Session Management Guidelines
- NIST Digital Identity Guidelines
- Web Security Standards (OWASP Top 10)

## Conclusion

This implementation significantly improves the security posture of the mdraft application by:

1. **Reducing session exposure time** through shorter TTLs
2. **Preventing common attacks** with proper cookie attributes
3. **Implementing session rotation** to prevent fixation
4. **Adding server-side storage** for better control
5. **Providing configuration flexibility** for different environments

The changes are backward compatible and can be deployed incrementally. Monitor the application after deployment to ensure proper functionality and security.
