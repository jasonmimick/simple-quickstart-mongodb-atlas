#!/usr/bin/env bash

# Generate a CloudFormation template which deploys
# a lambda function runninf the MongoDB Cloud Resource Manager
#
# MEANT FOR INTERNAL USE ONLY!
# To install the MongoDB Cloud Resource Manager lambda function
# in your own AWS region, see the commands in the `deploy.*` script
# found in this folder.

ROOT="$(git rev-parse --show-toplevel)"
echo "ROOT:${ROOT}"
TARGET="${ROOT}/templates/mongodbatlas-resource-manager.template.yaml"
echo "TARGET=${TARGET}"
LAMBDA_SRC="${2:-${ROOT}/functions/source/MongoDBCloudResourceManager/lambda_function.py}"
echo "LAMBDA_SRC=${LAMBDA_SRC}"
LAMBDA_STACK_TEMPLATE="${3:-${ROOT}/templates/common/MongoDBCloudResourceManager_lambda.template.yaml}"
echo "LAMBDA_STACK_TEMPLATE=${LAMBDA_STACK_TEMPLATE}"
CHAR_COUNT=$(wc -c "${LAMBDA_SRC}" | cut -d' ' -f1)
echo "Can we fit captain?  '${LAMBDA_SRC}' character count: ${CHAR_COUNT}, max 4096!"
if (( "$CHAR_COUNT" >= "4096" ))
then
  echo "WARNING - Won't fit!"
  exit 1
else
  echo "Smooth sailing sir!"
fi

# yq command to insert the code into cfn stack template to deploy
# keeping it simple....
echo "Generating target--->${TARGET}"
yq w "${LAMBDA_STACK_TEMPLATE}" \
    'Resources.MongoDBAtlasDeployment.Properties.Code.ZipFile' -- "$(< ${LAMBDA_SRC})" \
    > "${TARGET}"

ls -lah $(dirname ${TARGET})

# Future.
# When the lambda source crosses the 4096 barrier, enhance this packaging
# script to zip up the lambda, ship it off to well known s3 bucket, and
# then update the $TARGET templates/mongodbatlas-resource-manager.template.yaml
# to instead point to the s3 bucket.
