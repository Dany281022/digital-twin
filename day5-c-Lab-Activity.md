# Day 5: Hands-On Lab Activity
## CI/CD with GitHub Actions — Practice Workbook

---

> **How to use this workbook**
> Work through each section in order. Some steps are fully guided. Others ask you to write commands, fill in blanks, or answer questions yourself. Code blocks marked with `# YOUR CODE HERE` are cells you must complete. Reflection questions do not have a single right answer — they are designed to deepen your understanding. Check off each checkpoint as you complete it.

---

## Learning Objectives

By the end of this activity, you will be able to:

- Explain why Terraform state must be stored remotely when using CI/CD pipelines
- Set up a Git repository with a proper `.gitignore` and push it to GitHub
- Provision an S3 backend and DynamoDB lock table for Terraform state
- Configure OIDC-based authentication between GitHub Actions and AWS
- Write and interpret a GitHub Actions workflow YAML file
- Trigger automated and manual deployments across multiple environments
- Destroy infrastructure cleanly using a GitHub Actions workflow

---

## Section 1: Environment Cleanup

### Background

Before introducing automation, you must ensure your AWS account contains no manually created infrastructure from previous sessions. If manually created resources exist alongside Terraform-managed ones, the state will be inconsistent and deployments may fail or produce duplicates.

### Guided Step 1.1 — Destroy Existing Environments

Run the following commands for each environment you created during the week. Choose the version that matches your operating system.

**Mac/Linux:**
```bash
./scripts/destroy.sh dev
./scripts/destroy.sh test
./scripts/destroy.sh prod
```

**Windows (PowerShell):**
```powershell
.\scripts\destroy.ps1 -Environment dev
.\scripts\destroy.ps1 -Environment test
.\scripts\destroy.ps1 -Environment prod
```

Each destruction will take approximately 5–10 minutes.

### Guided Step 1.2 — Remove Terraform Workspaces

```bash
cd terraform
terraform workspace select default
terraform workspace delete dev
terraform workspace delete test
terraform workspace delete prod
cd ..
```

### ✏️ Task 1.1 — Verify Clean State

After the destruction completes, log into the AWS Console and check each service listed below. In the table, write what you found in each service. All entries should say "None" or "Empty" if the cleanup was successful.

| AWS Service | What I Found | Clean? ✅/❌ |
|---|---|---|
| Lambda — functions starting with `twin-` | | |
| S3 — buckets starting with `twin-` | | |
| API Gateway — APIs starting with `twin-` | | |
| CloudFront — twin distributions | | |

### 💬 Reflection 1.1

Why is it important to start from a clean state before setting up CI/CD, rather than running the pipeline on top of existing manually-created infrastructure?

```
Your answer:


```

---

## Section 2: Git Repository Setup

### Background

GitHub Actions can only operate on code that lives in a GitHub repository. This section walks you through turning the `twin/` project directory into a proper Git repository and pushing it to GitHub.

A `.gitignore` file controls which files Git will track. Files excluded from Git are also excluded from GitHub, which means they will not be available to GitHub Actions when it checks out the code. It is therefore important to exclude only files that either contain secrets or are auto-generated artefacts — not files that are required to build and deploy the application.

### ✏️ Task 2.1 — Analyse the `.gitignore`

Review the `.gitignore` entries below. For each entry, write a brief reason why that item should be excluded from source control.

| Entry | Why it should be excluded |
|---|---|
| `*.tfstate` | |
| `lambda-deployment.zip` | |
| `.env` | |
| `!.env.example` | |
| `node_modules/` | |
| `.aws/` | |

### ✏️ Task 2.2 — Complete the `.gitignore`

The `.gitignore` below is missing four entries. Fill in the blanks using the hints provided.

```gitignore
# Terraform
*.tfstate
*.tfstate.*
____________________    # hint: the hidden directory Terraform creates when you run init
.terraform.lock.hcl
terraform.tfstate.d/
*.tfvars.secret

# Lambda packages
lambda-deployment.zip
lambda-package/

# Memory storage
memory/

# Environment files
.env
____________________    # hint: exclude ALL .env variants except .env.example
!.env.example

# Node
node_modules/
out/
____________________    # hint: Next.js build output directory
*.log

# Python
__pycache__/
*.pyc
____________________    # hint: Python virtual environment created by uv
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

### Guided Step 2.1 — Initialise the Repository

Before running `git init`, nested `.git` directories must be removed from `frontend/` and `backend/`. These are created automatically by `create-next-app` and `uv init` and would cause conflicts.

**Mac/Linux:**
```bash
cd twin
rm -rf frontend/.git backend/.git 2>/dev/null
git init -b main
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

