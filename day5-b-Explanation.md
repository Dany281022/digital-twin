# Day 5: CI/CD with GitHub Actions
## A Self-Contained Study Guide

---

## Introduction

Day 5 is the final session of Week 2, and it brings together every concept introduced during the week into a single, automated system. The goal is to implement a complete CI/CD (Continuous Integration and Continuous Deployment) pipeline so that whenever you push code to GitHub, your Digital Twin application is automatically built, tested, and deployed to AWS — without any manual steps.

By the end of this session, your project will be a professional, version-controlled repository on GitHub, with automated deployment pipelines that can create and destroy full cloud environments on demand.

The following paragraphs summarise each major step.

**Part 1 — Clean up existing environments.** Before introducing automation, all manually created infrastructure is destroyed to ensure a clean, known starting state. This prevents conflicts between manually created resources and those that will be managed by the automated pipeline going forward.

**Part 2 — Initialise the Git repository.** The project is set up as a proper Git repository and pushed to GitHub. This is a prerequisite for GitHub Actions, which can only operate on code stored in a GitHub repository. Care is taken to avoid having nested Git repositories inside the project.

**Part 3 — Set up S3 remote state for Terraform.** When GitHub Actions runs Terraform on its cloud-based virtual machines, those machines are temporary and are destroyed after each run. Terraform's state must therefore be stored somewhere permanent and shared — an S3 bucket. A DynamoDB table is also created to prevent two deployments from running simultaneously and corrupting the state. These resources are created locally using Terraform, before being used by the automated pipeline.

**Part 4 — Set up OIDC authentication.** GitHub Actions needs permission to create and destroy AWS resources on your behalf. Rather than using long-lived access keys (which are a security risk), the modern approach is OIDC (OpenID Connect) — a token-based system where GitHub and AWS trust each other directly. A temporary Terraform file is used to create the required IAM role and attach the necessary policies.

**Part 5 — Create the GitHub Actions workflow files.** Two YAML workflow files are created: `deploy.yml`, which runs automatically on every push to `main` and can also be triggered manually for `test` and `prod`; and `destroy.yml`, which can only be triggered manually and requires a typed confirmation to prevent accidental destruction.

**Part 6 — Test the deployment pipeline.** The workflows are committed and pushed to GitHub, triggering the first automated deployment to the `dev` environment. Manual deployments to `test` and `prod` are then triggered from the GitHub Actions interface.

**Part 7 — Improve the UI.** A small but practical improvement is made to the frontend: the chat input field is fixed to regain focus automatically after each message is sent, and an optional personal avatar image is added to the chat interface. This change is deployed automatically via a simple `git push`, demonstrating the value of the CI/CD pipeline.

**Part 8 — Explore AWS Console and CloudWatch.** The AWS Console is used to inspect the running infrastructure: Lambda invocations, CloudWatch logs, Bedrock usage metrics, S3 memory contents, API Gateway metrics, and CloudFront analytics.

**Part 9 — Test environment destruction via GitHub.** The destroy workflow is used to tear down environments, demonstrating that the entire infrastructure lifecycle — creation and destruction — can be managed entirely from GitHub without touching the AWS Console.

**Part 10 — Final cleanup and cost review.** All environments are destroyed, residual resources are identified using AWS Resource Explorer, and costs are reviewed in the Billing dashboard.

---

## Part 1: Clean Up Existing Infrastructure

Before introducing CI/CD automation, all existing environments must be destroyed. This ensures there are no conflicts between manually created resources and those that will be created and managed automatically by GitHub Actions going forward.

### Why This Step Matters

When Terraform creates infrastructure, it records what it has created in a state file. If resources already exist from previous manual deployments, Terraform's state may be inconsistent or incomplete. Starting from a clean slate ensures the automated pipeline begins with full, accurate control over the infrastructure.

### Step 1: Destroy All Environments

Run the destroy scripts for each environment you created during the week. These scripts were built on Day 4.

**Mac/Linux:**
```bash
# Destroy dev environment
./scripts/destroy.sh dev

# Destroy test environment
./scripts/destroy.sh test

# Destroy prod environment (if you created one)
./scripts/destroy.sh prod
```

**Windows (PowerShell):**
```powershell
# Destroy dev environment
.\scripts\destroy.ps1 -Environment dev

# Destroy test environment
.\scripts\destroy.ps1 -Environment test

# Destroy prod environment (if you created one)
.\scripts\destroy.ps1 -Environment prod
```

Each destruction will take 5–10 minutes, as CloudFront distributions are the slowest resource to remove.

### Step 2: Clean Up Terraform Workspaces

After the resources are destroyed, remove the Terraform workspaces themselves:

```bash
cd terraform

# Switch to the default workspace first
terraform workspace select default

# Delete each workspace
terraform workspace delete dev
terraform workspace delete test
terraform workspace delete prod

cd ..
```

This step is optional if you will not be running Terraform locally again during this session, but it keeps your local environment tidy.

### Step 3: Verify Clean State

Log into the AWS Console and confirm that no twin-related resources remain:

- **Lambda:** No functions starting with `twin-`
- **S3:** No buckets starting with `twin-`
- **API Gateway:** No APIs starting with `twin-`
- **CloudFront:** No twin distributions

✅ **Checkpoint:** Your AWS account is clean and ready for CI/CD deployment.

---

## Part 2: Initialise Git Repository

GitHub Actions can only operate on code that is stored in a GitHub repository. This part sets up the project as a proper Git repository and pushes it to GitHub.

### Step 1: Create `.gitignore`

A `.gitignore` file tells Git which files and directories should not be tracked in the repository. This is important for several reasons: it prevents sensitive data (like environment variable files) from being accidentally committed, and it avoids committing large or auto-generated files that do not belong in source control.

Ensure your `.gitignore` at the project root (`twin/.gitignore`) contains the following:

```gitignore
# Terraform
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl
terraform.tfstate.d/
*.tfvars.secret

# Lambda packages
lambda-deployment.zip
lambda-package/

# Memory storage (contains conversation history)
memory/

# Environment files
.env
.env.*
!.env.example

# Node
node_modules/
out/
.next/
*.log

# Python
__pycache__/
*.pyc
.venv/
venv/

# IDE
.vscode/
.idea/
*.swp
.DS_Store
Thumbs.db

# AWS
.aws/
```

