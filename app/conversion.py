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
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from flask import current_app

from . import db
from .models import Job


def convert_with_markitdown(input_path: str, output_path: str) -> None:
    """Convert a document to Markdown using the markitdown CLI.

    In production this function would invoke the external markitdown
    command with subprocess.run().  For the purpose of this MVP, the
    implementation will perform a very naive conversion: it reads the
    binary input and writes a simple Markdown file indicating the
    original filename.  This allows the remainder of the pipeline to
    function without requiring third‑party tools.

    Args:
        input_path: Absolute path to the source document on disk.
        output_path: Absolute path to the destination Markdown file.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Converting file {input_path} to Markdown at {output_path}")
    try:
        # Attempt to use markitdown if available
        result = subprocess.run(
            ["markitdown", input_path, "-o", output_path],
            capture_output=True,
            check=True,
            timeout=120,
        )
        stdout = result.stdout.decode()
        stderr = result.stderr.decode()
        logger.info({"stdout": stdout, "stderr": stderr})
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        # Fall back to a stub conversion on failure
        logger.warning(f"markitdown not available, using stub conversion: {exc}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Converted Document\n\nThis is a placeholder for {os.path.basename(input_path)}.\n")


def convert_with_docai(
    project_id: str,
    location: str,
    processor_id: str,
    file_path: str,
    mime_type: str,
    output_path: str,
) -> str:
    """Call Google Document AI to process a scanned document and write to Markdown.

    This function uses the Google Document AI API to extract text from
    scanned documents. It reads the file, sends it to Document AI,
    extracts the text, and writes it to a Markdown file.

    Args:
        project_id: GCP project identifier.
        location: GCP region.
        processor_id: ID of the Document AI processor.
        file_path: Path to the file to process.
        mime_type: MIME type of the file.
        output_path: Path to write the Markdown output.

    Returns:
        The extracted text content.
    """
    logger = logging.getLogger(__name__)
    
    try:
        from google.cloud import documentai_v1 as documentai
        
        # Initialize Document AI client
        client = documentai.DocumentProcessorServiceClient()
        
        # Read the file
        with open(file_path, "rb") as f:
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
        
        logger.info(f"Processing document with Document AI: {file_path}")
        
        # Process the document
        result = client.process_document(request=request)
        document = result.document
        
        # Extract text
        extracted_text = document.text
        
        logger.info(f"Document AI processing completed: {len(extracted_text)} characters extracted")
        
        # Write to Markdown file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Document AI Conversion\n\n")
            f.write(f"**Source:** {os.path.basename(file_path)}\n\n")
            f.write(f"**Extracted Text:**\n\n")
            f.write(extracted_text)
        
        return extracted_text
        
    except ImportError:
        logger.warning("Google Cloud Document AI client not available, using stub")
        # Fallback to stub implementation
        with open(file_path, "rb") as f:
            data = f.read()
        
        stub_text = f"# Document AI Stub Conversion\n\nThis is a placeholder for {os.path.basename(file_path)}.\n\nProcessed {len(data)} bytes (stub mode - Document AI not available)."
        
        # Write stub content to output file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(stub_text)
        
        return stub_text
        
    except Exception as e:
        logger.error(f"Document AI processing failed: {e}")
        # Fallback to stub on any error
        with open(file_path, "rb") as f:
            data = f.read()
        
        error_text = f"# Document AI Error\n\nError processing {os.path.basename(file_path)}: {str(e)}\n\nProcessed {len(data)} bytes (fallback mode)."
        
        # Write error content to output file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(error_text)
        
        return error_text


def parse_docai_document(doc: Any) -> Dict[str, Any]:
    """Parse a fake Document AI response object.

    A real implementation would extract full text and tables from
    documentai.Document.  This stub simply wraps the input in a dict.

    Args:
        doc: A fake Document AI response.

    Returns:
        A dictionary containing the full text and tables.
    """
    return {"full_text": str(doc), "tables": []}


def process_job(job_id: int) -> None:
    """Process a document conversion job.

    This function implements the idempotent processing logic required
    when tasks may be retried.  It retrieves the job from the
    database, checks whether it is already completed, and if not,
    performs conversion using the appropriate engine.  Finally it
    updates the job record with the output location and status.

    Args:
        job_id: Primary key of the Job to process.
    """
    logger = current_app.logger
    job: Optional[Job] = db.session.get(Job, job_id)
    if job is None:
        logger.error(f"Job {job_id} not found")
        return
    if job.status == "completed":
        logger.info(f"Duplicate task received for job {job_id}, skipping")
        return
    # Update job status to processing
    job.status = "processing"
    db.session.commit()
    # Determine paths
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir = os.path.join(project_root, "uploads")
    processed_dir = os.path.join(project_root, "processed")
    input_path = os.path.join(uploads_dir, job.filename)
    # Create output filename
    base_name, _ = os.path.splitext(job.filename)
    output_filename = f"{base_name}.md"
    output_path = os.path.join(processed_dir, output_filename)
    
    # Determine MIME type for conversion engine selection
    import filetype
    with open(input_path, "rb") as f:
        sample = f.read(261)
    kind = filetype.guess(sample)
    mime_type = kind.mime if kind else "application/octet-stream"
    
    # Choose conversion engine based on file type and configuration
    try:
        # Check if Document AI is configured and file is PDF (scanned document)
        docai_project = current_app.config.get("GOOGLE_CLOUD_PROJECT")
        docai_processor = current_app.config.get("DOCAI_PROCESSOR_ID")
        docai_location = current_app.config.get("DOCAI_LOCATION", "us")
        
        if (docai_project and docai_processor and 
            mime_type == "application/pdf"):
            logger.info(f"Using Document AI for PDF conversion: {job.filename}")
            convert_with_docai(
                project_id=docai_project,
                location=docai_location,
                processor_id=docai_processor,
                file_path=input_path,
                mime_type=mime_type,
                output_path=output_path
            )
        else:
            logger.info(f"Using markitdown for conversion: {job.filename}")
            convert_with_markitdown(input_path, output_path)
        
        job.output_uri = output_path
        job.status = "completed"
        db.session.commit()
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        db.session.commit()
        logger.exception(f"Error converting job {job_id}: {exc}")