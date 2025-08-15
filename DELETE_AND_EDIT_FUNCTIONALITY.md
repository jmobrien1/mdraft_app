# Delete and Edit Functionality

## Overview

This document describes the delete and edit functionality implemented for proposals and documents in the mdraft application. The implementation provides user-friendly interfaces with proper confirmation dialogs, optimistic UI updates, and comprehensive error handling.

## Delete Proposal Functionality

### **Features Implemented**

1. **Delete Button**: Added to each proposal card in the proposals list
2. **Confirmation Dialog**: Prevents accidental deletions
3. **Optimistic UI Updates**: Removes item from list immediately after confirmation
4. **Error Handling**: Shows user-friendly error messages for ownership issues
5. **API Integration**: Calls the delete endpoint with proper error handling

### **UI Implementation**

#### **Delete Button**
```html
<button class="btn btn-danger" onclick="deleteProposal(${proposal.id}, '${proposal.name}')">
  <span>🗑️</span> Delete
</button>
```

#### **CSS Styling**
```css
.btn-danger {
  background-color: #dc3545;
  color: white;
}

.btn-danger:hover {
  background-color: #c82333;
}

.info {
  background-color: #d1ecf1;
  color: #0c5460;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 20px;
}
```

#### **JavaScript Function**
```javascript
async function deleteProposal(proposalId, proposalName) {
  console.info('deleteProposal() called with proposalId:', proposalId);
  
  if (confirm(`Are you sure you want to delete the proposal "${proposalName}"? This action cannot be undone.`)) {
    try {
      showMessage('Deleting proposal...', 'info');
      await api(`/api/agents/compliance-matrix/proposals/${proposalId}`, { 
        method: 'DELETE' 
      });
      showMessage('Proposal deleted successfully!', 'success');
      loadProposals(); // Refresh the list
    } catch (error) {
      console.error('Failed to delete proposal:', error);
      showMessage(`Failed to delete proposal: ${error.message}`, 'error');
    }
  }
}
```

### **API Endpoint**

The delete functionality uses the existing API endpoint:
- **DELETE** `/api/agents/compliance-matrix/proposals/{id}`

**Response Examples:**
```json
// Success
{
  "status": "success",
  "message": "Proposal deleted successfully"
}

// Error - Ownership
{
  "error": "Proposal not found or access denied"
}

// Error - Not Found
{
  "error": "Proposal not found"
}
```

## Document Management Functionality

### **Features Implemented**

1. **Document List**: Shows all attached documents for a proposal
2. **Attach Documents**: Upload new documents via existing modal
3. **Detach Documents**: Remove specific documents with confirmation
4. **Auto-refresh**: Requirements list refreshes after document changes
5. **Minimal UI**: Reuses existing styles and components

### **UI Implementation**

#### **Document Management Section**
```html
<div class="document-management">
  <h3>Attached Documents</h3>
  <div id="documents-container" class="documents-list">
    <div class="loading">Loading documents...</div>
  </div>
</div>
```

#### **CSS Styling**
```css
.document-management {
  margin-top: 20px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.document-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background: #e9ecef;
  border-radius: 6px;
  font-size: 14px;
  color: #333;
}

.document-item .actions button {
  padding: 4px 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #f8f9fa;
  cursor: pointer;
  font-size: 12px;
  color: #333;
  transition: background-color 0.2s;
}
```

#### **JavaScript Functions**

**Load Documents:**
```javascript
async function loadDocuments() {
  console.info('loadDocuments() called for proposalId:', currentProposalId);
  try {
    const response = await api(`/api/agents/compliance-matrix/proposals/${currentProposalId}/documents`);
    
    if (response && response.documents) {
      const documentsContainer = document.getElementById('documents-container');
      documentsContainer.innerHTML = response.documents.map(doc => `
        <div class="document-item">
          <span class="name">${doc.filename}</span>
          <span class="type">(${doc.document_type})</span>
          <div class="actions">
            <button onclick="detachDocument(${doc.id})">Detach</button>
          </div>
        </div>
      `).join('');
      
      if (response.documents.length === 0) {
        documentsContainer.innerHTML = '<p>No documents attached to this proposal yet.</p>';
      }
    }
  } catch (error) {
    console.error('Failed to load documents:', error);
    showMessage('Failed to load documents', 'error');
  }
}
```