Note the line `!.env.example` — the exclamation mark means "do not ignore this file." This allows the `.env.example` file (created in the next step) to be included in the repository even though all other `.env.*` files are excluded.

### Step 2: Create an Example Environment File

It is good practice to include an `.env.example` file in the repository. This file does not contain any real secrets — it simply shows other developers (or your future self) what environment variables need to be set up.

Create `.env.example` with the following content:

```bash
# AWS Configuration
AWS_ACCOUNT_ID=your_12_digit_account_id
DEFAULT_AWS_REGION=us-east-1

# Project Configuration
PROJECT_NAME=twin
```

### Step 3: Initialise the Git Repository

There is a small but important issue to address before initialising Git. When the frontend was originally created using `create-next-app`, that tool automatically created its own Git repository inside the `frontend/` folder. Similarly, if you used `uv init` (rather than `uv init --bare`) when setting up the backend, the `backend/` folder may also contain its own Git repository.

This matters because a Git repository cannot cleanly contain another Git repository as a subdirectory — the result is a "nested repository" (also called a submodule), which causes significant confusion. To avoid this, the nested `.git` directories must be removed first.

> ⚠️ **Important:** The commands below use `rm -rf` (Mac/Linux) and `Remove-Item` (Windows), which permanently delete files without confirmation. Make absolutely sure you are inside the `twin/` project directory when running these commands, and that the paths specified are exactly `frontend/.git` and `backend/.git`. Deleting the wrong directory with `rm -rf` is one of the most destructive mistakes in computing. Read the command carefully before pressing Enter.

**Mac/Linux:**
```bash
cd twin

# Remove any git repos created by create-next-app or uv (if they exist)
rm -rf frontend/.git backend/.git 2>/dev/null

# Initialise git repository with main as the default branch
git init -b main

# If you get an error that -b is not supported (older Git versions), use:
# git init
# git checkout -b main

# Configure git (replace with your details)
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

**Windows (PowerShell):**
```powershell
cd twin

# Remove any git repos created by create-next-app or uv (if they exist)
Remove-Item -Path frontend/.git -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path backend/.git -Recurse -Force -ErrorAction SilentlyContinue

# Initialise git repository with main as the default branch
git init -b main

# Configure git (replace with your details)
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

> **Note:** If the `Remove-Item` or `rm -rf` command shows an error or a red indicator, this simply means that the `.git` folder did not exist in that location — which is fine. The important confirmation is the line that follows: `Initialized empty Git repository in .../twin/.git/`

After configuring Git, stage and commit all files:

```bash
# Stage all files
git add .

# Create the initial commit
git commit -m "Initial commit: Digital Twin infrastructure and application"
```

You may see warnings about `LF will be replaced by CRLF` on Windows. These are informational only and do not indicate a problem.

### Step 4: Create a GitHub Repository

