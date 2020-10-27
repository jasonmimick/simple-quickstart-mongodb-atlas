#!/usr/bin/env bash
STACK_NAME="${1:-aws-quickstart}"
aws cloudformation create-stack \
  --capabilities CAPABILITY_IAM --disable-rollback \
  --template-body file://templates/quickstart-mongodb-atlas.template.yaml \
  --stack-name "${STACK_NAME}"