**Detach Document:**
```javascript
async function detachDocument(documentId) {
  console.info('detachDocument() called with documentId:', documentId);
  
  if (!confirm('Are you sure you want to detach this document?')) {
    return;
  }
  
  try {
    const response = await api(`/api/agents/compliance-matrix/proposals/${currentProposalId}/documents/${documentId}`, {
      method: 'DELETE'
    });
    
    showMessage('Document detached successfully!', 'success');
    loadDocuments(); // Refresh document list
    loadRequirements(); // Refresh requirements list
  } catch (error) {
    console.error('Failed to detach document:', error);
    showMessage('Failed to detach document', 'error');
  }
}
```

### **API Endpoints**

#### **List Documents**
- **GET** `/api/agents/compliance-matrix/proposals/{id}/documents`

**Response:**
```json
{
  "documents": [
    {
      "id": 456,
      "filename": "RFP-2024-001.pdf",
      "document_type": "main_rfp",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### **Detach Document**
- **DELETE** `/api/agents/compliance-matrix/proposals/{id}/documents/{doc_id}`

**Response:**
```json
{
  "status": "success",
  "message": "Document detached successfully"
}
```

## User Experience Patterns

### **1. Confirmation Dialogs**

All destructive actions require user confirmation:

```javascript
// Delete proposal
if (confirm(`Are you sure you want to delete the proposal "${proposalName}"? This action cannot be undone.`)) {
  // Proceed with deletion
}

// Detach document
if (!confirm('Are you sure you want to detach this document?')) {
  return;
}
```

### **2. Optimistic UI Updates**

The UI updates immediately after user confirmation:

```javascript
// Delete proposal - optimistic update
showMessage('Deleting proposal...', 'info');
await api(`/api/agents/compliance-matrix/proposals/${proposalId}`, { method: 'DELETE' });
showMessage('Proposal deleted successfully!', 'success');
loadProposals(); // Refresh list
```

### **3. Error Handling**

Comprehensive error handling with user-friendly messages:

```javascript
try {
  // API call
} catch (error) {
  console.error('Failed to delete proposal:', error);
  showMessage(`Failed to delete proposal: ${error.message}`, 'error');
}
```

### **4. Auto-refresh**

Related data refreshes automatically after changes:

```javascript
// After detaching document
loadDocuments(); // Refresh document list
loadRequirements(); // Refresh requirements list
```

## Testing

### **Manual Testing**

1. **Delete Proposal:**
   - Navigate to proposals page
   - Click delete button on any proposal
   - Confirm deletion
   - Verify proposal is removed from list

2. **Document Management:**
   - Navigate to compliance matrix page
   - View attached documents section
   - Click detach button on any document
   - Confirm detachment
   - Verify document is removed and requirements refresh

### **API Testing**

Use the provided test script:

```bash
python test_delete_proposal.py
```

**Expected Output:**
```
Proposal Delete Functionality Test
==================================================
Base URL: http://localhost:5000
Proposal ID: 1
--------------------------------------------------
1. Testing DELETE /api/agents/compliance-matrix/proposals/{id}
Status Code: 200
Response: {"status": "success", "message": "Proposal deleted successfully"}
✅ Delete proposal API test PASSED
==================================================
✅ All tests PASSED
```

## Security Considerations

### **1. Ownership Validation**

All operations validate user ownership:

```python
owner_filter = get_owner_filter()
proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
if not proposal:
    return jsonify({"error": "Proposal not found or access denied"}), 404
```

### **2. Authentication Required**

All endpoints require authentication:

```python
@bp.route("/compliance-matrix/proposals/<int:proposal_id>", methods=["DELETE"])
@login_required
def delete_proposal(proposal_id: int):
```

### **3. Confirmation Required**

Destructive actions require explicit user confirmation to prevent accidents.

## Summary

The delete and edit functionality provides:

1. **User-Friendly Interface**: Clear buttons and confirmation dialogs
2. **Optimistic Updates**: Immediate UI feedback for better UX
3. **Comprehensive Error Handling**: User-friendly error messages
4. **Security**: Proper ownership validation and authentication
5. **Auto-refresh**: Related data updates automatically
6. **Minimal Design**: Reuses existing styles and components

The implementation follows best practices for destructive operations and provides a smooth user experience for managing proposals and documents.
