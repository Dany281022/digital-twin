from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict
import json
import uuid
from datetime import datetime
import boto3
from context import prompt

load_dotenv()

app = FastAPI()

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET", "")
MEMORY_DIR = os.getenv("MEMORY_DIR", "../memory")

if USE_S3:
    s3_client = boto3.client("s3")


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


def get_memory(session_id: str) -> List[Dict]:
    try:
        if USE_S3:
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=f"{session_id}.json")
            data = json.loads(response["Body"].read().decode("utf-8"))
            return data.get("messages", [])
        else:
            file_path = f"{MEMORY_DIR}/{session_id}.json"
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    return json.load(f).get("messages", [])
    except Exception as e:
        print(f"Error reading memory: {e}")
    return []


def save_memory(session_id: str, messages: List[Dict]):
    try:
        data = {
            "session_id": session_id,
            "messages": messages,
            "timestamp": datetime.now().isoformat()
        }
        if USE_S3:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=f"{session_id}.json",
                Body=json.dumps(data),
                ContentType="application/json"
            )
        else:
            os.makedirs(MEMORY_DIR, exist_ok=True)
            with open(f"{MEMORY_DIR}/{session_id}.json", "w") as f:
                json.dump(data, f)
    except Exception as e:
        print(f"Error saving memory: {e}")


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        session_id = request.session_id or str(uuid.uuid4())
        messages = get_memory(session_id)

        openai_messages = [
            {"role": "system", "content": prompt()},
            *messages,
            {"role": "user", "content": request.message}
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=openai_messages,
            temperature=0.7,
            max_tokens=500
        )

        assistant_message = response.choices[0].message.content

        messages.append({"role": "user", "content": request.message})
        messages.append({"role": "assistant", "content": assistant_message})
        save_memory(session_id, messages)

        return ChatResponse(response=assistant_message, session_id=session_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy", "storage": "s3" if USE_S3 else "local"}


@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    return {}