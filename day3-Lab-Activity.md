# Day 3 Lab Activity: Transitioning to AWS Bedrock
### Hands-On Practice Manual

---

> **How to use this lab manual**
>
> This activity is structured as a guided lab. Each section contains:
> - 📖 **Background** — a short explanation of the concept before you act on it
> - ✅ **Guided Steps** — instructions you follow directly
> - 🔧 **Your Task** — sections where you must complete something yourself (write code, fill in blanks, answer questions, or make a decision)
> - 💬 **Reflection prompts** — short questions to consolidate your understanding
>
> Work through the sections in order. Do not skip ahead — each part builds on the previous one.
>
> **Estimated time:** 90–120 minutes

---

## Pre-Lab: What You're Building

Before you start, read this architecture diagram carefully. By the end of this lab, your application will look like this:

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
    ├──► AWS Bedrock (Nova models — AI responses)   ← You are building this today
    │
    └──► S3 Memory Bucket (conversation history)
```

---

### 🔧 Pre-Lab Task: Architecture Audit

Answer the following questions **before** you start the lab. Use your knowledge from Days 1 and 2. Write your answers in the space provided.

**Question 1:** Which component in the diagram above was responsible for AI responses *before* today's changes? What did it require that Bedrock does not?

```
Your answer:



```

**Question 2:** Why does it matter that the AI call now stays *inside* AWS rather than going to an external provider? Name at least two reasons.

```
Your answer:



```

**Question 3:** In your own words, what is the purpose of IAM in AWS?

```
Your answer:



```

---

## Lab 1: Configuring IAM Permissions

### 📖 Background

AWS uses a **deny-by-default** security model. This means that no AWS service or user can take any action unless a permission has been explicitly granted. Today you need to grant Bedrock permissions in two separate places:

1. Your **user group** (`TwinAccess`) — controls what *you* as a human user can do in the console
2. The **Lambda execution role** — controls what the *Lambda function* can do when your code runs

These are not the same thing. Even if your own user account has full Bedrock access, your Lambda function will still get an `AccessDeniedException` until it has its own permission. This is a very common mistake — you will address both in this lab.

---

### ✅ Guided Steps — Part A: User Group Permissions

1. Go to [aws.amazon.com](https://aws.amazon.com) and sign in as the **root user** (the email address you used to create the account).

   > **Why root?** Modifying IAM group policies requires elevated privileges that your day-to-day IAM user (`aiengineer`) does not have. Root has unrestricted access.

2. In the search bar at the top, search for **IAM** and open it.

3. In the left sidebar, click **User groups**.

4. Click on **TwinAccess**.

5. Click the **Permissions** tab → **Add permissions** → **Attach policies**.

6. Search for and select:
   - `AmazonBedrockFullAccess`
   - `CloudWatchFullAccess`

7. Click **Attach policies**.

---

### 🔧 Your Task 1.1 — Complete the Permissions Table

After attaching the two new policies, your `TwinAccess` group should have a total of **eight** policies. Fill in the missing information in the table below. For the **Purpose** column, write a one-line description in your own words.

| Policy | Purpose (write your own) | Status |
|--------|--------------------------|--------|
| `AWSLambda_FullAccess` | | From Day 1–2 |
| `AmazonS3FullAccess` | | From Day 1–2 |
| `AmazonAPIGatewayAdministrator` | | From Day 1–2 |
| `CloudFrontFullAccess` | | From Day 1–2 |
| `IAMReadOnlyAccess` | | From Day 1–2 |
| `AmazonBedrockFullAccess` | | ✅ Added today |
| `CloudWatchFullAccess` | | ✅ Added today |
| `AmazonDynamoDBFullAccess` | | ⚠️ Add this now — needed for Day 5 |

> **Action:** If `AmazonDynamoDBFullAccess` is not already in the list, add it now following the same steps above. Adding it today means you will not hit a permissions error on Day 5.

---

### ✅ Guided Steps — Part B: Switch Back to Your IAM User

1. Sign out of the root account.
2. Sign back in as your IAM user `aiengineer`.
3. Confirm you are signed in as the right account by checking the name in the **top-right corner** of the AWS Console.

---

### 💬 Reflection 1

Why must you sign back in as your IAM user after configuring permissions — why not just continue working as root?

```
Your answer:



