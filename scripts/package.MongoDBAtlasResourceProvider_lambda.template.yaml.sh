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
TARGET="${ROOT}/templates/mongodb-atlas-resource-provider.template.yaml"
echo "TARGET=${TARGET}"
LAMBDA_SRC="${2:-${ROOT}/functions/source/MongoDBAtlasResourceProvider/lambda_function.py}"
echo "LAMBDA_SRC=${LAMBDA_SRC}"
LAMBDA_STACK_TEMPLATE="${3:-${ROOT}/templates/common/MongoDBAtlasResourceProvider_lambda.template.yaml}"
echo "LAMBDA_STACK_TEMPLATE=${LAMBDA_STACK_TEMPLATE}"
CHAR_COUNT=$(wc -c "${LAMBDA_SRC}" | cut -d' ' -f1)
echo "Can we fit captain?  '${LAMBDA_SRC}' character count: ${CHAR_COUNT}, max 4096!"
if (( "$CHAR_COUNT" >= "4096" ))
then
  echo "WARNING - Won't fit!"
  #exit 1
else
  echo "Smooth sailing sir!"
fi

# Freshen our python libs
rm -rf functions/source/MongoDBAtlasResourceProvider/package
mkdir functions/source/MongoDBAtlasResourceProvider/package
python3 -m pip install \
 --target functions/source/MongoDBAtlasResourceProvider/package \
 -r functions/source/MongoDBAtlasResourceProvider/requirements.txt

pylint functions/source/MongoDBAtlasResourceProvider/*.py

# Zip up the lambda source
LAMBDA_ZIP="$(pwd)/functions/packages/MongoDBAtlasResourceProvider.zip"
rm "${LAMBDA_ZIP}"
ls -lR functions/packages
cd functions/source/MongoDBAtlasResourceProvider/package
zip -r9 "${LAMBDA_ZIP}" .
cd -;

cd functions/source/MongoDBAtlasResourceProvider
# explicitly adding what we need to make cloudformation register-type work
zip -g "${LAMBDA_ZIP}" lambda_function.py schema.json template.yml .rpdk-config requirements.txt
cd -;

ls -lR functions/packages
aws s3api put-object \
    --bucket simple-quickstart-mongodb-atlas \
    --key lambdas/MongoDBAtlasResourceProvider.zip \
    --body "${LAMBDA_ZIP}"



# Future.
# When the lambda source crosses the 4096 barrier, enhance this packaging
# script to zip up the lambda, ship it off to well known s3 bucket, and
# then update the $TARGET templates/mongodb-atlas-resource-provider.template.yaml
# to instead point to the s3 bucket.