1. Go to [github.com](https://github.com) and sign in
2. Click the **+** icon in the top right → **New repository**
3. Configure your repository:
   - **Repository name:** `twin` (or your preferred name — note this name exactly, you will need it later)
   - **Description:** "AI Digital Twin deployed on AWS with Terraform"
   - **Visibility:** Public or Private (public is recommended if you want to share your work)
   - ❗ **Do NOT** initialise with a README, `.gitignore`, or licence — your repository already has content, and adding these would create a conflict
4. Click **Create repository**

### Step 5: Push to GitHub

After creating the repository, GitHub will display the commands needed to connect your local repository to it. Run the following (replacing `YOUR_USERNAME` with your actual GitHub username and `twin` with your actual repository name if different):

```bash
# Add GitHub as the remote origin
git remote add origin https://github.com/YOUR_USERNAME/twin.git

# Push to GitHub
git push -u origin main
```

If prompted for authentication, use a Personal Access Token rather than your GitHub password (GitHub → Settings → Developer settings → Personal access tokens → generate a token with `repo` scope).

✅ **Checkpoint:** Your code is now on GitHub. Refresh the repository page to confirm all files are visible.

---

## Part 3: Set Up S3 Remote State for Terraform

### Why Terraform State Needs a Shared Location

When you run Terraform locally, it stores a state file on your computer. This file is Terraform's record of what infrastructure it has created — it maps every resource in your configuration files to a real resource running in AWS.

When GitHub Actions runs Terraform, it does so on a freshly created virtual machine that is discarded immediately after the workflow finishes. This means the local state file on your computer is completely inaccessible to GitHub Actions, and vice versa. If both were to manage state independently, they would quickly fall out of sync, leading to duplicate infrastructure or failed deployments.

The solution is to store the Terraform state file in a location that is always accessible, regardless of where Terraform is being run: an **S3 bucket**. A **DynamoDB table** is also required to provide state locking — a mechanism that prevents two simultaneous deployments from writing to the state file at the same time, which would corrupt it.

These two resources are created locally using a temporary Terraform file, run once, and then deleted. This is a common and recommended pattern in production Terraform workflows.

### Step 1: Create State Management Resources

Create `terraform/backend-setup.tf`:

```hcl
# This file creates the S3 bucket and DynamoDB table for Terraform state
# Run this once per AWS account, then remove the file

resource "aws_s3_bucket" "terraform_state" {
  bucket = "twin-terraform-state-${data.aws_caller_identity.current.account_id}"
  
  tags = {
    Name        = "Terraform State Store"
    Environment = "global"
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "terraform_locks" {
  name         = "twin-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name        = "Terraform State Locks"
    Environment = "global"
    ManagedBy   = "terraform"
  }
}

# Note: aws_caller_identity.current is already defined in main.tf

output "state_bucket_name" {
  value = aws_s3_bucket.terraform_state.id
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.terraform_locks.name
}
```

### Step 2: Create the Backend Resources

Note that the `terraform apply` command below uses the `-target` flag to apply only the specific resources defined in this setup file, rather than applying everything in `main.tf` as well.

```bash
cd terraform

# Make sure you are in the default workspace
terraform workspace select default

# Initialise Terraform
terraform init

# Apply just the backend resources
# Mac/Linux version (one long command — copy and paste in full):
terraform apply -target=aws_s3_bucket.terraform_state -target=aws_s3_bucket_versioning.terraform_state -target=aws_s3_bucket_server_side_encryption_configuration.terraform_state -target=aws_s3_bucket_public_access_block.terraform_state -target=aws_dynamodb_table.terraform_locks

# Windows (PowerShell) version (one long command — copy and paste in full):
terraform apply --% -target="aws_s3_bucket.terraform_state" -target="aws_s3_bucket_versioning.terraform_state" -target="aws_s3_bucket_server_side_encryption_configuration.terraform_state" -target="aws_s3_bucket_public_access_block.terraform_state" -target="aws_dynamodb_table.terraform_locks"

# Verify the resources were created
terraform output
```

Type `yes` when prompted. The output will confirm the names of the S3 bucket and DynamoDB table that have been created.

> **Windows note:** PowerShell interprets the `-` characters in `-target` flags differently from Bash. The `--%` flag (stop-parsing symbol) instructs PowerShell to pass everything that follows literally to the underlying command, avoiding this issue. Always use the PowerShell version of this command on Windows.

### Step 3: Remove the Setup File

Now that the backend resources exist, this temporary file is no longer needed:

```bash
rm backend-setup.tf          # Mac/Linux
Remove-Item backend-setup.tf  # Windows PowerShell
```

### Step 4: Update Scripts to Use the S3 Backend

The deployment and destroy scripts need to be updated to point Terraform to the S3 bucket when initialising.

#### Update `scripts/deploy.sh`

Find the existing `terraform init` line and replace it with:

```bash
# Old line:
terraform init -input=false

# New lines:
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${DEFAULT_AWS_REGION:-us-east-1}
terraform init -input=false \
  -backend-config="bucket=twin-terraform-state-${AWS_ACCOUNT_ID}" \
  -backend-config="key=${ENVIRONMENT}/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  -backend-config="dynamodb_table=twin-terraform-locks" \
  -backend-config="encrypt=true"
```

#### Update `scripts/deploy.ps1`

Find the existing `terraform init` line and replace it with:

```powershell
# Old line:
terraform init -input=false

# New lines:
$awsAccountId = aws sts get-caller-identity --query Account --output text
$awsRegion = if ($env:DEFAULT_AWS_REGION) { $env:DEFAULT_AWS_REGION } else { "us-east-1" }
terraform init -input=false `
  -backend-config="bucket=twin-terraform-state-$awsAccountId" `
  -backend-config="key=$Environment/terraform.tfstate" `
  -backend-config="region=$awsRegion" `
  -backend-config="dynamodb_table=twin-terraform-locks" `
  -backend-config="encrypt=true"
```

#### Replace `scripts/destroy.sh`

Replace the entire file with the updated version that includes S3 backend support:

```bash
#!/bin/bash
set -e

if [ $# -eq 0 ]; then
    echo "❌ Error: Environment parameter is required"
    echo "Usage: $0 <environment>"
    echo "Example: $0 dev"
    echo "Available environments: dev, test, prod"
    exit 1
fi

ENVIRONMENT=$1
PROJECT_NAME=${2:-twin}

echo "🗑️ Preparing to destroy ${PROJECT_NAME}-${ENVIRONMENT} infrastructure..."

cd "$(dirname "$0")/../terraform"

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${DEFAULT_AWS_REGION:-us-east-1}

echo "🔧 Initializing Terraform with S3 backend..."
terraform init -input=false \
  -backend-config="bucket=twin-terraform-state-${AWS_ACCOUNT_ID}" \
  -backend-config="key=${ENVIRONMENT}/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  -backend-config="dynamodb_table=twin-terraform-locks" \
  -backend-config="encrypt=true"

if ! terraform workspace list | grep -q "$ENVIRONMENT"; then
    echo "❌ Error: Workspace '$ENVIRONMENT' does not exist"
    terraform workspace list
    exit 1
fi

terraform workspace select "$ENVIRONMENT"

echo "📦 Emptying S3 buckets..."

FRONTEND_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-frontend-${AWS_ACCOUNT_ID}"
MEMORY_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-memory-${AWS_ACCOUNT_ID}"

if aws s3 ls "s3://$FRONTEND_BUCKET" 2>/dev/null; then
    echo "  Emptying $FRONTEND_BUCKET..."
    aws s3 rm "s3://$FRONTEND_BUCKET" --recursive
else
    echo "  Frontend bucket not found or already empty"
fi

if aws s3 ls "s3://$MEMORY_BUCKET" 2>/dev/null; then
    echo "  Emptying $MEMORY_BUCKET..."
    aws s3 rm "s3://$MEMORY_BUCKET" --recursive
else
    echo "  Memory bucket not found or already empty"
fi

echo "🔥 Running terraform destroy..."

if [ ! -f "../backend/lambda-deployment.zip" ]; then
    echo "Creating dummy lambda package for destroy operation..."
    echo "dummy" | zip ../backend/lambda-deployment.zip -
fi

if [ "$ENVIRONMENT" = "prod" ] && [ -f "prod.tfvars" ]; then
    terraform destroy -var-file=prod.tfvars -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve
else
    terraform destroy -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve
fi

echo "✅ Infrastructure for ${ENVIRONMENT} has been destroyed!"
```

Replace `scripts/destroy.ps1` with the equivalent PowerShell version (see the original lab guide for the full PowerShell script).

> **Why keep both `.sh` and `.ps1` files?** When running locally on Windows, you use `destroy.ps1`. When GitHub Actions runs the destroy workflow, it uses an Ubuntu Linux runner, so it calls `destroy.sh`. Both files need to exist for the system to work correctly across all contexts.

---

## Part 4: Set Up OIDC Authentication

### Why OIDC Instead of Access Keys?

For GitHub Actions to deploy infrastructure to AWS, it must authenticate with AWS. The traditional approach is to create an IAM user, generate long-lived access keys, and store them as GitHub secrets. This works but is considered a security risk: long-lived keys can be leaked, forgotten, or left in place indefinitely.

The modern and recommended approach is **OpenID Connect (OIDC)**. With OIDC, GitHub and AWS establish a trust relationship directly. When a workflow runs, GitHub generates a short-lived token proving "this workflow is running in repository X", and AWS verifies that token using the trust relationship rather than a stored password. No long-lived credentials are ever created or stored.

This setup requires:
1. An **OIDC provider** in AWS that trusts GitHub's token issuer
2. An **IAM role** that GitHub Actions can assume when presenting a valid token
3. **IAM policies** attached to that role giving it the permissions needed to deploy infrastructure

### Step 1: Create the OIDC and IAM Configuration File

In your `terraform/` directory, create a temporary file called `github-oidc.tf` with the following complete content:

```hcl
# This creates an IAM role that GitHub Actions can assume
# Run this once, then you can remove the file

variable "github_repository" {
  description = "GitHub repository in format 'owner/repo'"
  type        = string
}

# GitHub OIDC Provider
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1"
  ]
}