```

---

## Lab 2: Understanding Model IDs and Cross-Region Inference

### 📖 Background

Amazon Bedrock gives you access to a catalogue of foundation models. For today's lab, you are using Amazon's own **Nova** model family. Before the course videos were recorded, AWS changed both how models are accessed and how they are named. This section ensures you are using the correct, up-to-date format.

**The two changes to know:**

1. Nova has been updated from version 1 to version 2. Model IDs now include `nova-2` instead of `nova`.

2. AWS now recommends using **cross-region inference profiles** — model IDs with a geographic prefix. This tells Bedrock it can route your request to the most available region, which gives you higher quotas and fewer throttling errors.

The prefix options are:

| Prefix | Meaning |
|--------|---------|
| `global.` | AWS picks the best region worldwide (start here) |
| `us.` | United States regions only |
| `eu.` | European regions only |
| `ap.` | Asia-Pacific regions only |

---

### 🔧 Your Task 2.1 — Construct the Correct Model IDs

You have been given the **old-format** model IDs from the original course videos. Rewrite each one in the **correct current format**, using the `global.` prefix and the version 2 naming convention.

| Old Model ID (do not use) | Correct Model ID (write yours here) |
|---------------------------|--------------------------------------|
| `amazon.nova-micro-v1:0` | |
| `amazon.nova-lite-v1:0` | |
| `amazon.nova-pro-v1:0` | |

> **Check your answers:** Each correct ID should follow this pattern: `global.amazon.nova-2-[tier]-v1:0`

---

### 🔧 Your Task 2.2 — Decision: Which Prefix Would You Use?

For each scenario below, decide which prefix (`global.`, `us.`, `eu.`, or `ap.`) you would use and explain your reasoning.

**Scenario A:** You are building a production application for a European company and must ensure all data stays within EU infrastructure for compliance reasons.

```
Prefix: 
Reason:

```

**Scenario B:** You are a student running experiments and want the lowest possible chance of hitting quota limits.

```
Prefix: 
Reason:

```

**Scenario C:** You get a `ThrottlingException` with `global.amazon.nova-2-lite-v1:0`. What should you try next?

```
Your answer:

```

---

## Lab 3: Understanding Bedrock Costs

### 📖 Background

Bedrock charges based on **tokens** — the units that language models use to process text. One token is roughly three-quarters of a word. Every request has:
- **Input tokens:** everything sent *to* the model (system prompt + conversation history + new message)
- **Output tokens:** the text the model generates *in response*

Pricing is quoted **per 1,000 tokens**. This is an important detail: some providers quote per million tokens, which makes the numbers look very different. Always check which unit is being used when comparing prices.

Crucially, Bedrock does not require a separate API key. Your Lambda function authenticates to Bedrock using its **IAM execution role** — the same permission system that governs all other AWS services. This is more secure than managing API keys, and costs appear directly on your AWS bill.

---

### 🔧 Your Task 3.1 — Cost Estimation

A typical conversation turn with your Digital Twin sends approximately **1,500 input tokens** (system prompt + history + new message) and generates **250 output tokens** in response.

Use the [AWS Bedrock Pricing page](https://aws.amazon.com/bedrock/pricing/) to look up the current Nova Lite pricing, then fill in the table below.

| | Input token price (per 1,000) | Output token price (per 1,000) |
|-|-------------------------------|-------------------------------|
| Nova Lite | $ | $ |

Now calculate the cost of **one conversation turn** with Nova Lite:

```
Input cost  = 1,500 tokens ÷ 1,000 × $[your input price]  = $___________

Output cost = 250 tokens ÷ 1,000 × $[your output price]   = $___________

Total cost per turn                                         = $___________
```

Using that total, estimate how many conversation turns you could have for **$1.00**:

```
Number of turns for $1.00 = $1.00 ÷ $[cost per turn] ≈ ___________
```

---

### 💬 Reflection 2

You noticed that the pricing page quotes costs per 1,000 tokens. A student looks at the Nova Micro price (something like $0.000035 per 1,000 input tokens) and says "these numbers are tiny, they must be per million tokens like other providers." How would you explain why they are wrong?

```
Your answer:



