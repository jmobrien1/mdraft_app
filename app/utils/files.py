import uuid


def is_file_allowed(filename: str) -> bool:
    """
    Check if the file extension is in the allowed list.
    
    Args:
        filename: The filename to check
        
    Returns:
        True if the file extension is allowed, False otherwise
        
    Allowed extensions: {"pdf","docx","pptx","xlsx","txt","md"}
    """
    allowed_extensions = {"pdf", "docx", "pptx", "xlsx", "txt", "md"}
    
    # Return False if no dot in filename
    if "." not in filename:
        return False
    
    # Extract extension (everything after the last dot)
    extension = filename.rsplit(".", 1)[-1].lower()
    
    # Return True if extension is in allowed list
    return extension in allowed_extensions


def generate_job_id() -> str:
    """
    Generate a URL-safe unique identifier for a job.
    
    Returns:
        A URL-safe string representation of a UUID4
    """
    return uuid.uuid4().hex
