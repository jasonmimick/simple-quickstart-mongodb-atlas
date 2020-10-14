#!/usr/bin/env bash
STACK_NAME="${1}"
EXPORTS=$(aws cloudformation list-exports)
#echo "EXPORTS=${EXPORTS}"

MDB=$(echo "${EXPORTS}" | jq -r --arg STACKNAME "${STACK_NAME}" '.Exports[] | select(.Name==$STACKNAME+"-standardSrv") | .Value')
echo "New ${STACK_NAME} database url: ${MDB}"

STACK_ROLE=$(aws cloudformation describe-stack-resources --stack-name "${STACK_NAME}" --logical-resource-id AtlasIAMRole)
echo "STACK_ROLE=${STACK_ROLE}"

ROLE=$(aws iam get-role --role-name $( echo "${STACK_ROLE}" | jq -r '.StackResources[] | .PhysicalResourceId'))
echo "ROLE=${ROLE}"

ROLE_ARN=$(echo "${ROLE}" | jq -r '.Role.Arn')
echo "ROLE_ARN=${ROLE_ARN}"

ROLE_CREDS=$(aws sts assume-role --role-session-name test --role-arn ${ROLE_ARN})
echo "ROLE_CREDS=${ROLE_CREDS}"

mongo "${MDB}/${STACK_NAME}?authSource=%24external&authMechanism=MONGODB-AWS" \
    --username $(echo "${ROLE_CREDS}" | jq -r '.Credentials.AccessKeyId') \
    --password $(echo "${ROLE_CREDS}" | jq -r '.Credentials.SecretAccessKey') \
    --awsIamSessionToken $(echo "${ROLE_CREDS}" | jq -r '.Credentials.SessionToken')