```

---

## Lab 4: Updating the Code

This is the core coding section of the lab. You will make two code changes: updating `requirements.txt` and rewriting the Bedrock integration in `server.py`.

---

### Part A: Update `requirements.txt`

### 📖 Background

The `requirements.txt` file lists all the Python packages your backend depends on. When the deployment package is built, these packages are installed and bundled into the ZIP file that Lambda runs. Including unnecessary packages wastes space, can introduce security vulnerabilities, and causes confusion. Since you are removing OpenAI, its package should go too.

Good news: `boto3` is already in your requirements because you used it for S3 on Day 2. The same library handles Bedrock — you just need to use a different service name when creating the client.

---

### 🔧 Your Task 4.1 — Edit `requirements.txt`

Open `twin/backend/requirements.txt`. It currently looks like this:

```
fastapi
uvicorn
python-dotenv
python-multipart
boto3
pypdf
openai
mangum
```

Make the necessary change and write the corrected file contents here:

```
# Write the corrected requirements.txt below:




```

> **What to change:** Remove the one package that is no longer needed. Do not add any new packages — none are required for Bedrock.

---

### Part B: Rewrite `server.py`

### 📖 Background

The key differences between the OpenAI integration and the Bedrock integration are:

**1. Creating the client**

| | Code |
|-|------|
| OpenAI | `client = OpenAI()` — uses `OPENAI_API_KEY` automatically |
| Bedrock | `boto3.client(service_name="bedrock-runtime", region_name=...)` — uses IAM role automatically |

Note the service name: `bedrock-runtime` is for *inference* (calling models). The service name `bedrock` (without `-runtime`) is for *administration* (managing model access). You want `bedrock-runtime`.

**2. The message format**

OpenAI expects a flat list including the system message:
```python
[
    {"role": "system", "content": "..."},
    {"role": "user",   "content": "..."},
    ...
]
```

Bedrock's `converse` API separates the system prompt from the conversation messages:
```python
# System prompt as a separate parameter
system=[{"text": "..."}]

# Conversation as a list of content-block messages
messages=[
    {"role": "user",      "content": [{"text": "..."}]},
    {"role": "assistant", "content": [{"text": "..."}]},
    ...
]
```

Notice that `content` in each Bedrock message is a **list of blocks** (e.g., `[{"text": "..."}]`), not a plain string. This design allows Bedrock to support multi-modal content (images, documents) in the future. For now, each block is always `{"text": "your text here"}`.

**3. Reading the response**

| | Code |
|-|------|
| OpenAI | `response.choices[0].message.content` — a Pydantic object |
| Bedrock | `response["output"]["message"]["content"][0]["text"]` — a plain Python dict |

---

### 🔧 Your Task 4.2 — Initialise the Bedrock Client

The code below is incomplete. Fill in the three blanks to correctly create the Bedrock client. Use what you learned in the Background section above.

```python
import boto3
import os

bedrock_client = boto3.client(
    service_name=____________,          # Blank 1: the correct Bedrock service name for inference
    region_name=os.getenv(___________, "us-east-1")   # Blank 2: the environment variable name
)

BEDROCK_MODEL_ID = os.getenv(___________, "global.amazon.nova-2-lite-v1:0")  # Blank 3: the env var name
```

Write your completed version here:

```python
# Your completed code:

bedrock_client = boto3.client(
    service_name=_______________,
    region_name=os.getenv(_______________, "us-east-1")
)

BEDROCK_MODEL_ID = os.getenv(_______________, "global.amazon.nova-2-lite-v1:0")
```

---

### 🔧 Your Task 4.3 — Convert the Conversation History to Bedrock Format

The function below converts your stored conversation history (a list of dicts with `role` and `content` keys) into the format Bedrock expects. The loop body is incomplete — fill in the blank to produce correctly formatted Bedrock messages.

```python
def convert_to_bedrock_messages(conversation):
    messages = []
    for msg in conversation[-50:]:          # Limit to last 50 entries (25 exchanges)
        messages.append({
            "role": msg["role"],
            "content": _______________      # Blank: what should content look like for Bedrock?
        })
    return messages
```

> **Hint:** Each message's `content` in Bedrock format is a list containing a single dict. That dict has one key: `"text"`, whose value is the message content string from your stored history.

Write your completed version here:

```python
def convert_to_bedrock_messages(conversation):
    messages = []
    for msg in conversation[-50:]:
        messages.append({
            "role": msg["role"],
            "content": _______________
        })
    return messages