# IAM Role for GitHub Actions
resource "aws_iam_role" "github_actions" {
  name = "github-actions-twin-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:*"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "github_lambda" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AWSLambda_FullAccess"
}

resource "aws_iam_role_policy_attachment" "github_s3" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "github_apigateway" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonAPIGatewayAdministrator"
}

resource "aws_iam_role_policy_attachment" "github_cloudfront" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/CloudFrontFullAccess"
}

resource "aws_iam_role_policy_attachment" "github_iam_read" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/IAMReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "github_bedrock" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

resource "aws_iam_role_policy_attachment" "github_dynamodb" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
}

resource "aws_iam_role_policy_attachment" "github_acm" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AWSCertificateManagerFullAccess"
}

resource "aws_iam_role_policy_attachment" "github_route53" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonRoute53FullAccess"
}

resource "aws_iam_role_policy" "github_additional" {
  name = "github-actions-additional"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:UpdateAssumeRolePolicy",
          "iam:PassRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:ListInstanceProfilesForRole",
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      }
    ]
  })
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}
```

> **About the thumbprint:** The value `6938fd4d98bab03faadb97b34396831e3780aea1` is a SHA-1 fingerprint of GitHub's SSL certificate for `token.actions.githubusercontent.com`. AWS uses it to verify that OIDC tokens are genuinely coming from GitHub's servers. This value is the same for every user worldwide — it belongs to GitHub's server, not to any individual account. The original lab guide contains an incorrect thumbprint (41 characters instead of the required 40). Always use the corrected value shown here.

### Step 2: Check Whether the OIDC Provider Already Exists

If you have previously set up GitHub OIDC in your AWS account (for another project, for example), the provider may already exist. Running the command to create it again would cause an error.

Check first:

**Mac/Linux:**
```bash
aws iam list-open-id-connect-providers | grep token.actions.githubusercontent.com
```

**Windows (PowerShell):**
```powershell
aws iam list-open-id-connect-providers | Select-String "token.actions.githubusercontent.com"
```

> **Windows note:** PowerShell does not have `grep`. The equivalent command is `Select-String`. Always use the PowerShell version of this command on Windows.

**If no output appears** → The OIDC provider does not exist. Proceed with **Scenario A**.

**If an ARN appears** (e.g., `arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com`) → The provider already exists. Proceed with **Scenario B**.

### Apply the GitHub OIDC Resources

Before running the apply commands, make sure you are in the `terraform/` directory and in the default workspace:

```bash
cd terraform
terraform workspace select default
terraform init
```

> ⚠️ **Critical:** In the commands below, replace `YOUR_GITHUB_USERNAME/YOUR_REPO_NAME` with your **actual** GitHub username and repository name, exactly as they appear in your GitHub URL. For example, if your repository URL is `https://github.com/jane-smith/twin`, use `jane-smith/twin`. If you use the wrong values here, GitHub Actions will receive an authentication error every time it tries to deploy. The username and repository name are case-sensitive.

#### Scenario A: OIDC Provider Does NOT Exist

**Mac/Linux:**
```bash
terraform apply -target=aws_iam_openid_connect_provider.github -target=aws_iam_role.github_actions -target=aws_iam_role_policy_attachment.github_lambda -target=aws_iam_role_policy_attachment.github_s3 -target=aws_iam_role_policy_attachment.github_apigateway -target=aws_iam_role_policy_attachment.github_cloudfront -target=aws_iam_role_policy_attachment.github_iam_read -target=aws_iam_role_policy_attachment.github_bedrock -target=aws_iam_role_policy_attachment.github_dynamodb -target=aws_iam_role_policy_attachment.github_acm -target=aws_iam_role_policy_attachment.github_route53 -target=aws_iam_role_policy.github_additional -var="github_repository=YOUR_GITHUB_USERNAME/YOUR_REPO_NAME"
```

**Windows (PowerShell):**
```powershell
terraform apply -target="aws_iam_openid_connect_provider.github" -target="aws_iam_role.github_actions" -target="aws_iam_role_policy_attachment.github_lambda" -target="aws_iam_role_policy_attachment.github_s3" -target="aws_iam_role_policy_attachment.github_apigateway" -target="aws_iam_role_policy_attachment.github_cloudfront" -target="aws_iam_role_policy_attachment.github_iam_read" -target="aws_iam_role_policy_attachment.github_bedrock" -target="aws_iam_role_policy_attachment.github_dynamodb" -target="aws_iam_role_policy_attachment.github_acm" -target="aws_iam_role_policy_attachment.github_route53" -target="aws_iam_role_policy.github_additional" -var="github_repository=YOUR_GITHUB_USERNAME/YOUR_REPO_NAME"
```

#### Scenario B: OIDC Provider Already Exists

First, import the existing provider into Terraform's state:

**Mac/Linux:**
```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
terraform import aws_iam_openid_connect_provider.github arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com
```

**Windows (PowerShell):**
```powershell
$awsAccountId = aws sts get-caller-identity --query Account --output text
terraform import aws_iam_openid_connect_provider.github "arn:aws:iam::${awsAccountId}:oidc-provider/token.actions.githubusercontent.com"
```

Then apply, omitting the OIDC provider target:

**Mac/Linux:**
```bash
terraform apply -target=aws_iam_role.github_actions -target=aws_iam_role_policy_attachment.github_lambda -target=aws_iam_role_policy_attachment.github_s3 -target=aws_iam_role_policy_attachment.github_apigateway -target=aws_iam_role_policy_attachment.github_cloudfront -target=aws_iam_role_policy_attachment.github_iam_read -target=aws_iam_role_policy_attachment.github_bedrock -target=aws_iam_role_policy_attachment.github_dynamodb -target=aws_iam_role_policy_attachment.github_acm -target=aws_iam_role_policy_attachment.github_route53 -target=aws_iam_role_policy.github_additional -var="github_repository=YOUR_GITHUB_USERNAME/YOUR_REPO_NAME"
```

