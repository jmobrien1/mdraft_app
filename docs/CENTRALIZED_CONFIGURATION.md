# Centralized Configuration System

This document describes the centralized configuration system for the mdraft application, which consolidates all magic numbers, rate limits, file size limits, and other configuration values into a single, manageable location.

## Overview

The centralized configuration system provides:

- **Single Source of Truth**: All configuration values are defined in `app/config.py`
- **Environment Variable Overrides**: All values can be overridden via environment variables
- **Type Safety**: Uses dataclasses for structured configuration
- **Helper Functions**: Convenient access methods for common configuration needs
- **Documentation**: Self-documenting configuration with clear defaults

## Configuration Structure

### File Size Limits (`FileSizeLimits`)

```python
@dataclass
class FileSizeLimits:
    PDF_MB: int = 25
    OFFICE_MB: int = 20
    TEXT_MB: int = 5
    BINARY_MB: int = 10  # Fallback for unknown types
```

**Environment Variables:**
- `MAX_UPLOAD_PDF_MB` (default: 25)
- `MAX_UPLOAD_OFFICE_MB` (default: 20)
- `MAX_UPLOAD_TEXT_MB` (default: 5)
- `MAX_UPLOAD_BINARY_MB` (default: 10)

### Rate Limits (`RateLimits`)

```python
@dataclass
class RateLimits:
    GLOBAL_PER_MINUTE: str = "120 per minute"
    CONVERT_PER_MINUTE: str = "20 per minute"
    AI_PER_MINUTE: str = "10 per minute"
    ANON_PER_MINUTE: str = "20"
    ANON_PER_DAY: str = "200"
```

**Environment Variables:**
- `GLOBAL_RATE_LIMIT` (default: "120 per minute")
- `CONVERT_RATE_LIMIT_DEFAULT` (default: "20 per minute")
- `AI_RATE_LIMIT_DEFAULT` (default: "10 per minute")
- `ANON_RATE_LIMIT_PER_MINUTE` (default: "20")
- `ANON_RATE_LIMIT_PER_DAY` (default: "200")

### Billing Configuration (`BillingConfig`)

```python
@dataclass
class BillingConfig:
    ENABLED: bool = False
    PRICE_PER_PAGE_USD: str = "0.0000"
    STRIPE_PRICE_PRO: Optional[str] = None
```

**Environment Variables:**
- `BILLING_ENABLED` (default: "0" → False)
- `PRICING_DOC_OCR_PER_PAGE_USD` (default: "0.0000")
- `STRIPE_PRICE_PRO` (default: None)

### Security Configuration (`SecurityConfig`)

```python
@dataclass
class SecurityConfig:
    SESSION_LIFETIME_DAYS: int = 7
    CSRF_TIMEOUT_HOURS: int = 1
    ANON_PROPOSAL_TTL_DAYS: int = 14
```

**Environment Variables:**
- `SESSION_LIFETIME_DAYS` (default: 7)
- `CSRF_TIMEOUT_HOURS` (default: 1)
- `ANON_PROPOSAL_TTL_DAYS` (default: 14)

## Usage

### Basic Usage

```python
from app.config import get_config

# Get the global configuration instance
config = get_config()

# Access file size limits
pdf_limit = config.file_sizes.PDF_BYTES
office_limit = config.file_sizes.OFFICE_BYTES

# Access rate limits
global_limit = config.rate_limits.GLOBAL_PER_MINUTE
convert_limit = config.rate_limits.CONVERT_PER_MINUTE

# Access billing configuration
billing_enabled = config.billing.ENABLED
price_per_page = config.billing.PRICE_PER_PAGE_USD
```

### Helper Functions

```python
from app.config import get_file_size_limit, get_rate_limit

# Get file size limit for a specific category
pdf_limit = get_file_size_limit("pdf")      # Returns bytes
office_limit = get_file_size_limit("office") # Returns bytes
text_limit = get_file_size_limit("text")     # Returns bytes

# Get rate limit for a specific type
global_limit = get_rate_limit("global")      # Returns "120 per minute"
convert_limit = get_rate_limit("convert")    # Returns "20 per minute"
ai_limit = get_rate_limit("ai")              # Returns "10 per minute"
```

### Flask Application Integration

The configuration is automatically integrated into Flask's `app.config`:

```python
def create_app() -> Flask:
    app = Flask(__name__)
    
    # Get centralized configuration
    config = get_config()
    
    # Apply configuration to Flask app
    app.config.update(config.to_dict())
    
    # Configuration is now available as app.config["MAX_UPLOAD_PDF_MB"], etc.
```