```

---

### 🔧 Your Task 4.4 — Complete the `call_bedrock` Function

Below is the `call_bedrock` function with several key lines missing. Fill in each blank using what you have learned. Comments explain what each blank should do.

```python
from botocore.exceptions import ClientError
from fastapi import HTTPException

def call_bedrock(conversation, user_message):
    
    # Step 1: Convert history to Bedrock format
    messages = convert_to_bedrock_messages(conversation)
    
    # Step 2: Append the new user message in Bedrock format
    messages.append({
        "role": _______________,            # Blank A: which role is the new message?
        "content": _______________          # Blank B: wrap user_message in the correct Bedrock format
    })
    
    try:
        # Step 3: Call the Bedrock converse API
        response = bedrock_client.converse(
            modelId=_______________,        # Blank C: which variable holds the model ID?
            system=[{"text": prompt()}],    # System prompt passed as separate parameter
            messages=messages,
            inferenceConfig={
                "maxTokens": 2000,
                "temperature": 0.7,
                "topP": 0.9
            }
        )
        
        # Step 4: Extract the text from the response
        # The response is a plain Python dict, not a Pydantic object.
        # The path is: output -> message -> content (a list) -> first item -> text
        return _______________              # Blank D: write the full path to extract the response text

    except ClientError as e:
        error_code = e.response['Error']['Code']
        
        if error_code == 'ValidationException':
            # This usually means the message list is malformed —
            # e.g., two messages in a row with the same role.
            print(f"Bedrock validation error: {e}")
            raise HTTPException(status_code=400, detail="Invalid message format for Bedrock")
        
        elif error_code == _______________: # Blank E: which error code means "no permission"?
            print(f"Bedrock access denied: {e}")
            raise HTTPException(status_code=403, detail="Access denied to Bedrock model")
        
        else:
            print(f"Bedrock error: {e}")
            raise HTTPException(status_code=500, detail=f"Bedrock error: {str(e)}")
```

Write your completed function in full below. Replace all blanks with correct values.

```python
def call_bedrock(conversation, user_message):

    messages = convert_to_bedrock_messages(conversation)

    messages.append({
        "role": _______________,
        "content": _______________
    })

    try:
        response = bedrock_client.converse(
            modelId=_______________,
            system=[{"text": prompt()}],
            messages=messages,
            inferenceConfig={
                "maxTokens": 2000,
                "temperature": 0.7,
                "topP": 0.9
            }
        )

        return _______________

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ValidationException':
            raise HTTPException(status_code=400, detail="Invalid message format for Bedrock")
        elif error_code == _______________:
            raise HTTPException(status_code=403, detail="Access denied to Bedrock model")
        else:
            raise HTTPException(status_code=500, detail=f"Bedrock error: {str(e)}")
```

---

### 🔧 Your Task 4.5 — Spot the Bug

The code snippet below contains a subtle but serious bug that would cause a `ValidationException` from Bedrock. Read it carefully and identify what is wrong.

```python
def build_messages(conversation, user_message, system_prompt):
    messages = []
    
    # Add system prompt
    messages.append({
        "role": "user",
        "content": [{"text": f"System: {system_prompt}"}]
    })
    
    # Add conversation history
    for msg in conversation[-50:]:
        messages.append({
            "role": msg["role"],
            "content": [{"text": msg["content"]}]
        })
    
    # Add the new user message
    messages.append({
        "role": "user",
        "content": [{"text": user_message}]
    })
    
    return messages
```

**What is wrong with this code?**

```
Describe the bug:



```

**What would happen if the last message in `conversation` was from the user?**

```
Your answer:



```

**How does the corrected `call_bedrock` in this lab avoid this problem?**

```
Your answer:



```

> **Hint:** Bedrock's `converse` API will throw a `ValidationException` if two consecutive messages have the same `role`.

---

### 💬 Reflection 3

Why is it better to pass the system prompt via the `system=[{"text": ...}]` parameter rather than prepending it as a fake user message at the start of the messages list?

```
Your answer:



