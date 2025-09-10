
from typing import Any, Dict, List
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.document_loaders import PDFPlumberLoader, Docx2txtLoader
from docx import Document
from typing import List
import os

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

file_storage: Dict[str, Dict[str, Any]] = {}


class ComplianceState(Dict[str, Any]):
    """
    Shared state for agent workflow.
    Attributes:
        file_path (str): Path to the input document (PDF or DOCX).
        original_text (str): Full text extracted from the document.
        chunks (List[str]): Paragraph-based chunks of the text.
        compliance_reports (List[str]): Raw compliance reports for each chunk.
        corrected_chunks (List[str]): Corrected text chunks from Agent2.
        final_corrected_doc (str): Full corrected document text.
        output_path (str): Path where the corrected Word file is saved.
    """
    file_path: str
    original_text: str
    chunks: List[str]
    compliance_reports: List[str]
    corrected_chunks: List[str]
    final_corrected_doc: str
    output_path: str

    def __init__(self, **kwargs: Any):
        super().__init__()
        self.file_path = kwargs.get("file_path", "")
        self.original_text = kwargs.get("original_text", "")
        self.chunks = kwargs.get("chunks", [])
        self.compliance_reports = kwargs.get("compliance_reports", [])
        self.corrected_chunks = kwargs.get("corrected_chunks", [])
        self.final_corrected_doc = kwargs.get("final_corrected_doc", "")
        self.output_path = kwargs.get("output_path", "")
        # Add all attributes to the underlying dict
        self.update({
            "file_path": self.file_path,
            "original_text": self.original_text,
            "chunks": self.chunks,
            "compliance_reports": self.compliance_reports,
            "corrected_chunks": self.corrected_chunks,
            "final_corrected_doc": self.final_corrected_doc,
            "output_path": self.output_path
        })


async def load_document_node(state: ComplianceState) -> ComplianceState:
    """Load PDF/DOCX and extract text"""
    file_path = state["file_path"]

    if file_path.endswith(".pdf"):
        loader = PDFPlumberLoader(file_path)
        docs = loader.load()
        text = "\n\n".join([doc.page_content for doc in docs])
    elif file_path.endswith(".docx"):
        loader = Docx2txtLoader(file_path)
        docs = loader.load()
        text = "\n\n".join([doc.page_content for doc in docs])
    else:
        raise ValueError("Only PDF and DOCX supported.")

    state["original_text"] = text
    return state


async def chunk_text_node(state: ComplianceState) -> ComplianceState:
    """Split text into paragraph-based chunks of max 2000 chars"""
    text = state["original_text"]
    chunks = await paragraph_chunk_split(text, chunk_size=2000)
    state["chunks"] = chunks
    return state


async def compliance_check_node(state: ComplianceState) -> ComplianceState:
    """Check compliance for each chunk"""
    reports = []
    for chunk in state["chunks"]:
        response = await llm.ainvoke(
            f"Check the following text for compliance with English grammar, style, clarity, "
            f"and professional writing rules. Return a structured JSON report:\n\n{chunk}"
        )
        reports.append(response.content)

    state["compliance_reports"] = reports
    return state


async def correct_document_node(state: ComplianceState) -> ComplianceState:
    """Correct each chunk and assemble corrected text strictly"""
    corrected_chunks = []

    for chunk in state["chunks"]:
        response = await llm.ainvoke(
            f"Correct the following text to fully comply with English grammar, style, clarity, "
            f"and professional writing rules.\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Return ONLY the corrected text.\n"
            f"2. Do NOT add any explanations, summaries, or extra comments.\n"
            f"3. Keep the original paragraph structure.\n"
            f"4. Maintain the original meaning.\n\n"
            f"ORIGINAL TEXT:\n{chunk}\n\n"
            f"CORRECTED TEXT:"
        )
        # Ensure we strip any accidental leading/trailing whitespace
        corrected_chunks.append(response.content.strip())

    state["corrected_chunks"] = corrected_chunks
    state["final_corrected_doc"] = "\n\n".join(corrected_chunks)
    return state


async def save_corrected_doc_node(state: ComplianceState) -> ComplianceState:
    """Save corrected text as Word file"""
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Generate unique filename
    file_id = os.path.basename(state["file_path"]).split('.')[0]
    output_path = os.path.join(output_dir, f"corrected_{file_id}.docx")

    doc = Document()
    for para in state["final_corrected_doc"].split("\n\n"):
        if para.strip():
            doc.add_paragraph(para.strip())

    doc.save(output_path)
    state["output_path"] = output_path
    return state


async def build_compliance_workflow():
    """Build compliance checking workflow"""
    graph = StateGraph(ComplianceState)
    graph.add_node("load", load_document_node)
    graph.add_node("chunk", chunk_text_node)
    graph.add_node("check", compliance_check_node)

    graph.set_entry_point("load")
    graph.add_edge("load", "chunk")
    graph.add_edge("chunk", "check")
    graph.add_edge("check", END)

    return graph.compile()


async def build_correction_workflow():
    """Build correction workflow"""
    graph = StateGraph(ComplianceState)
    graph.add_node("correct", correct_document_node)
    graph.add_node("save", save_corrected_doc_node)

    graph.set_entry_point("correct")
    graph.add_edge("correct", "save")
    graph.add_edge("save", END)

    return graph.compile()


async def paragraph_chunk_split(text: str,
                                chunk_size: int = 2000) -> List[str]:
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


async def process_compliance_check(file_id: str, file_path: str):
    """Background task for compliance checking"""
    try:
        file_storage[file_id]["status"] = "processing_compliance"
        state = ComplianceState(file_path=file_path)
        agent1 = await build_compliance_workflow()
        state = await agent1.ainvoke(state)

        # Store results
        file_storage[file_id]["compliance_reports"] = state["compliance_reports"]
        file_storage[file_id]["chunks"] = state["chunks"]
        file_storage[file_id]["original_text"] = state["original_text"]
        file_storage[file_id]["state"] = state
        file_storage[file_id]["status"] = "compliance_complete"

    except Exception as e:
        file_storage[file_id]["status"] = "error"
        file_storage[file_id]["error"] = str(e)


async def process_document_correction(file_id: str):
    """Background task for document correction"""
    try:
        # Update status
        file_storage[file_id]["status"] = "processing_correction"

        # Get existing state
        state = file_storage[file_id]["state"]

        # Run Agent2
        agent2 = await build_correction_workflow()
        state = await agent2.ainvoke(state)

        # Store results
        file_storage[file_id]["corrected_chunks"] = state["corrected_chunks"]
        file_storage[file_id]["final_corrected_doc"] = state["final_corrected_doc"]
        file_storage[file_id]["output_path"] = state["output_path"]
        file_storage[file_id]["state"] = state
        file_storage[file_id]["status"] = "correction_complete"

    except Exception as e:
        file_storage[file_id]["status"] = "error"
        file_storage[file_id]["error"] = str(e)