**Windows (PowerShell):**
```powershell
cd twin
Remove-Item -Path frontend/.git -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path backend/.git -Recurse -Force -ErrorAction SilentlyContinue
git init -b main
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### ✏️ Task 2.3 — Stage and Commit

Write the two commands needed to stage all files and create the initial commit. Use the commit message: `"Initial commit: Digital Twin infrastructure and application"`

```bash
# Stage all files
# YOUR CODE HERE


# Create the initial commit with the message above
# YOUR CODE HERE

```

### ✏️ Task 2.4 — Push to GitHub

Fill in the blank in the command below with your actual GitHub username and repository name:

```bash
git remote add origin https://github.com/____________________/____________________

git push -u origin main
```

### ✅ Checkpoint 2

- [ ] `.gitignore` is complete and correct
- [ ] No nested `.git` directories in `frontend/` or `backend/`
- [ ] Repository initialised on `main` branch
- [ ] Initial commit created
- [ ] Code pushed to GitHub and visible on github.com

### 💬 Reflection 2.1

The `-b main` flag in `git init -b main` sets the default branch name to `main`. Older versions of Git use `master` as the default. Why does it matter which name is used, and what problem could arise if the branch name does not match what is expected?

```
Your answer:


```

---

## Section 3: Remote State Storage for Terraform

### Background

When GitHub Actions runs Terraform, it does so on a freshly created virtual machine. That machine is discarded immediately after the workflow completes, which means any local Terraform state file would be permanently lost. To keep state persistent and accessible across all workflow runs, Terraform must be configured to store its state in a remote backend.

The two AWS resources required are:
- An **S3 bucket** — stores the state files themselves
- A **DynamoDB table** — provides state locking to prevent two simultaneous deployments from corrupting state

### ✏️ Task 3.1 — Label the Architecture

The diagram below shows the relationship between GitHub Actions, Terraform, S3, and DynamoDB during a deployment. Fill in each blank with the correct label from this list: `State File`, `Lock Acquired`, `GitHub Actions Runner`, `Terraform`, `S3 Bucket`, `DynamoDB Table`.

```
[ ___________________ ]   ← short-lived virtual machine, destroyed after each run
        |
        | runs
        ↓
[ ___________________ ]   ← reads configuration, plans and applies changes
        |
        |--- reads/writes --→ [ ___________________ ]  ← persists [ ___________________ ]
        |
        |--- acquires ------→ [ ___________________ ]  ← records [ ___________________ ]
```

### Guided Step 3.1 — Create `backend-setup.tf`

Create `terraform/backend-setup.tf` with the following content. Read through it before moving on — the task that follows asks you questions about it.

```hcl
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
  bucket                  = aws_s3_bucket.terraform_state.id
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
}