```

---

## Lab 5: Deploying to Lambda

### 📖 Background

Lambda functions use **environment variables** to receive configuration at runtime without hardcoding values in the code. This is important because:
- It lets you change configuration (like switching models) without redeploying code
- It keeps sensitive values out of your source code
- It makes your code work identically across different environments

Your Lambda function also needs its own explicit permission to call Bedrock — separate from your user account's permissions. This is because Lambda runs under a service **execution role**, which is an IAM role (not a user), and IAM treats users and roles as completely independent identities.

---

### ✅ Guided Steps — Environment Variables

1. In the AWS Console, go to **Lambda**.
2. Click on your `twin-api` function.
3. Go to **Configuration** → **Environment variables** → **Edit**.

---

### 🔧 Your Task 5.1 — Fill in the Environment Variable Values

Using what you have learned in Labs 2 and 4, fill in the correct values for the environment variables you need to add. Write your answers in the table before you type them into the console.

| Key | Value (fill this in) | Purpose |
|-----|----------------------|---------|
| `DEFAULT_AWS_REGION` | | AWS region for the Bedrock client |
| `BEDROCK_MODEL_ID` | | The model ID including cross-region prefix |

> **Note:** `OPENAI_API_KEY` can now be deleted. Removing credentials you no longer use is good security hygiene.

After completing the table, enter these values in the Lambda console and click **Save**.

---

### ✅ Guided Steps — Lambda Execution Role Permissions

1. In Lambda, go to **Configuration** → **Permissions**.
2. Under *Execution role*, click the role name link. This opens IAM.
3. Click **Add permissions** → **Attach policies**.
4. Search for `AmazonBedrockFullAccess` and select it.
5. Click **Add permissions**.

---

### 🔧 Your Task 5.2 — Explain the Two-Permission Requirement

In your own words, explain why you needed to grant Bedrock permissions in *two separate places*: once on the `TwinAccess` user group (Lab 1) and again on the Lambda execution role (this step). What would happen if you only did one of them?

```
Your explanation:



What happens if you only grant it to TwinAccess but not the Lambda role?



What happens if you only grant it to the Lambda role but not TwinAccess?



```

---

### ✅ Guided Steps — Rebuild and Deploy

Run the following commands from your project's `backend` directory to rebuild the deployment package with the updated code and without the `openai` package:

```bash
cd backend
uv add -r requirements.txt
uv run deploy.py
```

Then upload to Lambda via S3 (recommended for reliable deployment on all connection speeds):

**Mac/Linux:**
```bash
source .env
cd backend

DEPLOY_BUCKET="twin-deploy-$(date +%s)"
aws s3 mb s3://$DEPLOY_BUCKET --region $DEFAULT_AWS_REGION
aws s3 cp lambda-deployment.zip s3://$DEPLOY_BUCKET/ --region $DEFAULT_AWS_REGION

aws lambda update-function-code \
    --function-name twin-api \
    --s3-bucket $DEPLOY_BUCKET \
    --s3-key lambda-deployment.zip \
    --region $DEFAULT_AWS_REGION

aws s3 rm s3://$DEPLOY_BUCKET/lambda-deployment.zip
aws s3 rb s3://$DEPLOY_BUCKET
```

**Windows (PowerShell — from the project root):**
```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
cd backend

$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$deployBucket = "twin-deploy-$timestamp"

aws s3 mb s3://$deployBucket --region $env:DEFAULT_AWS_REGION
aws s3 cp lambda-deployment.zip s3://$deployBucket/ --region $env:DEFAULT_AWS_REGION

aws lambda update-function-code `
    --function-name twin-api `
    --s3-bucket $deployBucket `
    --s3-key lambda-deployment.zip `
    --region $env:DEFAULT_AWS_REGION

aws s3 rm s3://$deployBucket/lambda-deployment.zip
aws s3 rb s3://$deployBucket
```

---

### 🔧 Your Task 5.3 — Verify the Deployment

After the upload completes, test the Lambda function directly:

1. In Lambda Console, go to the **Test** tab.
2. Select your existing `HealthCheck` test event and click **Test**.
3. Examine the response body.

A successful response will contain a `bedrock_model` field. Write what you observe here:

```json
{
  "statusCode": 200,
  "body": "Write the actual response body you received here:"
}
```

**Is the model ID in the response exactly what you expected?**

```
Yes / No — explain:

