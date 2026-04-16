# Day 3: Transition to AWS Bedrock

## From OpenAI to AWS AI Services

Welcome to Day 3! Today, we're making a significant architectural shift - replacing OpenAI with AWS Bedrock for AI responses. This change brings several advantages: lower latency (requests stay within AWS), potential cost savings, and deeper integration with AWS services. You'll learn how enterprise applications leverage cloud-native AI services for production deployments.

## What You'll Learn Today

- **AWS Bedrock fundamentals** - Amazon's managed AI service
- **Nova models** - AWS's latest foundation models
- **IAM permissions for AI services** - Security best practices
- **Model selection** based on cost and performance
- **CloudWatch monitoring** for AI applications
- **Production AI deployment patterns** in AWS

## Understanding AWS Bedrock

### What is Amazon Bedrock?

Amazon Bedrock is AWS's fully managed service that provides access to foundation models (FMs) from leading AI companies through a single API. Key benefits include:

- **No infrastructure management** - Serverless AI models
- **Pay per request** - No upfront costs or idle charges
- **Low latency** - Models run in your AWS region
- **Enterprise security** - IAM integration, VPC endpoints, encryption
- **Multiple model choices** - Amazon, Anthropic, Meta, and more

### Amazon Nova Models

AWS's Nova family of models are their latest foundation models optimized for different use cases:

- **Nova Micro** - Fastest, most cost-effective for simple tasks
- **Nova Lite** - Balanced performance for general use
- **Nova Pro** - Highest capability for complex reasoning

Today, we'll implement all three so you can choose based on your needs.

## Part 1: Configure IAM Permissions

### Step 1: Sign In as Root User

Since we need to modify IAM permissions, sign in as the root user:

1. Go to [aws.amazon.com](https://aws.amazon.com)
2. Sign in with your **root user** credentials

### Step 2: Add Bedrock and CloudWatch Permissions to User Group

1. In AWS Console, search for **IAM**
2. Click **User groups** in the left sidebar
3. Click on **TwinAccess** (the group we created on Day 2)
4. Click **Permissions** tab → **Add permissions** → **Attach policies**
5. Search for and select these two policies:
   - **AmazonBedrockFullAccess** - For Bedrock AI services
   - **CloudWatchFullAccess** - For creating dashboards and viewing metrics
6. Click **Attach policies**

Your TwinAccess group now has these policies:
- AWSLambda_FullAccess
- AmazonS3FullAccess  
- AmazonAPIGatewayAdministrator
- CloudFrontFullAccess
- IAMReadOnlyAccess
- **AmazonBedrockFullAccess** (new!)
- **CloudWatchFullAccess** (new!)
- **AmazonDynamoDBFullAccess** (VERY new!)

That last entry was a catch by student Andy C (thanks once again Andy) - without this, you may get a permissions error in Day 5.

### Step 3: Sign Back In as IAM User

1. Sign out from the root account
2. Sign back in as `aiengineer` with your IAM credentials

## Part 2: Bedrock Model Access and Model IDs — Important Update

> **⚠️ The AWS Bedrock Model access page has been retired.** If you are following along with the course videos, you will see a step where I navigate to Bedrock → Model access and request access to the Nova models. **This step no longer exists and is no longer required.** Read the section below before proceeding.

### What has changed

AWS has retired the manual model access request flow. Foundation models — including all Amazon Nova models — are now **automatically available** in your account the first time they are invoked. There is nothing to click, no approval to wait for, and no "Access granted" status to check.

AWS has replaced manual activation with a **quota-based system**. This means:

- You can start calling Nova models immediately after setting up your Lambda function
- If you send a very high volume of requests quickly, you may hit a regional quota limit and receive a `ThrottlingException`
- In that case, you can request a quota increase through AWS Service Quotas → Amazon Bedrock

### Model ID changes

The model IDs shown in the course videos are outdated. There are two things to update:

**1. Nova has been updated to version 2.** The old format was:
```
amazon.nova-lite-v1:0
```
The current format is:
```
amazon.nova-2-lite-v1:0
```

**2. Use a cross-region inference profile.** Rather than a bare model ID, you should use an ID with a geographic prefix. This tells Bedrock it can route your request to the best available region, which gives you higher effective quotas and fewer throttling issues.

The prefix options are:

| Prefix | Coverage |
|--------|----------|
| `global.` | AWS selects the best region worldwide — **start here** |
| `us.` | United States regions only |
| `eu.` | European regions only |
| `ap.` | Asia-Pacific regions only |

**The model IDs you should use throughout this activity:**

| Model | Recommended ID |
|-------|---------------|
| Nova Micro | `global.amazon.nova-2-micro-v1:0` |
| Nova Lite | `global.amazon.nova-2-lite-v1:0` |
| Nova Pro | `global.amazon.nova-2-pro-v1:0` |

**Start with `global.amazon.nova-2-lite-v1:0`.** If you hit quota limits, switch to a geography-specific prefix for your region (`us.`, `eu.`, or `ap.`).

### Region note

Your Bedrock region does not need to match the region of your Lambda function or other AWS services. If you encounter issues, `us-east-1` is a reliable choice with broad model availability.

If you need to check or request a quota increase, see the [full write-up in Q42 here](https://edwarddonner.com/faq).

**For now, you do not need to do anything here.** Simply use `global.amazon.nova-2-lite-v1:0` as your model ID in the steps below and you are good to go.

## Part 3: Understanding Model Costs

### Nova Model Pricing

The Nova models offer different price points based on their capabilities:

- **Nova Micro** - Most cost-effective for simple tasks
- **Nova Lite** - Balanced cost for general use
- **Nova Pro** - Higher cost for complex reasoning

For current pricing details, visit: [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)

The pricing page will show you:
- Cost per 1,000 input tokens
- Cost per 1,000 output tokens
- Comparison with other available models
- Regional pricing differences

Generally, Nova Micro and Lite are very cost-effective options for most conversational AI use cases.

## Part 4: Update Your Code for Bedrock

### Step 1: Update Requirements

Update `twin/backend/requirements.txt` - remove the openai package since we're not using it:

```
fastapi
uvicorn
python-dotenv
python-multipart
boto3
pypdf
mangum
```

Note: We removed `openai` from the requirements.

### Step 2: Update the Server Code

Replace your `twin/backend/server.py` with this Bedrock-enabled version:

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

# Initialize Bedrock client - see Q42 on https://edwarddonner.com/faq if the Region gives you problems
bedrock_client = boto3.client(
    service_name="bedrock-runtime", 
    region_name=os.getenv("DEFAULT_AWS_REGION", "us-east-1")
)

# Bedrock model selection - see Q42 on https://edwarddonner.com/faq for more
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.amazon.nova-2-lite-v1:0")

# Memory storage configuration
USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET", "")
MEMORY_DIR = os.getenv("MEMORY_DIR", "../memory")

# Initialize S3 client if needed
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


# Memory management functions
def get_memory_path(session_id: str) -> str:
    return f"{session_id}.json"


def load_conversation(session_id: str) -> List[Dict]:
    """Load conversation history from storage"""
    if USE_S3:
        try:
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=get_memory_path(session_id))
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return []
            raise
    else:
        # Local file storage
        file_path = os.path.join(MEMORY_DIR, get_memory_path(session_id))
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return []


def save_conversation(session_id: str, messages: List[Dict]):
    """Save conversation history to storage"""
    if USE_S3:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=get_memory_path(session_id),
            Body=json.dumps(messages, indent=2),
            ContentType="application/json",
        )
    else:
        # Local file storage
        os.makedirs(MEMORY_DIR, exist_ok=True)
        file_path = os.path.join(MEMORY_DIR, get_memory_path(session_id))
        with open(file_path, "w") as f:
            json.dump(messages, f, indent=2)


