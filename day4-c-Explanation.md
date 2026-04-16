# Day 4: Infrastructure as Code with Terraform — A Self-Study Guide

## Introduction

This guide accompanies the Day 4 practical session, in which you transition from manually provisioning AWS resources through the Management Console to defining and deploying your entire Digital Twin infrastructure through code. The tool you will use for this purpose is **Terraform**, an open-source Infrastructure-as-Code (IaC) platform created by HashiCorp. By the end of this session you will be able to deploy, verify, and tear down fully isolated development, test, and production environments using a single shell command for each.

The document follows the structure of the original Day 4 lab guide, but every step is accompanied by an explanation of *what* is happening and *why*, so that you can work through the material independently with a clear understanding of the underlying principles.

### Overview of Each Major Step

**Part 1 — Clean Slate: Remove Manual Resources.** Before introducing automation, you will delete all of the AWS resources that you created by hand in earlier sessions — the Lambda function, API Gateway, S3 buckets, and CloudFront distribution. This serves two purposes: it returns your AWS account to a known empty state so that Terraform can manage everything from scratch, and it provides one final hands-on tour of the console, reinforcing exactly how tedious manual provisioning is at scale.

**Part 2 — Understanding Terraform.** This section introduces the conceptual foundations of Infrastructure as Code: what it means to describe your cloud environment in declarative configuration files, how Terraform tracks the state of deployed resources, and the six key terms (provider, variable, resource, state, output, workspace) that you will encounter throughout the rest of the course. You will also install Terraform and prepare your project's `.gitignore` file.

**Part 3 — Create Terraform Configuration.** Here you build the actual Terraform files that describe your Digital Twin's infrastructure: the provider and version constraints (`versions.tf`), the configurable parameters (`variables.tf`), the full resource graph (`main.tf`), the deployment outputs (`outputs.tf`), and the default variable values (`terraform.tfvars`). You will also update the frontend code so that the API URL can be injected at build time rather than being hard-coded.

**Part 4 — Create Deployment Scripts.** You write shell scripts (Bash for Mac/Linux and PowerShell for Windows) that orchestrate the entire deployment pipeline: packaging the Lambda function, running Terraform, extracting the generated API URL, building the static frontend with that URL baked in, and uploading it to S3.

**Part 5 — Deploy the Development Environment.** You initialise Terraform, run the deployment script with the `dev` workspace, and verify the resulting environment by visiting the CloudFront URL and inspecting resources in the AWS Console.

**Part 6 — Deploy the Test Environment.** You run the same script a second time with the `test` workspace, which creates an entirely separate, parallel set of AWS resources. You then verify that the two environments are fully isolated.

**Part 7 — Destroying Infrastructure.** You create destroy scripts that empty S3 buckets and then call `terraform destroy` to remove all resources for a given environment. You run them against dev, test, and (if applicable) production to confirm that teardown is as automated as provisioning.

**Part 8 — Optional: Custom Domain for Production.** If you wish, you register a domain through AWS Route 53, create a `prod.tfvars` file that enables custom-domain support, and deploy a production environment that includes an SSL certificate, DNS records, and a professional URL.

---

## Part 1: Clean Slate — Remove Manual Resources

### Why This Step Matters

In earlier sessions you created AWS resources — a Lambda function, an API Gateway, S3 buckets, and a CloudFront distribution — by clicking through the AWS Management Console. Before Terraform can take over as the sole manager of your infrastructure, you need to remove those manually created resources. If you leave them in place, you risk naming conflicts (two S3 buckets cannot share the same name globally) and confusion over which resources Terraform is responsible for.

This cleanup also serves as a practical reminder of how many individual steps manual provisioning involves. By the time you have finished deleting everything, the value of an automated approach should feel self-evident.

> **Tip from the lecturer:** This is also a good moment to sign in as your root user, navigate to **Billing and Cost Management**, and verify that your AWS spending is exactly what you expect — ideally zero if you are on the free tier. Building the habit of checking your bill regularly is an important part of working with cloud services.

### Step 1: Delete the Lambda Function

1. Sign in to the AWS Console as your IAM user (e.g. `aiengineer`).
2. Navigate to **Lambda** (you can type "Lambda" in the search bar or find it under Recently Visited).
3. Select the `twin-api` function.
4. Click **Actions → Delete**.
5. Type "delete" to confirm, then click **Delete**.

**What is happening:** You are removing the serverless function that handled incoming API requests for your Digital Twin. The function's code, configuration, and all associated CloudWatch log groups will be permanently deleted.

### Step 2: Delete the API Gateway

1. Navigate to **API Gateway**.
2. Click on `twin-api-gateway`.
3. Click **Actions → Delete**.
4. Type the API name to confirm, then click **Delete**.

**What is happening:** The API Gateway is the routing layer that accepted HTTP requests and forwarded them to your Lambda function. Deleting it removes all routes, stages, and integrations.

### Step 3: Empty and Delete S3 Buckets

AWS does not allow you to delete an S3 bucket that still contains objects. You must empty it first.

**Memory Bucket:**

1. Navigate to **S3**.
2. Click on your memory bucket (e.g. `twin-memory-xyz`).
3. Click **Empty**. Type "permanently delete" to confirm, then click **Empty**.
4. Return to the bucket list, select the now-empty bucket, and click **Delete**.
5. Type the bucket name to confirm, then click **Delete bucket**.

**Frontend Bucket:**

Repeat the same empty-then-delete process for your frontend bucket (e.g. `twin-frontend-xyz`).

> **Console shortcut:** When the confirmation dialogue asks you to type a phrase, you can often use the small copy icon next to the required text to paste it in, rather than typing it manually.

### Step 4: Delete the CloudFront Distribution

1. Navigate to **CloudFront**.
2. Select your distribution.
3. Click **Disable** (CloudFront requires a distribution to be disabled before it can be deleted).
4. Wait for the status to change from "Deploying" to "Disabled". This typically takes **5–10 minutes**; you can refresh the page periodically to check.
5. Once the status shows "Disabled", select the distribution again and click **Delete**.

**Why the wait?** CloudFront distributions are replicated across edge locations worldwide. Disabling a distribution requires propagating that change to every edge location, which is why the process takes several minutes.

### Step 5: Verify a Clean State

Return to each service and confirm that no twin-related resources remain:

- **Lambda:** No functions with `twin` in the name.
- **API Gateway:** No APIs with `twin` in the name.
- **S3:** No buckets with a `twin-` prefix.
- **CloudFront:** No distributions associated with your twin project.

Your AWS account is now in a clean state, ready for Terraform to manage everything going forward.

---

## Part 2: Understanding Terraform

### What is Infrastructure as Code?

Infrastructure as Code (IaC) is the practice of defining your cloud infrastructure — servers, databases, networking rules, permissions, and so on — in text-based configuration files rather than through graphical console interfaces. These files are treated like any other source code: they are stored in a version-control system (such as Git), reviewed through pull requests, and executed automatically by a tool that translates the declared configuration into real cloud resources.