```

> **If something is wrong:** The most common issues are a missing Bedrock permission on the Lambda role, or a typo in the `BEDROCK_MODEL_ID` environment variable. Go back and check those two things first.

---

## Lab 6: Testing and CloudWatch Monitoring

### 📖 Background

Deploying code and getting a successful health check response is a good sign — but it is not proof that Bedrock is actually being called when a user sends a chat message. CloudWatch provides the evidence. By examining **Bedrock metrics**, you can see exactly how many times the model was invoked, how many tokens were processed, and how long the model took to respond. This kind of observability is a standard requirement for production AI applications.

---

### ✅ Guided Steps — End-to-End Test

1. Visit your CloudFront URL: `https://YOUR-DISTRIBUTION.cloudfront.net`
2. Send **three different messages** to your Digital Twin.
3. Record whether each one returned a response or an error.

| Message sent | Response received? | Notes |
|--------------|--------------------|-------|
| | Yes / No | |
| | Yes / No | |
| | Yes / No | |

> **If you see "Sorry, I encountered an error":** Open your browser's developer tools (F12) and check the Network tab. Find the `/chat` request and read the response body to identify the specific error. The most common causes are a wrong model ID format or missing Bedrock permissions on the Lambda role.

---

### ✅ Guided Steps — Lambda Metrics in CloudWatch

1. In the AWS Console, go to **CloudWatch**.
2. Click **Metrics** → **All metrics**.
3. Select **Lambda** → **By Function Name** → **twin-api**.
4. Check the boxes next to: **Invocations**, **Duration**, **Errors**, and **Throttles**.

> **Shortcut tip:** You can also reach these metrics directly from Lambda → Monitor tab. This is often the quickest route for function-specific monitoring.

---

### ✅ Guided Steps — Bedrock Metrics in CloudWatch

1. Navigate back to **All metrics** in CloudWatch.
2. Select **AWS/Bedrock** → **By Model Id**.
3. Select your Nova model.
4. Check the boxes next to: **Invocations**, **InvocationLatency**, **InputTokenCount**, **OutputTokenCount**.

---

### 🔧 Your Task 6.1 — Read Your Bedrock Metrics

After adding the Bedrock metrics to your CloudWatch chart, look at the data points generated by the three test messages you sent. Record what you observe.

```
Number of Bedrock Invocations shown: _______________

Approximate InvocationLatency (ms): _______________

Approximate InputTokenCount per request: _______________

Approximate OutputTokenCount per request: _______________
```

**Does the number of Bedrock invocations match the number of chat messages you sent?**

```
Yes / No — explain:

```

**Why is InputTokenCount much higher than you might expect from just a short message?**

```
Your answer:



```

> **Hint:** Think about everything that gets sent to the model on each request — not just the current message.

---

### ✅ Guided Steps — Lambda Log Insights

1. In CloudWatch, click **Log groups** → `/aws/lambda/twin-api`.
2. Click on the most recent log stream.
3. Expand a few log entries to see the request details.

Now run a Log Insights query to analyse execution times:

1. In CloudWatch, click **Log Insights** in the left sidebar.
2. Select `/aws/lambda/twin-api` as the log group.
3. Paste the following query and click **Run query**:

```
fields @timestamp, @duration
| filter @type = "REPORT"
| stats avg(@duration) as avg_duration,
        min(@duration) as min_duration,
        max(@duration) as max_duration
by bin(5m)
```

---

### 🔧 Your Task 6.2 — Interpret the Log Insights Output

Record the results of your query:

```
Average Lambda duration (avg_duration): _______________ ms

Minimum Lambda duration (min_duration): _______________ ms

Maximum Lambda duration (max_duration): _______________ ms
```

**Lambda's duration includes the time waiting for Bedrock to respond. What does a high `max_duration` value most likely indicate?**

```
Your answer:



```

---

### ✅ Guided Steps — Create a CloudWatch Dashboard

1. In CloudWatch, click **Dashboards** → **Create dashboard**.
2. Name it `twin-monitoring`.

Add the following three widgets:

**Widget 1 — Bedrock activity (Line chart)**
- Navigate to: `AWS/Bedrock` → By Model Id → your model
- Add metrics: Invocations, InputTokenCount, OutputTokenCount, InvocationLatency
- Period: 5 minutes

