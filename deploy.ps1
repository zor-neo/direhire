$ErrorActionPreference = "Stop"
$REGION = "ap-southeast-1"
$ACCOUNT_ID = "685134815483"
$ECR_REGISTRY = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
$REPO_NAME = "direhire/runtime"
$FRONTEND_BUCKET = "direhire-prod-$ACCOUNT_ID-frontend"
$CLOUDFRONT_DIST_ID = "E14N4HGYQK61ZM"

$TAG = (git rev-parse --short HEAD).Trim()
$IMAGE_URI = "${ECR_REGISTRY}/${REPO_NAME}:${TAG}"
Write-Host "=== Deploying DireHire Release $TAG to $REGION ===" -ForegroundColor Cyan

# 1. Build and Push Backend Docker Image
Write-Host "`n--- 1/4 Building and Pushing Docker Image ($TAG) ---" -ForegroundColor Yellow
docker build --provenance=false -t "direhire/runtime:$TAG" -f Dockerfile .
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
docker tag "direhire/runtime:$TAG" $IMAGE_URI
docker push $IMAGE_URI

# 2. Update All 8 Production Lambda Functions
Write-Host "`n--- 2/4 Updating All 8 Lambda Functions ---" -ForegroundColor Yellow
$LAMBDAS = @(
    "direhire-prod-api",
    "direhire-prod-source-discovery",
    "direhire-prod-ai-analysis",
    "direhire-prod-workflow-pump",
    "direhire-prod-interactive-ai",
    "direhire-prod-documents",
    "direhire-prod-notification",
    "direhire-prod-maintenance"
)

foreach ($fn in $LAMBDAS) {
    Write-Host "Updating Lambda function: $fn..."
    aws lambda update-function-code `
        --function-name $fn `
        --image-uri $IMAGE_URI `
        --region $REGION `
        --output text `
        --query "FunctionName"
}

# 3. Build Frontend
Write-Host "`n--- 3/4 Building Next.js Frontend ---" -ForegroundColor Yellow
Push-Location apps/web
try {
    npm run build
} finally {
    Pop-Location
}

# 4. Sync Frontend to S3 and Invalidate CloudFront
Write-Host "`n--- 4/4 Publishing Frontend to S3 & Invalidate CloudFront ---" -ForegroundColor Yellow
aws s3 sync apps/web/out/_next/static/ "s3://$FRONTEND_BUCKET/_next/static/" `
    --cache-control "public,max-age=31536000,immutable" `
    --region $REGION `
    --only-show-errors

aws s3 sync apps/web/out/ "s3://$FRONTEND_BUCKET/" `
    --exclude "_next/static/*" `
    --cache-control "no-cache,max-age=0,must-revalidate" `
    --region $REGION `
    --only-show-errors

$INVALIDATION_ID = aws cloudfront create-invalidation `
    --distribution-id $CLOUDFRONT_DIST_ID `
    --paths "/*" `
    --query "Invalidation.Id" `
    --output text

Write-Host "CloudFront Invalidation created: $INVALIDATION_ID" -ForegroundColor Green
Write-Host "`n=== Deployment $TAG successfully completed! ===" -ForegroundColor Green