There are four principal benefits to this approach:

1. **Version control.** Every change to your infrastructure is tracked in Git. You can see who changed what, when, and why. If a deployment breaks something, you can revert to a previous configuration.
2. **Peer review.** Infrastructure changes can be reviewed in pull requests just like application code, reducing the likelihood of misconfigurations.
3. **Automation.** Instead of navigating dozens of console screens and filling in forms by hand, you issue a single command and the tool handles everything — including the sequencing and dependency resolution between resources.
4. **Repeatability.** The same configuration can be applied as many times as needed to produce identical environments. This is especially important for maintaining consistency across development, testing, and production.

### Why Terraform Specifically?

Terraform, created by Mitchell Hashimoto and the company HashiCorp, uses a declarative language called **HCL** (HashiCorp Configuration Language) to describe infrastructure. It has become one of the most widely adopted IaC tools in the industry for several reasons:

- **Provider-agnostic.** The same language and workflow can target AWS, Google Cloud Platform, Microsoft Azure, Cloudflare, Datadog, GitHub, and hundreds of other services. This portability makes Terraform a transferable skill.
- **Mature ecosystem.** Terraform has been in active development for over a decade, with a vast library of community-maintained providers and modules.
- **Declarative model.** You describe the *desired end state* of your infrastructure, and Terraform calculates the minimal set of changes needed to reach that state from the current one.

AWS offers its own IaC tool called the **Cloud Development Kit (CDK)**, which lets you define infrastructure in general-purpose programming languages such as TypeScript or Python. CDK is tightly integrated with AWS and has a growing community. However, because CDK is AWS-specific and Terraform works across all major cloud providers, this course uses Terraform — it is the more broadly applicable skill and the one you are most likely to encounter in industry.

### Six Key Concepts

Before you write any Terraform code, internalise these six terms:

**1. Provider** — A provider is a plugin that teaches Terraform how to interact with a specific cloud platform or service. When you declare `provider "aws"`, Terraform downloads the AWS plugin and gains the ability to create, read, update, and delete AWS resources. Providers exist for all major cloud vendors as well as many third-party services.

**2. Variable** — A variable is a configurable parameter that you can change without modifying the underlying configuration logic. For example, the Bedrock model ID, the AWS region, or the project name might each be defined as a variable. Variables promote reusability: the same configuration can be deployed with different settings for different environments.

**3. Resource** — A resource is the fundamental building block of your infrastructure. Each `resource` block in a Terraform file corresponds to a single infrastructure component: an S3 bucket, a Lambda function, an API Gateway, a CloudFront distribution, and so on. Terraform manages each resource's full lifecycle — creation, modification, and deletion.

**4. State** — Terraform maintains an internal record called the *state* that maps your declared configuration to the actual resources deployed in the cloud. The state is stored in a file called `terraform.tfstate`. It is critical because it allows Terraform to determine what currently exists and to compute the minimal diff needed to reach the desired configuration. State files should **never** be committed to Git, because they change with every deployment and may contain sensitive information (such as resource ARNs and internal identifiers).

**5. Output** — Outputs are values that Terraform exposes after a successful deployment. They typically include information you need in order to use the deployed infrastructure — for example, the URL of a CloudFront distribution or the endpoint of an API Gateway. Outputs serve as a bridge between Terraform and the rest of your workflow (such as a deployment script that needs to know where to upload frontend files).

**6. Workspace** — Workspaces provide isolated instances of state for the same configuration. You might have one workspace called `dev`, another called `test`, and a third called `prod`. Each workspace tracks its own set of deployed resources independently. When you switch workspaces, Terraform operates against an entirely different state file. This allows you to deploy three parallel copies of the same architecture — with different names, different settings, and no interference between them — from a single set of configuration files. The concept is analogous to namespaces in programming.

### Key Terraform Commands

You will use three commands repeatedly:

| Command | Purpose |
|---------|---------|
| `terraform init` | Initialises the working directory, downloads provider plugins, and prepares Terraform for use. Run this once when you first set up a project, or whenever you change provider versions. |
| `terraform apply` | Reads your configuration files, compares them against the current state, computes a plan of changes, and (after confirmation) executes those changes to create, update, or delete resources. |
| `terraform destroy` | Removes all resources that Terraform is currently managing in the active workspace. |

A fourth command, `terraform plan`, is worth knowing: it shows you *what* Terraform would do without actually doing it. This is valuable for reviewing changes before applying them.

### Step 1: Install Terraform

Terraform is distributed as a single binary. Installation methods vary by operating system.

**Mac (using Homebrew):**

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

> **Note on the tap:** The `hashicorp/tap` is HashiCorp's official Homebrew tap. Using it ensures that you receive the officially packaged binary directly from HashiCorp, rather than a community-maintained formula.

**Mac/Linux (manual download):**