output "state_bucket_name" {
  value = aws_s3_bucket.terraform_state.id
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.terraform_locks.name
}
```

### ✏️ Task 3.2 — Reading Terraform Configuration

Answer the following questions based on the `backend-setup.tf` file above:

**Q1.** What is the name of the S3 bucket that will be created? (Write the pattern, including the dynamic part.)

```
Answer:
```

**Q2.** What does `PAY_PER_REQUEST` billing mode mean for the DynamoDB table? What are the cost implications?

```
Answer:
```

**Q3.** What is the purpose of `aws_s3_bucket_public_access_block`? What security risk does it prevent?

```
Answer:
```

**Q4.** S3 versioning is enabled on the state bucket. Why is versioning useful specifically for a Terraform state file?

```
Answer:
```

### Guided Step 3.2 — Apply the Backend Resources

Navigate to the `terraform/` directory and run the commands below. Note that the `-target` flag restricts the apply to only the resources listed, rather than applying everything in all `.tf` files.

```bash
cd terraform
terraform workspace select default
terraform init
```

**Mac/Linux (one long command — copy and paste in full):**
```bash
terraform apply -target=aws_s3_bucket.terraform_state -target=aws_s3_bucket_versioning.terraform_state -target=aws_s3_bucket_server_side_encryption_configuration.terraform_state -target=aws_s3_bucket_public_access_block.terraform_state -target=aws_dynamodb_table.terraform_locks
```

**Windows PowerShell (one long command — copy and paste in full):**
```powershell
terraform apply --% -target="aws_s3_bucket.terraform_state" -target="aws_s3_bucket_versioning.terraform_state" -target="aws_s3_bucket_server_side_encryption_configuration.terraform_state" -target="aws_s3_bucket_public_access_block.terraform_state" -target="aws_dynamodb_table.terraform_locks"
```

Type `yes` when prompted, then run:
```bash
terraform output
```

### ✏️ Task 3.3 — Record the Outputs

Copy the output values from the terminal below:

```
state_bucket_name    = "____________________"
dynamodb_table_name  = "____________________"
```

### Guided Step 3.3 — Remove the Setup File and Update Scripts

```bash
rm backend-setup.tf          # Mac/Linux
Remove-Item backend-setup.tf  # Windows PowerShell
```

### ✏️ Task 3.4 — Complete the Updated `deploy.sh`

The updated `terraform init` block below configures Terraform to use the S3 backend. Fill in the four missing `-backend-config` values using the bucket name and table name you recorded above.

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${DEFAULT_AWS_REGION:-us-east-1}
terraform init -input=false \
  -backend-config="bucket=____________________" \
  -backend-config="key=${ENVIRONMENT}/terraform.tfstate" \
  -backend-config="region=____________________" \
  -backend-config="dynamodb_table=____________________" \
  -backend-config="encrypt=____________________"
```

### ✅ Checkpoint 3

- [ ] `backend-setup.tf` created and applied successfully
- [ ] S3 bucket and DynamoDB table confirmed in AWS Console
- [ ] `backend-setup.tf` deleted after use
- [ ] `deploy.sh` and `deploy.ps1` updated with S3 backend configuration
- [ ] `destroy.sh` and `destroy.ps1` replaced with updated versions

### 💬 Reflection 3.1

The `backend-setup.tf` file is created, used once, and then deleted. Why is it necessary to delete it after use? What would happen if it were left in place and `terraform apply` was run again later?

```
Your answer:


```

---

## Section 4: OIDC Authentication

### Background

GitHub Actions needs permission to create and manage AWS infrastructure on your behalf. There are two ways to provide this:

1. **Long-lived IAM access keys** — create an IAM user, generate an access key ID and secret, store them as GitHub secrets. Simple, but a security risk: if leaked, these keys are valid until manually revoked.

2. **OIDC (OpenID Connect)** — establish a trust relationship between GitHub and AWS. When a workflow runs, GitHub issues a short-lived token proving the workflow's identity. AWS verifies the token and grants temporary credentials. No long-lived secrets are stored anywhere.

This session uses OIDC.

### ✏️ Task 4.1 — OIDC Concept Check

Match each term on the left with its correct description on the right by writing the correct letter next to each number.

| # | Term | Letter | Description |
|---|---|---|---|
| 1 | OIDC Provider | | A. A short-lived credential issued by GitHub that proves which repository and workflow is running |
| 2 | IAM Role | | B. A named collection of permissions in AWS that can be temporarily assumed by an authorised identity |
| 3 | Trust Policy | | C. An AWS resource that registers GitHub as a trusted identity provider |
| 4 | OIDC Token | | D. A JSON document attached to an IAM role that defines who is allowed to assume it and under what conditions |
| 5 | Thumbprint | | E. A SHA-1 fingerprint of the identity provider's SSL certificate, used by AWS to verify authenticity |

### Guided Step 4.1 — Check for an Existing OIDC Provider

Run the appropriate command for your operating system:

**Mac/Linux:**
```bash
aws iam list-open-id-connect-providers | grep token.actions.githubusercontent.com
```

**Windows (PowerShell):**
```powershell
aws iam list-open-id-connect-providers | Select-String "token.actions.githubusercontent.com"
```

### ✏️ Task 4.2 — Determine Your Scenario

Based on the output of the command above, circle which scenario applies to you and explain how you know:

```
My scenario is:   A — OIDC provider does NOT exist   /   B — OIDC provider already exists

How I know:



```

### Guided Step 4.2 — Create `github-oidc.tf`

Create `terraform/github-oidc.tf`. This file defines the OIDC provider, the IAM role, and all required policy attachments. The complete content is provided in the lab guide `day5-a-Original.md` (Part 4, Step 1). Copy it exactly — pay careful attention to the `thumbprint_list` value and the structure of the `assume_role_policy`.

