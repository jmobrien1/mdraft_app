# API Endpoints Inventory

## Proposals and Requirements API

### Current Endpoints

| Method | Path | Auth | Purpose | Response Shape | Status |
|--------|------|------|---------|----------------|--------|
| **Proposals** |
| GET | `/api/agents/compliance-matrix/proposals` | `@login_required` | List all proposals | `{"proposals": [...]}` | ✅ **EXISTS** |
| POST | `/api/agents/compliance-matrix/proposals` | `@login_required` | Create new proposal | `{"id": 123, "name": "...", ...}` | ✅ **EXISTS** |
| GET | `/api/agents/compliance-matrix/proposals/{id}` | `@login_required` | Get proposal detail | `{"id": 123, "name": "...", ...}` | ✅ **ADDED** |
| DELETE | `/api/agents/compliance-matrix/proposals/{id}` | `@login_required` | Delete proposal | `{"status": "success", "message": "..."}` | ✅ **ADDED** |
| **Requirements** |
| GET | `/api/agents/compliance-matrix/proposals/{id}/requirements` | `@login_required` | List requirements | `{"proposal_id": 123, "total_requirements": 45, "requirements": [...]}` | ✅ **EXISTS** |
| PUT | `/api/agents/compliance-matrix/requirements/{id}` | `@login_required` | Update requirement | `{"id": "R-1", "assigned_owner": "...", ...}` | ✅ **EXISTS** |
| **Documents** |
| POST | `/api/agents/compliance-matrix/proposals/{id}/documents` | `@login_required` | Upload document | `{"id": 456, "filename": "...", ...}` | ✅ **EXISTS** |
| DELETE | `/api/agents/compliance-matrix/proposals/{id}/documents/{doc_id}` | `@login_required` | Detach document | `{"status": "success", "message": "..."}` | ✅ **ADDED** |
| **Export** |
| GET | `/api/agents/compliance-matrix/proposals/{id}/export` | `@login_required` | Export matrix | File download | ✅ **EXISTS** |
| **Agent Operations** |
| POST | `/api/agents/compliance-matrix/run` | `@login_required` | Run compliance agent | `{"status": "success", "total_requirements": 45, ...}` | ✅ **EXISTS** |

### Response Formats

#### Proposal Object
```json
{
  "id": 123,
  "name": "RFP-2024-001",
  "description": "Software development services RFP",
  "status": "active",
  "user_id": 456,
  "visitor_session_id": null,
  "document_count": 3,
  "requirement_count": 45,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "is_anonymous": false
}
```

#### Requirement Object
```json
{
  "id": "R-1",
  "text": "The contractor shall provide...",
  "section_ref": "C.1.2",
  "page_number": 5,
  "source_document": "RFP-2024-001.pdf",
  "assigned_owner": "John Doe",
  "status": "pending",
  "notes": "Working on this requirement",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### Document Object
```json
{
  "id": 456,
  "filename": "RFP-2024-001.pdf",
  "document_type": "main_rfp",
  "status": "completed",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Error Response Format

All API endpoints return consistent JSON error responses:

```json
{
  "error": "error_code",
  "detail": "Human-readable error message"
}
```

Common error codes:
- `bad_request` (400) - Invalid request data
- `unauthorized` (401) - Login required
- `forbidden` (403) - Access denied
- `not_found` (404) - Resource not found
- `internal_server_error` (500) - Server error

### Authentication

All endpoints require authentication via `@login_required` decorator. The system supports both:
- Authenticated users (via `user_id`)
- Anonymous users (via `visitor_session_id`)

### Ownership Validation

All endpoints validate ownership using `get_owner_filter()` which ensures users can only access their own proposals and data.

### Idempotency

- **Document Upload**: Re-uploading the same document to the same proposal is handled gracefully
- **Requirement Updates**: Multiple updates to the same requirement are safe
- **Proposal Operations**: Delete operations are idempotent (safe to call multiple times)

### Database Transactions

All endpoints use proper database transactions with rollback on errors to ensure data consistency.

## Implementation Notes

### Added Endpoints

1. **GET `/api/agents/compliance-matrix/proposals/{id}`**
   - Returns detailed proposal information including counts
   - Validates ownership before returning data
   - Includes document and requirement counts

2. **DELETE `/api/agents/compliance-matrix/proposals/{id}`**
   - Deletes proposal and all associated data (cascade)
   - Validates ownership before deletion
   - Returns success message

3. **DELETE `/api/agents/compliance-matrix/proposals/{id}/documents/{doc_id}`**
   - Detaches document from proposal (doesn't delete file)
   - Validates both proposal and document ownership
   - Returns success message

### Enhanced Error Handling

- Added comprehensive error handlers for 400, 401, 403, 404, 500 status codes
- All API endpoints return structured JSON errors
- Non-API routes continue to use normal HTML error handling
- Added database rollback on errors for data consistency

### Validation Improvements

- Enhanced input validation for proposal creation
- Added document type validation for uploads
- Improved error messages for better debugging
- Added proper string trimming and validation