**Windows (PowerShell):**
```powershell
terraform apply -target="aws_iam_role.github_actions" -target="aws_iam_role_policy_attachment.github_lambda" -target="aws_iam_role_policy_attachment.github_s3" -target="aws_iam_role_policy_attachment.github_apigateway" -target="aws_iam_role_policy_attachment.github_cloudfront" -target="aws_iam_role_policy_attachment.github_iam_read" -target="aws_iam_role_policy_attachment.github_bedrock" -target="aws_iam_role_policy_attachment.github_dynamodb" -target="aws_iam_role_policy_attachment.github_acm" -target="aws_iam_role_policy_attachment.github_route53" -target="aws_iam_role_policy.github_additional" -var="github_repository=YOUR_GITHUB_USERNAME/YOUR_REPO_NAME"
```

### Save the Role ARN and Clean Up

After the apply completes, record the role ARN from the output:

```bash
terraform output github_actions_role_arn
```

The output will look like: `arn:aws:iam::123456789012:role/github-actions-twin-deploy`

**Copy this value** — you will need it in the next step.

Then delete the temporary setup file:

```bash
rm github-oidc.tf          # Mac/Linux
Remove-Item github-oidc.tf  # Windows PowerShell
```

### Step 3: Configure the Terraform Backend

Create `terraform/backend.tf`:

```hcl
terraform {
  backend "s3" {
    # These values will be provided by deployment scripts via -backend-config flags
  }
}
```

This file tells Terraform to use S3 as its state backend, but intentionally leaves the configuration values empty. The actual bucket name, region, and other details are passed in at runtime by the deploy and destroy scripts, which allows the same configuration to work across different environments and AWS accounts.

### Step 4: Add Secrets to GitHub

GitHub Actions needs to know three values to authenticate with AWS and deploy your infrastructure. These are stored as **repository secrets** — encrypted values that are available to workflows but never visible in logs.

1. Go to your GitHub repository
2. Click **Settings** tab
3. In the left sidebar: **Secrets and variables** → **Actions**
4. Click **New repository secret** for each of the following:

| Secret Name | Value |
|---|---|
| `AWS_ROLE_ARN` | The ARN from the Terraform output above (e.g., `arn:aws:iam::123456789012:role/github-actions-twin-deploy`) |
| `DEFAULT_AWS_REGION` | The AWS region you have been using throughout the week (check your `.env` file to confirm — it must match exactly) |
| `AWS_ACCOUNT_ID` | Your 12-digit AWS account ID (visible in the ARN above, or run `aws sts get-caller-identity --query Account --output text`) |

> **Important:** Copy and paste these values rather than typing them. Even a single incorrect character in the region (e.g., `us-east-1` vs `us-east-2`) will cause all deployments to fail with an obscure error that is difficult to trace.

✅ **Checkpoint:** GitHub can now securely authenticate with your AWS account using OIDC.

---

## Part 5: Create GitHub Actions Workflows

### Step 1: Create the Workflow Directory

In Cursor's file explorer, create the following folder structure at the project root:

```
twin/
└── .github/
    └── workflows/
```

Right-click in the Explorer → New Folder → `.github`, then right-click on `.github` → New Folder → `workflows`.

### Step 2: Create the Deployment Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Digital Twin

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy'
        required: true
        default: 'dev'
        type: choice
        options:
          - dev
          - test
          - prod

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    name: Deploy to ${{ github.event.inputs.environment || 'dev' }}
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'dev' }}
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          role-session-name: github-actions-deploy
          aws-region: ${{ secrets.DEFAULT_AWS_REGION }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_wrapper: false

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Run Deployment Script
        run: |
          export AWS_ACCOUNT_ID=${{ secrets.AWS_ACCOUNT_ID }}
          export DEFAULT_AWS_REGION=${{ secrets.DEFAULT_AWS_REGION }}
          chmod +x scripts/deploy.sh
          ./scripts/deploy.sh ${{ github.event.inputs.environment || 'dev' }}
        env:
          AWS_ROLE_ARN: ${{ secrets.AWS_ROLE_ARN }}
          
      - name: Get Deployment URLs
        id: deploy_outputs
        working-directory: ./terraform
        run: |
          terraform workspace select ${{ github.event.inputs.environment || 'dev' }}
          echo "cloudfront_url=$(terraform output -raw cloudfront_url)" >> $GITHUB_OUTPUT
          echo "api_url=$(terraform output -raw api_gateway_url)" >> $GITHUB_OUTPUT
          echo "frontend_bucket=$(terraform output -raw s3_frontend_bucket)" >> $GITHUB_OUTPUT

      - name: Invalidate CloudFront
        run: |
          DISTRIBUTION_ID=$(aws cloudfront list-distributions \
            --query "DistributionList.Items[?Origins.Items[?DomainName=='${{ steps.deploy_outputs.outputs.frontend_bucket }}.s3-website-${{ secrets.DEFAULT_AWS_REGION }}.amazonaws.com']].Id | [0]" \
            --output text)
          
          if [ "$DISTRIBUTION_ID" != "None" ] && [ -n "$DISTRIBUTION_ID" ]; then
            aws cloudfront create-invalidation \
              --distribution-id $DISTRIBUTION_ID \
              --paths "/*"
          fi

      - name: Deployment Summary
        run: |
          echo "✅ Deployment Complete!"
          echo "🌐 CloudFront URL: ${{ steps.deploy_outputs.outputs.cloudfront_url }}"
          echo "📡 API Gateway: ${{ steps.deploy_outputs.outputs.api_url }}"
          echo "🪣 Frontend Bucket: ${{ steps.deploy_outputs.outputs.frontend_bucket }}"
```

**How this workflow works:**
- It triggers automatically on every push to `main` (deploying to `dev`)
- It can also be triggered manually via the GitHub Actions interface, with a dropdown to choose `dev`, `test`, or `prod`
- It sets up the required tools (Python, uv, Terraform, Node.js) on a fresh Ubuntu runner
- It authenticates with AWS using OIDC (the `configure-aws-credentials` step)
- It runs your existing `deploy.sh` script, which handles the actual Terraform and build steps
- The `terraform_wrapper: false` setting is important — without it, Terraform's output is wrapped in a format that breaks the output-parsing step

### Step 3: Create the Destroy Workflow

Create `.github/workflows/destroy.yml`:

```yaml
name: Destroy Environment

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to destroy'
        required: true
        type: choice
        options:
          - dev
          - test
          - prod
      confirm:
        description: 'Type the environment name to confirm destruction'
        required: true

permissions:
  id-token: write
  contents: read

jobs:
  destroy:
    name: Destroy ${{ github.event.inputs.environment }}
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment }}
    
    steps:
      - name: Verify confirmation
        run: |
          if [ "${{ github.event.inputs.confirm }}" != "${{ github.event.inputs.environment }}" ]; then
            echo "❌ Confirmation does not match environment name!"
            echo "You entered: '${{ github.event.inputs.confirm }}'"
            echo "Expected: '${{ github.event.inputs.environment }}'"
            exit 1
          fi
          echo "✅ Destruction confirmed for ${{ github.event.inputs.environment }}"

      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          role-session-name: github-actions-destroy
          aws-region: ${{ secrets.DEFAULT_AWS_REGION }}

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_wrapper: false

      - name: Run Destroy Script
        run: |
          export AWS_ACCOUNT_ID=${{ secrets.AWS_ACCOUNT_ID }}
          export DEFAULT_AWS_REGION=${{ secrets.DEFAULT_AWS_REGION }}
          chmod +x scripts/destroy.sh
          ./scripts/destroy.sh ${{ github.event.inputs.environment }}
        env:
          AWS_ROLE_ARN: ${{ secrets.AWS_ROLE_ARN }}

      - name: Destruction Complete
        run: |
          echo "✅ Environment ${{ github.event.inputs.environment }} has been destroyed!"