Before running anything, complete Task 4.3 below.

### ✏️ Task 4.3 — Read the Trust Policy

The `assume_role_policy` in `github-oidc.tf` contains a `Condition` block. Study it carefully and answer the following questions:

```hcl
Condition = {
  StringEquals = {
    "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
  }
  StringLike = {
    "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:*"
  }
}
```

**Q1.** What does `StringLike` with `"repo:${var.github_repository}:*"` mean? What would happen if a workflow from a different GitHub repository tried to assume this role?

```
Answer:
```

**Q2.** What does the `:*` wildcard at the end of the `sub` condition allow? What is it covering?

```
Answer:
```

**Q3.** Why is it important that `var.github_repository` uses the correct case (e.g., `Reza-Dibaj/twin` rather than `reza-dibaj/twin`)?

```
Answer:
```

### Guided Step 4.3 — Apply the OIDC Resources

Make sure you are in the `terraform/` directory and in the default workspace:

```bash
cd terraform
terraform workspace select default
terraform init
```

Run the appropriate apply command for your scenario (A or B) — see `day5-a-Original.md` Part 4 for the full commands. Remember to replace `YOUR_GITHUB_USERNAME/YOUR_REPO_NAME` with your actual values.

### ✏️ Task 4.4 — Record the Role ARN

After the apply completes, run the output command and record the role ARN:

```bash
terraform output github_actions_role_arn
```

```
My Role ARN: arn:aws:iam::____________________:role/____________________
```

Now delete the temporary file:

```bash
rm github-oidc.tf          # Mac/Linux
Remove-Item github-oidc.tf  # Windows PowerShell
```

### Guided Step 4.4 — Create `backend.tf`

Create `terraform/backend.tf`:

```hcl
terraform {
  backend "s3" {
    # Configuration is provided at runtime via -backend-config flags
  }
}
```

### Guided Step 4.5 — Add GitHub Repository Secrets

1. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**
2. Add the following three secrets:

| Secret Name | Value |
|---|---|
| `AWS_ROLE_ARN` | The ARN you recorded in Task 4.4 |
| `DEFAULT_AWS_REGION` | Your AWS region (check your `.env` file) |
| `AWS_ACCOUNT_ID` | Your 12-digit AWS account number |

### ✏️ Task 4.5 — Verify Your Secrets

After adding all three secrets, confirm they appear correctly. Write the name of each secret you see listed (the values will be hidden):

```
Secret 1: ____________________
Secret 2: ____________________
Secret 3: ____________________
```

### ✅ Checkpoint 4

- [ ] OIDC provider scenario determined (A or B)
- [ ] `github-oidc.tf` applied successfully
- [ ] Role ARN recorded
- [ ] `github-oidc.tf` deleted after use
- [ ] `backend.tf` created
- [ ] All three GitHub secrets added

---

## Section 5: GitHub Actions Workflows

### Background

A GitHub Actions workflow is a YAML file stored in `.github/workflows/`. YAML is a human-readable configuration format that uses indentation to express structure. Each workflow defines: when it should run (the trigger), what permissions it needs, and what jobs it should execute.

### ✏️ Task 5.1 — Anatomy of a Workflow

Study the extract from `deploy.yml` below, then answer the questions that follow.

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
```

**Q1.** This workflow has two triggers. Name them and describe what causes each one to fire.

```
Trigger 1:


Trigger 2:

```

**Q2.** What does `${{ github.event.inputs.environment || 'dev' }}` mean? What value will it have when the workflow is triggered by a push rather than manually?

```
Answer:
```

**Q3.** Why does the workflow require `id-token: write` permission? What would happen without it?

```
Answer:
```

**Q4.** What does `runs-on: ubuntu-latest` specify? Why does this matter for Windows users who run the scripts locally in PowerShell?

```
Answer:
```

### ✏️ Task 5.2 — Complete the Workflow Step

The workflow step below is incomplete. Fill in the three blanks to configure AWS credentials using OIDC. Use the GitHub secrets you set up in Section 4.

```yaml
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.____________________ }}
          role-session-name: github-actions-deploy
          aws-region: ${{ secrets.____________________ }}
