#!/usr/bin/env bash
REGION="${1:-us-east-1}"
FILTER="${2:-XXX}"
STACKS=$(aws cloudformation describe-stacks --region ${REGION} --output text --query 'Stacks[*].{Stack:StackName}'  | grep "${FILTER}")
if [[ "$*" == *killall* ]]
then
    echo "*********** killall initiated ******************"
    STACKS=$(aws cloudformation describe-stacks --region ${REGION} --output text --query 'Stacks[*].{Stack:StackName}')
    echo "Region: ${REGION} Stacks: ${STACKS}"
fi
if [[ "$*" == *dry-run* ]]
then
    echo "dry-run"
    echo "Region: ${REGION}"
    echo "Stacks: ${STACKS}"
    exit 0
fi
if [[ -z "${STACKS}" ]]; then
    echo "Skys look clear, no stacks in sight, proceed."
    exit 0
fi

echo "WARNING: This will blow-away all the stacks in a region. Swim at your own risk."

echo "Region: ${REGION}"
echo "Stacks: ${STACKS}"
while IFS= read -r stack
do
    term_resp=$(aws cloudformation update-termination-protection \
    --no-enable-termination-protection \
    --region "${REGION}" --stack-name "$stack" 2>&1)

    delete_resp=$(aws cloudformation delete-stack \
    --region "${REGION}" \
    --retain-resources "AtlasDeployment" "AtlasDatabaseUser" \
    --stack-name "$stack" 2>&1)


    if grep -q "error" <<< "$delete_resp"; then
        echo "Caught error: ${delete_resp}, trying again - forcefully"
        aws cloudformation delete-stack \
        --region "${REGION}" \
        --retain-resources "AtlasDatabaseUser" \
        --stack-name "$stack"
        aws cloudformation delete-stack \
        --region "${REGION}" \
        --retain-resources "AtlasDeployment" \
        --stack-name "$stack"
        aws cloudformation delete-stack \
        --region "${REGION}" \
        --stack-name "$stack"
    fi


    echo "stack:${stack}"
    echo "update-termination-protection:${term_resp}"
    echo "delete-stack-deploy: ${delete_resp_deploy}"
    echo "delete-stack-dbuser: ${delete_resp_dbuser}"
done < <(printf '%s\n' "${STACKS}")