**Widget 2 — Lambda activity (Line chart)**
- Navigate to: `Lambda` → By Function Name → twin-api
- Add metrics: Invocations (Sum), Duration (Average)
- Period: 5 minutes

**Widget 3 — Error count (Number)**
- Navigate to: `Lambda` → By Function Name → twin-api
- Add metric: Errors (Sum)
- Period: 1 hour

3. Save the dashboard.

---

### ✅ Guided Steps — Set Up a Billing Alert

1. In the AWS Console, search for **Billing** and open it.
2. Click **Budgets** → **Create budget**.
3. Choose **Cost budget** → **Use a template** → **Monthly cost budget**.
4. Set:
   - Budget name: `twin-budget`
   - Monthly amount: $10
   - Alert threshold: 80%
   - Your email address
5. Click **Create budget**.

---

### 💬 Reflection 4

You now have three separate monitoring tools: Lambda metrics, Bedrock metrics, and Lambda logs. If a user reported that the chat was very slow, which monitoring source would you check first and why?

```
Your answer:



```

---

## Lab 7 (Extension): Compare the Nova Models

> **This section is optional but strongly recommended.** It reinforces understanding of how model choice affects real-world performance and cost.

### 📖 Background

You can switch between Nova Micro, Lite, and Pro without changing any code — just update the `BEDROCK_MODEL_ID` environment variable in Lambda. The change takes effect immediately (no redeployment needed).

| Model | Recommended ID | Expected Latency | Relative Cost |
|-------|---------------|-----------------|---------------|
| Nova Micro | `global.amazon.nova-2-micro-v1:0` | < 1 second | Very low |
| Nova Lite | `global.amazon.nova-2-lite-v1:0` | 1–2 seconds | Low |
| Nova Pro | `global.amazon.nova-2-pro-v1:0` | 2–4 seconds | Moderate |

---

### 🔧 Your Task 7.1 — Model Comparison Experiment

Send the **same three messages** to your Digital Twin using each of the three Nova models. Record your observations.

**Test prompt 1:** "Summarise your professional background in one paragraph."

**Test prompt 2:** "Explain the difference between supervised and unsupervised machine learning."

**Test prompt 3:** "What would you recommend to someone just starting to learn cloud computing?"

For each model, note the response quality (subjective) and use CloudWatch to check the `InvocationLatency`.

| Model | Response quality (1–5) | Approx. latency (ms) | Tokens in response (approx.) |
|-------|----------------------|---------------------|------------------------------|
| Nova Micro | | | |
| Nova Lite | | | |
| Nova Pro | | | |

---

### 🔧 Your Task 7.2 — Model Selection Recommendation

Based on your experiment, answer the following:

**For a simple, high-volume FAQ chatbot that needs to respond in under a second, which model would you choose and why?**

```
Your answer:



```

**For a Digital Twin that needs to give detailed, nuanced answers about a complex topic, which model would you choose?**

```
Your answer:



```

**The guide mentions that Nova Pro is currently priced comparably to or below Claude Haiku. Does this change your intuition about when to use Pro?**

```
Your answer:



```

---

### 🔧 Your Task 7.3 — Cost Optimisation Decisions

The current code sends the last **50 messages** (25 exchanges) as conversation history on every request. Consider the cost and quality tradeoffs of changing this number.

**What would happen to cost if you reduced this to the last 10 messages (5 exchanges)?**

```
Your answer:



```

**What would happen to the quality of the conversation if you reduced it too aggressively?**

```
Your answer:



```

**What value would you choose for a production Digital Twin, and how would you decide?**

```
Your answer:



```

---

## Lab Completion Checklist

Work through this checklist before finishing the lab. Each item corresponds to a step you completed.

