def normalize_db_url(raw: str) -> str:
    """Normalize database URL for SQLAlchemy compatibility.
    
    Handles:
    - PostgreSQL URL normalization (postgres:// -> postgresql://)
    - PostgreSQL driver specification (+psycopg)
    - SQLite URL validation
    
    Args:
        raw: Raw database URL string
        
    Returns:
        Normalized database URL string
    """
    if not raw:
        return raw
    
    url = raw
    
    # Handle PostgreSQL URLs
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    
    # Validate SQLite URLs (should start with sqlite:///)
    if url.startswith("sqlite://"):
        # Ensure proper SQLite URL format
        if not url.startswith("sqlite:///"):
            # Convert relative paths to absolute
            if url.startswith("sqlite://"):
                url = url.replace("sqlite://", "sqlite:///", 1)
    
    return url
