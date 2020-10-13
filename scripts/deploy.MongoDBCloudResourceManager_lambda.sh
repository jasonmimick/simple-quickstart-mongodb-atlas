#!/usr/bin/env bash

# Deploys a CloudFormation stack running the MongoDB Cloud Resource Manager
set -ex
STACK_NAME="${1:-mongodb-cloud-resource-manager}"
echo "STACK_NAME=${STACK_NAME}"
REGION="${2:-$(aws configure get region)}"
echo "REGION=${REGION}"
TARGET="$(git rev-parse --show-toplevel)/templates/mongodbatlas-resource-manager.template.yaml"
echo "TARGET=${TARGET}"
echo "input;;; $*"
echo "bounce - will delete ${STACK_NAME} and create"
aws cloudformation delete-stack --stack-name "${STACK_NAME}" \
    --region "${REGION}"
echo "deleted stack, nap time"
sleep 10
echo "up & adam"
aws cloudformation create-stack --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --template-body "file://${TARGET}" \
    --capabilities CAPABILITY_IAM