| Task | Done? |
|------|-------|
| Added `AmazonBedrockFullAccess` and `CloudWatchFullAccess` to `TwinAccess` group | ☐ |
| Added `AmazonDynamoDBFullAccess` to `TwinAccess` group (for Day 5) | ☐ |
| Confirmed signed back in as `aiengineer` IAM user | ☐ |
| Removed `openai` from `requirements.txt` | ☐ |
| Wrote a working `call_bedrock` function using the Bedrock `converse` API | ☐ |
| Added `DEFAULT_AWS_REGION` and `BEDROCK_MODEL_ID` environment variables to Lambda | ☐ |
| Removed `OPENAI_API_KEY` environment variable from Lambda | ☐ |
| Attached `AmazonBedrockFullAccess` to the Lambda execution role | ☐ |
| Rebuilt and deployed the Lambda package | ☐ |
| Verified the health check returns the correct Bedrock model ID | ☐ |
| Tested the Digital Twin via CloudFront and confirmed responses | ☐ |
| Viewed Bedrock metrics in CloudWatch and confirmed invocations | ☐ |
| Created the `twin-monitoring` CloudWatch dashboard | ☐ |
| Set up a `twin-budget` billing alert | ☐ |
| *(Extension)* Compared all three Nova models | ☐ |

---

## Answer Key — Quick Reference

Use this section only after completing the tasks yourself.

<details>
<summary><strong>Click to reveal answers</strong></summary>

### Task 4.2 — Bedrock Client

```python
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("DEFAULT_AWS_REGION", "us-east-1")
)

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.amazon.nova-2-lite-v1:0")
```

### Task 4.3 — Convert Conversation History

```python
def convert_to_bedrock_messages(conversation):
    messages = []
    for msg in conversation[-50:]:
        messages.append({
            "role": msg["role"],
            "content": [{"text": msg["content"]}]   # Content is a list of blocks
        })
    return messages
```

### Task 4.4 — Completed `call_bedrock`

```python
def call_bedrock(conversation, user_message):

    messages = convert_to_bedrock_messages(conversation)

    messages.append({
        "role": "user",                              # Blank A
        "content": [{"text": user_message}]         # Blank B
    })

    try:
        response = bedrock_client.converse(
            modelId=BEDROCK_MODEL_ID,                # Blank C
            system=[{"text": prompt()}],
            messages=messages,
            inferenceConfig={
                "maxTokens": 2000,
                "temperature": 0.7,
                "topP": 0.9
            }
        )

        return response["output"]["message"]["content"][0]["text"]   # Blank D

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ValidationException':
            raise HTTPException(status_code=400, detail="Invalid message format for Bedrock")
        elif error_code == 'AccessDeniedException':             # Blank E
            raise HTTPException(status_code=403, detail="Access denied to Bedrock model")
        else:
            raise HTTPException(status_code=500, detail=f"Bedrock error: {str(e)}")
```

### Task 4.5 — The Bug

The bug is that the system prompt is injected as a `"user"` message at the beginning of the list. If the first message in `conversation` is also from the `"user"` role, then the message list starts with two consecutive `user` messages. Bedrock requires that roles must alternate strictly between `user` and `assistant`. This would trigger a `ValidationException`. The corrected code avoids this entirely by using the `system=[...]` parameter instead.

### Task 2.1 — Correct Model IDs

```
global.amazon.nova-2-micro-v1:0
global.amazon.nova-2-lite-v1:0
global.amazon.nova-2-pro-v1:0
```

### Task 5.1 — Environment Variable Values

| Key | Value |
|-----|-------|
| `DEFAULT_AWS_REGION` | `us-east-1` |
| `BEDROCK_MODEL_ID` | `global.amazon.nova-2-lite-v1:0` |

</details>

---

## Troubleshooting Reference

Keep this section handy if something goes wrong during the lab.

| Error | Most Likely Cause | Fix |
|-------|-------------------|-----|
| `AccessDeniedException` from Bedrock | Lambda execution role is missing `AmazonBedrockFullAccess` | Lambda → Configuration → Permissions → role → attach policy |
| `ValidationException` from Bedrock | Two consecutive messages with the same role, or empty message list | Check `call_bedrock` logic; verify conversation history format |
| `"Sorry, I encountered an error"` in UI | Server-side error — could be any of the above | Open browser DevTools (F12) → Network → inspect `/chat` response body |
| Health check shows old OpenAI fields | Wrong or uncached deployment package | Redeploy; check the zip was built *after* code changes |
| High latency (> 5 seconds consistently) | Lambda timeout too short, or try Nova Micro | Lambda → Configuration → General → increase timeout to 30s |
| Bedrock metrics not showing in CloudWatch | No requests have been made yet, or wrong model selected | Send a chat message first; ensure you selected the matching model ID in CloudWatch |
