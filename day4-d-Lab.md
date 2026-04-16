# Day 4 Lab: Infrastructure as Code with Terraform — Hands-On Practice

## About This Lab

This lab manual is designed to be worked through alongside the Day 4 Explanation Guide. Each exercise reinforces a concept from the guide by asking you to apply it yourself — reading code, completing configurations, writing scripts, deploying infrastructure, and verifying results.

The lab is divided into eight exercises that follow the same progression as the explanation guide. Some steps are fully guided; others require you to work out the answer independently. Where you are expected to write or complete code, you will see an empty code block marked with a prompt.

**Conventions used in this lab:**

- **📋 Guided Step** — Follow these instructions directly.
- **✏️ Your Task** — You must complete this yourself before moving on.
- **💡 Hint** — A nudge in the right direction if you are stuck.
- **✅ Checkpoint** — Expected output or result to verify your work.
- **🧩 Challenge** — An optional extension that goes slightly beyond the guided material.

**Prerequisites:** You should have completed Days 1–3 of the course and have the following ready: an AWS account with an IAM user configured, the AWS CLI installed and authenticated (`aws configure`), Node.js and npm installed, Python and `uv` installed, and a working copy of the Digital Twin project.

---

## Exercise 1: Conceptual Foundations

Before touching any code, make sure you have a solid grasp of *why* Infrastructure as Code matters and *what* Terraform's core concepts are. This exercise asks you to articulate the ideas in your own words — a reliable test of whether you have truly understood them.

### 1.1 — Why Infrastructure as Code?

✏️ **Your Task:** In the space below, write two or three sentences explaining the problem that Infrastructure as Code solves. Think about your experience manually creating resources in the AWS Console over the past few days.

```text
Your answer:



```

Now consider the four benefits described in the explanation guide: version control, peer review, automation, and repeatability.

✏️ **Your Task:** For each benefit, write one concrete example from the Digital Twin project where that benefit would help. The first one is done for you.

```text
Version control:
  Example: If a teammate changes the Lambda timeout from 60s to 120s,
  Git records who made the change and when, and the team can revert
  it if the longer timeout causes problems.

Peer review:
  Example:


Automation:
  Example:


Repeatability:
  Example:


```

### 1.2 — Terraform Terminology Matching

✏️ **Your Task:** Match each Terraform term on the left with its correct definition on the right. Write the letter of the matching definition next to each term.

```text
1. Provider   [ ]      A. A configurable parameter that controls deployment
                           behaviour without changing the underlying logic.

2. Variable   [ ]      B. A plugin that enables Terraform to interact with
                           a specific cloud platform (e.g. AWS, GCP, Azure).

3. Resource   [ ]      C. An isolated instance of state that allows parallel
                           environments from one configuration.

4. State      [ ]      D. A value exposed after deployment, such as a URL
                           or bucket name.

5. Output     [ ]      E. The fundamental building block — a single
                           infrastructure component to be created.

6. Workspace  [ ]      F. An internal record that maps your declared
                           configuration to actual deployed resources.
```

<details>
<summary>✅ Check your answers</summary>

1–B, 2–A, 3–E, 4–F, 5–D, 6–C

</details>

### 1.3 — Commands and Their Roles

✏️ **Your Task:** Complete the table by writing what each Terraform command does. Do this from memory before checking the guide.

```text
| Command              | What it does                                     |
|----------------------|--------------------------------------------------|
| terraform init       |                                                  |
| terraform plan       |                                                  |
| terraform apply      |                                                  |
| terraform destroy    |                                                  |
```

<details>
<summary>✅ Check your answers</summary>

- `terraform init` — Initialises the working directory, downloads provider plugins, and prepares Terraform for use.
- `terraform plan` — Shows what changes Terraform would make without actually executing them.
- `terraform apply` — Reads the configuration, computes a change plan, and executes it to create, update, or delete resources.
- `terraform destroy` — Removes all resources managed by Terraform in the current workspace.

</details>

---

## Exercise 2: Installing and Verifying Terraform

### 2.1 — Install Terraform