```

**Key design decisions in this workflow:**
- It is `workflow_dispatch` only — it cannot be triggered by a push, only by a deliberate manual action
- It requires the user to type the environment name again as a confirmation check, preventing accidental destruction
- The `destroy.sh` script is used (not the PowerShell version) because the GitHub runner is Linux

### Step 4: Commit and Push All Changes

From the project root:

```bash
git add .
git commit -m "Add CI/CD with GitHub Actions, S3 backend, and updated scripts"
git push
```

> **What happens next:** The moment you push, GitHub detects the push to `main` and triggers the `deploy.yml` workflow automatically. Navigate to your GitHub repository → **Actions** tab to watch it run.

---

## Part 6: Test Deployments

### Step 1: Automatic Dev Deployment

The push in the previous step will have already triggered a deployment to `dev`. To monitor it:

1. Go to your GitHub repository
2. Click the **Actions** tab
3. You will see the "Deploy Digital Twin" workflow running (indicated by a yellow spinning circle)
4. Click on it to view the live log output
5. Wait for completion (typically 5–10 minutes)

Once complete, expand the **"Deployment Summary"** step to see your deployment URLs:
- 🌐 **CloudFront URL** — your live Digital Twin application
- 📡 **API Gateway** — the backend API endpoint
- 🪣 **Frontend Bucket** — the S3 bucket name

Click the CloudFront URL to verify your Digital Twin is running.

### Step 2: Manual Test Deployment

1. In GitHub, go to **Actions** tab
2. Click **Deploy Digital Twin** in the left sidebar
3. Click **Run workflow** dropdown (top right)
4. Select:
   - Branch: `main`
   - Environment: `test`
5. Click **Run workflow**

### Step 3: Manual Production Deployment

Repeat the process above, selecting `prod` as the environment. If you have configured a custom domain, the production environment will use it.

### Step 4: Understanding Re-deployments

One important aspect of this workflow is how Terraform handles re-deployments. When you run the workflow a second time for the same environment, Terraform compares the current state (stored in S3) with what the configuration describes, and only makes changes where necessary. If the infrastructure already exists and is unchanged, Terraform leaves it in place. This is the core principle of declarative infrastructure — you describe the desired state, and Terraform ensures reality matches it.

✅ **Checkpoint:** You now have CI/CD deploying to multiple environments automatically.

---

## Part 7: Improve the UI — Fix Focus and Add Avatar

### Step 1: Add a Profile Picture (Optional)

If you wish to display a personal avatar in the chat interface instead of the default bot icon:

1. Add your profile picture as `frontend/public/avatar.png`
2. Keep the file small — ideally under 100KB
3. A square aspect ratio works best (e.g., 200×200 pixels)

### Step 2: Update the Twin Component

Update `frontend/components/twin.tsx` with the following complete revised version, which adds focus management and avatar support. The key changes are the use of `useRef` to hold a reference to the input field, and a `useEffect` to focus that field after each message:

```typescript
'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User } from 'lucide-react';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

