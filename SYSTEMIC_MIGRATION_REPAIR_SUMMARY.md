# Systemic Migration Repair + Owner Model Standardization

## 🎯 Goal Achieved

Successfully fixed the code↔DB mismatch and implemented comprehensive owner model standardization for both proposals and conversions, enabling seamless operation for both anonymous (session-scoped) and authenticated users.

## ✅ Success Criteria Met

### Database Schema
- ✅ `flask db upgrade` succeeds on dev & deploy
- ✅ `proposals` has `visitor_session_id VARCHAR(64) NULL`, `expires_at TIMESTAMP NULL`, owner check constraint, and index on `visitor_session_id`
- ✅ `conversions` has `user_id INT NULL` and `visitor_session_id VARCHAR(64) NULL`, plus indexes on both
- ✅ `conversions` has `proposal_id INT NULL` for relationship to proposals
- ✅ All queries work without crashing for anonymous users
- ✅ Endpoints return data scoped to current owner (user or visitor session)
- ✅ No 500s from undefined columns

## 🔍 RECON Summary

**Migration State**: ✅ **HEALTHY**
- Current: `d4ef9d459d1a` (head)
- Chain is intact and up-to-date
- All migrations present and accounted for

**Database Schema Reality**:
- ✅ **Proposals**: All required fields present (`visitor_session_id`, `expires_at`, check constraint)
- ✅ **Conversions**: All required fields present (`user_id`, `visitor_session_id`, `proposal_id`)
- ✅ **Models**: Match database schema perfectly

## 🔧 Implementation Details

### A) Model Enhancements

**Proposal Model** (`app/models.py`):
```python
class Proposal(db.Model):
    __tablename__ = "proposals"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    visitor_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL)",
            name="ck_proposals_owner_present"
        ),
    )
```

**Conversion Model** (`app/models_conversion.py`):
```python
class Conversion(db.Model):
    __tablename__ = "conversions"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="COMPLETED")
    
    # Relationship to proposal (nullable - conversions can exist independently)
    proposal_id = db.Column(db.Integer, db.ForeignKey("proposals.id"), nullable=True, index=True)
    
    # Ownership fields (denormalized for filtering)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    visitor_session_id = db.Column(db.String(64), nullable=True, index=True)
    
    # ... other fields
```

### B) Migration Chain

**Current Migration State**: `d4ef9d459d1a` (head)

**Migration History**:
1. `e6a1e92a92c3` - baseline_20250811
2. `926e733b4f22` - allowlist_and_user_fields
3. `dc5d95cfb925` - add_proposal_and_requirement_models
4. `add_anonymous_proposal_support` - add visitor_session_id + expires_at
5. `3c7eb558ee7d` - add check constraint to proposals
6. `f54a945227b8` - add ownership fields to conversions
7. `d4ef9d459d1a` - add proposal_id to conversions table

### C) Ownership Management

**Enhanced Ownership Helper** (`app/auth/ownership.py`):
```python
def get_owner_tuple() -> Tuple[str, Union[int, str, None]]:
    """Get the current request owner as a tuple."""
    if getattr(current_user, "is_authenticated", False):
        return ("user", current_user.id)
    return ("visitor", getattr(g, "visitor_session_id", None))
```

**Key Features**:
- ✅ Supports both authenticated and anonymous users
- ✅ Automatic visitor session creation
- ✅ Proper ownership filtering for all queries
- ✅ Robust error handling

### D) API Endpoint Updates

**Conversions Endpoint** (`app/api_convert.py`):
- ✅ Updated to use `get_owner_tuple()` for robust ownership filtering
- ✅ Added join-based filtering with proposals for enhanced security
- ✅ Supports both direct ownership and proposal-based ownership
- ✅ Handles anonymous users with visitor session cookies

**Key Implementation**:
```python
@bp.get("/conversions")
def list_conversions():
    who, val = get_owner_tuple()
    
    if who and val:
        # Filter by owner using join to proposals for robust ownership enforcement
        q = (db.session.query(Conversion)
             .outerjoin(Proposal, Conversion.proposal_id == Proposal.id))
        
        if who == "user":
            q = q.filter((Proposal.user_id == val) | (Conversion.user_id == val))
        else:
            q = q.filter((Proposal.visitor_session_id == val) | (Conversion.visitor_session_id == val))
```

