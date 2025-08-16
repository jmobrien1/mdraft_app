# SQLAlchemy Engine Pooling Configuration for Render

## Overview

This document describes the SQLAlchemy engine pooling configuration implemented for optimal performance on Render's PaaS environment. The configuration is designed to prevent "connection closed" errors and maintain stable database connections under load.

## Configuration Settings

The pooling configuration is defined in `app/__init__.py` under the `SQLALCHEMY_ENGINE_OPTIONS` setting:

```python
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,      # Validate connections before use
    "pool_size": 5,             # Maintain 5 persistent connections
    "max_overflow": 5,          # Allow 5 additional connections when pool is full
    "pool_recycle": 1800,       # Recycle connections after 30 minutes
    "pool_timeout": 30,         # Wait up to 30 seconds for available connection
    "echo": False,              # Disable SQL echo in production
}
```

## Parameter Details

### `pool_pre_ping: True`
- **Purpose**: Validates database connections before use
- **Benefit**: Prevents "connection closed" errors by detecting stale connections
- **How it works**: Sends a lightweight query (`SELECT 1`) before using a connection
- **Impact**: Slight performance overhead, but prevents connection failures

### `pool_size: 5`
- **Purpose**: Maintains 5 persistent connections in the pool
- **Benefit**: Reduces connection establishment overhead
- **Rationale**: Balanced for Render's typical web service load
- **Consideration**: Too high can exhaust database connections; too low can cause waiting

### `max_overflow: 5`
- **Purpose**: Allows up to 5 additional connections when the pool is full
- **Benefit**: Handles traffic spikes without blocking requests
- **Behavior**: Connections beyond pool_size are created on-demand and destroyed after use
- **Total max connections**: pool_size + max_overflow = 10 connections

### `pool_recycle: 1800`
- **Purpose**: Recycles connections after 30 minutes (1800 seconds)
- **Benefit**: Prevents issues with long-lived connections that may become stale
- **Rationale**: Render's infrastructure may close idle connections
- **Impact**: Automatic connection refresh without application restarts

### `pool_timeout: 30`
- **Purpose**: Maximum time to wait for an available connection
- **Benefit**: Prevents indefinite waiting during high load
- **Behavior**: Raises `QueuePool` exception if no connection available within 30 seconds
- **Error handling**: Should be caught and handled gracefully

### `echo: False`
- **Purpose**: Disables SQL query logging in production
- **Benefit**: Reduces log noise and improves performance
- **Usage**: Set to `True` only for debugging in development

## Monitoring and Observability

### Pool Statistics Logging

The application includes automatic pool statistics logging for monitoring:

```python
@app.after_request
def _log_pool_stats(resp):
    """Log connection pool statistics for monitoring."""
    try:
        if hasattr(db.engine, 'pool'):
            pool = db.engine.pool
            app.logger.debug(
                "DB Pool Stats",
                extra={
                    "pool_size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": pool.invalid()
                }
            )
    except Exception as e:
        app.logger.debug(f"Could not log pool stats: {e}")
    return resp
```

### Key Metrics to Monitor

1. **`checked_out`**: Number of connections currently in use
2. **`checked_in`**: Number of connections available in the pool
3. **`overflow`**: Number of connections created beyond pool_size
4. **`invalid`**: Number of connections that failed validation

### Log Analysis

Monitor these patterns in your logs:

- **High `checked_out` values**: Indicates high database load
- **Frequent `overflow`**: Consider increasing `pool_size`
- **High `invalid` counts**: May indicate connection stability issues
- **Connection timeout errors**: May need to adjust `pool_timeout`

## Testing

### Validation Script

Use the provided test script to validate your configuration:

```bash
python test_pool_config.py
```

This script tests:
- Basic connectivity
- Pool configuration parameters
- Concurrent connection handling
- Load simulation

### Manual Testing

You can also test manually in your application:

```python
from app import create_app, db

app = create_app()
with app.app_context():
    # Check pool configuration
    pool = db.engine.pool
    print(f"Pool size: {pool.size()}")
    print(f"Pool overflow: {pool.overflow()}")
    print(f"Pool pre-ping: {pool.pre_ping}")
    
    # Test connection
    result = db.session.execute(text("SELECT 1"))
    print(f"Connection test: {result.scalar()}")
```

## Troubleshooting

### Common Issues

1. **"Connection closed" errors**
   - Ensure `pool_pre_ping=True` is set
   - Check if `pool_recycle` is appropriate for your environment

2. **Connection timeouts**
   - Increase `pool_timeout` if requests are waiting too long
   - Consider increasing `pool_size` if load is consistently high

3. **Database connection exhaustion**
   - Monitor `max_overflow` usage
   - Consider reducing `pool_size` or `max_overflow`
   - Check for connection leaks in your application code

4. **Performance issues**
   - Monitor pool statistics in logs
   - Adjust `pool_size` based on actual usage patterns
   - Consider connection pooling at the database level (if using PostgreSQL)

### Performance Tuning

1. **For high-traffic applications**:
   ```python
   "pool_size": 10,
   "max_overflow": 10,
   ```

2. **For low-traffic applications**:
   ```python
   "pool_size": 3,
   "max_overflow": 3,
   ```

3. **For applications with long-running queries**:
   ```python
   "pool_timeout": 60,  # Increase timeout
   "pool_recycle": 3600,  # Recycle every hour
   ```

## Best Practices

1. **Monitor pool statistics regularly** in production logs
2. **Set appropriate timeouts** to prevent indefinite waiting
3. **Use connection pooling** at the database level when possible
4. **Test under load** before deploying to production
5. **Adjust settings** based on actual usage patterns and monitoring data
6. **Handle connection errors gracefully** in your application code

## Render-Specific Considerations

1. **Automatic scaling**: Render may restart your application, so connections will be recreated
2. **Database limits**: Be aware of your database's connection limits
3. **Health checks**: Render's health checks should use minimal database connections
4. **Logging**: Use structured logging for better monitoring in Render's dashboard

## Conclusion

This pooling configuration provides a robust foundation for database connectivity on Render. The settings are optimized for typical web application workloads while providing flexibility for different traffic patterns. Regular monitoring and adjustment based on actual usage will ensure optimal performance.
