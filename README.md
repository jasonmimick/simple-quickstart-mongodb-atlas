# Clone

```bash
git clone
```

# Setup AWS & API Keys

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
  --stack-name mongodbatlas-quickstart
```

# Connect to your database

After the cluster provisions, you can connect with the `mongo` shell or MongoDB Compass.


**TODO** Get `SRVHOST_DB` output into the Stack output.

```bash
mongo "${SRVHOST_DB}?authSource=%24external&authMechanism=MONGODB-AWS" \
    --username $(aws sts get-session-token --output text --query 'Credentials.AccessKeyId') \
    --password $(aws sts get-session-token --output text --query 'Credentials.SecretAccessKey') \
    --awsIamSessionToken $(aws sts get-session-token --output text --query 'Credentials.SessionToken')
```
