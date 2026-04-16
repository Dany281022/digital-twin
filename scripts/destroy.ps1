param(
    [Parameter(Mandatory=$true)]
    [string]$Environment,
    [string]$ProjectName = "twin"
)

if ($Environment -notmatch "^(dev|test|prod)$") {
    Write-Host "Error: Invalid environment" -ForegroundColor Red
    exit 1
}

Write-Host "Preparing to destroy $ProjectName-$Environment..." -ForegroundColor Yellow

Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) "terraform")

$workspaces = terraform workspace list
if (-not ($workspaces | Select-String $Environment)) {
    Write-Host "Error: Workspace does not exist" -ForegroundColor Red
    exit 1
}

terraform workspace select $Environment

$awsAccountId = aws sts get-caller-identity --query Account --output text
$FrontendBucket = "$ProjectName-$Environment-frontend-$awsAccountId"
$MemoryBucket = "$ProjectName-$Environment-memory-$awsAccountId"

aws s3 rm "s3://$FrontendBucket" --recursive 2>$null
aws s3 rm "s3://$MemoryBucket" --recursive 2>$null

terraform destroy -var="project_name=$ProjectName" -var="environment=$Environment" -auto-approve

Write-Host "Infrastructure destroyed!" -ForegroundColor Green
