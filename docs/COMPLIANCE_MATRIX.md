# Compliance Matrix Agent

The Compliance Matrix Agent is a powerful AI-driven tool for extracting and managing requirements from RFP (Request for Proposal) documents. It automatically identifies explicit requirements ("shall", "must", "will") from RFP documents, assigns stable IDs, records exact citations, and provides a comprehensive web interface for managing compliance matrices.

## Features

### Core Functionality
- **Multi-file RFP Processing**: Handles main RFP documents plus PWS, SOO, and specification attachments
- **UCF Section Detection**: Automatically detects and processes UCF sections (A-M) in RFP documents
- **Section J Integration**: Follows Section J pointers to process referenced attachments
- **LLM-Powered Extraction**: Uses advanced AI to extract requirements with high accuracy
- **Stable Requirement IDs**: Assigns persistent R-1, R-2, etc. identifiers that survive re-processing
- **Exact Citations**: Records section references, page numbers, and source documents
- **Duplicate Prevention**: Intelligently detects and merges duplicate requirements

### Web Interface
- **Interactive Table**: Sortable, filterable requirements table with real-time updates
- **Owner Assignment**: Assign team members to specific requirements
- **Status Tracking**: Track requirement status (pending, in-progress, completed)
- **Notes & Comments**: Add detailed notes to each requirement
- **Export Options**: Export to CSV, Excel (XLSX), or PDF formats
- **Responsive Design**: Works on desktop, tablet, and mobile devices

### API Integration
- **RESTful API**: Complete API for programmatic access
- **Background Processing**: Asynchronous requirement extraction
- **Batch Operations**: Process multiple documents simultaneously
- **Webhook Support**: Real-time notifications for processing completion

## Architecture

### Data Models

#### Proposal
Represents an RFP package containing multiple documents:
```python
class Proposal:
    id: int
    user_id: int
    name: str
    description: str
    status: str  # active, archived
    created_at: datetime
    updated_at: datetime
```

#### ProposalDocument
Represents individual documents within a proposal:
```python
class ProposalDocument:
    id: int
    proposal_id: int
    filename: str
    document_type: str  # main_rfp, pws, soo, spec
    gcs_uri: str
    parsed_text: str
    section_mapping: str  # JSON mapping of UCF sections
```

#### Requirement
Represents extracted requirements with full citations:
```python
class Requirement:
    id: int
    proposal_id: int
    requirement_id: str  # R-1, R-2, etc.
    requirement_text: str
    section_ref: str  # C.1.2, PWS 3.1, etc.
    page_number: int
    source_document: str
    assigned_owner: str
    status: str  # pending, in_progress, completed
    notes: str
```

### Service Layer

#### RFPDataLayer
Manages multi-file proposal data and document collation:
- **Proposal Management**: Create, update, and manage proposals
- **Document Processing**: Add documents and extract parsed text
- **Section Detection**: Identify UCF sections (A-M) in documents
- **Reference Extraction**: Parse Section J for attachment references
- **Content Collation**: Combine content from multiple documents

#### ComplianceAgent
AI-powered requirement extraction engine:
- **LLM Integration**: Uses Vertex AI/Gemini for intelligent extraction
- **Pattern Matching**: Fallback regex patterns for requirement detection
- **Deduplication**: Smart duplicate detection and merging
- **Citation Extraction**: Automatic section reference and page number detection
- **Confidence Scoring**: Assigns confidence levels to extracted requirements

## Usage Guide

### Getting Started

1. **Create a Proposal**
   ```bash
   curl -X POST /api/agents/compliance-matrix/proposals \
     -H "Content-Type: application/json" \
     -d '{"name": "RFP-2024-001", "description": "Software development services"}'
   ```

2. **Upload Documents**
   ```bash
   curl -X POST /api/agents/compliance-matrix/proposals/{proposal_id}/documents \
     -F "file=@main_rfp.pdf" \
     -F "document_type=main_rfp"
   ```

3. **Run Compliance Agent**
   ```bash
   curl -X POST /api/agents/compliance-matrix/run \
     -H "Content-Type: application/json" \
     -d '{"proposal_id": 123, "target_sections": ["C"], "force_reprocess": false}'
   ```

4. **View Results**
   - Web Interface: Navigate to `/compliance-matrix/{proposal_id}`
   - API: `GET /api/agents/compliance-matrix/proposals/{proposal_id}/requirements`

### Web Interface Workflow

1. **Access Proposals**: Visit `/proposals` to see all your RFP proposals
2. **Create New Proposal**: Click "New Proposal" and provide basic information
3. **Add Documents**: Upload RFP documents (main RFP, PWS, SOO, specs)
4. **Run Agent**: Click "Run Agent" to extract requirements
5. **Review Results**: View the compliance matrix table with extracted requirements
6. **Assign Owners**: Assign team members to specific requirements
7. **Track Progress**: Update status and add notes as work progresses
8. **Export Results**: Download compliance matrix in CSV, Excel, or PDF format

### API Reference

#### Proposals

**Create Proposal**
```http
POST /api/agents/compliance-matrix/proposals
Content-Type: application/json

{
  "name": "RFP-2024-001",
  "description": "Software development services RFP"
}
```

**List Proposals**
```http
GET /api/agents/compliance-matrix/proposals?status=active
```

**Get Proposal Details**
```http
GET /api/agents/compliance-matrix/proposals/{proposal_id}
```

#### Documents

**Add Document**
```http
POST /api/agents/compliance-matrix/proposals/{proposal_id}/documents
Content-Type: multipart/form-data

file: [binary file data]
document_type: main_rfp|pws|soo|spec
```

