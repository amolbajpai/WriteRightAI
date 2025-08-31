# Document Compliance Service

A FastAPI-based service for checking and correcting documents (PDF or DOCX) for English grammar, style, clarity, and professional writing compliance using Google’s Generative AI (Gemini 1.5 Flash).

---

## Features

- **Upload Documents:** Accepts PDF and DOCX files.
- **Compliance Checking:** Analyzes document content to generate structured compliance reports.
- **Document Correction:** Automatically corrects grammar, style, and clarity issues while preserving paragraph structure.
- **Background Processing:** Handles long-running operations asynchronously using FastAPI BackgroundTasks.
- **Download Corrected Document:** Users can download the corrected Word document.
- **Status Tracking:** Check progress and status of uploaded files.

---

## Installation

1. Clone the repository:
```bash
git clone https://github.com/amolbajpai/WriteRightAI.git
cd WriteRightAI
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate    # Linux/macOS
venv\Scriptsctivate       # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set your Google API Key in a `.env` file:
```
GOOGLE_API_KEY=<your_api_key_here>
```

---

## Running the Server

Start the FastAPI server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) to access the service.

---

## API Endpoints

### Health Check
```http
GET /
```
**Response:**
```json
{"message": "Document Compliance Service is running"}
```

---

### Upload a Document
```http
POST /upload
```
**Form Data:**
- `file` (PDF or DOCX)

**Response:**
```json
{
  "file_id": "unique-file-id",
  "message": "File uploaded successfully"
}
```

---

### Start Compliance Check
```http
POST /check_compliance/{file_id}
```

**Response:**
```json
{
  "file_id": "unique-file-id",
  "compliance_reports": [],
  "message": "Compliance checking started. Check status for progress."
}
```

---

### Start Document Correction
```http
POST /correct_document/{file_id}
```

**Response:**
```json
{
  "file_id": "unique-file-id",
  "message": "Document correction started. Check status for progress."
}
```

---

### Check File Status
```http
GET /status/{file_id}
```

**Response Example:**
```json
{
  "file_id": "unique-file-id",
  "status": "processing_compliance",
  "compliance_reports": [],
  "message": "Compliance checking in progress..."
}
```

Statuses include:
- `uploaded`
- `processing_compliance`
- `compliance_complete`
- `processing_correction`
- `correction_complete`
- `error`

---

### Download Corrected Document
```http
GET /download/{file_id}
```
Returns a corrected `.docx` file once document correction is complete.

---

## Architecture

- **Agent1 (Compliance Check):**
  - Load document (PDF/DOCX)
  - Split text into paragraph-based chunks
  - Run compliance check using LLM
- **Agent2 (Correction):**
  - Correct each text chunk via LLM
  - Assemble corrected chunks into final document
  - Save as Word document
- **State Management:** In-memory dictionary stores file state, status, and results.

---

## Dependencies

- FastAPI
- Pydantic
- LangChain Community (Document loaders)
- LangGraph
- LangChain Google Generative AI (`ChatGoogleGenerativeAI`)
- python-docx
- python-dotenv
- Uvicorn

---

## Notes

- Only PDF and DOCX formats are supported.
- Large documents are chunked (max 2000 characters per chunk) for efficient processing.
- Background tasks ensure asynchronous compliance checks and corrections.
- Corrected documents preserve original paragraph structure.

---

## License

MIT License
