$TAG = (git rev-parse --short HEAD).Trim()
docker build --provenance=false -t direhire/runtime:$TAG -f Dockerfile .
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin 685134815483.dkr.ecr.ap-southeast-1.amazonaws.com
docker tag direhire/runtime:$TAG 685134815483.dkr.ecr.ap-southeast-1.amazonaws.com/direhire/runtime:$TAG
docker push 685134815483.dkr.ecr.ap-southeast-1.amazonaws.com/direhire/runtime:$TAG
aws lambda update-function-code --function-name direhire-prod-api --image-uri 685134815483.dkr.ecr.ap-southeast-1.amazonaws.com/direhire/runtime:$TAG --region ap-southeast-1

