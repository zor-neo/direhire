docker build --provenance=false -t direhire/runtime -f Dockerfile .
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin 685134815483.dkr.ecr.ap-southeast-1.amazonaws.com
docker tag direhire/runtime 685134815483.dkr.ecr.ap-southeast-1.amazonaws.com/direhire/runtime:latest
docker push 685134815483.dkr.ecr.ap-southeast-1.amazonaws.com/direhire/runtime:latest
aws lambda update-function-code --function-name direhire-prod-api --image-uri 685134815483.dkr.ecr.ap-southeast-1.amazonaws.com/direhire/runtime:latest --region ap-southeast-1