#### Requirements

**Run Compliance Agent**
```http
POST /api/agents/compliance-matrix/run
Content-Type: application/json

{
  "proposal_id": 123,
  "target_sections": ["C", "PWS"],
  "force_reprocess": false
}
```

**Get Requirements**
```http
GET /api/agents/compliance-matrix/proposals/{proposal_id}/requirements?status=pending&assigned_owner=John
```

**Update Requirement**
```http
PUT /api/agents/compliance-matrix/requirements/{requirement_id}
Content-Type: application/json

{
  "proposal_id": 123,
  "assigned_owner": "John Doe",
  "status": "in_progress",
  "notes": "Working on implementation"
}
```

**Export Compliance Matrix**
```http
GET /api/agents/compliance-matrix/proposals/{proposal_id}/export?format=csv|xlsx|pdf
```

## Configuration

### Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=your_openai_api_key
MDRAFT_MODEL=gpt-4o-mini
MDRAFT_TIMEOUT_SEC=60

# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Document AI Configuration
DOCAI_PROCESSOR_ID=your-docai-processor-id
DOCAI_LOCATION=us

# Storage Configuration
GCS_BUCKET_NAME=mdraft-uploads
GCS_PROCESSED_BUCKET_NAME=mdraft-processed
```

### LLM Prompt Engineering

The compliance agent uses carefully crafted prompts to extract requirements:

```python
def _build_extraction_prompt(self, content: str, section_id: str) -> str:
    return f"""
Extract all explicit requirements from the following RFP section content. 
Focus on statements that use "shall", "must", "will", "required", or similar mandatory language.

Section: {section_id}
Content: {content[:8000]}

Return a JSON array of requirements with the following structure:
{{
  "requirements": [
    {{
      "requirement_text": "The exact requirement text as written in the document",
      "section_ref": "Section reference (e.g., C.1.2, PWS 3.1)",
      "page_number": null,
      "source_document": "Document name or identifier",
      "confidence": 1.0
    }}
  ]
}}

Guidelines:
1. Only extract explicit requirements (shall, must, will, required)
2. Keep the original wording exactly as written
3. Include section references when available
4. Set source_document to the document name if identifiable
5. Set confidence to 1.0 for clear requirements, 0.8 for ambiguous ones
6. Do not include requirements that are already satisfied or optional
"""
```

## Testing

### Running Tests

```bash
# Run all compliance matrix tests
pytest tests/test_compliance_matrix.py -v

# Run specific test class
pytest tests/test_compliance_matrix.py::TestRFPDataLayer -v

# Run with coverage
pytest tests/test_compliance_matrix.py --cov=app.services.rfp_data_layer --cov=app.agents.compliance_agent
```

### Test Coverage

The test suite covers:
- **RFP Data Layer**: Proposal creation, document management, section detection
- **Compliance Agent**: Requirement extraction, deduplication, LLM integration
- **API Endpoints**: All CRUD operations, file uploads, agent execution
- **Edge Cases**: Error handling, duplicate detection, fallback scenarios

## Performance Considerations

### Processing Limits
- **Document Size**: Maximum 25MB per document
- **Processing Time**: Typically 30-60 seconds per document
- **Concurrent Requests**: Limited by rate limiting (20/minute default)
- **Memory Usage**: ~100MB per document during processing

### Optimization Tips
1. **Pre-process Documents**: Ensure documents are OCR'd and text-searchable
2. **Batch Processing**: Upload multiple documents before running the agent
3. **Section Targeting**: Specify target sections to reduce processing time
4. **Caching**: Results are cached to avoid re-processing identical content

## Troubleshooting

### Common Issues

**LLM Extraction Fails**
- Check API key configuration
- Verify network connectivity
- Review rate limits
- Check document content quality

**No Requirements Found**
- Verify document contains UCF sections
- Check for "shall", "must", "will" language
- Ensure document is properly parsed
- Try different target sections

**Duplicate Requirements**
- Use `force_reprocess=false` to preserve existing IDs
- Check similarity threshold settings
- Review requirement text normalization

**Export Failures**
- Verify file permissions
- Check available disk space
- Ensure required packages are installed (pandas, openpyxl, reportlab)

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
export FLASK_DEBUG=1
```

### Monitoring

Key metrics to monitor:
- **Processing Time**: Average time per document
- **Extraction Accuracy**: Requirements found vs. expected
- **API Response Times**: Endpoint performance
- **Error Rates**: Failed extractions and API calls
- **Storage Usage**: Document and requirement storage

## Future Enhancements

### Planned Features
- **Advanced Filtering**: Complex query language for requirements
- **Requirement Templates**: Pre-defined requirement categories
- **Collaboration Tools**: Comments, approvals, and workflows
- **Integration APIs**: Connect with project management tools
- **Advanced Analytics**: Requirement complexity scoring, dependency mapping
- **Multi-language Support**: Process RFPs in different languages
- **Custom Models**: Fine-tuned models for specific industries

### Technical Improvements
- **Streaming Processing**: Real-time requirement extraction
- **Incremental Updates**: Process only changed sections
- **Advanced Deduplication**: Semantic similarity matching
- **Performance Optimization**: Parallel processing and caching
- **Enhanced Security**: Role-based access control and audit trails

## Support

For technical support or feature requests:
- **Documentation**: Check this guide and API documentation
- **Issues**: Report bugs via GitHub issues
- **Questions**: Contact the development team
- **Training**: Request custom training sessions for your team

## License

This feature is part of the mdraft application and follows the same licensing terms.
