# Runtime Checklist

This document tracks critical runtime dependencies and deployment steps to ensure consistent, stable deployments.

## Pinned Dependencies

- **Pinned Python via runtime.txt -> 3.11.11**
- **Pinned psycopg2-binary -> 2.9.9**

## Deployment Steps

- **After push: Clear build cache on Render and Manual Deploy.**

## Notes

- Python 3.11.11 provides stable C API for compiled extensions
- psycopg2-binary 2.9.9 is the last version with full Python 3.11 support
- Clearing build cache ensures clean dependency resolution