```

And complete the environment variable injection in the Run Deployment Script step:

```yaml
      - name: Run Deployment Script
        run: |
          export AWS_ACCOUNT_ID=${{ secrets.____________________ }}
          export DEFAULT_AWS_REGION=${{ secrets.DEFAULT_AWS_REGION }}
          chmod +x scripts/deploy.sh
          ./scripts/deploy.sh ${{ github.event.inputs.environment || 'dev' }}
```

### ✏️ Task 5.3 — Analyse the Destroy Workflow Safeguard

The `destroy.yml` workflow includes the following verification step:

```yaml
      - name: Verify confirmation
        run: |
          if [ "${{ github.event.inputs.confirm }}" != "${{ github.event.inputs.environment }}" ]; then
            echo "❌ Confirmation does not match environment name!"
            exit 1
          fi
          echo "✅ Destruction confirmed for ${{ github.event.inputs.environment }}"
```

**Q1.** In plain language, what does this step do and why?

```
Answer:
```

**Q2.** The `destroy.yml` workflow uses `workflow_dispatch` only — it has no `push` trigger. Why is this design decision important?

```
Answer:
```

**Q3.** Suggest one additional safeguard that could be added to make the destroy workflow even safer for production environments.

```
Your suggestion:
```

### Guided Step 5.1 — Create the Workflow Directory and Files

In Cursor's Explorer panel:
1. Create `.github/` at the project root
2. Create `workflows/` inside `.github/`
3. Create `deploy.yml` inside `.github/workflows/` — paste the full content from `day5-a-Original.md` Part 5, Step 2
4. Create `destroy.yml` inside `.github/workflows/` — paste the full content from `day5-a-Original.md` Part 5, Step 3

### ✏️ Task 5.4 — Commit and Push

Write the three commands needed to stage, commit, and push all changes to GitHub. Use the commit message: `"Add CI/CD with GitHub Actions, S3 backend, and updated scripts"`

```bash
# Stage all changes
# YOUR CODE HERE


# Commit with the message above
# YOUR CODE HERE


# Push to GitHub
# YOUR CODE HERE

```

### ✅ Checkpoint 5

- [ ] `.github/workflows/` directory created
- [ ] `deploy.yml` created and saved
- [ ] `destroy.yml` created and saved
- [ ] All changes committed and pushed
- [ ] Workflow appears in GitHub → Actions tab

---

## Section 6: Testing Deployments

### Background

Once the push is made, GitHub Actions automatically triggers the deploy workflow. The first deployment provisions the entire infrastructure stack from scratch in the `dev` environment. Subsequent deployments to the same environment will only update what has changed — Terraform uses the state stored in S3 to determine what already exists.

### Guided Step 6.1 — Monitor the Automatic Dev Deployment

1. Go to your GitHub repository
2. Click the **Actions** tab
3. You should see the workflow triggered by your push
4. Click on the workflow run, then click on the **Deploy to dev** job to watch the live log

### ✏️ Task 6.1 — Read the Workflow Log

As the workflow runs (or after it completes), find and record the step names that appear in the job log. List at least six steps in the order they execute:

```
Step 1: ____________________
Step 2: ____________________
Step 3: ____________________
Step 4: ____________________
Step 5: ____________________
Step 6: ____________________
Step 7: ____________________
Step 8: ____________________
```

### ✏️ Task 6.2 — Record Deployment Outputs

After the workflow completes, expand the **Deployment Summary** step and record the values:

```
CloudFront URL:   ____________________
API Gateway URL:  ____________________
Frontend Bucket:  ____________________
```

Open the CloudFront URL in your browser and confirm your Digital Twin is running.

```
Did it work?   YES  /  NO

If no, what error did you see?


```

### Guided Step 6.2 — Trigger a Manual Test Deployment

1. In GitHub → **Actions** tab, click **Deploy Digital Twin** in the left sidebar
2. Click **Run workflow** (top right)
3. Select environment: `test`
4. Click **Run workflow**

### ✏️ Task 6.3 — Compare Environments

After the test deployment completes, record the CloudFront URL for the test environment and compare it to dev:

```
Dev CloudFront URL:   ____________________
Test CloudFront URL:  ____________________
```

Both URLs should serve the same application. What is different between the two environments at the infrastructure level?

```
Answer:


```

### 💬 Reflection 6.1

When you run the deploy workflow for the second time on the same environment, Terraform does not recreate all resources — it only changes what is different from the current state. Why is this behaviour valuable in a production CI/CD pipeline?

```
Your answer:


