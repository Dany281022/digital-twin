# Day 3: Transition to AWS Bedrock — Explanation Guide

> **Purpose of this guide:** This is a self-contained, teach-yourself companion to `day3.md`. It follows the same structure as the original material but explains *what* is happening at every step and *why*, so you can work through the lab independently with a clear understanding of the decisions being made.

---

## Introduction: What is Day 3 About?

By the end of Day 2, you had a fully working Digital Twin application deployed on AWS: a React frontend served through CloudFront, a FastAPI backend running as a Lambda function, an API Gateway routing traffic to it, and an S3 bucket storing conversation history. The one part of that stack that still reached *outside* of AWS was the AI layer — the Lambda function was making calls to the OpenAI API to generate responses. Today, we close that gap.

**Day 3 is about replacing OpenAI with Amazon Bedrock** — AWS's managed AI service — so that every component of the application lives within your AWS account. This is a meaningful architectural shift for several reasons: it removes the dependency on a third-party API key, keeps all traffic within AWS (which reduces latency), and unifies billing and monitoring in one place.

The day has six major phases:

**1. IAM Permissions.** Before you can use any new AWS service, you must grant permission to use it. This applies both to your user account (via IAM policies) and to the Lambda function itself (via its execution role). You will add `AmazonBedrockFullAccess` and `CloudWatchFullAccess` to your user group, and then separately attach Bedrock permissions to the Lambda execution role.

**2. Model Access and Model IDs.** AWS Bedrock provides access to a catalogue of foundation models from Amazon, Anthropic, Meta, and others. Amazon's own Nova model family — available in Micro, Lite, and Pro variants — is what you will use today. This section explains how model access works, why model IDs have changed since the course videos were recorded, and how to use "cross-region inference profiles" to maximise availability and avoid quota errors.

**3. Understanding Model Costs.** A brief but important orientation to Bedrock's pricing model. The Nova models are inexpensive — a typical conversation costs fractions of a cent — but understanding how the pricing is structured (per 1,000 tokens, not per million) helps you interpret the numbers correctly and make informed choices about which model to use.

**4. Updating the Code.** The core technical change of the day: rewriting `server.py` to replace the OpenAI client with a Bedrock client using the `boto3` library. You will also remove the `openai` package from `requirements.txt`. This section explains the differences between the OpenAI and Bedrock message formats and why the code is structured the way it is.

**5. Deploying to Lambda.** Rebuilding the deployment package and uploading the updated code to Lambda, along with adding the necessary environment variables and Bedrock permissions to the Lambda execution role.

**6. Testing and CloudWatch Monitoring.** Verifying that the application is working end-to-end, and then using CloudWatch to confirm — with concrete evidence — that requests are genuinely reaching Amazon Bedrock's Nova models. You will also set up a basic monitoring dashboard.

---

## What You'll Learn Today

- **AWS Bedrock fundamentals** — what it is, how it fits into the AWS AI landscape, and how it differs from calling OpenAI directly
- **Nova models** — AWS's own foundation model family, and how to select between them based on your needs
- **IAM permissions for AI services** — how permission controls work at two levels: your user account and the Lambda execution role
- **Model IDs and cross-region inference profiles** — the current naming conventions and how to handle quota limitations
- **The Bedrock `converse` API** — how its message format differs from OpenAI's and how to translate between them
- **CloudWatch monitoring** — using metrics and logs to verify and observe your application's behaviour in production

---

## Understanding AWS Bedrock

### What is Amazon Bedrock?

Amazon Bedrock is AWS's fully managed service for accessing and using foundation models — large pre-trained AI models capable of generating text, answering questions, writing code, and more. The key word is *managed*: AWS takes care of the infrastructure, security, and model updates, so you do not need to provision servers or manage model deployments yourself.

Bedrock is best understood as a **gateway** into a catalogue of AI models. Through a single, consistent API, you can access models from Amazon (the Nova family), Anthropic (Claude), Meta (Llama), and others. You do not need a separate API key for each provider — you access them all through your AWS account, and costs are billed directly to your AWS bill.

It is worth noting that Bedrock is growing rapidly. Beyond simple model inference, AWS is adding agent capabilities, knowledge bases, and fine-tuning features to Bedrock. However, for today's purposes, you are using the model inference part — sending messages and receiving responses.

AWS also has another AI service called **Amazon SageMaker**, which provides more low-level control over model training, fine-tuning, and deployment. Bedrock is the higher-level, simpler option. You will encounter SageMaker later in the course.

**Why switch from OpenAI to Bedrock?**

- **No external API dependency** — No OpenAI API key to manage, rotate, or pay separately for
- **In-AWS billing** — Costs appear on your standard AWS bill with full Cost Explorer visibility
- **IAM-based security** — Access is controlled through AWS's identity and permissions system, which you are already using
- **Lower latency** — The call from Lambda to Bedrock stays within the AWS network; there is no public internet hop
- **Unified monitoring** — CloudWatch can observe both your Lambda function and your Bedrock calls in one place

