#!/usr/bin/env bash

# register-type.MongoDBAtlasDeployment.sh
#
# This script will register the MongoDB::Atlas::Deployment
# CloudFormation Custom Resouce type into the AWS region of your choice.
REGION="${1:-$(aws configure get region)}"
echo "REGION=${REGION}"

RESOURCE_TYPE_NAME="${2:-MongoDB::Atlas::Deployment}"
echo "RESOURCE_TYPE_NAME=${RESOURCE_TYPE_NAME}"

QSS3BUCKETNAME="${3:-s3://simple-quickstart-mongodb-atlas}"
echo "QSS3BUCKETNAME=${QSS3BUCKETNAME}"

CUSTOMPROVIDERZIPFILENAME="${4:-/lambdas/MongoDBCloudResourceManager.zip}"
echo "CUSTOMPROVIDERZIPFILENAME=${CUSTOMPROVIDERZIPFILENAME}"

REGISTER_RESP=$(aws cloudformation register-type \
    --region "${REGION}" \
    --type RESOURCE \
    --type-name "${RESOURCE_TYPE_NAME}" \
    --schema-handler-package "${QSS3BUCKETNAME}${CUSTOMPROVIDERZIPFILENAME}")

echo "REGISTER_RESP=${REGISTER_RESP}"

REGISTRATION_TOKEN=$(echo ${REGISTER_RESP} | jq -r '.RegistrationToken')
echo "REGISTRATION_TOKEN=${REGISTRATION_TOKEN}"

aws cloudformation describe-type-registration --registration-token "${REGISTRATION_TOKEN}"

echo " \
 \
watch aws cloudformation describe-type-registration --registration-token \"${REGISTRATION_TOKEN}\" \
"
