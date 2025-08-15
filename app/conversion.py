"""
Document conversion pipeline for mdraft.

This module encapsulates the logic for converting uploaded documents
into Markdown using either an open source engine (markitdown) or
Google's Document AI for scanned files.  The MVP uses a simplified
stub implementation because external CLI tools and cloud APIs are not
available in this environment.  Functions defined here should log
meaningful messages to aid troubleshooting when integrated with
background workers.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from flask import current_app

from . import db
from .models import Job


def convert_with_markitdown(input_path: str) -> str:
    """Convert a document to Markdown using the markitdown CLI.

    This function invokes the external markitdown command with proper
    error handling and logging. If markitdown is not available or fails,
    it returns a stub conversion.

    Args:
        input_path: Absolute path to the source document on disk.

    Returns:
        Markdown text content as string.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Converting file {input_path} to Markdown using markitdown")
    
    try:
        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
            temp_output_path = temp_file.name
        
        # Attempt to use markitdown CLI
        result = subprocess.run(
            ["markitdown", input_path, "-o", temp_output_path],
            capture_output=True,
            check=True,
            timeout=120,
        )
        
        # Log successful conversion
        stdout = result.stdout.decode()
        stderr = result.stderr.decode()
        if stdout:
            logger.info(f"markitdown stdout: {stdout}")
        if stderr:
            logger.info(f"markitdown stderr: {stderr}")
            
        # Read the converted content
        with open(temp_output_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
        
        # Clean up temporary file
        try:
            os.unlink(temp_output_path)
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {temp_output_path}: {e}")
            
        logger.info(f"Successfully converted {input_path} using markitdown: {len(markdown_content)} characters")
        return markdown_content
        
    except FileNotFoundError:
        logger.warning("markitdown CLI not found, using stub conversion")
        return _generate_stub_conversion(input_path, "markitdown CLI not available")
        
    except subprocess.TimeoutExpired:
        logger.error("markitdown conversion timed out after 120 seconds")
        return _generate_stub_conversion(input_path, "markitdown conversion timed out")
        
    except subprocess.CalledProcessError as exc:
        stderr_snippet = exc.stderr.decode()[:200] if exc.stderr else "No stderr output"
        logger.error(f"markitdown conversion failed with exit code {exc.returncode}")
        logger.error(f"markitdown stderr snippet: {stderr_snippet}")
        return _generate_stub_conversion(input_path, f"markitdown failed (exit code {exc.returncode}): {stderr_snippet}")
        
    except Exception as exc:
        logger.error(f"Unexpected error during markitdown conversion: {exc}")
        return _generate_stub_conversion(input_path, f"Unexpected error: {str(exc)}")


def _generate_stub_conversion(input_path: str, reason: str) -> str:
    """Generate a stub conversion when conversion fails.
    
    Args:
        input_path: Path to the input file.
        reason: Reason for the stub conversion.
        
    Returns:
        Stub markdown content as string.
    """
    logger = logging.getLogger(__name__)
    stub_content = f"""# Converted Document

This is a placeholder for {os.path.basename(input_path)}.

**Note:** {reason}

**File:** {input_path}

**Status:** Stub conversion generated due to conversion failure.
"""
    logger.info(f"Generated stub conversion for {input_path}: {reason}")
    return stub_content


def convert_with_docai(project_id: str, location: str, processor_id: str, input_path: str, mime_type: str) -> str:
    """Call Google Document AI to process a scanned document.

    This function uses the Google Document AI API to extract text from
    scanned documents. It reads the file, sends it to Document AI,
    and returns the extracted text as Markdown.

    Args:
        project_id: GCP project identifier.
        location: GCP region.
        processor_id: ID of the Document AI processor.
        input_path: Path to the file to process.
        mime_type: MIME type of the file.

    Returns:
        The extracted text content as Markdown string.
    """
    logger = logging.getLogger(__name__)
    
    try:
        from google.cloud import documentai_v1 as documentai
        
        # Initialize Document AI client
        client = documentai.DocumentProcessorServiceClient()
        
        # Read the file
        with open(input_path, "rb") as f:
            image_content = f.read()
        
        # Build processor name
        name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
        
        # Configure the process request
        raw_document = documentai.RawDocument(
            content=image_content, mime_type=mime_type
        )
        
        request = documentai.ProcessRequest(
            name=name, raw_document=raw_document
        )
        
        logger.info(f"Processing document with Document AI: {input_path}")
        
        # Process the document
        result = client.process_document(request=request)
        document = result.document
        
        # Parse the document to extract text and tables
        parsed_doc = parse_docai_document(document)
        extracted_text = parsed_doc["full_text"]
        tables = parsed_doc.get("tables", [])
        
        # Build markdown content
        markdown_content = f"# Document AI Conversion\n\n"
        markdown_content += f"**Source:** {os.path.basename(input_path)}\n\n"
        markdown_content += f"**Extracted Text:**\n\n"
        markdown_content += extracted_text
        
        # Add tables if present
        if tables:
            markdown_content += f"\n\n## Tables\n\n"
            for i, table in enumerate(tables):
                markdown_content += f"### Table {i+1}\n\n"
                if table.get("headers"):
                    markdown_content += "| " + " | ".join(table["headers"][0]) + " |\n"
                    markdown_content += "| " + " | ".join(["---"] * len(table["headers"][0])) + " |\n"
                for row in table.get("rows", []):
                    markdown_content += "| " + " | ".join(row) + " |\n"
                markdown_content += "\n"
        
        logger.info(f"Document AI processing completed: {len(extracted_text)} characters extracted, {len(tables)} tables")
        return markdown_content
        
    except ImportError:
        logger.warning("Google Cloud Document AI client not available, using stub")
        return _generate_stub_conversion(input_path, "Document AI client not available")
        
    except Exception as e:
        logger.error(f"Document AI processing failed: {e}")
        return _generate_stub_conversion(input_path, f"Document AI error: {str(e)}")


def choose_engine(mime_type: str, flags: Dict[str, Any]) -> str:
    """Choose the conversion engine based on MIME type and configuration flags.
    
    Args:
        mime_type: MIME type of the input file.
        flags: Configuration flags including PRO_CONVERSION_ENABLED and DocAI settings.
        
    Returns:
        Engine name: "markitdown" or "docai"
    """
    logger = logging.getLogger(__name__)
    
    # Check if pro conversion is enabled
    pro_conversion_enabled = flags.get("PRO_CONVERSION_ENABLED", "false").lower() == "true"
    if not pro_conversion_enabled:
        logger.info(f"Pro conversion disabled, using markitdown for {mime_type}")
        return "markitdown"
    
    # Check if DocAI environment is properly configured
    docai_project = flags.get("GOOGLE_CLOUD_PROJECT")
    docai_processor = flags.get("DOCAI_PROCESSOR_ID")
    
    if not all([docai_project, docai_processor]):
        logger.info(f"DocAI not configured (project: {docai_project}, processor: {docai_processor}), using markitdown")
        return "markitdown"
    
    # Use DocAI for PDFs (scanned documents)
    if mime_type == "application/pdf":
        logger.info(f"Using DocAI for PDF conversion")
        return "docai"
    else:
        logger.info(f"Using markitdown for {mime_type} (not PDF)")
        return "markitdown"


def parse_docai_document(document: Any) -> Dict[str, Any]:
    """Parse a Document AI response object to extract text and tables.

    This function extracts the full text and any tables from a Document AI
    response, formatting them appropriately for Markdown output.

    Args:
        document: A Document AI Document object.

    Returns:
        A dictionary containing the full text and tables.
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Extract full text
        full_text = document.text if hasattr(document, 'text') else ""
        
        # Extract tables if present
        tables = []
        if hasattr(document, 'pages'):
            for page in document.pages:
                if hasattr(page, 'tables'):
                    for table in page.tables:
                        table_data = _extract_table_data(table, document.text)
                        if table_data:
                            tables.append(table_data)
        
        logger.info(f"Parsed document: {len(full_text)} characters, {len(tables)} tables")
        
        return {
            "full_text": full_text,
            "tables": tables
        }
        
    except Exception as e:
        logger.error(f"Error parsing Document AI response: {e}")
        # Fallback to basic text extraction
        full_text = getattr(document, 'text', str(document))
        return {
            "full_text": full_text,
            "tables": []
        }


def _extract_table_data(table: Any, document_text: str) -> Dict[str, Any]:
    """Extract table data from a Document AI table object.
    
    Args:
        table: Document AI table object.
        document_text: Full document text for reference.
        
    Returns:
        Dictionary containing table headers and rows.
    """
    try:
        headers = []
        rows = []
        
        if hasattr(table, 'header_rows'):
            for header_row in table.header_rows:
                row_data = []
                for cell in header_row.cells:
                    if hasattr(cell, 'text_anchor') and cell.text_anchor.text_segments:
                        # Extract text from the document using text anchor
                        text = ""
                        for segment in cell.text_anchor.text_segments:
                            start_index = segment.start_index
                            end_index = segment.end_index
                            text += document_text[start_index:end_index]
                        row_data.append(text.strip())
                    else:
                        row_data.append("")
                headers.append(row_data)
        
        if hasattr(table, 'body_rows'):
            for body_row in table.body_rows:
                row_data = []
                for cell in body_row.cells:
                    if hasattr(cell, 'text_anchor') and cell.text_anchor.text_segments:
                        # Extract text from the document using text anchor
                        text = ""
                        for segment in cell.text_anchor.text_segments:
                            start_index = segment.start_index
                            end_index = segment.end_index
                            text += document_text[start_index:end_index]
                        row_data.append(text.strip())
                    else:
                        row_data.append("")
                rows.append(row_data)
        
        return {
            "headers": headers,
            "rows": rows
        }
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error extracting table data: {e}")
        return {"headers": [], "rows": []}


def process_job(job_id: int, gcs_uri: str) -> str:
    """Process a document conversion job with GCS integration.

    This function implements the idempotent processing logic required
    when tasks may be retried. It retrieves the job from the database,
    downloads the file from GCS, performs conversion using the appropriate
    engine, and returns the Markdown content.

    Args:
        job_id: Primary key of the Job to process.
        gcs_uri: GCS URI of the input file (required)

    Returns:
        Markdown content as string.
    """
    import time
    from .services import Storage
    
    logger = current_app.logger
    start_time = time.time()
    
    job: Optional[Job] = db.session.get(Job, job_id)
    if job is None:
        logger.error(f"Job {job_id} not found")
        raise ValueError("Job not found")
    
    if job.status == "completed":
        logger.info(f"Duplicate task received for job {job_id}, skipping")
        # Return existing content if available, otherwise empty string
        return ""
    
    # Validate storage path
    if not gcs_uri:
        logger.error(f"No storage path provided for job {job_id}")
        raise ValueError("No storage path provided")
    
    # Download file from storage to temp
    try:
        storage = Storage()
        
        # Check if file exists in storage
        if not storage.exists(gcs_uri):
            logger.error(f"File not found in storage for job {job_id}: {gcs_uri}")
            raise FileNotFoundError(f"File not found in storage: {gcs_uri}")
        
        # Read file data from storage
        file_data = storage.read_bytes(gcs_uri)
        
        # Write to temporary file for processing
        import tempfile
        temp_fd, input_path = tempfile.mkstemp(suffix=f"_{job.filename}")
        with os.fdopen(temp_fd, 'wb') as f:
            f.write(file_data)
        
        logger.info(f"Downloaded {gcs_uri} to temporary file {input_path}")
    except Exception as e:
        logger.error(f"Failed to download file for job {job_id}: {e}")
        raise
    
    # Determine MIME type for conversion engine selection
    import filetype
    with open(input_path, "rb") as f:
        sample = f.read(261)
    kind = filetype.guess(sample)
    mime_type = kind.mime if kind else "application/octet-stream"
    
    # Get configuration flags
    flags = {
        "PRO_CONVERSION_ENABLED": os.getenv("PRO_CONVERSION_ENABLED", "false"),
        "GOOGLE_CLOUD_PROJECT": current_app.config.get("GOOGLE_CLOUD_PROJECT"),
        "DOCAI_PROCESSOR_ID": current_app.config.get("DOCAI_PROCESSOR_ID"),
        "DOCAI_LOCATION": current_app.config.get("DOCAI_LOCATION", "us")
    }
    
    # Choose conversion engine
    engine = choose_engine(mime_type, flags)
    
    # Log which extractor is being used and why
    pro_enabled = flags.get("PRO_CONVERSION_ENABLED", "false").lower() == "true"
    docai_configured = all([flags.get("GOOGLE_CLOUD_PROJECT"), flags.get("DOCAI_PROCESSOR_ID")])
    
    if engine == "docai":
        logger.info(f"Using DocAI extractor for {job.filename} (MIME: {mime_type}) - Pro conversion enabled: {pro_enabled}, DocAI configured: {docai_configured}")
    else:
        reason = "Pro conversion disabled" if not pro_enabled else "DocAI not configured" if not docai_configured else f"Not PDF ({mime_type})"
        logger.info(f"Using markitdown extractor for {job.filename} (MIME: {mime_type}) - Reason: {reason}")
    
    try:
        if engine == "docai":
            # Use Document AI for PDF conversion
            markdown_content = convert_with_docai(
                project_id=flags["GOOGLE_CLOUD_PROJECT"],
                location=flags["DOCAI_LOCATION"],
                processor_id=flags["DOCAI_PROCESSOR_ID"],
                input_path=input_path,
                mime_type=mime_type
            )
        else:
            # Use markitdown for other file types
            markdown_content = convert_with_markitdown(input_path)
        
        # Calculate processing duration
        processing_duration = time.time() - start_time
        logger.info(f"Job {job_id} completed successfully using {engine} engine in {processing_duration:.2f}s")
        
        # Clean up temporary files
        try:
            os.unlink(input_path)
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {input_path}: {e}")
        
        return markdown_content
        
    except Exception as exc:
        logger.exception(f"Error converting job {job_id}: {exc}")
        raise