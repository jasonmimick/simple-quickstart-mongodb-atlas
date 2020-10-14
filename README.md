# quickstart-mongodb-atlas 

```bash
git clone
```

# Setup AWS & API Keys

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
unzip /tmp/awscliv2.zip
sudo /tmp/aws/install
MONGOCLI_VERSION="1.7.0"
curl -L "https://github.com/mongodb/mongocli/releases/download/${MONGOCLI_VERSION}/mongocli_${MONGOCLI_VERSION}_linux_x86_64.tar.gz" -o "/tmp/mongocli_${MONGOCLI_VERSION}_linux_x86_64.tar.gz"
tar xzvf "/tmp/mongocli_${MONGOCLI_VERSION}_linux_x86_64.tar.gz" --directory /tmp
cp "/tmp/mongocli_${MONGOCLI_VERSION}_linux_x86_64/mongocli" "~/.local/bin"
~/.local/bin/mongocli --version

```bash
aws configure
mongocli config
```

+ Run this helper to setup environment variables for your 
MongoDB Atlas API keys (read from mongocli config)

```bash
source <(./scripts/export-mongocli-config.py)
```

# Deploy the MongoDB Cloud Resource Manager into AWS

This quickstart is powered by a lightweight lambda-controller
which connects your AWS CloudFormation control plane directly into
the MongoDB Cloud. Run this command to install the Resource Manager 
into the `AWS_REGION` of your choice before running the quickstart.

```bash
aws cloudformation create-stack \
  --template-body file://templates/mongodbatlas-resource-manager.template.yaml \
  --capabilities CAPABILITY_IAM \
  --stack-name mongodbatlas-resource-manager 
```

# Launch the quickstart stack

The `templates/mongodbatlas-quickstart.template.yaml` stack will 
provision a complete you MongoDB Atlas Deployment for you. This includes
the follow resources
* MongoDB Atlas Project
* MongoDB Atlas Cluster
* AWS IAM Role Integration 
* MongoDB Atlas DatabaseUser (AWS IAM) 

__NOTE__ Never keep your apikey or secrets in plain text. Don't do this and use secrets.

```bash
# Fetch my current awscli user
AWS_USER_ARN=$(aws sts get-caller-identity --output text --query 'Arn') \
source <(./scripts/export-mongocli-config.py)
env | grep ATLAS && \
aws cloudformation create-stack \
  --capabilities CAPABILITY_IAM \
  --template-body file://templates/quickstart-mongodb-atlas.template.yaml \
  --parameters ParameterKey=PublicKey,ParameterValue=${ATLAS_PUBLIC_KEY} \
               ParameterKey=PrivateKey,ParameterValue=${ATLAS_PRIVATE_KEY} \
               ParameterKey=OrgId,ParameterValue=${ATLAS_ORG_ID} \
               ParameterKey=DBUserArn,ParameterValue=${AWS_USER_ARN} \
  --stack-name mongodb-atlas-quickstart
```

# Connect to your database

After the cluster provisions, you can connect with the `mongo` shell or MongoDB Compass.

**TODO** *Right now - need to trigger and update-stack to force refresh of
the stack output/export. Is there a better way for this?*

Fetch the new cluster `mongodb+srv://` host info:

```bash
MDB=$(aws cloudformation list-exports | \
 jq '.Exports[] | select(.Name=="mongodb-atlas-quickstart-standardSrv") | .Value')
echo "mongodb-atlas-quickstart database url: ${MDB}"
```

```bash
MDB=$(aws cloudformation list-exports | \
 jq '.Exports[] | select(.Name=="${STACK_NAME}-standardSrv") | .Value')
echo "New ${STACK_NAME} database url: ${MDB}"
```
Use this url along with your `aws` cli credentials to seamlessly and securly connect to your new MongoDB Atlas database:

```bash
STACK_ROLE=$(aws cloudformation describe-stack-resources --stack-name cookies-99-5x --logical-resource-id AtlasIAMRole)
ROLE=$(aws iam get-role --role-name $( echo "{$STACK_ROLE}" | jq -r '.StackResources[] | .PhysicalResourceId'))
ROLE_ARN=$(echo "${ROLE}" | jq -r '.Role.Arn')
ROLE_CREDS=$(aws sts assume-role --role-session-name test --role-arn ${ROLE_ARN})
mongo "${MDB}/${STACK_NAME}?authSource=%24external&authMechanism=MONGODB-AWS" \
    --username $(echo "${ROLE_CRED}" | jq -r '.Credentials.AccessKeyId') \
    --password $(echo "${ROLE_CRED}" | jq -r '.Credentials.SecretAccessKey') \
    --awsIamSessionToken $(echo "${ROLE_CRED}" | jq -r '.Credentials.SessionToken')
```