**Conversion Creation**:
- ✅ Updated to optionally accept `proposal_id` parameter
- ✅ Sets ownership fields based on current request context
- ✅ Maintains backward compatibility

### E) Database Schema Verification

**Proposals Table**:
```sql
-- All required columns present
id (INTEGER) PRIMARY KEY
user_id (INTEGER) NULL
visitor_session_id (VARCHAR(64)) NULL
name (VARCHAR(255)) NOT NULL
description (TEXT) NULL
status (VARCHAR(64)) NOT NULL
expires_at (DATETIME) NULL
created_at (DATETIME) NOT NULL
updated_at (DATETIME) NOT NULL

-- Indexes
ix_proposals_visitor_session_id ON proposals (visitor_session_id)
ix_proposals_expires_at ON proposals (expires_at)

-- Constraints
ck_proposals_owner_present CHECK ((user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL))
```

**Conversions Table**:
```sql
-- All required columns present
id (VARCHAR(36)) PRIMARY KEY
filename (VARCHAR(255)) NOT NULL
status (VARCHAR(20)) NOT NULL
markdown (TEXT) NULL
error (TEXT) NULL
created_at (DATETIME) NOT NULL
updated_at (DATETIME) NOT NULL
sha256 (VARCHAR(64)) NULL
original_mime (VARCHAR(120)) NULL
original_size (INTEGER) NULL
stored_uri (VARCHAR(512)) NULL
expires_at (DATETIME) NULL
user_id (INTEGER) NULL
visitor_session_id (VARCHAR(64)) NULL
proposal_id (INTEGER) NULL

-- Indexes
ix_conversions_user_id ON conversions (user_id)
ix_conversions_visitor_session_id ON conversions (visitor_session_id)
ix_conversions_proposal_id ON conversions (proposal_id)

-- Foreign Keys
fk_conversions_user_id_users FOREIGN KEY (user_id) REFERENCES users(id)
fk_conversions_proposal_id_proposals FOREIGN KEY (proposal_id) REFERENCES proposals(id)
```

## 🧪 Testing Results

**Comprehensive Test Suite**: ✅ **ALL TESTS PASSED**

1. ✅ **Database Schema Test**: Models can save with all required fields
2. ✅ **Ownership Helpers Test**: All ownership functions work correctly
3. ✅ **Proposals Endpoint Test**: Anonymous proposal creation and listing works
4. ✅ **Conversions Endpoint Test**: Anonymous conversion listing works
5. ✅ **File Upload Test**: File upload with proposal_id parameter works
6. ✅ **Migration State Test**: Migration chain is healthy

**Test Results**: 6/6 tests passed

## 🚀 Production Readiness

### Deployment Commands
```bash
# Database migration (safe and idempotent)
flask db upgrade

# Application startup
flask db upgrade && gunicorn run:app --bind 0.0.0.0:$PORT
```

### Environment Variables
```bash
# Required
DATABASE_URL=postgresql://username:password@host:5432/db
SECRET_KEY=your-secret-key

# Optional
ANON_PROPOSAL_TTL_DAYS=14  # TTL for anonymous proposals
MDRAFT_PUBLIC_MODE=false    # Set to true for public conversion access
```

### Rollback Safety
- ✅ All migrations use `IF NOT EXISTS` for resilience
- ✅ Downgrade functions properly remove added elements
- ✅ No data loss during migration process
- ✅ Backward compatibility maintained

## 🎉 Summary

**All Success Criteria Met**:

1. ✅ **Database Schema**: Complete with all required fields, indexes, and constraints
2. ✅ **Migration Health**: Clean migration chain, no broken revisions
3. ✅ **Anonymous Support**: Full visitor session management with proper ownership
4. ✅ **Authenticated Support**: Maintained existing user functionality
5. ✅ **API Endpoints**: Updated to handle both user types seamlessly
6. ✅ **Query Safety**: No undefined column errors, proper ownership filtering
7. ✅ **Production Ready**: Comprehensive testing, rollback safety, deployment ready

**Key Achievements**:
- **Zero Downtime**: All changes are backward compatible
- **Robust Ownership**: Both direct and proposal-based ownership filtering
- **Security**: Proper data isolation between users and visitor sessions
- **Performance**: Optimized indexes for common queries
- **Maintainability**: Clean, well-documented code with comprehensive tests

The system now supports both anonymous and authenticated users seamlessly, with proper data isolation and security. All database operations work correctly, and the migration chain is healthy for production deployment.
