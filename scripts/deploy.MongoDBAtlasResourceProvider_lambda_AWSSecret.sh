#!/usr/bin/env bash

# Deploys a CloudFormation stack running the MongoDB Cloud Resource Manager
STACK_NAME="${1:-mongodb-atlas-resource-provider}"
echo "STACK_NAME=${STACK_NAME}"
REGION="${2:-$(aws configure get region)}"
echo "REGION=${REGION}"
SECRET_NAME="${3:-aws-quickstart-test-key}"
echo "SECRET_NAME=${SECRET_NAME}"

PUBLIC_KEY_REF="\"{{resolve:secretsmanager:${SECRET_NAME}:SecretString:PublicKey}}\""
echo "PUBLIC_KEY_REF=${PUBLIC_KEY_REF}"
PRIVATE_KEY_REF="\"{{resolve:secretsmanager:${SECRET_NAME}:SecretString:PrivateKey}}\""
echo "PRIVATE_KEY_REF=${PRIVATE_KEY_REF}"
ORG_ID_REF="\"{{resolve:secretsmanager:${SECRET_NAME}:SecretString:OrgId}}\""
echo "ORG_ID_REF=${ORG_ID_REF}"



TARGET="$(git rev-parse --show-toplevel)/templates/mongodb-atlas-resource-provider.template.yaml"
echo "TARGET=${TARGET}"
EXISTS=$(aws cloudformation describe-stacks --output json --region ${REGION} --stack-name ${STACK_NAME} 2>&1)
echo "EXISTS=${EXISTS}"
echo ""
if [[ -z "${EXISTS}" ]]
then
    echo "${STACK_NAME} not found"
else
    aws cloudformation delete-stack --output json --stack-name "${STACK_NAME}" --region "${REGION}"
    echo "deleted stack, nap time"
    sleep 10
    echo "up & adam"
fi



aws cloudformation create-stack \
  --region "${REGION}" --output json \
  --template-body "file://${TARGET}" \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=PublicKey,ParameterValue="${PUBLIC_KEY_REF}" \
               ParameterKey=PrivateKey,ParameterValue="${PRIVATE_KEY_REF}" \
               ParameterKey=OrgId,ParameterValue="${ORG_ID_REF}" \
  --stack-name "${STACK_NAME}"

