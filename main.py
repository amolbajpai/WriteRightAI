import os
import uuid
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from agents import process_compliance_check, process_document_correction
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agents import file_storage
import shutil
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Document Compliance Service")


class FileUploadResponse(BaseModel):
    file_id: str
    message: str


class StatusResponse(BaseModel):
    file_id: str
    status: str
    message: Optional[str] = None
    compliance_reports: Optional[List[str]] = None


class ComplianceResponse(BaseModel):
    file_id: str
    compliance_reports: List[str]
    message: str


class CorrectionResponse(BaseModel):
    file_id: str
    message: str


@app.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a PDF or DOCX file for processing"""

    # Validate file type
    if not file.filename.endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400,
                            detail="Only PDF and DOCX files are supported")

    # Generate unique file ID
    file_id = str(uuid.uuid4())

    # Create temporary file
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)

    file_path = os.path.join(temp_dir, f"{file_id}_{file.filename}")

    # Save uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Initialize file storage
    file_storage[file_id] = {
        "file_path": file_path,
        "original_filename": file.filename,
        "status": "uploaded",
        "compliance_reports": [],
        "chunks": [],
        "original_text": "",
        "corrected_chunks": [],
        "final_corrected_doc": "",
        "output_path": "",
        "state": None,
        "error": None
    }

    return FileUploadResponse(
        file_id=file_id,
        message=f"File {file.filename} uploaded successfully"
    )


@app.post("/check_compliance/{file_id}", response_model=ComplianceResponse)
async def check_compliance(file_id: str, background_tasks: BackgroundTasks):
    """Start compliance checking for uploaded file"""

    if file_id not in file_storage:
        raise HTTPException(status_code=404, detail="File not found")

    file_info = file_storage[file_id]

    if file_info["status"] not in ["uploaded", "compliance_complete"]:
        raise HTTPException(
            status_code=400,
            detail=f"File is currently {
                file_info['status']}")

    background_tasks.add_task(
        process_compliance_check,
        file_id,
        file_info["file_path"])

    return ComplianceResponse(
        file_id=file_id,
        compliance_reports=[],
        message="Compliance checking started. Check status for progress."
    )


@app.post("/correct_document/{file_id}", response_model=CorrectionResponse)
async def correct_document(file_id: str, background_tasks: BackgroundTasks):
    """Start document correction for a file that has been compliance checked"""

    if file_id not in file_storage:
        raise HTTPException(status_code=404, detail="File not found")

    file_info = file_storage[file_id]

    if file_info["status"] != "compliance_complete":
        raise HTTPException(
            status_code=400,
            detail=f"File must be compliance checked first. Current status: {
                file_info['status']}")

    # Add background task
    background_tasks.add_task(process_document_correction, file_id)

    return CorrectionResponse(
        file_id=file_id,
        message="Document correction started. Check status for progress."
    )


@app.get("/status/{file_id}", response_model=StatusResponse)
async def get_status(file_id: str):
    """Get the current processing status of a file"""

    if file_id not in file_storage:
        raise HTTPException(status_code=404, detail="File not found")

    file_info = file_storage[file_id]

    response = StatusResponse(
        file_id=file_id,
        status=file_info["status"],
        compliance_reports=file_info.get("compliance_reports", [])
    )

    if file_info["error"]:
        response.message = f"Error: {file_info['error']}"
    elif file_info["status"] == "uploaded":
        response.message = "File uploaded, ready for compliance checking"
    elif file_info["status"] == "processing_compliance":
        response.message = "Compliance checking in progress..."
    elif file_info["status"] == "compliance_complete":
        response.message = "Compliance checking complete, ready for correction"
    elif file_info["status"] == "processing_correction":
        response.message = "Document correction in progress..."
    elif file_info["status"] == "correction_complete":
        response.message = "Document correction complete, ready for download"

    return response


@app.get("/download/{file_id}")
async def download_file(file_id: str):
    """Download the corrected document"""

    if file_id not in file_storage:
        raise HTTPException(status_code=404, detail="File not found")

    file_info = file_storage[file_id]

    if file_info["status"] != "correction_complete":
        raise HTTPException(
            status_code=400,
            detail=f"Document correction not complete. Current status: {
                file_info['status']}")

    if not os.path.exists(file_info["output_path"]):
        raise HTTPException(status_code=404, detail="Corrected file not found")

    return FileResponse(
        path=file_info["output_path"],
        filename=f"corrected_{file_info['original_filename'].split('.')[0]}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


async def paragraph_chunk_split_async(
        text: str, chunk_size: int = 2000) -> List[str]:
    """
    Split text into chunks of max `chunk_size` characters,
    but always keep paragraphs intact.
    Paragraphs are separated by double newlines (\n\n).
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para_with_newline = para.strip() + "\n\n"
        if len(current_chunk) + len(para_with_newline) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para_with_newline
        else:
            current_chunk += para_with_newline

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


@app.on_event("startup")
async def startup_event():
    """Create necessary directories on startup"""
    os.makedirs("temp_uploads", exist_ok=True)
    os.makedirs("output", exist_ok=True)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Document Compliance Service is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
