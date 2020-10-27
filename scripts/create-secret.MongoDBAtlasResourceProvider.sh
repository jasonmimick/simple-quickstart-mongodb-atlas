#!/usr/bin/env bash
SECRET_NAME="${1:-aws-quickstart-test-key}"
echo "SECRET_NAME=${SECRET_NAME}"

REGION="${2:-$(aws configure get region)}"
echo "REGION=${REGION}"

# Deal with delete/create a secret to hold the MongoDB Atlas API Key.
# We will then launch the MongoDB Cloud Resource Manager lambda stack with
# environment variables 'encoded' just like a cloud foration secret reference
# this will trigger the Resource Manager to lookup the secret API key values
# dynamically at runtime, thus making your cloud deployment much most secure!
GOT_SECRET=$(aws secretsmanager list-secrets | \
    jq --arg SECRETNAME "${SECRET_NAME}" \
    '.SecretList[] | select(.Name=="$SECRETNAME")' \
    2>&1)
echo "GOT_SECRET=${GOT_SECRET}"
if [ "$GOT_SECRET" ];
then
    echo "We have the secret"
    echo "But first, need delete the old one and then take a nap to let it happen"
    DELETE_SECRET_RESPONSE=$(aws secretsmanager delete-secret --secret-id "${SECRET_NAME}" 2>&1)
    echo "DELETE_SECRET_RESPONSE=${DELETE_SECRET_RESPONSE}"
    echo "Breate, 30 seconds."
    for i in {1..30}
    do
        echo ". "
        sleep 3
    done
    sleep 3
    echo "  Ahh."
else
    echo "Didn't have ${SECRET_NAME} don't need to delete it!"
fi

secret=$(mktemp)
cat << EOF > "${secret}"
{
    "PublicKey" : "${ATLAS_PUBLIC_KEY}",
    "PrivateKey": "${ATLAS_PRIVATE_KEY}",
    "OrgId": "${ATLAS_ORG_ID}"
}
EOF
echo "${secret}"
cat "${secret}"
echo "standby, baking a fresh yummy secret for your MongoDB Atlas API Key..."
CREATE_SECRET_RESPONSE=$(aws secretsmanager create-secret \
    --region "${REGION}" \
    --name "${SECRET_NAME}" \
    --secret-string "file://${secret}" 2>&1)
echo "CREATE_SECRET_RESPONSE=${CREATE_SECRET_RESPONSE}"

rm "${secret}"
PUBLIC_KEY_REF="{{resolve:secretsmanager:${SECRET_NAME}:SecretString:PublicKey}}"
echo "PUBLIC_KEY_REF=${PUBLIC_KEY_REF}"
PRIVATE_KEY_REF="{{resolve:secretsmanager:${SECRET_NAME}:SecretString:PrivateKey}}"
echo "PRIVATE_KEY_REF=${PRIVATE_KEY_REF}"
ORG_ID_REF="{{resolve:secretsmanager:${SECRET_NAME}:SecretString:OrgId}}"
echo "ORG_ID_REF=${ORG_ID_REF}"




