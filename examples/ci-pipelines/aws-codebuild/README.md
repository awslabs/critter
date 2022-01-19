# CodeBuild Continuous Integration Example

This example shows a Config rule Continuous Integration (CI) workflow within AWS CodeCommit and CodeBuild. It includes a CodeCommit repository of Config rules and `critter` test CloudFormation stacks to validate the Config rules. Any commit to the CodeCommit repository triggers a CodeBuild project. The build job:

1. Deploys Config rules defined as CloudFormation stacks
1. Runs `critter` integration tests
1. Deletes all CloudFormation stacks deployed by the build to prepare a clean environment for the next test cycle

A cloud governance team can use this workflow to add or update Config rules in the repository, and automatically run `critter` integration tests against the Config rules to be confident their Config rules evaluate AWS resources as expected. In its current state, a project like this would run within a dedicated integration environment. This example could be extended to implement Continuous Deployment (CD) by automatically deploy Config rules to production accounts after they have been tested in the integration environment.

## Setup

Follow these steps to deploy this example into an AWS account. This will add all example Config rules and `critter` test CloudFormation stack templates into the CodeCommit repository.

```shell
# Update this variable with an S3 bucket name already created in the AWS account
# and Region the example will be deployed to.
S3_BUCKET_NAME='my-bucket'

# Build distribution of critter
cd ../../../
python setup.py sdist --dist-dir "${OLDPWD}/"
cd -

# Package CodeCommit repo as zip file
ZIP_FILE_NAME='codecommit-repo.zip'
rm -f "$ZIP_FILE_NAME"
cd ../../
# By default, this will include all example config rules and test stacks in the
# CodeCommit repository
zip -r "${OLDPWD}/${ZIP_FILE_NAME}" config-rules/ test-stacks/
cd -
zip -u "$ZIP_FILE_NAME" *

# Upload the codecommit-repo.zip to an S3 bucket
aws s3 cp "./${ZIP_FILE_NAME}" "s3://${S3_BUCKET_NAME}/"

# Create the CodeCommit repository and CodeBuild project
aws cloudformation deploy \
  --stack-name CritterCiExample \
  --template-file ./cfn-stack.yml \
  --parameter-overrides "CodeZipS3BucketName=${S3_BUCKET_NAME}" "CodeZipS3Key=${ZIP_FILE_NAME}" \
  --capabilities CAPABILITY_IAM
```

After deploy, run the CodeBuild job `CritterCiExample`. It should create Config rule CloudFormation stacks with the name `CritterCiExample-<rule-name>`. Then it will test the Config rules using `critter`. All CloudFormation stacks should be cleaned up at the end of the CodeBuild job. If any issues are encountered, it should be safe to delete any CloudFormation stacks with the name prefix `Critter-` or `CritterCiExample-`.

To clean up the example deployment, delete the CloudFormation stack `CritterCiExample`.
