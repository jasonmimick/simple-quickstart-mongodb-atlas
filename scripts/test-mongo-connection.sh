#!/usr/bin/env bash
SRVHOST_DB="${1}"
echo "Testing connection to ${SRVHOST_DB} via AWS IAM current user"

mongo "${SRVHOST_DB}?authSource=%24external&authMechanism=MONGODB-AWS" \
    --username $(aws sts get-session-token --output text --query 'Credentials.AccessKeyId') \
    --password $(aws sts get-session-token --output text --query 'Credentials.SecretAccessKey') \
    --awsIamSessionToken $(aws sts get-session-token --output text --query 'Credentials.SessionToken')