export default function Twin() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [hasAvatar, setHasAvatar] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        const img = new Image();
        img.onload = () => setHasAvatar(true);
        img.onerror = () => setHasAvatar(false);
        img.src = '/avatar.png';
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    useEffect(() => {
        if (!isLoading) {
            inputRef.current?.focus();
        }
    }, [isLoading]);

    const sendMessage = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input.trim(),
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage.content }),
            });

            const data = await response.json();

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.response,
                timestamp: new Date(),
            };

            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            console.error('Error:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className="flex flex-col h-screen max-w-2xl mx-auto p-4">
            <div className="flex-1 overflow-y-auto space-y-4 mb-4">
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        {message.role === 'assistant' && (
                            <div className="flex-shrink-0">
                                {hasAvatar ? (
                                    <img
                                        src="/avatar.png"
                                        alt="Digital Twin Avatar"
                                        className="w-8 h-8 rounded-full border border-slate-300"
                                    />
                                ) : (
                                    <div className="w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center">
                                        <Bot className="w-5 h-5 text-white" />
                                    </div>
                                )}
                            </div>
                        )}

                        <div className={`max-w-xs lg:max-w-md ${message.role === 'user' ? 'order-first' : ''}`}>
                            <div
                                className={`rounded-lg p-3 ${
                                    message.role === 'user'
                                        ? 'bg-slate-700 text-white'
                                        : 'bg-white border border-gray-200 text-gray-800'
                                }`}
                            >
                                {message.content}
                            </div>
                            <p
                                className={`text-xs text-gray-500 mt-1 ${
                                    message.role === 'user' ? 'text-right' : 'text-left'
                                }`}
                            >
                                {message.timestamp.toLocaleTimeString()}
                            </p>
                        </div>

                        {message.role === 'user' && (
                            <div className="flex-shrink-0">
                                <div className="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center">
                                    <User className="w-5 h-5 text-white" />
                                </div>
                            </div>
                        )}
                    </div>
                ))}

                {isLoading && (
                    <div className="flex gap-3 justify-start">
                        <div className="flex-shrink-0">
                            {hasAvatar ? (
                                <img
                                    src="/avatar.png"
                                    alt="Digital Twin Avatar"
                                    className="w-8 h-8 rounded-full border border-slate-300"
                                />
                            ) : (
                                <div className="w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center">
                                    <Bot className="w-5 h-5 text-white" />
                                </div>
                            )}
                        </div>
                        <div className="bg-white border border-gray-200 rounded-lg p-3">
                            <div className="flex space-x-2">
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100" />
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200" />
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            <div className="border-t border-gray-200 p-4 bg-white rounded-b-lg">
                <div className="flex gap-2">
                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyPress}
                        placeholder="Type your message..."
                        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-600 focus:border-transparent text-gray-800"
                        disabled={isLoading}
                        autoFocus
                    />
                    <button
                        onClick={sendMessage}
                        disabled={!input.trim() || isLoading}
                        className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
}
```

### Step 3: Commit and Push

From the project root:

```bash
git add frontend/components/twin.tsx
git add frontend/public/avatar.png  # Only if you added an avatar

git commit -m "Fix input focus issue and add avatar support"
git push
```

This push will automatically trigger a deployment to `dev`. Navigate to GitHub Actions to watch it run.

✅ **Checkpoint:** The input focus issue is resolved, and your avatar (if added) will appear in the chat interface.

---

## Part 8: Explore the AWS Console and CloudWatch

Now that infrastructure is running, it is worth spending time exploring what is happening behind the scenes. Sign in to the AWS Console as your IAM user (`aiengineer`).

### Lambda Functions

1. Navigate to **Lambda**
2. You should see functions for each deployed environment: `twin-dev-api`, `twin-test-api`, etc.
3. Click on `twin-dev-api` → **Monitor** tab to view invocation counts, duration metrics, error rates, and success rates

### CloudWatch Logs

From within the Lambda function page, click **View CloudWatch logs**. Select the latest log stream to see detailed records of every API request, Bedrock model invocation, and response. CloudWatch logs are invaluable for debugging issues in production, as they capture everything that was printed to the console in your Lambda function.

### Bedrock Usage Metrics

1. Navigate to **CloudWatch** → **Metrics** → **All metrics**
2. Click **AWS/Bedrock** → **By Model Id**
3. Select metrics for the Nova model: `InvocationLatency`, `InputTokenCount`, `OutputTokenCount`

This allows you to track how heavily the model is being used and how much each conversation is costing in tokens.

### S3 Conversation Memory

1. Navigate to **S3**
2. Click on the `twin-dev-memory` bucket
3. You will see individual JSON files, one per conversation session, named by UUID
4. Click on any file to inspect its contents — this is the conversation history that gives your Digital Twin its memory

### API Gateway and CloudFront Metrics

Both services expose built-in dashboards in the AWS Console showing request counts, latency percentiles, and error rates. These are useful for understanding how the application is performing under real traffic.

---

## Part 9: Environment Management via GitHub

### Destroy an Environment

To tear down an environment using the destroy workflow:

1. Go to GitHub → **Actions** tab
2. Click **Destroy Environment** in the left sidebar
3. Click **Run workflow**
4. Select:
   - Branch: `main`
   - Environment: `test`
   - Confirm: type `test`
5. Click **Run workflow**

The workflow will run the `destroy.sh` script on a Linux runner, emptying S3 buckets and running `terraform destroy` to remove all infrastructure for that environment.

### Redeploy an Environment

After destroying, you can redeploy at any time by triggering the Deploy Digital Twin workflow manually and selecting the desired environment. Terraform will recognise from the S3 state file that no infrastructure exists and will create everything from scratch.

This demonstrates the full power of the infrastructure-as-code approach: environments are fully reproducible, ephemeral, and interchangeable. There is no difference between the "first time" and the "tenth time" creating an environment — Terraform always produces exactly what the configuration describes.

---

## Part 10: Final Cleanup and Cost Review

### Step 1: Destroy All Active Environments

Using the destroy workflow, tear down each environment:
- Run **Destroy Environment** with `dev` and confirm with `dev`
- Run **Destroy Environment** with `test` and confirm with `test`
- Run **Destroy Environment** with `prod` and confirm with `prod`

### Step 2: Check What Remains

After all environments are destroyed, some resources will intentionally remain. These are the one-time setup resources that support GitHub Actions and are not tied to any specific environment:

- **IAM Role** (`github-actions-twin-deploy`): Free — IAM has no per-resource cost
- **S3 State Bucket** (`twin-terraform-state-*`): Approximately $0.02/month
- **DynamoDB Table** (`twin-terraform-locks`): Effectively $0.00/month with PAY_PER_REQUEST billing

**Total ongoing cost if left in place: less than $0.05/month**

These resources should generally be left in place, as they allow you to redeploy the project immediately at any time without repeating the setup process.

### Step 3: Verify Using AWS Resource Explorer

1. Sign in as the **root user**
2. Navigate to **Resource Explorer** in the AWS Console
3. If prompted, click **Quick setup** (a one-time process)
4. Search for `tag.Project:twin` to see all tagged project resources
5. Confirm that only the expected residual resources remain

Alternatively, use **AWS Tag Editor** (search from the AWS Console) with Key = `Project`, Value = `twin`, searching across all regions and all resource types.

### Step 4: Review Costs

1. Navigate to **Billing & Cost Management**
2. Click **Cost Explorer** → **Cost and usage**
3. Set the date range to the last 7 days
4. Group by **Service**

Expected costs for a typical week of use:
- Lambda: Under $1
- API Gateway: Under $1
- S3: A few cents
- CloudFront: A few cents
- Bedrock: Typically under $5, depending on usage
- DynamoDB: A few cents

Any unexpected charges in services you did not intentionally use should be investigated and the relevant resources deleted.

### Step 5: Complete Removal (Optional)

If you are entirely finished with the project and wish to remove all remaining resources, including the GitHub Actions infrastructure:

```bash
# Sign in as IAM user first, then:
cd twin/terraform