### Amazon Nova Models

AWS's Nova model family is their own set of foundation models, designed for different points on the cost-performance spectrum:

| Model | Best For | Speed | Cost |
|-------|----------|-------|------|
| **Nova Micro** | Simple questions, fast responses | Very fast | Very low |
| **Nova Lite** | General conversation, balanced use | Fast | Low |
| **Nova Pro** | Complex reasoning, detailed responses | Moderate | Moderate |

To give you a sense of scale: Nova Pro, the most expensive of the three, is currently priced lower than Claude Haiku (Anthropic's most cost-effective model). Nova Micro is extraordinarily cheap — a typical single conversation would cost a fraction of a cent. You would need hundreds of conversations to spend even a dollar. That said, always verify current pricing on the AWS Bedrock pricing page, as prices do change.

Today, you will implement all three models via an environment variable, so you can switch between them without changing code.

---

## Part 1: Configure IAM Permissions

### Why permissions must come first

AWS follows a "deny by default" security model: unless a permission has been explicitly granted, an action is not permitted. This applies at every level — your user account, your user group, and even the Lambda function itself. Before your code can successfully call Bedrock, you need to grant permission in two separate places:

1. Your **user group** (`TwinAccess`) — so your IAM user can interact with Bedrock and CloudWatch from the console
2. The **Lambda execution role** — so the Lambda function itself can call Bedrock at runtime (covered in Part 5)

These are separate permission grants because they apply to different identities: you as a human user, and the Lambda function as a service.

### Step 1: Sign In as Root User

Since modifying IAM group policies requires elevated privileges, sign in as the root user:

1. Go to [aws.amazon.com](https://aws.amazon.com)
2. Sign in with your **root user** credentials (the email address used to create the AWS account)

The root user is the only account that has unrestricted access to all AWS services and billing. You use it here specifically to manage IAM policies. In normal operation, you work as your IAM user (`aiengineer`).

### Step 2: Add Bedrock and CloudWatch Permissions to Your User Group

1. In the AWS Console, search for **IAM** in the search bar
2. Click **User groups** in the left sidebar
3. Click on **TwinAccess** (the group created on Day 2)
4. Click the **Permissions** tab → **Add permissions** → **Attach policies**
5. Search for and select each of these two policies:
   - **AmazonBedrockFullAccess** — grants your user account the ability to interact with all Bedrock services, including model access management and invoking models
   - **CloudWatchFullAccess** — grants access to AWS CloudWatch for viewing metrics, logs, and creating dashboards
6. Click **Attach policies**

After this step, your `TwinAccess` group should have the following policies attached. This is the complete expected list:

| Policy | Purpose |
|--------|---------|
| `AWSLambda_FullAccess` | Managing Lambda functions |
| `AmazonS3FullAccess` | S3 bucket and object operations |
| `AmazonAPIGatewayAdministrator` | API Gateway configuration |
| `CloudFrontFullAccess` | CloudFront distribution management |
| `IAMReadOnlyAccess` | Reading IAM roles and policies |
| `AmazonBedrockFullAccess` | ✅ New — Bedrock model access |
| `CloudWatchFullAccess` | ✅ New — Monitoring and logs |
| `AmazonDynamoDBFullAccess` | ⚠️ Needed for Day 5 — add this now |

> **Note on DynamoDB:** The last policy in the table was identified by a student (credit to Andy C) as being needed on Day 5. Adding it now saves you from a permissions error later. Even though you will not use DynamoDB today, there is no harm in granting the permission in advance.

### Step 3: Sign Back In as Your IAM User

1. Sign out of the root account
2. Sign back in as `aiengineer` with your IAM user credentials

You should now be working as your IAM user, which you can confirm by checking the account name in the top-right corner of the AWS Console.

---

## Part 2: Model Access and Model IDs

### ⚠️ Important: This Section Has Changed — Please Read Carefully

The original course videos were recorded before AWS made significant changes to how Bedrock models are accessed and named. The information here reflects the current state as of 2026.

### How model access works today

When Bedrock was first launched, you had to individually request access to each model before you could use it. AWS has since moved to a **quota-based system**: most models are now accessible without a formal access request, but there are limits on how many requests you can make per minute or hour. If you exceed these quotas, your requests will be throttled.

For Amazon's own Nova models, access is generally granted immediately — you do not need to wait or go through an approval process. For third-party models (like Anthropic's Claude models), there may be a brief wait.

**What this means practically:** For most students, you can proceed directly to the code changes without any model access configuration. However, if you encounter quota errors, see the guidance on cross-region inference profiles below.

### Model IDs: What has changed

In the course videos, you will see model IDs in this format:

```
amazon.nova-lite-v1:0
```

There are two important updates to be aware of:

**1. Nova has been updated to version 2:**
```
amazon.nova-2-lite-v1:0
```

**2. Cross-region inference profiles are now recommended.** A cross-region inference profile is a model ID with a geographic prefix that tells Bedrock it is allowed to route your request to the most available region. This results in higher effective quotas and fewer throttling errors.

The prefix options are:

| Prefix | Coverage |
|--------|----------|
| `global.` | AWS selects the best region worldwide |
| `us.` | United States regions only |
| `eu.` | European regions only |
| `ap.` | Asia-Pacific regions only |

**What you should use:**

Start with the global prefix:
```
global.amazon.nova-2-lite-v1:0
```

If you encounter quota or access errors, try a geography-specific prefix:
```
us.amazon.nova-2-lite-v1:0
eu.amazon.nova-2-lite-v1:0
ap.amazon.nova-2-lite-v1:0
```

> **Why does this matter?** Bedrock has service quotas — limits on how many tokens or requests you can process per minute, per region. By using a cross-region inference profile, you effectively pool quotas across multiple regions, making it much less likely that you will hit a limit during normal use. AWS recommends this approach for production deployments.

> **Region note:** Your Bedrock region does not need to match the region of your other services (Lambda, S3, API Gateway). It is fine to use `us-east-1` as your Bedrock region regardless of where your Lambda function is deployed. `us-east-1` is generally a safe and well-supported choice.

For a complete reference on quota issues and how to request increased limits, see the [full write-up in Q42](https://edwarddonner.com/faq).

---

## Part 3: Understanding Model Costs

### How Bedrock pricing works

Bedrock charges based on the number of **tokens** your requests consume. A token is roughly equivalent to three-quarters of a word in English. Every request has two components:

- **Input tokens:** Everything you send to the model — the system prompt, the conversation history, and the current user message
- **Output tokens:** The text the model generates in response

Pricing is listed **per 1,000 tokens** on the AWS Bedrock pricing page. Some other AI provider sites list prices per million tokens, which can make the numbers look much larger. It is worth keeping this in mind when comparing costs.

### How much will you actually spend?

To calibrate your expectations: a typical single conversation turn might consume around 1,000–2,000 input tokens (including the system prompt and conversation history) and perhaps 200–400 output tokens. At Nova Micro or Lite prices, this amounts to less than a tenth of a cent per exchange. You would need hundreds of conversations to spend a dollar.

Even Nova Pro — the most expensive of Amazon's Nova models — is priced comparably to or below Claude Haiku, which is Anthropic's most cost-effective offering. For this course, cost should not be a significant concern, but it is good practice to set up a billing alert (covered in Part 7) so you are never surprised.

**For current pricing figures, always check:** [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)

Select "Amazon" from the model tabs to see the Nova pricing table. The page shows both input and output token prices for each Nova tier, broken down by region if applicable.

### Why no API key is required

If you noticed that the code below does not include any API key for Bedrock — that is intentional and is one of Bedrock's advantages. When your Lambda function runs, it assumes the IAM execution role that you configure. That role carries the `AmazonBedrockFullAccess` permission, which authorises it to call Bedrock. The request is authenticated automatically by the AWS SDK using the Lambda function's identity.

In other words: instead of a separate API key, access is controlled by IAM — the same permission system that governs everything else in your AWS account. This is more secure (no secret to leak) and more manageable (permissions are revocable centrally).

---

## Part 4: Update Your Code for Bedrock

### Step 1: Update `requirements.txt`

Open `twin/backend/requirements.txt` and remove the `openai` package. The updated file should look like this:

```
fastapi
uvicorn
python-dotenv
python-multipart
boto3
pypdf
mangum
```

**Why remove `openai`?** Good software practice is to avoid including packages that are no longer used. An unused dependency adds to your deployment package size, can introduce security vulnerabilities if left unpatched, and creates confusion for anyone reading the code later. Since you are completely replacing the OpenAI integration, the package should be removed.

**Why is `boto3` already there?** You added `boto3` earlier in the course to interact with S3. The same library is used to communicate with Bedrock, so no new package is required — you are simply using a different boto3 service client.

### Step 2: Update `server.py`

Replace the contents of `twin/backend/server.py` with the version below. This is a significant rewrite of the AI-related portions; the memory management, routing, and CORS configuration are largely unchanged.

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict
import json
import uuid
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from context import prompt

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Initialise Bedrock client
# The region controls which AWS region handles your Bedrock requests.
# It does not need to match the region of your Lambda or other services.
# See Part 2 for guidance on Bedrock regions.
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("DEFAULT_AWS_REGION", "us-east-1")
)

# Bedrock model selection
# The model ID is read from an environment variable, making it easy to
# switch between Nova Micro, Lite, and Pro without changing code.
# Use cross-region inference profile IDs (with a geographic prefix) for
# better availability. See Part 2 for the full explanation.
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.amazon.nova-2-lite-v1:0")

# Memory storage configuration
USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET", "")
MEMORY_DIR = os.getenv("MEMORY_DIR", "../memory")

# Initialise S3 client only if we are using S3 for memory storage
if USE_S3:
    s3_client = boto3.client("s3")


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


class Message(BaseModel):
    role: str
    content: str
    timestamp: str


# Memory management functions — unchanged from Day 2
def get_memory_path(session_id: str) -> str:
    return f"{session_id}.json"


def load_conversation(session_id: str) -> List[Dict]:
    """Load conversation history from storage (S3 or local file)."""
    if USE_S3:
        try:
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=get_memory_path(session_id))
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return []
            raise
    else:
        file_path = os.path.join(MEMORY_DIR, get_memory_path(session_id))
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return []