## Migration from Magic Numbers

### Before (Magic Numbers Scattered)

```python
# In app/utils/validation.py
SIZE_LIMITS = {
    "pdf": 25 * 1024 * 1024,      # 25 MB
    "office": 20 * 1024 * 1024,   # 20 MB
    "text": 5 * 1024 * 1024,      # 5 MB
}

# In app/security.py
MAX_BY_TYPE = {
    "text": 5 * 1024 * 1024,       # 5 MB
    "doc":  20 * 1024 * 1024,      # 20 MB
    "bin":  10 * 1024 * 1024,      # 10 MB fallback
}

# In app/__init__.py
app.config.setdefault("MAX_CONTENT_LENGTH", 25 * 1024 * 1024)  # 25 MB hard cap

# In app/routes.py
@limiter.limit(os.getenv("CONVERT_RATE_LIMIT_DEFAULT", "20 per minute"))

# In app/api_estimate.py
max_size_bytes = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
```

### After (Centralized Configuration)

```python
# In app/utils/validation.py
from ..config import get_config
config = get_config()
self.SIZE_LIMITS = {
    "pdf": config.get_file_size_limit("pdf"),
    "office": config.get_file_size_limit("office"),
    "text": config.get_file_size_limit("text"),
}

# In app/security.py
from .config import get_config
config = get_config()
MAX_BY_TYPE = {
    "text": config.get_file_size_limit("text"),
    "doc": config.get_file_size_limit("office"),
    "bin": config.get_file_size_limit("binary"),
}

# In app/__init__.py
config = get_config()
app.config.update(config.to_dict())  # Includes MAX_CONTENT_LENGTH

# In app/routes.py
@limiter.limit("20 per minute")  # Rate limit configured in centralized config

# In app/api_estimate.py
from .config import get_config
config = get_config()
max_size_bytes = config.get_file_size_limit("binary")
```

## Environment Variable Reference

### File Upload Limits
| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_PDF_MB` | 25 | Maximum PDF file size in MB |
| `MAX_UPLOAD_OFFICE_MB` | 20 | Maximum Office document size in MB |
| `MAX_UPLOAD_TEXT_MB` | 5 | Maximum text file size in MB |
| `MAX_UPLOAD_BINARY_MB` | 10 | Maximum binary file size in MB (fallback) |

### Rate Limiting
| Variable | Default | Description |
|----------|---------|-------------|
| `GLOBAL_RATE_LIMIT` | "120 per minute" | Global rate limit for all endpoints |
| `CONVERT_RATE_LIMIT_DEFAULT` | "20 per minute" | Rate limit for conversion endpoints |
| `AI_RATE_LIMIT_DEFAULT` | "10 per minute" | Rate limit for AI generation endpoints |
| `ANON_RATE_LIMIT_PER_MINUTE` | "20" | Anonymous user rate limit per minute |
| `ANON_RATE_LIMIT_PER_DAY` | "200" | Anonymous user rate limit per day |

### Billing
| Variable | Default | Description |
|----------|---------|-------------|
| `BILLING_ENABLED` | "0" | Enable billing features (0/1) |
| `PRICING_DOC_OCR_PER_PAGE_USD` | "0.0000" | Price per page for OCR processing |
| `STRIPE_PRICE_PRO` | None | Stripe price ID for Pro subscription |

### Security
| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_LIFETIME_DAYS` | 7 | Session lifetime in days |
| `CSRF_TIMEOUT_HOURS` | 1 | CSRF token timeout in hours |
| `ANON_PROPOSAL_TTL_DAYS` | 14 | Anonymous proposal TTL in days |

## Testing

Run the configuration test to verify everything is working:

```bash
python3 test_config.py
```

This will output all configuration values and test environment variable overrides.

## Benefits

1. **Maintainability**: All configuration in one place
2. **Consistency**: No more scattered magic numbers
3. **Flexibility**: Easy environment variable overrides
4. **Documentation**: Self-documenting configuration structure
5. **Type Safety**: Dataclasses provide type hints and validation
6. **Testing**: Easy to test configuration values
7. **Deployment**: Simple to adjust limits for different environments

## Future Enhancements

- Add configuration validation (e.g., ensure positive numbers)
- Add configuration schema validation
- Add configuration hot-reloading for development
- Add configuration export/import functionality
- Add configuration documentation generation