# 1. Remove IAM role policies and the role itself
aws iam detach-role-policy --role-name github-actions-twin-deploy --policy-arn arn:aws:iam::aws:policy/AWSLambda_FullAccess
aws iam detach-role-policy --role-name github-actions-twin-deploy --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam detach-role-policy --role-name github-actions-twin-deploy --policy-arn arn:aws:iam::aws:policy/AmazonAPIGatewayAdministrator
aws iam detach-role-policy --role-name github-actions-twin-deploy --policy-arn arn:aws:iam::aws:policy/CloudFrontFullAccess
aws iam detach-role-policy --role-name github-actions-twin-deploy --policy-arn arn:aws:iam::aws:policy/IAMReadOnlyAccess
aws iam detach-role-policy --role-name github-actions-twin-deploy --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
aws iam detach-role-policy --role-name github-actions-twin-deploy --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
aws iam detach-role-policy --role-name github-actions-twin-deploy --policy-arn arn:aws:iam::aws:policy/AWSCertificateManagerFullAccess
aws iam detach-role-policy --role-name github-actions-twin-deploy --policy-arn arn:aws:iam::aws:policy/AmazonRoute53FullAccess
aws iam delete-role-policy --role-name github-actions-twin-deploy --policy-name github-actions-additional
aws iam delete-role --role-name github-actions-twin-deploy

# 2. Empty and delete the state bucket
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3 rm s3://twin-terraform-state-${AWS_ACCOUNT_ID} --recursive
aws s3 rb s3://twin-terraform-state-${AWS_ACCOUNT_ID}

# 3. Delete the DynamoDB table
aws dynamodb delete-table --table-name twin-terraform-locks
```

**Recommendation:** Only perform this step if you are completely finished with the course. The residual cost is negligible, and keeping these resources means you can redeploy your project at any time without repeating the setup.

---

## Congratulations 🎉

You have successfully completed Week 2 and built a production-grade, fully automated AI deployment system.

### What You Have Built This Week

| Day | Achievement |
|-----|-------------|
| Day 1 | Built a local Digital Twin application with persistent conversation memory |
| Day 2 | Deployed to AWS using the console: Lambda, S3, API Gateway, CloudFront |
| Day 3 | Integrated Amazon Bedrock with the Nova foundation model |
| Day 4 | Automated infrastructure provisioning with Terraform and multiple environments |
| Day 5 | Implemented CI/CD with GitHub Actions — automated deployment on every push |

### Your Final Architecture

```
GitHub Repository
    ↓ (Push to main)
GitHub Actions (CI/CD)
    ↓ (Automated deployment)
AWS Infrastructure (via Terraform)
    ├── Dev Environment
    ├── Test Environment
    └── Prod Environment

Each Environment:
    ├── CloudFront → S3 (Frontend static site)
    ├── API Gateway → Lambda (Backend business logic)
    ├── Amazon Bedrock / Nova (AI model)
    └── S3 (Conversation memory)

Supporting Infrastructure:
    ├── Terraform (Infrastructure as Code)
    ├── GitHub Actions (CI/CD pipeline)
    ├── S3 + DynamoDB (Terraform remote state)
    └── IAM + OIDC (Secure authentication)
```

---

## Troubleshooting Common Issues

### "Could not assume role with OIDC"

This error means GitHub could not authenticate with AWS. The most common cause is a mismatch between the repository name stored in the IAM role's trust policy and the actual repository triggering the workflow.

- Check the `github_repository` variable you used when creating the IAM role
- It must exactly match `YOUR_GITHUB_USERNAME/YOUR_REPO_NAME` as it appears in your GitHub URL
- Username and repository name are **case-sensitive**
- To fix: re-run the `terraform apply` command with the correct repository name

### "Terraform state lock"

Another deployment may be running simultaneously, or a previous run failed while holding the lock.

- Check the DynamoDB table `twin-terraform-locks` in the AWS Console for active lock entries
- If you are certain no deployment is running, force-unlock: `terraform force-unlock LOCK_ID`

### "S3 bucket already exists"

S3 bucket names are globally unique across all AWS accounts. If the name is already taken by another account, append your account ID or a unique identifier to the bucket name in your Terraform configuration.

### "Frontend not updating after deployment"

CloudFront aggressively caches content. The deploy workflow includes a CloudFront cache invalidation step, but browser caches can also hold stale content. Try a hard refresh (`Ctrl+Shift+R` or `Cmd+Shift+R`) or open the URL in a private/incognito window.

### "API returning 403 Forbidden"

- Check that CORS is configured correctly in API Gateway
- Verify that the Lambda function's execution role has the necessary permissions
- Review CloudWatch logs for the Lambda function to identify the specific error

### "Bedrock not responding"

- Confirm that model access has been granted in the Amazon Bedrock console for your region
- Check that the IAM role used by Lambda includes `AmazonBedrockFullAccess`
- Review CloudWatch logs for the Lambda function

---

## Best Practices Going Forward

### Development Workflow

Always test changes in `dev` before promoting to `test` or `prod`. For larger changes, use feature branches:

```bash
git checkout -b feature/my-new-feature
# Make changes
git push -u origin feature/my-new-feature
# Create a pull request, review, then merge to main
```

Merging to `main` will trigger an automatic deployment to `dev`. Promotion to `test` and `prod` remains a deliberate manual step.

### Security

Never commit secrets or credentials to your repository. Use GitHub Secrets for all sensitive values. Review IAM role permissions periodically and apply the principle of least privilege — grant only the permissions that are actually needed.

### Cost Management

Check the AWS Billing dashboard regularly. Set up budget alerts to notify you if spending exceeds a threshold. Destroy `dev` and `test` environments when they are not actively needed — they cost money even when unused.