def save_conversation(session_id: str, messages: List[Dict]):
    """Save conversation history to storage (S3 or local file)."""
    if USE_S3:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=get_memory_path(session_id),
            Body=json.dumps(messages, indent=2),
            ContentType="application/json",
        )
    else:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        file_path = os.path.join(MEMORY_DIR, get_memory_path(session_id))
        with open(file_path, "w") as f:
            json.dump(messages, f, indent=2)


def call_bedrock(conversation: List[Dict], user_message: str) -> str:
    """
    Call AWS Bedrock with the current conversation history and return the
    model's response as a plain string.

    Bedrock's `converse` API expects messages in a specific format:
    each message is a dict with a "role" ("user" or "assistant") and
    a "content" key containing a list of content blocks. For text, each
    block is {"text": "..."}.

    The system prompt is passed separately via the `system` parameter,
    which is the cleanest approach. This avoids the awkward workaround
    of injecting the system prompt as a fake first user message.
    """

    # Convert conversation history into Bedrock's message format.
    # We limit to the last 50 entries (25 exchanges) to avoid sending
    # excessive tokens and to stay within context window limits.
    messages = []
    for msg in conversation[-50:]:
        messages.append({
            "role": msg["role"],
            "content": [{"text": msg["content"]}]
        })

    # Add the current user message
    messages.append({
        "role": "user",
        "content": [{"text": user_message}]
    })

    try:
        response = bedrock_client.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": prompt()}],   # System prompt passed cleanly here
            messages=messages,
            inferenceConfig={
                "maxTokens": 2000,
                "temperature": 0.7,
                "topP": 0.9
            }
        )

        # The response structure is a Python dictionary (not a Pydantic object).
        # The generated text is nested at: output -> message -> content[0] -> text
        return response["output"]["message"]["content"][0]["text"]

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ValidationException':
            print(f"Bedrock validation error: {e}")
            raise HTTPException(status_code=400, detail="Invalid message format for Bedrock")
        elif error_code == 'AccessDeniedException':
            print(f"Bedrock access denied: {e}")
            raise HTTPException(status_code=403, detail="Access denied to Bedrock model")
        else:
            print(f"Bedrock error: {e}")
            raise HTTPException(status_code=500, detail=f"Bedrock error: {str(e)}")