def call_bedrock(conversation: List[Dict], user_message: str) -> str:
    """Call AWS Bedrock with conversation history"""

    # Build messages in Bedrock format from conversation history
    messages = []

    # Add conversation history (limit to last 25 exchanges)
    for msg in conversation[-50:]:
        messages.append({
            "role": msg["role"],
            "content": [{"text": msg["content"]}]
        })

    # Add current user message
    messages.append({
        "role": "user",
        "content": [{"text": user_message}]
    })

    try:
        # Call Bedrock using the converse API.
        # The system prompt is passed via the 'system' parameter — the correct
        # approach that avoids adding a fake user message to the messages list.
        response = bedrock_client.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": prompt()}],
            messages=messages,
            inferenceConfig={
                "maxTokens": 2000,
                "temperature": 0.7,
                "topP": 0.9
            }
        )
        
        # Extract the response text
        return response["output"]["message"]["content"][0]["text"]
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ValidationException':
            # Handle message format issues
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
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        # Load conversation history
        conversation = load_conversation(session_id)

        # Call Bedrock for response
        assistant_response = call_bedrock(conversation, request.message)

        # Update conversation history
        conversation.append(
            {"role": "user", "content": request.message, "timestamp": datetime.now().isoformat()}
        )
        conversation.append(
            {
                "role": "assistant",
                "content": assistant_response,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Save conversation
        save_conversation(session_id, conversation)

        return ChatResponse(response=assistant_response, session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    """Retrieve conversation history"""
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

1. **Removed OpenAI import** - No longer using `from openai import OpenAI`
2. **Added Bedrock client** - Using boto3 to connect to Bedrock
3. **New `call_bedrock` function** - Handles Bedrock's message format
4. **Model selection via environment variable** - Easy to switch between Nova models
5. **Better error handling** - Specific handling for Bedrock errors

## Part 5: Deploy to Lambda

### Step 1: Update Lambda Environment Variables

1. In AWS Console, go to **Lambda**
2. Click on your `twin-api` function
3. Go to **Configuration** → **Environment variables**
4. Click **Edit**
5. Add these new variables:
   - Key: `DEFAULT_AWS_REGION` | Value: `us-east-1` (or your region)
   - Key: `BEDROCK_MODEL_ID` | Value: `global.amazon.nova-2-lite-v1:0` (see Part 2 for model ID options and what to do if you hit quota errors)
6. You can now remove `OPENAI_API_KEY` since we're not using it
7. Click **Save**

### Model ID Options

You can change `BEDROCK_MODEL_ID` to any of the following. Always use the `global.` prefix for best availability, and switch to a region-specific prefix (`us.`, `eu.`, `ap.`) only if you encounter quota errors:

- `global.amazon.nova-2-micro-v1:0` - Fastest and cheapest
- `global.amazon.nova-2-lite-v1:0` - Balanced (recommended)
- `global.amazon.nova-2-pro-v1:0` - Most capable but more expensive

### Step 2: Add Bedrock Permissions to Lambda

Your Lambda function needs permission to call Bedrock:

1. In Lambda → **Configuration** → **Permissions**
2. Click on the execution role name (opens IAM)
3. Click **Add permissions** → **Attach policies**
4. Search for and select: **AmazonBedrockFullAccess**
5. Click **Add permissions**

### Step 3: Rebuild and Deploy Lambda Package

Since we changed requirements.txt, we need to install dependencies and rebuild the deployment package:

```bash
cd backend
uv add -r requirements.txt
uv run deploy.py
```

This creates a new `lambda-deployment.zip` with the updated dependencies.

### Step 4: Upload to Lambda

We'll upload your code via S3, which is more reliable for larger packages and slower connections.

**Mac/Linux:**

```bash
# Load environment variables
source .env

# Navigate to backend
cd backend

# Create a unique S3 bucket name for deployment
DEPLOY_BUCKET="twin-deploy-$(date +%s)"

# Create the bucket
aws s3 mb s3://$DEPLOY_BUCKET --region $DEFAULT_AWS_REGION

# Upload your zip file to S3
aws s3 cp lambda-deployment.zip s3://$DEPLOY_BUCKET/ --region $DEFAULT_AWS_REGION

# Update Lambda function from S3
aws lambda update-function-code \
    --function-name twin-api \
    --s3-bucket $DEPLOY_BUCKET \
    --s3-key lambda-deployment.zip \
    --region $DEFAULT_AWS_REGION

# Clean up: delete the temporary bucket
aws s3 rm s3://$DEPLOY_BUCKET/lambda-deployment.zip
aws s3 rb s3://$DEPLOY_BUCKET
```

**Windows (PowerShell): starting in the project root**

```powershell
# Load environment variables
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}

# Navigate to backend
cd backend

# Create a unique S3 bucket name for deployment
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$deployBucket = "twin-deploy-$timestamp"

# Create the bucket
aws s3 mb s3://$deployBucket --region $env:DEFAULT_AWS_REGION

# Upload your zip file to S3
aws s3 cp lambda-deployment.zip s3://$deployBucket/ --region $env:DEFAULT_AWS_REGION

# Update Lambda function from S3
aws lambda update-function-code `
    --function-name twin-api `
    --s3-bucket $deployBucket `
    --s3-key lambda-deployment.zip `
    --region $env:DEFAULT_AWS_REGION

# Clean up: delete the temporary bucket
aws s3 rm s3://$deployBucket/lambda-deployment.zip
aws s3 rb s3://$deployBucket
```

**Alternative: Direct Upload (for fast connections only)**

If you have a fast, stable connection, you can upload directly:

```bash
aws lambda update-function-code \
    --function-name twin-api \
    --zip-file fileb://lambda-deployment.zip \
    --region $DEFAULT_AWS_REGION
```

**Note**: The S3 method is recommended because:
- S3 uploads can resume if interrupted
- AWS Lambda pulls directly from S3 (faster than uploading through CLI)
- Works better with corporate firewalls and VPNs
- More reliable for packages over 10MB

Wait for the update to complete. You should see output with `"LastUpdateStatus": "Successful"`.

### Step 5: Test the Lambda Function

1. In Lambda console, go to the **Test** tab
2. Use your existing `HealthCheck` test event
3. Click **Test**
4. Check the response - it should now show the Bedrock model:

```json
{
  "statusCode": 200,
  "body": "{\"status\":\"healthy\",\"use_s3\":true,\"bedrock_model\":\"global.amazon.nova-2-lite-v1:0\"}"
}
```

## Part 6: Test Your Bedrock-Powered Twin

### Step 1: Test via API Gateway

Test your API directly in the browser: https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/health

You should see the Bedrock model in the response.

### Step 2: Test via CloudFront

1. Visit your CloudFront URL: `https://YOUR-DISTRIBUTION.cloudfront.net`
2. Start a conversation with your twin
3. Test that the chat is working properly - if you get a reply "Sorry, I encountered an error. Please try again" then see below.  
4. Verify that responses are coming through successfully

If your twin replies "Sorry, I encountered an error. Please try again" then you may be receiving an error from the server. See the Browser's Javascript Console and you'll probably see a 500 error from the server. If it's a Bedrock error, check that your `BEDROCK_MODEL_ID` environment variable uses the correct current format. Try switching to a geography-specific prefix if the global one is hitting quota limits:
- `us.amazon.nova-2-lite-v1:0`
- `eu.amazon.nova-2-lite-v1:0`
- `ap.amazon.nova-2-lite-v1:0`

## Part 7: CloudWatch Monitoring

Now let's set up monitoring to track your Bedrock usage and Lambda performance.

### Step 1: View Lambda Metrics

1. In AWS Console, go to **CloudWatch**
2. Click **Metrics** → **All metrics**
3. Click **Lambda** → **By Function Name**
4. Select `twin-api`
5. Check these key metrics:
   - ✅ Invocations
   - ✅ Duration
   - ✅ Errors
   - ✅ Throttles

### Step 2: View Bedrock Metrics

1. In CloudWatch Metrics, click **AWS/Bedrock**
2. Click **By Model Id**
3. Select your Nova model
4. Monitor these metrics:
   - **InvocationLatency** - Response time
   - **Invocations** - Number of requests
   - **InputTokenCount** - Tokens sent to the model
   - **OutputTokenCount** - Tokens generated by the model

### Step 3: View Lambda Logs

1. In CloudWatch, click **Log groups**
2. Click `/aws/lambda/twin-api`
3. Click on the latest log stream
4. You can see:
   - Each function invocation
   - Bedrock API calls
   - Any errors or warnings
   - Response times

### Step 4: Create a CloudWatch Dashboard (Optional)

Let's create a dashboard to monitor everything at a glance:

1. In CloudWatch, click **Dashboards** → **Create dashboard**
2. Name: `twin-monitoring`
3. Add widgets:

**Widget 1: Lambda Invocations**
- Widget type: Line
- Metric: Lambda → twin-api → Invocations
- Statistic: Sum
- Period: 5 minutes

**Widget 2: Lambda Duration**
- Widget type: Line  
- Metric: Lambda → twin-api → Duration
- Statistic: Average
- Period: 5 minutes

**Widget 3: Lambda Errors**
- Widget type: Number
- Metric: Lambda → twin-api → Errors
- Statistic: Sum
- Period: 1 hour

**Widget 4: Bedrock Invocations**
- Widget type: Line
- Metric: AWS/Bedrock → Your Model → Invocations
- Statistic: Sum
- Period: 5 minutes

### Step 5: Set Up Cost Monitoring

Monitor your AWS costs:

1. Go to **AWS Cost Explorer** (search in console)
2. Click **Cost Explorer** → **Launch Cost Explorer**
3. Filter by:
   - Service: Bedrock
   - Time: Last 7 days
4. You can see your Bedrock costs accumulating

### Step 6: Create a Billing Alert (Recommended)

1. In AWS Console, search for **Billing**
2. Click **Budgets** → **Create budget**
3. Choose **Cost budget**
4. Set:
   - Budget name: `twin-budget`
   - Monthly budget: $10 (or your preference)
   - Alert at 80% of budget
5. Enter your email for notifications
6. Click **Create budget**

## Part 8: Performance Comparison (Optional)

### Test Different Models

Let's compare the Nova models. Update your Lambda environment variable `BEDROCK_MODEL_ID` to test each:

1. **Nova Micro** (`global.amazon.nova-2-micro-v1:0`)
   - Fastest response (typically <1 second)
   - Good for simple Q&A
   - Lowest cost

2. **Nova Lite** (`global.amazon.nova-2-lite-v1:0`)
   - Balanced performance (1-2 seconds)
   - Good for most conversations
   - Recommended for production

3. **Nova Pro** (`global.amazon.nova-2-pro-v1:0`)
   - Most sophisticated responses (2-4 seconds)
   - Best for complex reasoning
   - Higher cost

### Monitoring Response Times

After testing each model, check CloudWatch:

1. Go to CloudWatch → Log groups → `/aws/lambda/twin-api`
2. Use Log Insights with this query:

```
fields @timestamp, @duration
| filter @type = "REPORT"
| stats avg(@duration) as avg_duration,
        min(@duration) as min_duration,
        max(@duration) as max_duration
by bin(5m)
```

This shows your Lambda execution times for each model.

## Troubleshooting

### "Access Denied" Errors

If you see access denied errors:

1. Verify IAM permissions:
   - Lambda execution role has `AmazonBedrockFullAccess`
   - Your IAM user has Bedrock permissions
2. Verify your model ID format is correct — use the `global.` prefix (e.g., `global.amazon.nova-2-lite-v1:0`). An incorrectly formatted model ID can produce an `AccessDeniedException` rather than a `ValidationException`
3. Verify region:
   - The `DEFAULT_AWS_REGION` environment variable is set in Lambda
   - `us-east-1` is a safe fallback if you are unsure

### "Model Not Found" or `ValidationException` Errors

1. Check that your model ID uses the current format:
   - ✅ `global.amazon.nova-2-lite-v1:0` (correct)
   - ❌ `amazon.nova-lite-v1:0` (old format — version 1, no prefix)
   - The `:0` suffix at the end is required — do not omit it
   - Model IDs are case-sensitive
2. If you changed to a geography-specific prefix, verify it matches a supported region for that model
3. Confirm the current IDs in the [Bedrock model catalogue](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html) — AWS updates version numbers periodically

### High Latency Issues

If responses are slow:

1. Try Nova Micro for faster responses
2. Check Lambda timeout (should be 30+ seconds)
3. Review CloudWatch logs for bottlenecks
4. Consider increasing Lambda memory (faster CPU)

### Chat Not Working

1. Check CloudWatch logs for specific errors
2. Test Lambda function directly in console
3. Verify all environment variables are set
4. Check API Gateway is forwarding requests correctly

## Cost Optimization Tips

### Choosing the Right Model

- **Nova Micro**: Use for greetings, simple FAQs, basic queries
- **Nova Lite**: Use for standard conversations, general Q&A
- **Nova Pro**: Reserve for complex analysis, detailed responses

### Reducing Costs

1. **Limit context window** - We're sending last 20 messages; reduce if possible
2. **Cache common responses** - Store FAQs in DynamoDB
3. **Set max tokens appropriately** - We use 2000; adjust based on needs
4. **Monitor usage** - Set up billing alerts
5. **Use request throttling** - Implement rate limiting in API Gateway

### Estimated Monthly Costs

Your costs will depend on:
- Number of conversations per month
- Average conversation length
- Choice of Nova model
- Lambda, API Gateway, and S3 usage

Check the [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/) page and use the AWS pricing calculator to estimate your specific usage costs.

## What You've Accomplished Today!

- ✅ Transitioned from OpenAI to AWS Bedrock
- ✅ Configured IAM permissions for AI services
- ✅ Implemented three different AI models
- ✅ Deployed Bedrock integration to Lambda
- ✅ Set up CloudWatch monitoring
- ✅ Created cost tracking and alerts
- ✅ Learned enterprise AI deployment patterns

## Architecture Recap

Your updated architecture:

```
User Browser
    ↓ HTTPS
CloudFront (CDN)
    ↓ 
S3 Static Website (Frontend)
    ↓ HTTPS API Calls
API Gateway
    ↓
Lambda Function (Backend)
    ↓
    ├── AWS Bedrock (AI responses)  ← NEW!
    └── S3 Memory Bucket (persistence)
```

All services now stay within AWS, providing:
- Lower latency (no external API calls)
- Better security (IAM integration)
- Potential cost savings
- Unified billing and monitoring

## Next Steps

Tomorrow (Day 4), we'll:
- Introduce Infrastructure as Code with Terraform
- Automate the entire deployment process
- Implement environment management (dev/staging/prod)
- Add advanced features like DynamoDB for memory
- Set up proper secret management

Your Digital Twin is now powered entirely by AWS services - a true cloud-native application!

## Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [Nova Model Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)
- [CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)
- [AWS Cost Management](https://aws.amazon.com/cost-management/)

Congratulations on successfully integrating AWS Bedrock! 🚀