📋 **Guided Step:** Follow the installation instructions for your operating system from the explanation guide. For Mac users with Homebrew:

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

For other systems, visit [https://developer.hashicorp.com/terraform/install](https://developer.hashicorp.com/terraform/install).

### 2.2 — Verify the Installation

✏️ **Your Task:** Run the verification command and record the output below.

```bash
terraform --version
```

```text
Your output:

```

✅ **Checkpoint:** You should see a version string such as `Terraform v1.12.x`. Any recent stable version (1.0 or later) will work with this lab.

### 2.3 — Explore the Help System

Terraform has a built-in help system. This is a useful reference when you forget a command's flags.

✏️ **Your Task:** Run each of the following commands and note one thing you learn from each:

```bash
terraform -help
terraform init -help
terraform workspace -help
```

```text
Something I learned from 'terraform -help':


Something I learned from 'terraform init -help':


Something I learned from 'terraform workspace -help':


```

---

## Exercise 3: Reading and Understanding Terraform Configuration

Before you write Terraform code yourself, you need to be able to read it fluently. This exercise asks you to examine the configuration files from the explanation guide and explain what they do.

### 3.1 — Decoding `versions.tf`

📋 **Guided Step:** Open or refer to the `versions.tf` file from the explanation guide:

```hcl
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  # Uses AWS CLI configuration (aws configure)
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}
```

✏️ **Your Task:** Answer the following questions about this file.

```text
Q1: What does the version constraint "~> 6.0" mean?
    (Which versions would it allow? Which would it reject?)

A1:



Q2: Why is there no 'region' specified in the first provider block?

A2:



Q3: Why does the second provider block have an alias?
    When is this aliased provider used?

A3:


```

<details>
<summary>✅ Check your answers</summary>

**A1:** The `~>` operator (called the "pessimistic constraint operator") allows any version in the 6.x range (6.0, 6.1, 6.5, etc.) but would reject 7.0 or higher. It permits minor and patch updates while preventing breaking major-version changes.

**A2:** When no region is specified, Terraform inherits the region from the AWS CLI configuration that was set up with `aws configure`. This keeps the Terraform file portable — it works regardless of which region the user has configured.

**A3:** The alias creates a second, named provider instance locked to `us-east-1`. It is needed because AWS CloudFront requires SSL certificates to be provisioned in `us-east-1`, regardless of the default region. Resources that need this provider reference it with `provider = aws.us_east_1`.

</details>

### 3.2 — Tracing Resource References in `main.tf`

One of the most important skills in reading Terraform is understanding how resources reference each other. Terraform uses these references to determine the correct order of operations.

📋 **Guided Step:** Consider the following extract from `main.tf`:

```hcl
resource "aws_s3_bucket" "frontend" {
  bucket = "${local.name_prefix}-frontend-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  # ...
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    # ...
    Resource = "${aws_s3_bucket.frontend.arn}/*"
  })
  depends_on = [aws_s3_bucket_public_access_block.frontend]
}
```

✏️ **Your Task:** Draw the dependency chain for these three resources. Which must be created first? Which can be created in parallel? Why does the bucket policy have an explicit `depends_on`?

```text
Creation order (first → last):



Why the explicit depends_on on the bucket policy?


```

<details>
<summary>✅ Check your answers</summary>

**Creation order:** The S3 bucket (`aws_s3_bucket.frontend`) must be created first, because both the website configuration and the bucket policy reference it via `aws_s3_bucket.frontend.id`. The website configuration and the public access block can potentially be created in parallel (they both depend on the bucket but not on each other). The bucket policy must wait for the public access block to be applied (via the explicit `depends_on`) — without this, the policy could be rejected because the bucket's public access settings have not yet been configured to allow public policies.

</details>

### 3.3 — Understanding the Lambda Resource

📋 **Guided Step:** Refer to the Lambda function resource block in `main.tf`:

```hcl
resource "aws_lambda_function" "api" {
  filename         = "${path.module}/../backend/lambda-deployment.zip"
  function_name    = "${local.name_prefix}-api"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_handler.handler"
  source_code_hash = filebase64sha256("${path.module}/../backend/lambda-deployment.zip")
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  timeout          = var.lambda_timeout
  tags             = local.common_tags

  environment {
    variables = {
      CORS_ORIGINS     = var.use_custom_domain ? "https://${var.root_domain},https://www.${var.root_domain}" : "https://${aws_cloudfront_distribution.main.domain_name}"
      S3_BUCKET        = aws_s3_bucket.memory.id
      USE_S3           = "true"
      BEDROCK_MODEL_ID = var.bedrock_model_id
    }
  }

  depends_on = [aws_cloudfront_distribution.main]
}
```

✏️ **Your Task:** Answer the following questions.

```text
Q1: What does 'source_code_hash' do? What would happen if you
    removed this line entirely?

A1:



Q2: The CORS_ORIGINS value uses a ternary expression (condition ? A : B).
    In plain English, what does it evaluate to when use_custom_domain
    is false?

A2:



Q3: If the project_name variable is "twin" and the environment
    variable is "test", what would the function_name be?

A3:



Q4: The 'timeout' field references var.lambda_timeout. Looking at
    variables.tf, what is the default value? What unit is it in?

A4:


```

<details>
<summary>✅ Check your answers</summary>

**A1:** `source_code_hash` is a SHA-256 hash of the ZIP file. Terraform compares it against the previously stored hash to detect whether the code has changed. If removed, Terraform would not be able to detect code changes and might skip re-uploading the function even when the code has been updated.

**A2:** When `use_custom_domain` is false, it evaluates to `"https://<cloudfront-distribution-domain>"` — the auto-generated CloudFront URL.

**A3:** `twin-test-api` (constructed from `${local.name_prefix}-api`, where `name_prefix` is `${var.project_name}-${var.environment}`).

**A4:** The default is 60, and the unit is seconds (as stated in the variable description).

</details>

---

## Exercise 4: Writing Terraform Configuration

Now it is your turn to write Terraform code. Each task gives you a partially completed file and asks you to fill in the missing parts.

### 4.1 — Complete a Variable Definition

✏️ **Your Task:** The variable block below is incomplete. Fill in the missing fields so that it defines a variable called `notification_email` — a string with no default value that must be provided by the user, with a description explaining its purpose.

```hcl
variable "____________" {
  description = "____________________________________________"
  type        = ____________

}
```

<details>
<summary>💡 Hint</summary>

Look at how `project_name` is defined in `variables.tf` — it has a type of `string` and no `default`, which means Terraform will prompt for a value (or require it to be passed via `-var` or a `.tfvars` file).

</details>

<details>
<summary>✅ Sample answer</summary>

```hcl
variable "notification_email" {
  description = "Email address for deployment notifications"
  type        = string
}
```

</details>

### 4.2 — Complete a Variable with Validation

✏️ **Your Task:** Write a variable block called `log_retention_days` that accepts a number. It should default to `14` and include a validation rule that only permits values of 7, 14, 30, or 90.

```hcl
# Write your variable block here:




```

<details>
<summary>💡 Hint</summary>

Use the `contains()` function inside a `validation` block, similar to how the `environment` variable restricts values to `["dev", "test", "prod"]`.

</details>

<details>
<summary>✅ Sample answer</summary>

```hcl
variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14
  validation {
    condition     = contains([7, 14, 30, 90], var.log_retention_days)
    error_message = "Log retention must be one of: 7, 14, 30, or 90 days."
  }
}
```

</details>

### 4.3 — Write an Output Block

The deploy script needs to retrieve the Lambda function's ARN after deployment. Currently, `outputs.tf` exposes the function *name* but not the *ARN*.

✏️ **Your Task:** Write an output block called `lambda_function_arn` that exposes the ARN of the Lambda function. The resource is `aws_lambda_function.api`.

```hcl
# Write your output block here:




```

<details>
<summary>💡 Hint</summary>

The pattern for outputs is: `output "name" { description = "..." value = <resource>.<attribute> }`. The ARN attribute for a Lambda function is `.arn`.

</details>

<details>
<summary>✅ Sample answer</summary>

```hcl
output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.api.arn
}
```

</details>

### 4.4 — Write a Complete S3 Bucket Resource

Imagine you need to add a third S3 bucket to store application logs. It should be private (all public access blocked), tagged with the common tags, and named with the pattern `<name_prefix>-logs-<account_id>`.

✏️ **Your Task:** Write the resource blocks for this new bucket. You need two blocks: the bucket itself and its public access block. Use the existing `memory` bucket as a model.

```hcl
# Write your S3 bucket resource here:








# Write the public access block here:








```

<details>
<summary>✅ Sample answer</summary>

```hcl
resource "aws_s3_bucket" "logs" {
  bucket = "${local.name_prefix}-logs-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket = aws_s3_bucket.logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

</details>

### 4.5 — Write a `terraform.tfvars` for a Staging Environment

✏️ **Your Task:** Write a complete `staging.tfvars` file for a hypothetical staging environment. It should use the project name `twin`, the environment name `staging` (assume the validation rule has been updated to allow this), the `amazon.nova-lite-v1:0` model, a timeout of 90 seconds, burst limit of 15, rate limit of 8, and no custom domain.

```hcl
# Write your staging.tfvars file here:







```

<details>
<summary>✅ Sample answer</summary>

```hcl
project_name             = "twin"
environment              = "staging"
bedrock_model_id         = "amazon.nova-lite-v1:0"
lambda_timeout           = 90
api_throttle_burst_limit = 15
api_throttle_rate_limit  = 8
use_custom_domain        = false
root_domain              = ""
```

</details>

---

## Exercise 5: Understanding the Deployment Scripts

The deploy script is where Terraform, the frontend build, and AWS CLI come together. This exercise tests your understanding of how the pieces fit.

### 5.1 — Trace the Execution Flow

📋 **Guided Step:** Re-read the `deploy.sh` script from the explanation guide.

✏️ **Your Task:** Suppose you run `./scripts/deploy.sh test`. Write out, in order, the major actions the script performs. Be specific — include the actual commands or operations, not just vague descriptions.

```text
Step 1:

Step 2:

Step 3:

Step 4:

Step 5:

Step 6:

Step 7:

Step 8:

Step 9:
```

<details>
<summary>✅ Sample answer</summary>

1. Sets `ENVIRONMENT=test` and `PROJECT_NAME=twin`.
2. Changes to the project root directory.
3. Runs `(cd backend && uv run deploy.py)` to build `lambda-deployment.zip`.
4. Changes to the `terraform/` directory.
5. Runs `terraform init -input=false` to initialise providers.
6. Checks if the `test` workspace exists; creates it if not, otherwise selects it.
7. Runs `terraform apply -var="project_name=twin" -var="environment=test" -auto-approve`.
8. Extracts `api_gateway_url` and `s3_frontend_bucket` from Terraform outputs.
9. Changes to `frontend/`, writes `NEXT_PUBLIC_API_URL=<url>` to `.env.production`, runs `npm install`, `npm run build`, and `aws s3 sync ./out s3://<bucket>/ --delete`.

</details>

### 5.2 — The Frontend URL Problem

This is one of the trickiest parts of the deployment workflow. The explanation guide describes it in detail.

✏️ **Your Task:** In your own words, explain why the frontend needs an environment variable for the API URL, and why this cannot be handled by Terraform alone. Your answer should address three points: (a) what the frontend needs, (b) why it cannot be hard-coded, and (c) why Terraform cannot solve this.

```text
Your explanation:





```

<details>
<summary>✅ Key points to cover</summary>

**(a)** The frontend needs to know the API Gateway URL so it can send chat requests to the correct endpoint. This URL is embedded in the JavaScript that runs in the user's browser.

**(b)** It cannot be hard-coded because each environment (dev, test, prod) has a different API Gateway URL, and those URLs are not known until Terraform creates the resources.

**(c)** Terraform creates and configures cloud resources but cannot modify your application source code. The solution is for the deploy script to extract the URL from Terraform's outputs, write it into a Next.js environment file (`.env.production`), and then build the frontend — so the URL is injected at build time, not at infrastructure-provisioning time.

</details>

### 5.3 — Spot the Bug

The following deploy script excerpt contains a deliberate error that would cause the deployment to fail. Find it.

```bash
#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}
PROJECT_NAME=${2:-twin}

# Build Lambda package
cd "$(dirname "$0")/.."
(cd backend && uv run deploy.py)

# Terraform
cd terraform
terraform init -input=false

if ! terraform workspace list | grep -q "$ENVIRONMENT"; then
  terraform workspace new "$ENVIRONMENT"
else
  terraform workspace select "$ENVIRONMENT"
fi

terraform apply -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve

API_URL=$(terraform output -raw api_gateway_url)
FRONTEND_BUCKET=$(terraform output -raw s3_frontend_bucket)

# Build and deploy frontend
cd ../frontend
npm install
npm run build
aws s3 sync ./out "s3://$FRONTEND_BUCKET/" --delete
```

✏️ **Your Task:** Identify the error and explain what consequence it would have.

```text
The bug is:



The consequence would be:


```

<details>
<summary>✅ Answer</summary>

**The bug:** The script never creates the `.env.production` file with `NEXT_PUBLIC_API_URL`. The line `echo "NEXT_PUBLIC_API_URL=$API_URL" > .env.production` is missing between `cd ../frontend` and `npm install`.

**The consequence:** The frontend would be built without the API URL environment variable. `process.env.NEXT_PUBLIC_API_URL` would be `undefined`, so the fallback `http://localhost:8000` would be used. The deployed site would try to reach `localhost:8000` in the user's browser, which does not exist — all chat requests would fail.

</details>

### 5.4 — Production vs. Non-Production

✏️ **Your Task:** Examine the `deploy.sh` script. What does the script do differently when the environment is `prod` compared to `dev` or `test`? Why is this distinction important?

```text
What is different for prod:



Why this matters:


```

<details>
<summary>✅ Answer</summary>

**What is different:** When the environment is `prod`, the script adds `-var-file=prod.tfvars` to the `terraform apply` command. For `dev` and `test`, only the default `terraform.tfvars` is loaded (automatically).

**Why this matters:** `prod.tfvars` contains production-specific overrides: a more capable Bedrock model, higher API throttle limits, and custom domain settings. Without loading this file, production would deploy with the cheap development defaults.

</details>

---

## Exercise 6: Working with Workspaces

Workspaces are central to the multi-environment strategy. This exercise gives you practice managing them.

### 6.1 — Workspace Commands

📋 **Guided Step:** Ensure you are in the `terraform/` directory and that Terraform has been initialised. If not:

```bash
cd terraform
terraform init
```

✏️ **Your Task:** Run each command below and record the output.

**List all workspaces:**

```bash
terraform workspace list
```

```text
Your output:

```

**Show the current workspace:**

```bash
terraform workspace show
```

```text
Your output:

```

✅ **Checkpoint:** If you have already deployed dev and test, you should see three workspaces: `default`, `dev`, and `test`, with one of them marked with `*` (the currently active workspace).

### 6.2 — Workspace Scenario Questions

✏️ **Your Task:** Answer the following questions without running any commands.

```text
Q1: If you run 'terraform workspace select test' followed by
    'terraform destroy', which environment's resources get destroyed
    — dev or test?

A1:



Q2: You want to deploy a third environment called "staging". What
    workspace command would you run first?

A2:



Q3: A colleague runs 'terraform apply' without selecting a workspace
    first. Which workspace are they operating in? What is the risk?

A3:


```

<details>
<summary>✅ Answers</summary>

**A1:** The test environment's resources. `terraform destroy` operates against the currently selected workspace's state.

**A2:** `terraform workspace new staging` (which creates and switches to the new workspace).

**A3:** They are operating in whichever workspace was last selected — or the `default` workspace if none has ever been selected. The risk is that they might accidentally create or destroy resources in the wrong environment.

</details>

---

## Exercise 7: Deploy, Verify, and Explore

This is the core hands-on exercise. You will deploy a real environment, verify it works, and explore the resources that Terraform created.

### 7.1 — Deploy the Development Environment

📋 **Guided Step:** From the project root, run the deploy script:

**Mac/Linux:**

```bash
./scripts/deploy.sh dev
```

**Windows (PowerShell):**

```powershell
.\scripts\deploy.ps1 -Environment dev
```

Wait for the deployment to complete (5–10 minutes for the CloudFront distribution).

✏️ **Your Task:** Record the outputs displayed by the script:

```text
CloudFront URL:

API Gateway URL:

```

### 7.2 — Functional Verification

✏️ **Your Task:** Open the CloudFront URL in your browser and complete the following verification checklist. Tick each item as you confirm it.

```text
[ ] The Digital Twin interface loads in the browser.
[ ] Sending a message returns a response from the AI model.
[ ] Sending a follow-up message shows the model remembers context
    (e.g., tell it your name, then ask "What is my name?").
```

### 7.3 — Console Verification

Sign in to the AWS Console as your IAM user and verify that Terraform created the expected resources.

✏️ **Your Task:** For each resource below, navigate to the relevant AWS service and record the actual name or identifier you find.

```text
Lambda function name:

Lambda runtime:

Lambda timeout value:

BEDROCK_MODEL_ID env variable value:

S3 memory bucket name:

S3 frontend bucket name:

API Gateway name:

Number of CloudFront distributions:
```

### 7.4 — Inspect the State

✏️ **Your Task:** From the `terraform/` directory, run the following command and record how many resources Terraform is managing:

```bash
terraform state list | wc -l
```

```text
Number of managed resources:
```

Now pick any one resource from the state list and inspect its details:

```bash
terraform state list
# Pick one, e.g.:
terraform state show aws_s3_bucket.memory
```

✏️ **Your Task:** Record the bucket name and ARN from the state output:

```text
Bucket name:

Bucket ARN:
```

### 7.5 — Deploy the Test Environment

📋 **Guided Step:** Run the deploy script again with `test`:

**Mac/Linux:**

```bash
./scripts/deploy.sh test
```

**Windows (PowerShell):**

```powershell
.\scripts\deploy.ps1 -Environment test
```

✏️ **Your Task:** After deployment completes, open both the dev and test CloudFront URLs in separate browser tabs. Have a different conversation in each. Confirm isolation by answering:

```text
Does the dev twin know the test twin's conversation? (yes/no):

Are the CloudFront URLs different? (yes/no):

Go to the Lambda console — how many functions do you see now?

What are their names?


```

✅ **Checkpoint:** You should have two completely independent environments, each with its own set of resources, reachable at different URLs.

---

## Exercise 8: Teardown and Cleanup

### 8.1 — Destroy the Test Environment

📋 **Guided Step:** Run the destroy script for the test environment:

**Mac/Linux:**

```bash
./scripts/destroy.sh test
```

**Windows (PowerShell):**

```powershell
.\scripts\destroy.ps1 -Environment test
```

✏️ **Your Task:** After the destroy completes, verify the cleanup:

```text
[ ] Checked Lambda — only twin-dev-api remains (no twin-test-api).
[ ] Checked S3 — only dev buckets remain (no test buckets).
[ ] Checked CloudFront — only one distribution remains.
```

### 8.2 — Destroy the Dev Environment

📋 **Guided Step:** Destroy the dev environment as well:

**Mac/Linux:**

```bash
./scripts/destroy.sh dev
```

**Windows (PowerShell):**

```powershell
.\scripts\destroy.ps1 -Environment dev
```

✏️ **Your Task:** Verify that the account is completely clean:

```text
[ ] Lambda: No twin-related functions.
[ ] S3: No twin-related buckets.
[ ] API Gateway: No twin-related APIs.
[ ] CloudFront: No distributions (or back to the "Get Started" screen).
```

✅ **Checkpoint:** Your AWS account should now be in the same clean state as when you started this lab.

---

## Exercise 9: Synthesis and Reflection

### 9.1 — End-to-End Understanding

✏️ **Your Task:** Without looking at any notes, write a paragraph that explains the complete deployment pipeline from running `./scripts/deploy.sh dev` to having a working Digital Twin accessible via a CloudFront URL. Cover every major stage.

```text
Your paragraph:








```

### 9.2 — Comparing Manual and Automated Deployment

✏️ **Your Task:** Fill in the comparison table based on your experience in this course.

```text
| Aspect           | Manual (Console)       | Automated (Terraform)  |
|------------------|------------------------|------------------------|
| Time to deploy   |                        |                        |
| Risk of errors   |                        |                        |
| Reproducibility  |                        |                        |
| Multi-environment|                        |                        |
| Teardown         |                        |                        |
| Audit trail      |                        |                        |
```

### 9.3 — What Would You Change?

✏️ **Your Task:** The current configuration uses `AmazonS3FullAccess` and `AmazonBedrockFullAccess` managed policies for the Lambda role. The explanation guide notes this is a simplification. If you were tightening security for a real production deployment, what specific permissions would the Lambda function actually need? Think about what operations it performs.

```text
For S3, the Lambda needs permission to:



For Bedrock, the Lambda needs permission to:



A more restrictive policy would look like (describe in plain English):


```

<details>
<summary>✅ Sample answer</summary>

**S3:** The Lambda only needs `s3:GetObject` and `s3:PutObject` on the memory bucket (to read and write conversation history), and `s3:ListBucket` to check if a conversation file exists. It does not need access to any other bucket.

**Bedrock:** The Lambda only needs `bedrock:InvokeModel` for the specific model it uses. It does not need full Bedrock access (which includes model management, training, etc.).

**A more restrictive policy** would scope the `Resource` field to the specific bucket ARN and model ARN rather than using `*`, and would list only the actions actually needed.

</details>

---

## 🧩 Stretch Challenge: Add a New Resource

This optional challenge asks you to extend the Terraform configuration with a new resource that is not in the original guide.

**Scenario:** You want to add a CloudWatch Log Group for the Lambda function with a configurable retention period, rather than relying on the auto-created default (which retains logs indefinitely and can accumulate costs).

✏️ **Your Task:** Write the Terraform blocks needed:

1. A variable called `log_retention_days` (number, default 14, valid values: 7, 14, 30, 90).
2. A resource of type `aws_cloudwatch_log_group` named `lambda_logs`, with the name `/aws/lambda/${local.name_prefix}-api` and the retention set from the variable.
3. An output called `log_group_name` that exposes the log group's name.

```hcl
# 1. Variable definition:




# 2. Resource definition:




# 3. Output definition:



```

<details>
<summary>✅ Sample answer</summary>

```hcl
# 1. Variable
variable "log_retention_days" {
  description = "Number of days to retain Lambda CloudWatch logs"
  type        = number
  default     = 14
  validation {
    condition     = contains([7, 14, 30, 90], var.log_retention_days)
    error_message = "Log retention must be one of: 7, 14, 30, or 90 days."
  }
}

# 2. Resource
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

# 3. Output
output "log_group_name" {
  description = "Name of the Lambda CloudWatch log group"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}
```

**Bonus:** To ensure the Lambda function uses this log group (rather than auto-creating its own), you would add `depends_on = [aws_cloudwatch_log_group.lambda_logs]` to the Lambda resource.

</details>

---

## Lab Complete

If you have worked through all nine exercises, you have:

- Articulated *why* Infrastructure as Code matters from first principles.
- Demonstrated fluent reading of Terraform configuration files.
- Written your own variable definitions, resource blocks, and output blocks.
- Traced the execution flow of the deployment script and identified the frontend URL injection pattern.
- Deployed and verified two isolated environments on AWS.
- Destroyed both environments and confirmed a clean account state.
- Reflected on the manual-vs-automated tradeoff with concrete experience.

These skills form the foundation for tomorrow's session on GitHub Actions, where the deployment scripts you used today will be triggered automatically by a `git push`.