@app.get("/")
async def root():
    return {
        "message": "AI Digital Twin API (Powered by AWS Bedrock)",
        "memory_enabled": True,
        "storage": "S3" if USE_S3 else "local",
        "ai_model": BEDROCK_MODEL_ID
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "use_s3": USE_S3,
        "bedrock_model": BEDROCK_MODEL_ID
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        session_id = request.session_id or str(uuid.uuid4())
        conversation = load_conversation(session_id)
        assistant_response = call_bedrock(conversation, request.message)

        conversation.append(
            {"role": "user", "content": request.message, "timestamp": datetime.now().isoformat()}
        )
        conversation.append(
            {"role": "assistant", "content": assistant_response, "timestamp": datetime.now().isoformat()}
        )

        save_conversation(session_id, conversation)
        return ChatResponse(response=assistant_response, session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    """Retrieve the full conversation history for a given session."""
    try:
        conversation = load_conversation(session_id)
        return {"session_id": session_id, "messages": conversation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Key Changes Explained

Understanding the differences between this version and the previous OpenAI-based code will help you work with other Bedrock-based projects in the future.

**1. Bedrock client instead of OpenAI client**

Previously:
```python
from openai import OpenAI
client = OpenAI()  # reads OPENAI_API_KEY from environment automatically
```

Now:
```python
import boto3
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("DEFAULT_AWS_REGION", "us-east-1")
)
```

The `boto3` library is the standard AWS SDK for Python. You specify the service name (`bedrock-runtime` is the correct identifier for model inference — distinct from `bedrock` which is used for administrative operations like model access management). Authentication happens automatically because the Lambda function's IAM role is recognised by AWS.

**2. The message format difference**

OpenAI's API expects messages in this format:
```python
[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
    ...
]
```

Bedrock's `converse` API uses a slightly different structure. Each message's content is a list of *content blocks*, allowing for future extensibility (e.g., images, documents). For plain text:
```python
messages = [
    {"role": "user",      "content": [{"text": "Hello"}]},
    {"role": "assistant", "content": [{"text": "Hi there!"}]},
    ...
]
```

And the system prompt is passed as a separate parameter:
```python
bedrock_client.converse(
    modelId=BEDROCK_MODEL_ID,
    system=[{"text": "You are a helpful assistant."}],
    messages=messages,
    ...
)
```

> **Note on the original code in `day3.md`:** The first version of `call_bedrock` in the original guide injects the system prompt as a fake first user message (with `"System: ..."` prepended). This works, but it is not the recommended approach. The version above uses the `system` parameter directly, which is cleaner and ensures the model processes it correctly as a system instruction. The code above supersedes the original.

**3. The response structure**

With OpenAI, the response was a Pydantic object accessed like this:
```python
response.choices[0].message.content
```

With Bedrock, the response is a plain Python dictionary:
```python
response["output"]["message"]["content"][0]["text"]
```

The nested path reflects Bedrock's multi-modal response structure (`content` is a list because a response could include multiple blocks). For text-only responses, you always want index `[0]`.

**4. Error handling for Bedrock-specific errors**

The `ClientError` exception from `botocore` covers AWS API errors. Two are worth understanding:

- `ValidationException`: The request was rejected due to a formatting problem — most commonly a malformed message list (e.g., two consecutive messages with the same role, or an empty messages list)
- `AccessDeniedException`: The Lambda function's execution role does not have permission to call Bedrock. If you see this, double-check the role's attached policies (see Part 5, Step 2)

---

## Part 5: Deploy to Lambda

### Step 1: Update Lambda Environment Variables

Your Lambda function uses environment variables to configure its behaviour without hardcoding values in the code. You need to add two new variables and optionally remove one.

1. In the AWS Console, go to **Lambda**
2. Click on your `twin-api` function
3. Go to **Configuration** → **Environment variables** → **Edit**
4. Make the following changes:

**Add:**
| Key | Value | Purpose |
|-----|-------|---------|
| `DEFAULT_AWS_REGION` | `us-east-1` | The AWS region for the Bedrock client |
| `BEDROCK_MODEL_ID` | `global.amazon.nova-2-lite-v1:0` | The model to use for inference |

**Remove (optional but recommended):**
- `OPENAI_API_KEY` — No longer needed; removing it is good security hygiene

5. Click **Save**

> **Correcting the original guide:** The model ID shown in the original `day3.md` at this step is `amazon.nova-lite-v1:0`. This is the old format, without the version 2 update and without a cross-region prefix. Use `global.amazon.nova-2-lite-v1:0` instead, as described in Part 2.

**Alternative model IDs you can use:**

| Model | Recommended ID | Use Case |
|-------|---------------|----------|
| Nova Micro | `global.amazon.nova-2-micro-v1:0` | Fastest, cheapest — good for simple tasks |
| Nova Lite | `global.amazon.nova-2-lite-v1:0` | Balanced — recommended starting point |
| Nova Pro | `global.amazon.nova-2-pro-v1:0` | Most capable — for complex reasoning |

If you encounter quota errors with the `global.` prefix, substitute `us.`, `eu.`, or `ap.` as appropriate for your location.

### Step 2: Add Bedrock Permissions to the Lambda Execution Role

This is a separate and essential step that is easy to overlook. Your Lambda function runs under an **execution role** — an IAM role that defines what AWS services it is allowed to call. Even though your user account now has Bedrock permissions, the Lambda function needs its own permission to call Bedrock at runtime.

1. In Lambda → **Configuration** → **Permissions**
2. Under *Execution role*, click the role name — this opens the IAM console
3. Click **Add permissions** → **Attach policies**
4. Search for and select: **AmazonBedrockFullAccess**
5. Click **Add permissions**

**Why are there two separate permission grants?** Because IAM distinguishes between *human users* and *service roles*. When you (the user) log into the AWS Console, you operate under your user account's permissions. When Lambda runs your code, it operates under its execution role's permissions. These are independent identities with independent policies. Both need explicit Bedrock access.

### Step 3: Rebuild the Deployment Package

Since `requirements.txt` has changed (you removed `openai`), the deployment package needs to be rebuilt:

```bash
cd backend
uv add -r requirements.txt
uv run deploy.py
```

This script packages your backend code and its dependencies into `lambda-deployment.zip`, ready for upload. The build process uses Docker internally to ensure the compiled packages are compatible with the Lambda runtime environment (Amazon Linux), regardless of what operating system you are working on.

### Step 4: Upload the Package to Lambda

**Recommended: Via S3 (works for all connection speeds)**

**Mac/Linux:**
```bash
# Load environment variables from your .env file
source .env

# Navigate to the backend directory
cd backend

# Create a temporary S3 bucket with a unique name
DEPLOY_BUCKET="twin-deploy-$(date +%s)"

# Create the bucket in your configured region
aws s3 mb s3://$DEPLOY_BUCKET --region $DEFAULT_AWS_REGION

# Upload the deployment package to the temporary bucket
aws s3 cp lambda-deployment.zip s3://$DEPLOY_BUCKET/ --region $DEFAULT_AWS_REGION

# Tell Lambda to pull the new code from S3
aws lambda update-function-code \
    --function-name twin-api \
    --s3-bucket $DEPLOY_BUCKET \
    --s3-key lambda-deployment.zip \
    --region $DEFAULT_AWS_REGION

# Clean up: remove the temporary bucket
aws s3 rm s3://$DEPLOY_BUCKET/lambda-deployment.zip
aws s3 rb s3://$DEPLOY_BUCKET
```

**Windows (PowerShell — run from the project root):**
```powershell
# Load environment variables
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}

# Navigate to the backend directory
cd backend

# Create a unique bucket name using a timestamp
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$deployBucket = "twin-deploy-$timestamp"

# Create and use the temporary bucket
aws s3 mb s3://$deployBucket --region $env:DEFAULT_AWS_REGION
aws s3 cp lambda-deployment.zip s3://$deployBucket/ --region $env:DEFAULT_AWS_REGION

aws lambda update-function-code `
    --function-name twin-api `
    --s3-bucket $deployBucket `
    --s3-key lambda-deployment.zip `
    --region $env:DEFAULT_AWS_REGION

# Clean up
aws s3 rm s3://$deployBucket/lambda-deployment.zip
aws s3 rb s3://$deployBucket
```

**Why use S3 rather than uploading directly?** Lambda has a 50 MB direct upload limit via the CLI. More importantly, S3 uploads can resume if your connection drops, and Lambda pulls the package from S3 internally (which is faster and more reliable than streaming through the CLI from your machine). For anything beyond a trivial package, S3 is the better choice.

**Alternative: Direct upload (fast connections only)**
```bash
aws lambda update-function-code \
    --function-name twin-api \
    --zip-file fileb://lambda-deployment.zip \
    --region $DEFAULT_AWS_REGION
```

You can also upload directly through the Lambda Console UI: go to your function → **Code** tab → **Upload from** → **.zip file**.

Wait for the upload to complete. A successful update will show `"LastUpdateStatus": "Successful"` in the CLI output, or a green "Successfully updated the function" banner in the console.

### Step 5: Test the Lambda Function

Verify the updated function before testing the full stack:

1. In Lambda Console, go to the **Test** tab
2. Use your existing `HealthCheck` test event
3. Click **Test**

A successful response will look like this:

```json
{
  "statusCode": 200,
  "body": "{\"status\":\"healthy\",\"use_s3\":true,\"bedrock_model\":\"global.amazon.nova-2-lite-v1:0\"}"
}
```

The key thing to check is that `bedrock_model` reflects the model ID you set in the environment variable. If you see the old OpenAI-related fields or an error, review your environment variables and the deployment package.

---

## Part 6: Test Your Bedrock-Powered Twin

### Step 1: Test via the API Gateway health endpoint

Open a browser and navigate to:
```
https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/health
```

You should see a JSON response confirming the Bedrock model and `use_s3: true`.

### Step 2: Test via CloudFront

1. Visit your CloudFront URL: `https://YOUR-DISTRIBUTION.cloudfront.net`
2. Start a conversation with your Digital Twin
3. Send a few messages and verify that responses are returned successfully

> **If you receive "Sorry, I encountered an error. Please try again":** Open your browser's developer tools (F12), go to the Console or Network tab, and look for a 500 error from the API. If it is a Bedrock-related error, the most likely cause is a model ID format issue. Try adding or changing the geographic prefix:
> - `us.amazon.nova-2-lite-v1:0`
> - `eu.amazon.nova-2-lite-v1:0`
>
> Update the `BEDROCK_MODEL_ID` environment variable in Lambda, save, and try again.

---

## Part 7: CloudWatch Monitoring

CloudWatch is AWS's centralised monitoring and logging service. For a production AI application, monitoring is not optional — it is how you confirm that your system is behaving as designed, catch errors quickly, and understand usage patterns. This section walks through the most useful views.

### Step 1: View Lambda Metrics

1. In the AWS Console, go to **CloudWatch**
2. Click **Metrics** → **All metrics**
3. Click **Lambda** → **By Function Name**
4. Select `twin-api`
5. Check these key metrics to add them to the graph:
   - **Invocations** — Total number of function calls
   - **Duration** — How long each invocation took (in milliseconds)
   - **Errors** — Number of failed invocations
   - **Throttles** — Requests rejected because of concurrency limits

> **Shortcut:** The Lambda function itself has a **Monitor** tab in the console that displays a pre-configured CloudWatch dashboard. This is often the quickest way to see Lambda-specific metrics without navigating through CloudWatch manually.

### Step 2: View Bedrock Metrics — Confirming the Model is Being Called

This is one of the most important steps in the day. It provides concrete evidence that your application is genuinely routing requests through Amazon Bedrock, not some cached or fallback path.

1. In CloudWatch, navigate back to **All metrics**
2. Select **AWS/Bedrock** from the service list
3. Click **By Model Id**
4. Select your Nova model (e.g., `amazon.nova-2-lite-v1:0`)
5. Select these metrics to add to the chart:
   - **InvocationLatency** — How long the model took to respond (typically 500–2,000 ms for Nova)
   - **Invocations** — Number of times the model was called
   - **InputTokenCount** — Tokens sent to the model per request
   - **OutputTokenCount** — Tokens returned by the model per request

When you have done this and made some requests through your twin, you will see data points on the chart. A typical single conversation turn might show around 4,000–5,000 input tokens (because the system prompt and conversation history are included) and 100–300 output tokens. The invocation count will match the number of `/chat` requests made. This is your proof that Bedrock is being called.

### Step 3: View Lambda Logs

Logs give you detailed, request-level visibility — timestamps, durations, memory usage, and any print statements your code produces.

1. In CloudWatch, click **Log groups** in the left sidebar
2. Click on `/aws/lambda/twin-api`
3. Click on a recent log stream
4. Expand individual log entries to see:
   - Request start and end timestamps
   - Duration and billed duration
   - Memory usage
   - Any print() output from your code (useful for debugging)

You can also query across logs using **Log Insights**. For example, to analyse Lambda execution times:

```
fields @timestamp, @duration
| filter @type = "REPORT"
| stats avg(@duration) as avg_duration,
        min(@duration) as min_duration,
        max(@duration) as max_duration
by bin(5m)
```

### Step 4: Create a CloudWatch Dashboard (Optional)

A dashboard lets you see key metrics at a glance on a single screen. To create one:

1. In CloudWatch, click **Dashboards** → **Create dashboard**
2. Name it `twin-monitoring`
3. Add the following widgets:

**Widget 1: Bedrock Invocations (Line chart)**
- Namespace: `AWS/Bedrock` → By Model Id → your model
- Metric: Invocations, InputTokenCount, OutputTokenCount, InvocationLatency
- Statistic: Sum / Average as appropriate
- Period: 5 minutes

**Widget 2: Lambda Invocations and Duration (Line chart)**
- Namespace: `Lambda` → By Function Name → `twin-api`
- Metrics: Invocations (Sum), Duration (Average)
- Period: 5 minutes

**Widget 3: Lambda Error Count (Number)**
- Namespace: `Lambda` → By Function Name → `twin-api`
- Metric: Errors (Sum)
- Period: 1 hour
- A value of `0` here is what you want to see

Save the dashboard. You can now return to it at any time to get a quick view of your application's health and usage.

### Step 5: Set Up a Billing Alert (Strongly Recommended)

AWS charges accumulate in real time. Setting a budget alert ensures you are notified before spending reaches a threshold you are uncomfortable with.

1. In the AWS Console, search for **Billing** and open it
2. Click **Budgets** → **Create budget**
3. Choose **Cost budget** → **Use a template** → **Monthly cost budget**
4. Set:
   - **Budget name:** `twin-budget`
   - **Monthly budget amount:** $10 (or your preference)
   - **Alert threshold:** 80% of budget
   - **Email recipients:** your email address
5. Click **Create budget**

You will now receive an email notification if your AWS spend for the month approaches $10. Given the very low cost of the Nova models, this threshold is more than sufficient for course usage — it is primarily a safeguard against accidental runaway usage.

---

## Part 8: Performance Comparison (Optional)

### Comparing the Nova Models

To experiment with the different Nova tiers, update the `BEDROCK_MODEL_ID` environment variable in Lambda (Configuration → Environment variables) and re-test your twin. You do not need to redeploy the code — the environment variable change takes effect immediately.

| Model | Recommended ID | Typical Latency | Relative Cost |
|-------|---------------|-----------------|---------------|
| Nova Micro | `global.amazon.nova-2-micro-v1:0` | < 1 second | Very low |
| Nova Lite | `global.amazon.nova-2-lite-v1:0` | 1–2 seconds | Low |
| Nova Pro | `global.amazon.nova-2-pro-v1:0` | 2–4 seconds | Moderate |

> **Correcting the original guide:** The model IDs listed in Part 8 of `day3.md` use the old format (`amazon.nova-micro-v1:0`, etc.) without the version 2 update or cross-region prefixes. Use the IDs in the table above.

Note that "typical latency" depends on the complexity of the prompt, the length of the conversation history, and the current load on Bedrock. The figures above are approximate.

### Viewing Response Times in CloudWatch Log Insights

After testing each model, run the following Log Insights query to compare execution times:

```
fields @timestamp, @duration
| filter @type = "REPORT"
| stats avg(@duration) as avg_duration,
        min(@duration) as min_duration,
        max(@duration) as max_duration
by bin(5m)
```

This gives you average, minimum, and maximum Lambda execution times in five-minute buckets. Note that Lambda duration includes the Bedrock call, so a slower model will produce longer Lambda durations.

---

## Troubleshooting

### "Access Denied" errors

This error means something does not have permission to call Bedrock. Work through this checklist:

1. **Lambda execution role** — Go to Lambda → Configuration → Permissions → click the execution role name → verify `AmazonBedrockFullAccess` is attached. This is the most common cause.
2. **Model ID format** — Make sure the model ID string in your environment variable exactly matches a valid cross-region inference profile ID. Check for typos.
3. **Region** — Ensure the `DEFAULT_AWS_REGION` environment variable points to a region where Bedrock is available. `us-east-1` is always a safe choice.

### "Model Not Found" or "ValidationException" errors

1. Verify the model ID exactly: `global.amazon.nova-2-lite-v1:0` — these strings are case-sensitive and the version suffix (`:0`) is required
2. If using a regional prefix (`us.`, `eu.`, `ap.`), make sure it matches a supported region for that model
3. Check the [AWS Bedrock model IDs documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html) for the definitive list

### "Sorry, I encountered an error" in the chat UI

This message means the frontend received a non-200 response from the backend. To diagnose:

1. Open your browser's developer tools (F12) → Network tab
2. Send a chat message and look at the `/chat` request
3. Click on it and read the response body — it will contain the error detail
4. Then go to CloudWatch → Log groups → `/aws/lambda/twin-api` → latest log stream for the full server-side error

Common causes: wrong model ID, missing Bedrock permissions on the Lambda role, or a `ValidationException` due to message format issues.

### High Latency

If responses are taking more than a few seconds:

1. Try Nova Micro for the fastest responses
2. Check that Lambda's timeout is set to at least 30 seconds (Configuration → General configuration)
3. Consider increasing Lambda memory — AWS allocates CPU proportionally to memory, so more memory means faster execution as well as more RAM
4. Review CloudWatch Bedrock metrics for `InvocationLatency` to determine whether the slowness is in the model or in your Lambda code

---

## Cost Optimisation

### Choosing the Right Model

- Use **Nova Micro** for simple lookups, short answers, and high-volume use cases where cost matters most
- Use **Nova Lite** as the default for general-purpose conversation — it offers a good balance of quality and cost
- Reserve **Nova Pro** for tasks that genuinely require more sophisticated reasoning, and only if the quality difference is noticeable for your use case

### Controlling Costs in Code

1. **Limit conversation history:** The current code sends the last 50 messages (25 exchanges). Reducing this number lowers input token costs, at the expense of the model having less context about earlier parts of the conversation
2. **Tune `maxTokens`:** The current value is 2,000. If your responses are typically much shorter, reducing this does not save much (you are billed for actual tokens generated, not the maximum), but it does prevent unexpectedly verbose responses
3. **Set up billing alerts:** As described in Part 7, Step 5

---

## What You've Accomplished Today

- ✅ Replaced OpenAI with Amazon Bedrock as the AI inference provider
- ✅ Granted IAM permissions at both the user group level and the Lambda execution role level
- ✅ Understood model IDs, cross-region inference profiles, and how to handle quota issues
- ✅ Updated `server.py` to use the Bedrock `converse` API with proper message formatting
- ✅ Rebuilt and redeployed the Lambda function with updated dependencies
- ✅ Verified end-to-end functionality through the CloudFront-hosted frontend
- ✅ Used CloudWatch to confirm that Bedrock is being called, with real metrics as evidence
- ✅ Created a monitoring dashboard and billing alert

## Updated Architecture

Your Digital Twin application now looks like this:

```
User Browser
    │  HTTPS
    ▼
CloudFront (CDN)
    │
    ▼
S3 Static Website (React Frontend)
    │  HTTPS API Calls
    ▼
API Gateway
    │
    ▼
Lambda Function (FastAPI Backend)
    │
    ├──► AWS Bedrock (Nova models — AI responses)   ← New today
    │
    └──► S3 Memory Bucket (conversation history)
```

Every component now lives within AWS. There are no external API calls, no third-party API keys, and a single bill.

## Next Steps

Tomorrow (Day 4), you will be introduced to **Terraform** — an infrastructure-as-code tool that lets you define your entire AWS environment in configuration files and deploy it with a single command. Everything you built manually across Days 1–3 (Lambda, S3, API Gateway, CloudFront, IAM roles) can be described in Terraform and reproduced reliably in any environment. This is the standard approach for production cloud deployments, and it will make the manual work from this week feel very worthwhile in retrospect.

---

## Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Bedrock Converse API Reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
- [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [Bedrock Model IDs Reference](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)
- [CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)
- [AWS Cost Management](https://aws.amazon.com/cost-management/)
- [Q42 — Bedrock Quota and Access FAQ](https://edwarddonner.com/faq)