1. Visit [https://developer.hashicorp.com/terraform/install](https://developer.hashicorp.com/terraform/install).
2. Download the appropriate package for your system and architecture.
3. Extract and move the binary to a directory on your PATH:

```bash
# Example for Mac (adjust the URL and filename for your system and the latest version)
curl -O https://releases.hashicorp.com/terraform/1.12.2/terraform_1.12.2_darwin_amd64.zip
unzip terraform_1.12.2_darwin_amd64.zip
sudo mv terraform /usr/local/bin/
```

**Windows:**

1. Visit [https://developer.hashicorp.com/terraform/install](https://developer.hashicorp.com/terraform/install).
2. Download the Windows `.zip` package.
3. Extract the `terraform.exe` file.
4. Add the directory containing `terraform.exe` to your system PATH:
   - Right-click **This PC** → **Properties** → **Advanced system settings** → **Environment Variables**.
   - Under **System variables**, select **Path**, click **Edit**, and add the directory where you placed `terraform.exe`.

> **Windows Subsystem for Linux (WSL):** If you have WSL installed with Ubuntu, you may prefer to work from the Linux side for greater consistency with the Mac/Linux instructions. This is the lecturer's recommendation, though it is entirely your choice.

**Verify your installation:**

```bash
terraform --version
```

You should see output indicating the installed version (e.g. `Terraform v1.12.2`). The exact version number will depend on when you perform the installation; any recent stable release will work with the configuration files in this guide.

### Step 2: Update `.gitignore`

Your project is not yet a Git repository, but it will become one in the next session (Day 5). Preparing a `.gitignore` now ensures that sensitive and transient files are never accidentally committed.

Create a file called `.gitignore` in your project root with the following contents:

```gitignore
# Terraform
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl
terraform.tfstate.d/
*.tfvars
!terraform.tfvars
!prod.tfvars

# Lambda packages
lambda-deployment.zip
lambda-package/

# Environment files
.env
.env.*

# Node
node_modules/
out/
.next/

# Python
__pycache__/
*.pyc
.venv/

# IDE
.vscode/
.idea/
*.swp
.DS_Store
```

**Understanding what each block does:**

- **Terraform state files** (`*.tfstate`, `terraform.tfstate.d/`): These track the mapping between your configuration and real AWS resources. They change with every deployment and may contain sensitive information — they must never be committed to source control.
- **`.terraform/` directory**: Contains downloaded provider plugins. These are large binary files that can be re-downloaded at any time with `terraform init`.
- **`.terraform.lock.hcl`**: Records the exact provider versions used. Some teams *do* commit this file for reproducibility; excluding it here is a simplification.
- **`*.tfvars` with exceptions**: Variable files *can* contain secrets (e.g. API keys), so they are excluded by default. However, two specific files — `terraform.tfvars` (your defaults) and `prod.tfvars` (your production overrides) — are explicitly re-included with the `!` prefix, because they contain only non-sensitive configuration values in this project.
- **Lambda packages**: The `lambda-deployment.zip` and `lambda-package/` directory are build artefacts regenerated by the deploy script every time.
- **Environment, Node, and Python files**: Standard exclusions for transient or generated files that should not be version-controlled.

> **A note on `uv.lock`:** If you are using `uv` as your Python package manager, its lock file (`uv.lock`) should generally be committed to source control for reproducible builds, much like `package-lock.json` in Node.js projects. It is not excluded here.

---

## Part 3: Create Terraform Configuration

### Directory Structure

Create a new top-level folder called `terraform` in your project. Your project should now look like this:

```
twin/
├── backend/
├── frontend/
├── memory/
└── terraform/    ← new
```

All of the `.tf` files you create in the following steps will live inside this `terraform/` directory. Terraform automatically combines all `.tf` files in a directory into a single configuration, so how you split them across files is a matter of convention and readability rather than a technical requirement. The conventions used here — `versions.tf`, `variables.tf`, `main.tf`, `outputs.tf` — are standard in the Terraform community.

### Step 1: Provider Configuration (`versions.tf`)

Create the file `terraform/versions.tf`:

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

**What this file does:**

- **`terraform` block:** Declares that your configuration requires Terraform version 1.0 or later, and depends on the AWS provider from the HashiCorp registry at version 6.x (the `~>` operator allows patch and minor updates within the 6.x range but not a jump to 7.x).
- **First `provider "aws"` block:** This is the *default* AWS provider. It has no explicit region because it inherits the region from your AWS CLI configuration (which you set up with `aws configure` in an earlier session). Every AWS resource in your configuration will use this provider unless told otherwise.
- **Second `provider "aws"` block (with alias):** This creates a second, named provider instance locked to the `us-east-1` region. It exists because AWS CloudFront requires SSL certificates to be provisioned in `us-east-1` regardless of where your other resources live. The optional custom-domain section later in the configuration references this aliased provider for the ACM certificate.

### Step 2: Variables (`variables.tf`)

Create the file `terraform/variables.tf`:

```hcl
variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (dev, test, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Environment must be one of: dev, test, prod."
  }
}

variable "bedrock_model_id" {
  description = "Bedrock model ID"
  type        = string
  default     = "amazon.nova-micro-v1:0"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 60
}

variable "api_throttle_burst_limit" {
  description = "API Gateway throttle burst limit"
  type        = number
  default     = 10
}

variable "api_throttle_rate_limit" {
  description = "API Gateway throttle rate limit"
  type        = number
  default     = 5
}

variable "use_custom_domain" {
  description = "Attach a custom domain to CloudFront"
  type        = bool
  default     = false
}

variable "root_domain" {
  description = "Apex domain name, e.g. mydomain.com"
  type        = string
  default     = ""
}
```

**What this file does:**

Each `variable` block declares a named parameter that the rest of your configuration can reference. Think of variables as the knobs and dials of your infrastructure — they let you adjust behaviour without modifying the underlying logic.

- **`project_name`** and **`environment`**: Together, these form a naming prefix (e.g. `twin-dev`, `twin-test`, `twin-prod`) that is prepended to every resource. The `validation` blocks enforce constraints: the project name must be lowercase alphanumeric (because AWS resource names are often case-sensitive and restricted), and the environment must be one of the three permitted values.
- **`bedrock_model_id`**: Determines which Amazon Bedrock model the Lambda function will call. The default is `amazon.nova-micro-v1:0`, which is the cheapest option — appropriate for development and testing. For production, you will override this with a more capable model.
- **`lambda_timeout`**: How many seconds the Lambda function is allowed to run before AWS forcibly terminates it. Sixty seconds is generous for a chat response.
- **`api_throttle_burst_limit`** and **`api_throttle_rate_limit`**: These control how many requests per second the API Gateway will accept before throttling. They serve as a safety net against runaway costs from unexpected traffic spikes.
- **`use_custom_domain`** and **`root_domain`**: These are disabled by default (`false` and `""`). When you are ready to deploy with a professional domain name, you set `use_custom_domain = true` and provide your domain. Several resource blocks in `main.tf` are conditionally created based on these values.

### Step 3: Main Infrastructure (`main.tf`)

Create the file `terraform/main.tf` and paste in the full configuration below. This is the largest file in the project. Rather than reproduce every line here with inline annotations (which would make the file difficult to copy), the explanations follow in a dedicated walkthrough section.

```hcl
# Data source to get current AWS account ID
data "aws_caller_identity" "current" {}

locals {
  aliases = var.use_custom_domain && var.root_domain != "" ? [
    var.root_domain,
    "www.${var.root_domain}"
  ] : []

  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# S3 bucket for conversation memory
resource "aws_s3_bucket" "memory" {
  bucket = "${local.name_prefix}-memory-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "memory" {
  bucket = aws_s3_bucket.memory.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "memory" {
  bucket = aws_s3_bucket.memory.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# S3 bucket for frontend static website
resource "aws_s3_bucket" "frontend" {
  bucket = "${local.name_prefix}-frontend-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "404.html"
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
      },
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${local.name_prefix}-lambda-role"
  tags = local.common_tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_role.name
}

resource "aws_iam_role_policy_attachment" "lambda_bedrock" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
  role       = aws_iam_role.lambda_role.name
}

resource "aws_iam_role_policy_attachment" "lambda_s3" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
  role       = aws_iam_role.lambda_role.name
}

# Lambda function
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

# API Gateway HTTP API
resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name_prefix}-api-gateway"
  protocol_type = "HTTP"
  tags          = local.common_tags

  cors_configuration {
    allow_credentials = false
    allow_headers     = ["*"]
    allow_methods     = ["GET", "POST", "OPTIONS"]
    allow_origins     = ["*"]
    max_age           = 300
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
  tags        = local.common_tags

  default_route_settings {
    throttling_burst_limit = var.api_throttle_burst_limit
    throttling_rate_limit  = var.api_throttle_rate_limit
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.api.invoke_arn
}

# API Gateway Routes
resource "aws_apigatewayv2_route" "get_root" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "post_chat" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /chat"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "get_health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# CloudFront distribution
resource "aws_cloudfront_distribution" "main" {
  aliases = local.aliases

  viewer_certificate {
    acm_certificate_arn            = var.use_custom_domain ? aws_acm_certificate.site[0].arn : null
    cloudfront_default_certificate = var.use_custom_domain ? false : true
    ssl_support_method             = var.use_custom_domain ? "sni-only" : null
    minimum_protocol_version       = "TLSv1.2_2021"
  }

  origin {
    domain_name = aws_s3_bucket_website_configuration.frontend.website_endpoint
    origin_id   = "S3-${aws_s3_bucket.frontend.id}"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  tags                = local.common_tags

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.frontend.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }
}

# Optional: Custom domain configuration (only created when use_custom_domain = true)
data "aws_route53_zone" "root" {
  count        = var.use_custom_domain ? 1 : 0
  name         = var.root_domain
  private_zone = false
}

resource "aws_acm_certificate" "site" {
  count                     = var.use_custom_domain ? 1 : 0
  provider                  = aws.us_east_1
  domain_name               = var.root_domain
  subject_alternative_names = ["www.${var.root_domain}"]
  validation_method         = "DNS"
  lifecycle { create_before_destroy = true }
  tags = local.common_tags
}

resource "aws_route53_record" "site_validation" {
  for_each = var.use_custom_domain ? {
    for dvo in aws_acm_certificate.site[0].domain_validation_options :
    dvo.domain_name => dvo
  } : {}

  zone_id = data.aws_route53_zone.root[0].zone_id
  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  ttl     = 300
  records = [each.value.resource_record_value]
}

resource "aws_acm_certificate_validation" "site" {
  count           = var.use_custom_domain ? 1 : 0
  provider        = aws.us_east_1
  certificate_arn = aws_acm_certificate.site[0].arn
  validation_record_fqdns = [
    for r in aws_route53_record.site_validation : r.fqdn
  ]
}

resource "aws_route53_record" "alias_root" {
  count   = var.use_custom_domain ? 1 : 0
  zone_id = data.aws_route53_zone.root[0].zone_id
  name    = var.root_domain
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "alias_root_ipv6" {
  count   = var.use_custom_domain ? 1 : 0
  zone_id = data.aws_route53_zone.root[0].zone_id
  name    = var.root_domain
  type    = "AAAA"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "alias_www" {
  count   = var.use_custom_domain ? 1 : 0
  zone_id = data.aws_route53_zone.root[0].zone_id
  name    = "www.${var.root_domain}"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "alias_www_ipv6" {
  count   = var.use_custom_domain ? 1 : 0
  zone_id = data.aws_route53_zone.root[0].zone_id
  name    = "www.${var.root_domain}"
  type    = "AAAA"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}
```

### Walkthrough of `main.tf`

This section explains the major blocks in the file above, grouped by function.

#### Data Sources and Locals

```hcl
data "aws_caller_identity" "current" {}
```

This is a *data source*, not a resource. It does not create anything; it queries AWS to retrieve your account ID. The account ID is then appended to S3 bucket names to ensure global uniqueness (S3 bucket names must be unique across all of AWS, not just your account).

The `locals` block defines computed values that are reused throughout the file:

- **`name_prefix`** combines the project name and environment (e.g. `twin-dev`) and is prepended to every resource name.
- **`common_tags`** ensures that every resource is consistently tagged with the project, environment, and the fact that it is managed by Terraform. Tags are invaluable for cost tracking and for identifying what created a resource.
- **`aliases`** is set to an empty list unless custom-domain mode is enabled, in which case it contains the root domain and the `www.` subdomain.

#### S3 Buckets

Two S3 buckets are created:

- **`memory`**: A private bucket that stores conversation history as JSON files. All public access is blocked.
- **`frontend`**: A public bucket configured for static website hosting. Its bucket policy allows anyone to read objects (necessary for serving a website). The `depends_on` ensures the public-access settings are applied before the policy, avoiding a race condition.

#### IAM Role and Policies

The Lambda function needs an IAM role that grants it permission to execute and to access other AWS services. Three managed policies are attached:

- **`AWSLambdaBasicExecutionRole`**: Allows the function to write logs to CloudWatch.
- **`AmazonBedrockFullAccess`**: Allows the function to call Bedrock models.
- **`AmazonS3FullAccess`**: Allows the function to read and write S3 objects (for conversation memory).

In a production environment you would want to apply the *principle of least privilege* — crafting a custom policy that grants only the specific S3 and Bedrock permissions needed, rather than granting full access. The managed policies are used here for simplicity.

#### Lambda Function

The `aws_lambda_function` resource is one of the most important blocks. Key fields:

- **`filename`**: Points to the deployment ZIP file built by the deploy script. The `${path.module}/..` syntax navigates up from the `terraform/` directory to the project root.
- **`source_code_hash`**: A SHA-256 hash of the ZIP file. Terraform uses this to detect whether the code has changed since the last deployment. If the hash is the same, Terraform skips re-uploading the function, saving time.
- **`environment.variables`**: Sets the runtime environment variables that the Lambda code reads. The `CORS_ORIGINS` value is set conditionally: if a custom domain is in use, it is the domain URL; otherwise, it is the auto-generated CloudFront URL.
- **`depends_on`**: Tells Terraform to create the CloudFront distribution before the Lambda function. This is because the Lambda's `CORS_ORIGINS` variable references the CloudFront domain name. Terraform can often infer such dependencies automatically from resource references, but the explicit `depends_on` makes the relationship unambiguous.

#### API Gateway

The API Gateway configuration creates an HTTP API (not a REST API — HTTP APIs are simpler and cheaper) with three routes:

- `GET /` — Returns a status or welcome message.
- `POST /chat` — Handles chat requests from the frontend.
- `GET /health` — A health-check endpoint.

All three routes point to the same Lambda function via an `AWS_PROXY` integration, meaning the entire HTTP request is forwarded to Lambda and Lambda's response is returned directly to the client. The `aws_lambda_permission` block grants the API Gateway service permission to invoke the Lambda function.

#### CloudFront Distribution

CloudFront is the content delivery network that sits in front of your S3-hosted frontend. It caches your static files at edge locations around the world for low-latency delivery and provides HTTPS. Key configuration choices:

- **`origin_protocol_policy = "http-only"`**: CloudFront talks to the S3 website endpoint over plain HTTP (S3 website endpoints do not support HTTPS). The HTTPS layer is provided by CloudFront itself.
- **`viewer_protocol_policy = "redirect-to-https"`**: If a user visits via HTTP, they are automatically redirected to HTTPS.
- **`custom_error_response`**: Rewrites 404 errors to serve `index.html`, which is necessary for single-page applications that handle routing on the client side.

#### Optional Custom Domain Resources

The final section of the file is wrapped in `count = var.use_custom_domain ? 1 : 0` conditions. When `use_custom_domain` is `false`, these resources are not created at all. When it is `true`, they:

1. Look up the Route 53 hosted zone for your domain.
2. Request an SSL certificate from AWS Certificate Manager (ACM) in `us-east-1`.
3. Create DNS validation records so ACM can verify that you own the domain.
4. Wait for the certificate to be validated.
5. Create `A` and `AAAA` alias records pointing the root domain and `www.` subdomain to the CloudFront distribution.

### Step 4: Outputs (`outputs.tf`)

Create the file `terraform/outputs.tf`:

```hcl
output "api_gateway_url" {
  description = "URL of the API Gateway"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "cloudfront_url" {
  description = "URL of the CloudFront distribution"
  value       = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "s3_frontend_bucket" {
  description = "Name of the S3 bucket for frontend"
  value       = aws_s3_bucket.frontend.id
}

output "s3_memory_bucket" {
  description = "Name of the S3 bucket for memory storage"
  value       = aws_s3_bucket.memory.id
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.api.function_name
}

output "custom_domain_url" {
  description = "Root URL of the production site"
  value       = var.use_custom_domain ? "https://${var.root_domain}" : ""
}
```

**What this file does:** After `terraform apply` completes, these values are printed to the terminal and can also be queried programmatically with `terraform output -raw <name>`. The deploy script uses this mechanism to retrieve the API Gateway URL and frontend bucket name so that it can build and upload the frontend. Without outputs, you would have to dig through the Terraform state file or the AWS Console to find these values.

### Step 5: Default Variable Values (`terraform.tfvars`)

Create the file `terraform/terraform.tfvars`:

```hcl
project_name             = "twin"
environment              = "dev"
bedrock_model_id         = "amazon.nova-micro-v1:0"
lambda_timeout           = 60
api_throttle_burst_limit = 10
api_throttle_rate_limit  = 5
use_custom_domain        = false
root_domain              = ""
```

**What this file does:** When Terraform runs, it automatically loads any file named `terraform.tfvars` in the current directory and uses its values to populate the corresponding variables. This file provides sensible defaults for development: the cheapest Bedrock model, moderate throttling limits, and no custom domain. For production, you will create a separate `prod.tfvars` that overrides these values.

### Step 6: Update the Frontend to Use an Environment Variable

Before you create the deployment scripts, you need to address a subtle but important problem.

**The problem:** In earlier sessions, you hard-coded the API Gateway URL directly into your frontend source code (`twin.tsx`). This worked for a single manual deployment, but it breaks the moment you want multiple environments — each environment has a different API Gateway URL, and you cannot hard-code all of them.

**The solution:** Replace the hard-coded URL with a Next.js environment variable that is injected at build time.

In `frontend/components/twin.tsx`, find the `fetch` call (around line 43):

```typescript
// Find this line:
const response = await fetch('http://localhost:8000/chat', {

// Replace with:
const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat`, {
```

**How this works:**

- `process.env.NEXT_PUBLIC_API_URL` reads an environment variable at build time. The `NEXT_PUBLIC_` prefix is a Next.js convention: only variables with this prefix are embedded into the client-side JavaScript bundle and thus available in the browser. Variables without the prefix remain server-side only.
- The `|| 'http://localhost:8000'` part is a fallback: if the environment variable is not set (as when you are developing locally), the frontend defaults to your local development server.
- The deploy script will create a file called `.env.production` containing `NEXT_PUBLIC_API_URL=<gateway-url>` just before running `npm run build`, so the correct URL is baked into the static files for each environment.

This is an important pattern: **Terraform manages the infrastructure, but anything that requires modifying your application code or build process is handled by the deploy script.** Terraform cannot edit your source code — it can only create and configure cloud resources.

---

## Part 4: Create Deployment Scripts

### Why Deployment Scripts?

Terraform handles the provisioning of cloud resources, but a complete deployment involves more than just Terraform:

1. **Packaging the Lambda function** (running `uv run deploy.py` to create the ZIP file).
2. **Running Terraform** (initialising, selecting the workspace, applying the configuration).
3. **Extracting outputs** (retrieving the API Gateway URL and frontend bucket name from Terraform).
4. **Building the frontend** (injecting the API URL and running `npm run build`).
5. **Uploading the frontend** (syncing the built static files to S3).

The deploy script orchestrates all five steps in sequence. You run it with a single command and it handles everything.

### Directory Structure

Create a new top-level folder called `scripts`:

```
twin/
├── backend/
├── frontend/
├── memory/
├── scripts/     ← new
└── terraform/
```

### Step 1: Deploy Script for Mac/Linux (`scripts/deploy.sh`)

**Important:** All students — including Windows users — should create this file. It will be used by GitHub Actions in tomorrow's session (Day 5), which runs on Linux.

Create `scripts/deploy.sh`:

```bash
#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}          # dev | test | prod
PROJECT_NAME=${2:-twin}

echo "🚀 Deploying ${PROJECT_NAME} to ${ENVIRONMENT}..."

# 1. Build Lambda package
cd "$(dirname "$0")/.."        # project root
echo "📦 Building Lambda package..."
(cd backend && uv run deploy.py)

# 2. Terraform workspace & apply
cd terraform
terraform init -input=false

if ! terraform workspace list | grep -q "$ENVIRONMENT"; then
  terraform workspace new "$ENVIRONMENT"
else
  terraform workspace select "$ENVIRONMENT"
fi

# Use prod.tfvars for production environment
if [ "$ENVIRONMENT" = "prod" ]; then
  TF_APPLY_CMD=(terraform apply -var-file=prod.tfvars -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve)
else
  TF_APPLY_CMD=(terraform apply -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve)
fi

echo "🎯 Applying Terraform..."
"${TF_APPLY_CMD[@]}"

API_URL=$(terraform output -raw api_gateway_url)
FRONTEND_BUCKET=$(terraform output -raw s3_frontend_bucket)
CUSTOM_URL=$(terraform output -raw custom_domain_url 2>/dev/null || true)

# 3. Build + deploy frontend
cd ../frontend

# Create production environment file with API URL
echo "📝 Setting API URL for production..."
echo "NEXT_PUBLIC_API_URL=$API_URL" > .env.production

npm install
npm run build
aws s3 sync ./out "s3://$FRONTEND_BUCKET/" --delete
cd ..

# 4. Final messages
echo -e "\n✅ Deployment complete!"
echo "🌐 CloudFront URL : $(terraform -chdir=terraform output -raw cloudfront_url)"
if [ -n "$CUSTOM_URL" ]; then
  echo "🔗 Custom domain  : $CUSTOM_URL"
fi
echo "📡 API Gateway    : $API_URL"
```

**Make it executable (Mac/Linux only):**

```bash
chmod +x scripts/deploy.sh
```

> **What `chmod +x` does:** On Unix-like systems, files are not executable by default. The `chmod +x` command adds the "execute" permission, allowing you to run the script with `./scripts/deploy.sh` rather than having to invoke it through `bash scripts/deploy.sh`.

**Walkthrough of the script:**

1. **`set -e`** — Tells Bash to exit immediately if any command fails. Without this, the script would continue running even after an error, potentially making a bad situation worse.
2. **`ENVIRONMENT=${1:-dev}`** — Takes the first command-line argument as the environment name, defaulting to `dev` if none is provided.
3. **Lambda packaging** — Changes to the `backend/` directory and runs `uv run deploy.py`, which installs Python dependencies and creates `lambda-deployment.zip`.
4. **Terraform init** — Initialises the Terraform working directory and downloads provider plugins. The `-input=false` flag prevents Terraform from prompting for interactive input, which is important for automation.
5. **Workspace selection** — Checks whether a workspace with the given name exists. If not, it creates one; otherwise, it selects it. Each workspace maintains an independent state file.
6. **Terraform apply** — Creates or updates all resources. For the `prod` environment, it loads `prod.tfvars` (which overrides settings like the Bedrock model and throttle limits). The `-auto-approve` flag skips the interactive confirmation prompt.
7. **Output extraction** — Retrieves the API Gateway URL and S3 bucket name using `terraform output -raw`.
8. **Frontend build** — Writes the API URL into `.env.production`, runs `npm install` and `npm run build` to generate the static site, then uses `aws s3 sync` to upload it to the frontend bucket. The `--delete` flag removes files from S3 that no longer exist in the local build, keeping the bucket in sync.

### Step 2: Deploy Script for Windows (`scripts/deploy.ps1`)

**Mac/Linux users may skip this file** — it is only needed if you are deploying from a Windows PowerShell prompt.

Create `scripts/deploy.ps1`:

```powershell
param(
    [string]$Environment = "dev",   # dev | test | prod
    [string]$ProjectName = "twin"
)
$ErrorActionPreference = "Stop"

Write-Host "Deploying $ProjectName to $Environment ..." -ForegroundColor Green

# 1. Build Lambda package
Set-Location (Split-Path $PSScriptRoot -Parent)   # project root
Write-Host "Building Lambda package..." -ForegroundColor Yellow
Set-Location backend
uv run deploy.py
Set-Location ..

# 2. Terraform workspace & apply
Set-Location terraform
terraform init -input=false

if (-not (terraform workspace list | Select-String $Environment)) {
    terraform workspace new $Environment
} else {
    terraform workspace select $Environment
}

if ($Environment -eq "prod") {
    terraform apply -var-file="prod.tfvars" -var="project_name=$ProjectName" -var="environment=$Environment" -auto-approve
} else {
    terraform apply -var="project_name=$ProjectName" -var="environment=$Environment" -auto-approve
}

$ApiUrl        = terraform output -raw api_gateway_url
$FrontendBucket = terraform output -raw s3_frontend_bucket
try { $CustomUrl = terraform output -raw custom_domain_url } catch { $CustomUrl = "" }

# 3. Build + deploy frontend
Set-Location ..\frontend

# Create production environment file with API URL
Write-Host "Setting API URL for production..." -ForegroundColor Yellow
"NEXT_PUBLIC_API_URL=$ApiUrl" | Out-File .env.production -Encoding utf8

npm install
npm run build
aws s3 sync .\out "s3://$FrontendBucket/" --delete
Set-Location ..

# 4. Final summary
$CfUrl = terraform -chdir=terraform output -raw cloudfront_url
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "CloudFront URL : $CfUrl" -ForegroundColor Cyan
if ($CustomUrl) {
    Write-Host "Custom domain  : $CustomUrl" -ForegroundColor Cyan
}
Write-Host "API Gateway    : $ApiUrl" -ForegroundColor Cyan
```

The PowerShell script performs exactly the same operations as the Bash script, adapted for Windows conventions (`Set-Location` instead of `cd`, `$ErrorActionPreference = "Stop"` instead of `set -e`, and so on).

---

## Part 5: Deploy the Development Environment

### Step 1: Initialise Terraform

Before running the deploy script for the first time, verify that Terraform can initialise successfully:

```bash
cd terraform
terraform init
```

You should see output confirming that the backend has been initialised and the AWS provider plugin has been downloaded:

```
Initializing the backend...
Initializing provider plugins...
- Installing hashicorp/aws v6.x.x...
Terraform has been successfully initialized!
```

If this fails, check that Terraform is installed correctly (`terraform --version`) and that your AWS credentials are configured (`aws sts get-caller-identity`).

Return to the project root before running the deploy script:

```bash
cd ..
```

### Step 2: Run the Deploy Script

**Mac/Linux:**

```bash
./scripts/deploy.sh dev
```

**Windows (PowerShell):**

```powershell
.\scripts\deploy.ps1 -Environment dev
```

The script will progress through each stage, printing status messages as it goes. When it reaches the CloudFront distribution, you will see Terraform report `Still creating...` approximately every ten seconds. This is normal — CloudFront distributions take **5–10 minutes** to propagate to edge locations worldwide. Be patient and let it complete.

**What is happening behind the scenes:**

1. The Lambda deployment ZIP is built from your `backend/` directory.
2. Terraform creates a `dev` workspace (an isolated state container).
3. Terraform provisions all resources: S3 buckets, IAM role, Lambda function, API Gateway, and CloudFront distribution — in the correct dependency order.
4. The script extracts the API Gateway URL and writes it into `.env.production`.
5. The frontend is built with the production API URL baked in, then uploaded to the S3 frontend bucket.

When complete, you will see output similar to:

```
✅ Deployment complete!
🌐 CloudFront URL : https://d1234abcdef.cloudfront.net
📡 API Gateway    : https://abc123.execute-api.us-east-1.amazonaws.com
```

### Step 3: Test Your Development Environment

1. Open the CloudFront URL in your browser.
2. You should see your Digital Twin interface.
3. Send a test message and verify that you receive a response.
4. Send a follow-up message referencing your first message to verify that conversation memory (S3 storage) is working.

**Optional verification in the AWS Console:** Sign in as your IAM user and inspect the resources that Terraform created:

- **Lambda:** You should see a function called `twin-dev-api`. Click into it to verify the environment variables are set correctly (CORS origins, S3 bucket name, Bedrock model ID).
- **S3:** You should see `twin-dev-frontend-<account-id>` and `twin-dev-memory-<account-id>`. The memory bucket should contain a JSON file corresponding to your test conversation.
- **API Gateway:** You should see `twin-dev-api-gateway`.
- **CloudFront:** You should see one distribution pointing to your frontend bucket.

---

## Part 6: Deploy the Test Environment

One of the most powerful features of the Terraform workspace model is the ability to deploy multiple identical but isolated environments from the same configuration. You will now demonstrate this by creating a second environment.

### Step 1: Run the Deploy Script with `test`

**Mac/Linux:**

```bash
./scripts/deploy.sh test
```

**Windows (PowerShell):**

```powershell
.\scripts\deploy.ps1 -Environment test
```

The script goes through exactly the same process as before, but this time it creates (or selects) the `test` workspace. Because the workspace is different, all resources receive `test` in their names instead of `dev`, and Terraform maintains a completely separate state file.

Again, expect a 5–10 minute wait for the CloudFront distribution.

### Step 2: Verify Separate Resources

After the deployment completes, check the AWS Console. You should now see *two* of everything:

| Resource | Dev | Test |
|----------|-----|------|
| Lambda function | `twin-dev-api` | `twin-test-api` |
| Memory bucket | `twin-dev-memory-…` | `twin-test-memory-…` |
| Frontend bucket | `twin-dev-frontend-…` | `twin-test-frontend-…` |
| API Gateway | `twin-dev-api-gateway` | `twin-test-api-gateway` |
| CloudFront distribution | (one URL) | (a different URL) |

### Step 3: Confirm Environment Isolation

1. Open the dev CloudFront URL in one browser tab.
2. Open the test CloudFront URL in another tab.
3. Have different conversations in each tab.

The conversations are completely independent — different Lambda functions, different S3 memory buckets, different everything. This is the core value proposition of Infrastructure as Code with workspaces: identical architecture, isolated state, deployed and destroyed on demand.

> **A note on IAM isolation:** In a fully professional setup, you would also use separate IAM users or roles for each environment, so that the development environment could not accidentally access production data. This is left as an exercise; for now, all environments share the same IAM user.

---

## Part 7: Destroying Infrastructure

When you are finished with an environment — for example, after testing is complete, or to save on AWS charges — you need to tear it down cleanly. Because S3 buckets must be empty before Terraform can delete them, the destroy scripts handle the emptying step automatically.

### Step 1: Create the Destroy Script for Mac/Linux (`scripts/destroy.sh`)

Create `scripts/destroy.sh`:

```bash
#!/bin/bash
set -e

# Check if environment parameter is provided
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

# Navigate to terraform directory
cd "$(dirname "$0")/../terraform"

# Check if workspace exists
if ! terraform workspace list | grep -q "$ENVIRONMENT"; then
    echo "❌ Error: Workspace '$ENVIRONMENT' does not exist"
    echo "Available workspaces:"
    terraform workspace list
    exit 1
fi

# Select the workspace
terraform workspace select "$ENVIRONMENT"

echo "📦 Emptying S3 buckets..."

# Get AWS Account ID for bucket names
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Get bucket names with account ID
FRONTEND_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-frontend-${AWS_ACCOUNT_ID}"
MEMORY_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-memory-${AWS_ACCOUNT_ID}"

# Empty frontend bucket if it exists
if aws s3 ls "s3://$FRONTEND_BUCKET" 2>/dev/null; then
    echo "  Emptying $FRONTEND_BUCKET..."
    aws s3 rm "s3://$FRONTEND_BUCKET" --recursive
else
    echo "  Frontend bucket not found or already empty"
fi

# Empty memory bucket if it exists
if aws s3 ls "s3://$MEMORY_BUCKET" 2>/dev/null; then
    echo "  Emptying $MEMORY_BUCKET..."
    aws s3 rm "s3://$MEMORY_BUCKET" --recursive
else
    echo "  Memory bucket not found or already empty"
fi

echo "🔥 Running terraform destroy..."

# Run terraform destroy with auto-approve
if [ "$ENVIRONMENT" = "prod" ] && [ -f "prod.tfvars" ]; then
    terraform destroy -var-file=prod.tfvars -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve
else
    terraform destroy -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve
fi

echo "✅ Infrastructure for ${ENVIRONMENT} has been destroyed!"
echo ""
echo "💡 To remove the workspace completely, run:"
echo "   terraform workspace select default"
echo "   terraform workspace delete $ENVIRONMENT"
```

Make it executable:

```bash
chmod +x scripts/destroy.sh
```

### Step 2: Create the Destroy Script for Windows (`scripts/destroy.ps1`)

Create `scripts/destroy.ps1`:

```powershell
param(
    [Parameter(Mandatory=$true)]
    [string]$Environment,
    [string]$ProjectName = "twin"
)

# Validate environment parameter
if ($Environment -notmatch '^(dev|test|prod)$') {
    Write-Host "Error: Invalid environment '$Environment'" -ForegroundColor Red
    Write-Host "Available environments: dev, test, prod" -ForegroundColor Yellow
    exit 1
}

Write-Host "Preparing to destroy $ProjectName-$Environment infrastructure..." -ForegroundColor Yellow

# Navigate to terraform directory
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) "terraform")

# Check if workspace exists
$workspaces = terraform workspace list
if (-not ($workspaces | Select-String $Environment)) {
    Write-Host "Error: Workspace '$Environment' does not exist" -ForegroundColor Red
    Write-Host "Available workspaces:" -ForegroundColor Yellow
    terraform workspace list
    exit 1
}

# Select the workspace
terraform workspace select $Environment

Write-Host "Emptying S3 buckets..." -ForegroundColor Yellow

# Get AWS Account ID for bucket names
$awsAccountId = aws sts get-caller-identity --query Account --output text

# Define bucket names with account ID
$FrontendBucket = "$ProjectName-$Environment-frontend-$awsAccountId"
$MemoryBucket = "$ProjectName-$Environment-memory-$awsAccountId"

# Empty frontend bucket if it exists
try {
    aws s3 ls "s3://$FrontendBucket" 2>$null | Out-Null
    Write-Host "  Emptying $FrontendBucket..." -ForegroundColor Gray
    aws s3 rm "s3://$FrontendBucket" --recursive
} catch {
    Write-Host "  Frontend bucket not found or already empty" -ForegroundColor Gray
}

# Empty memory bucket if it exists
try {
    aws s3 ls "s3://$MemoryBucket" 2>$null | Out-Null
    Write-Host "  Emptying $MemoryBucket..." -ForegroundColor Gray
    aws s3 rm "s3://$MemoryBucket" --recursive
} catch {
    Write-Host "  Memory bucket not found or already empty" -ForegroundColor Gray
}

Write-Host "Running terraform destroy..." -ForegroundColor Yellow

# Run terraform destroy with auto-approve
if ($Environment -eq "prod" -and (Test-Path "prod.tfvars")) {
    terraform destroy -var-file="prod.tfvars" -var="project_name=$ProjectName" -var="environment=$Environment" -auto-approve
} else {
    terraform destroy -var="project_name=$ProjectName" -var="environment=$Environment" -auto-approve
}

Write-Host "Infrastructure for $Environment has been destroyed!" -ForegroundColor Green
Write-Host ""
Write-Host "  To remove the workspace completely, run:" -ForegroundColor Cyan
Write-Host "   terraform workspace select default" -ForegroundColor White
Write-Host "   terraform workspace delete $Environment" -ForegroundColor White
```

### Step 3: Using the Destroy Scripts

**Mac/Linux:**

```bash
./scripts/destroy.sh dev      # Destroy the development environment
./scripts/destroy.sh test     # Destroy the test environment
./scripts/destroy.sh prod     # Destroy the production environment
```

**Windows (PowerShell):**

```powershell
.\scripts\destroy.ps1 -Environment dev
.\scripts\destroy.ps1 -Environment test
.\scripts\destroy.ps1 -Environment prod
```

Each script invocation empties S3 buckets, then calls `terraform destroy` to remove all resources in the specified workspace. Expect the CloudFront distribution deletion to take 5–15 minutes, just as creation did.

### What Gets Destroyed — and What Does Not

The destroy scripts remove all AWS resources managed by Terraform in the target workspace: Lambda functions, API Gateway, S3 buckets, CloudFront distributions, IAM roles, and (if applicable) Route 53 records and ACM certificates.

The destroy scripts **do not** remove:

- **The Terraform workspace itself.** To delete a workspace after its resources have been destroyed, run `terraform workspace select default` followed by `terraform workspace delete <name>`.
- **Your registered domain.** If you registered a domain through Route 53, that registration (and the annual fee) persists independently of Terraform.
- **IAM users.** The IAM user you set up manually in an earlier session is not managed by Terraform.

### Cost Management

Always destroy unused environments when you are not actively working with them. The primary cost drivers are CloudFront distributions and Lambda invocations, but even idle resources can accumulate small charges over time. Get into the habit of running your destroy scripts at the end of each working session.

---

## Part 8: Optional — Custom Domain for Production

This section is entirely optional. It walks you through registering a domain, configuring production-specific variable overrides, and deploying a production environment with a professional URL and SSL certificate.

### Step 1: Register a Domain

Domain registration requires billing permissions, so you must sign in as the **root user** (not your IAM user) for this step.

**Option A — Register through AWS Route 53:**

1. Sign in to the AWS Console as your root user.
2. Navigate to **Route 53**.
3. Click **Registered domains → Register domain**.
4. Search for your desired domain name and check availability.
5. Add it to your cart and complete the purchase (typically $12–40 per year depending on the extension).
6. AWS will require you to verify your email address.
7. Wait for the registration to complete (5–30 minutes).
8. Once registered, sign back in as your IAM user to continue.

Route 53 will automatically create a **hosted zone** for your new domain, which is where DNS records are managed.

**Option B — Use an existing domain:**

If you already own a domain registered elsewhere, you can either transfer it to Route 53 or create a hosted zone manually and update the nameservers at your current registrar to point to Route 53. The Terraform configuration expects a Route 53 hosted zone to exist for the domain.

### Step 2: Create Production Configuration (`terraform/prod.tfvars`)

Create the file `terraform/prod.tfvars`:

```hcl
project_name             = "twin"
environment              = "prod"
bedrock_model_id         = "amazon.nova-lite-v1:0"
lambda_timeout           = 60
api_throttle_burst_limit = 20
api_throttle_rate_limit  = 10
use_custom_domain        = true
root_domain              = "yourdomain.com"    # ← Replace with your actual domain
```

**Key differences from the default `terraform.tfvars`:**

- **`bedrock_model_id`**: Upgraded from `nova-micro` to `nova-lite`, which produces higher-quality responses. You could also use `amazon.nova-pro-v1:0` for even better quality at a slightly higher cost — it remains very affordable.
- **`api_throttle_burst_limit` and `rate_limit`**: Increased to handle more concurrent users in a production setting.
- **`use_custom_domain = true`**: Activates all of the conditional Route 53 and ACM resources in `main.tf`.
- **`root_domain`**: Your registered domain name.

### Step 3: Deploy Production

**Mac/Linux:**

```bash
./scripts/deploy.sh prod
```

**Windows (PowerShell):**

```powershell
.\scripts\deploy.ps1 -Environment prod
```

In addition to the usual resources, Terraform will now:

1. Request an SSL certificate from ACM for your domain and its `www.` subdomain.
2. Create DNS validation records in Route 53 to prove domain ownership.
3. Wait for the certificate to be validated (this can take 5–30 minutes).
4. Attach the certificate to the CloudFront distribution.
5. Create `A` and `AAAA` alias records pointing your domain to CloudFront.

### Step 4: Test Your Custom Domain

Once the deployment completes:

1. Visit `https://yourdomain.com` in your browser.
2. Also visit `https://www.yourdomain.com` — both should work.
3. Verify that the connection is secure (look for the padlock icon in your browser's address bar).
4. Test the chat functionality to confirm everything is operational.

You now have three fully independent environments: development (on an auto-generated CloudFront URL), test (on a different auto-generated URL), and production (on your custom domain with SSL).

---

## Best Practices Summary

### Version Control

Commit your Terraform configuration files to Git:

```bash
git add terraform/*.tf terraform/*.tfvars scripts/
git commit -m "Add Terraform infrastructure and deployment scripts"
```

Never commit `terraform.tfstate` files, the `.terraform/` directory, or AWS credentials.

### Plan Before You Apply

Before applying changes to a production environment, preview them:

```bash
terraform plan -var="project_name=twin" -var="environment=prod" -var-file=prod.tfvars
```

This shows exactly what Terraform will create, modify, or destroy, giving you the opportunity to review before committing.

### Use Variables, Not Hard-Coded Values

Every value that might differ between environments — model IDs, throttle limits, bucket names — should be expressed as a variable. This makes your configuration reusable and reduces the risk of errors when deploying to different environments.

### Tag Everything

The `common_tags` local in `main.tf` ensures that every resource is tagged with the project name, environment, and the fact that it is managed by Terraform. Tags are invaluable for cost tracking, resource discovery, and for answering the question "what created this resource and why?".

---

## Troubleshooting

### Terraform State Conflicts

If Terraform becomes confused about the state of your resources (for example, if a resource was deleted manually outside of Terraform):

```bash
# Refresh the state from AWS to detect any drift
terraform refresh

# If a resource exists in AWS but not in the state, import it
terraform import aws_lambda_function.api twin-dev-api
```

### Common Deployment Errors

**"Lambda package not found":** The deploy script could not find `lambda-deployment.zip` in the `backend/` directory. Ensure you can run `cd backend && uv run deploy.py` manually without errors.

**"S3 bucket already exists":** S3 bucket names are globally unique. If another AWS account has already taken the name, change your `project_name` in `terraform.tfvars` to something different.

**"Certificate validation timeout":** ACM certificate validation depends on DNS propagation. Check that the validation records have been created in your Route 53 hosted zone, and allow up to 30 minutes for propagation.

### Frontend Not Updating After Deployment

CloudFront caches content at edge locations. After deploying new frontend files, you may need to invalidate the cache:

```bash
# Find your distribution ID
aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(Origins.Items[0].DomainName, 'twin-dev')].Id" \
  --output text

# Create an invalidation
aws cloudfront create-invalidation --distribution-id YOUR_DISTRIBUTION_ID --paths "/*"
```

---

## What You Have Accomplished

By completing this session, you have:

- Understood the principles of Infrastructure as Code and why it is superior to manual provisioning.
- Learned the six core Terraform concepts: provider, variable, resource, state, output, and workspace.
- Written a complete Terraform configuration that describes your Digital Twin's entire AWS architecture.
- Created deployment scripts that orchestrate the full build-and-deploy pipeline in a single command.
- Deployed isolated development and test environments and verified their independence.
- Destroyed environments cleanly with automated teardown scripts.
- Optionally: configured a production environment with a custom domain and SSL certificate.

Tomorrow (Day 5) you will add CI/CD with GitHub Actions, which will allow you to trigger this entire pipeline automatically with a `git push` — the final piece of a professional deployment workflow.
