#!/usr/bin/env bash
STACK_NAME="${1:-aws-quickstart}"
VPC="${2}"
echo "VPC=${VPC}"
aws cloudformation create-stack \
  --capabilities CAPABILITY_IAM --disable-rollback \
  --template-body file://templates/quickstart-mongodb-atlas.template.yaml \
  --parameters ParameterKey=VPC,ParameterValue=${VPC} \
  --stack-name "${STACK_NAME}"
