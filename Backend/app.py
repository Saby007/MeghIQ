from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import os

class PromptRequest(BaseModel):
    prompt: str

class ConversationRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = []

app = FastAPI(
    title="ArchMate",
    description="API with generating architecture diagrams & costing based on user input",
    version="1.0.0"
)

# Configure CORS for Angular frontend (allow all localhost origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",  # Allow any localhost port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to ArchMate",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return JSONResponse(status_code=200, content={"status": "healthy"})

@app.post("/generate-architecture", response_class=JSONResponse)
async def generate_architecture(request: ConversationRequest, save_to_file: bool = False):
    """Conversational architecture diagram generation
    
    Args:
        request: Conversation request with message and session info
        save_to_file: If True, saves diagram to file (useful for console/testing, not needed for UI)
    """
    from orchestrator import process_conversation_async
    
    print(f"Processing message: {request.message}")
    print(f"Save to file: {save_to_file}")
    
    # Call orchestrator to handle conversation
    result = await process_conversation_async(
        message=request.message,
        session_id=request.session_id,
        history=request.history,
        save_to_file=save_to_file
    )
    
    return JSONResponse(content=result)

@app.post("/get-pricing", response_class=JSONResponse)
async def get_pricing(request: PromptRequest):
    """Get pricing information based on user prompt"""
    print(f"Finding pricing information for prompt: {request.prompt}")
    
    # TODO: Replace with actual pricing calculation logic
    html_table = """
    <table border="1" style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif;">
        <thead style="background-color: #0078d4; color: white;">
            <tr>
                <th style="padding: 12px; text-align: left;">Service</th>
                <th style="padding: 12px; text-align: left;">Tier</th>
                <th style="padding: 12px; text-align: right;">Monthly Cost (USD)</th>
            </tr>
        </thead>
        <tbody>
            <tr style="background-color: #f9f9f9;">
                <td style="padding: 10px;">Azure App Service</td>
                <td style="padding: 10px;">Basic B1</td>
                <td style="padding: 10px; text-align: right;">$13.14</td>
            </tr>
            <tr>
                <td style="padding: 10px;">Azure SQL Database</td>
                <td style="padding: 10px;">Basic</td>
                <td style="padding: 10px; text-align: right;">$4.90</td>
            </tr>
            <tr style="background-color: #f9f9f9;">
                <td style="padding: 10px;">Azure Cache for Redis</td>
                <td style="padding: 10px;">Basic C0</td>
                <td style="padding: 10px; text-align: right;">$16.06</td>
            </tr>
            <tr style="background-color: #e6f2ff; font-weight: bold;">
                <td colspan="2" style="padding: 10px;">Total Estimated Cost</td>
                <td style="padding: 10px; text-align: right;">$34.10</td>
            </tr>
        </tbody>
    </table>
    """
    
    return JSONResponse(content={"html": html_table})

class DiagramXmlRequest(BaseModel):
    xml: str

@app.post("/estimate-cost", response_class=JSONResponse)
async def estimate_cost(request: DiagramXmlRequest):
    """Generate detailed cost estimation from diagram XML
    
    Args:
        request: Request containing the DrawIO XML diagram
    
    Returns:
        Detailed cost breakdown with service-level pricing
    """
    from orchestrator import estimate_architecture_cost
    
    print(f"Estimating cost for architecture diagram ({len(request.xml)} chars)")
    
    try:
        result = await estimate_architecture_cost(request.xml)
        return JSONResponse(content=result)
    except Exception as e:
        print(f"Error estimating cost: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to estimate cost: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
