from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sqlite3
import datetime

app = FastAPI()

DB_PATH = "./data/news.db"  

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class Summary(BaseModel):
    source: str
    original_title: str
    llm_title: str
    url: str
    summary: str
    report_timestamp: str  

class SummaryOut(Summary):
    created_at: str  

# --- Utilities ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- Routes ---
@app.get("/summaries", response_model=List[SummaryOut])
def read_summaries(limit: int = 10):
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT source, original_title, llm_title, url, summary, report_timestamp, created_at "
                "FROM summaries ORDER BY report_timestamp DESC LIMIT ?", 
                (limit,)
            )
            rows = cur.fetchall()
            summaries = [SummaryOut(**dict(row)) for row in rows]
            return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summaries")
def create_summary(summary: Summary):
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT OR IGNORE INTO summaries 
                (source, original_title, llm_title, url, summary, report_timestamp, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                summary.source,
                summary.original_title,
                summary.llm_title,
                summary.url,
                summary.summary,
                summary.report_timestamp,
                datetime.now().isoformat()
            ))
            conn.commit()
        return {"message": "Summary added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/summary/{summary_id}", response_model=SummaryOut)
def get_summary(summary_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM summaries WHERE id = ?", (summary_id,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            raise HTTPException(status_code=404, detail="Summary not found")
        return SummaryOut(**dict(row))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