```

### ✅ Checkpoint 6

- [ ] Automatic `dev` deployment succeeded (green tick in Actions)
- [ ] Digital Twin accessible via CloudFront URL
- [ ] Manual `test` deployment triggered and succeeded
- [ ] Deployment URLs recorded

---

## Section 7: UI Improvements — Git Push to Deploy

### Background

One of the most powerful aspects of CI/CD is that a code change can go from your editor to a live production environment in a matter of minutes with a single `git push`. This section demonstrates that by making two small improvements to the frontend.

### Guided Step 7.1 — Add an Avatar (Optional)

If you have a profile picture, save it as `frontend/public/avatar.png`. It should be square and under 100KB.

### ✏️ Task 7.1 — Identify the Code Change

The updated `twin.tsx` component adds focus management so the input field automatically regains focus after each message. The key addition is:

```typescript
const inputRef = useRef<HTMLInputElement>(null);

useEffect(() => {
    if (!isLoading) {
        inputRef.current?.focus();
    }
}, [isLoading]);
```

Explain in your own words what this code does. Specifically: what is `useRef` used for, what triggers the `useEffect`, and what does `?.focus()` do?

```
Your explanation:


```

### Guided Step 7.2 — Update `twin.tsx`

Replace the contents of `frontend/components/twin.tsx` with the updated version from `day5-a-Original.md` Part 7, Step 2.

### ✏️ Task 7.2 — Deploy the Change

Write the commands to commit and push this change. Use the commit message: `"Fix input focus issue and add avatar support"`

```bash
# Stage only the relevant files
# YOUR CODE HERE



# Commit
# YOUR CODE HERE


# Push — this will automatically trigger a deployment to dev
# YOUR CODE HERE

```

### ✏️ Task 7.3 — Verify the Deployment

After the workflow completes, visit the dev CloudFront URL and test the fix.

```
Before the fix — what happened after sending a message?


After the fix — what happens now?


Did the avatar appear (if you added one)?   YES  /  NO  /  N/A
```

### ✅ Checkpoint 7

- [ ] `twin.tsx` updated with focus fix
- [ ] Change committed and pushed
- [ ] Automatic deployment triggered successfully
- [ ] Focus behaviour confirmed working in browser

---

## Section 8: Environment Destruction via GitHub

### Background

Just as deployment is automated, so is teardown. The `destroy.yml` workflow calls the same `destroy.sh` script that was used locally in Part 1, but runs it entirely in the cloud. This means you can tear down any environment from the GitHub interface without opening a terminal.

### ✏️ Task 8.1 — Trace the Destroy Workflow

Trace the path of a destroy request from the moment you click "Run workflow" to the moment the infrastructure is gone. Fill in the missing steps:

```
1. User clicks "Run workflow" in GitHub Actions UI
        ↓
2. GitHub validates that the confirmation input matches the environment name
        ↓
3. ____________________
        ↓
4. GitHub Actions runner checks out the repository code
        ↓
5. ____________________
        ↓
6. ____________________
        ↓
7. `destroy.sh` runs: empties S3 buckets, then runs `terraform destroy`
        ↓
8. Terraform reads state from S3 to identify all resources to destroy
        ↓
9. ____________________
        ↓
10. Terraform updates state file in S3 to reflect that all resources are gone
```

### Guided Step 8.1 — Destroy the Test Environment

1. Go to GitHub → **Actions** → **Destroy Environment**
2. Click **Run workflow**
3. Set environment: `test`, confirm: `test`
4. Click **Run workflow**

### ✏️ Task 8.2 — Verify the Destruction

After the workflow completes, check the AWS Console and confirm the test environment resources are gone:

| Resource | Present Before | Present After | Destroyed? ✅/❌ |
|---|---|---|---|
| Lambda `twin-test-api` | ✅ | | |
| S3 `twin-test-frontend-*` | ✅ | | |
| S3 `twin-test-memory-*` | ✅ | | |
| API Gateway `twin-test-*` | ✅ | | |
| CloudFront distribution | ✅ | | |

### 💬 Reflection 8.1

After destroying the test environment, the Terraform state file for `test` in S3 is updated to reflect that all resources have been removed. If you run the deploy workflow for `test` again tomorrow, Terraform will create everything from scratch. What does this tell you about the relationship between infrastructure and state in a Terraform-managed system?

```
Your answer:


```

---

## Section 9: Cost Management and Final Cleanup

### Background

Even after all application environments are destroyed, some residual resources remain — specifically the one-time setup resources created in Sections 3 and 4. Understanding what remains and what it costs is an important part of responsible cloud usage.

### ✏️ Task 9.1 — Identify Residual Resources

After destroying all environments (dev, test, prod), the following resources will still exist in your AWS account. For each one, explain why it was not destroyed by the `terraform destroy` commands and estimate its monthly cost based on the information in the lab guide.

| Resource | Why it remains | Estimated monthly cost |
|---|---|---|
| S3 state bucket (`twin-terraform-state-*`) | | |
| DynamoDB table (`twin-terraform-locks`) | | |
| IAM Role (`github-actions-twin-deploy`) | | |

### Guided Step 9.1 — Use AWS Resource Explorer

1. Sign in as the **root user**
2. Search for **Resource Explorer** in the AWS Console
3. Click **Quick setup** if prompted
4. In Resource Explorer, search for `tag.Project:twin`

### ✏️ Task 9.2 — Resource Audit

Record how many resources you found in Resource Explorer before and after destroying all environments:

```
Resources found BEFORE destroying all environments: ____________________
Resources found AFTER destroying all environments:  ____________________
Resources that remain (residual):                   ____________________
```

### ✏️ Task 9.3 — Cost Review

Navigate to **Billing & Cost Management** → **Cost Explorer** and set the date range to the last 7 days. Record actual costs by service:

| Service | Cost this week |
|---|---|
| Lambda | |
| API Gateway | |
| S3 | |
| CloudFront | |
| Amazon Bedrock | |
| DynamoDB | |
| **Total** | |

Is the total within what you expected? If any service is higher than expected, what might explain it?

```
Analysis:


```

### ✅ Final Checkpoint

- [ ] All environments (dev, test, prod) destroyed via GitHub Actions
- [ ] AWS Resource Explorer confirms only residual resources remain
- [ ] Cost review completed
- [ ] All GitHub Actions workflow runs show green ticks

---

## Final Reflection

Take a few minutes to answer the following questions thoughtfully. There are no wrong answers.

### 💬 Question 1

At the beginning of the week, you deployed the Digital Twin manually using the AWS Console. By the end of today, the same deployment happens automatically when you run `git push`. What are three specific advantages of the automated approach over the manual one?

```
Advantage 1:


Advantage 2:


Advantage 3:

```

### 💬 Question 2

The CI/CD pipeline set up today covers the `dev` environment automatically and `test`/`prod` manually. In a professional team setting, what criteria might you use to decide when to automatically promote a deployment from `dev` to `test`, and from `test` to `prod`?

```
Your answer:


```

### 💬 Question 3

OIDC is more secure than long-lived access keys, but it added several setup steps. In your own judgement, was the complexity of the OIDC setup worth the security benefit? Would your answer change depending on the type of project?

```
Your answer:


```

### 💬 Question 4

Looking back at the week as a whole, identify one concept that you feel confident about and one concept that you would like to understand more deeply. For the second one, write one specific question you would want answered.

```
Concept I feel confident about:


Concept I want to understand more deeply:


My specific question:

```

---

## Summary: Key Commands Reference

Use this table as a quick reference for the most important commands used today.

| Action | Command |
|---|---|
| Destroy environment (Mac/Linux) | `./scripts/destroy.sh <env>` |
| Destroy environment (Windows) | `.\scripts\destroy.ps1 -Environment <env>` |
| Switch Terraform workspace | `terraform workspace select <name>` |
| Delete Terraform workspace | `terraform workspace delete <name>` |
| Initialise Git repo | `git init -b main` |
| Stage all changes | `git add .` |
| Commit with message | `git commit -m "message"` |
| Push to GitHub | `git push` |
| Check Git status | `git status` |
| Add remote origin | `git remote add origin <url>` |
| Check OIDC provider (Mac/Linux) | `aws iam list-open-id-connect-providers \| grep token.actions.githubusercontent.com` |
| Check OIDC provider (Windows) | `aws iam list-open-id-connect-providers \| Select-String "token.actions.githubusercontent.com"` |
| Get AWS account ID | `aws sts get-caller-identity --query Account --output text` |
| View Terraform outputs | `terraform output` |

---

*End of Day 5 Lab Activity*
