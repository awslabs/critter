# Contributing Guidelines

Thank you for your interest in contributing to our project. Whether it's a bug report, new feature, correction, or additional
documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary
information to effectively respond to your bug report or contribution.


## Reporting Bugs/Feature Requests

We welcome you to use the GitHub issue tracker to report bugs or suggest features.

When filing an issue, please check existing open, or recently closed, issues to make sure somebody else hasn't already
reported the issue. Please try to include as much information as you can. Details like these are incredibly useful:

* A reproducible test case or series of steps
* The version of our code being used
* Any modifications you've made relevant to the bug
* Anything unusual about your environment or deployment


## Contributing via Pull Requests
Contributions via pull requests are much appreciated. Before sending us a pull request, please ensure that:

1. You are working against the latest source on the *main* branch.
2. You check existing open, and recently merged, pull requests to make sure someone else hasn't addressed the problem already.
3. You open an issue to discuss any significant work - we would hate for your time to be wasted.

To send us a pull request, please:

1. Fork the repository.
2. Modify the source; please focus on the specific change you are contributing. If you also reformat all the code, it will be hard for us to focus on your change.
3. Ensure local tests pass.
4. Commit to your fork using clear commit messages.
5. Send us a pull request, answering any default questions in the pull request interface.
6. Pay attention to any automated CI failures reported in the pull request, and stay involved in the conversation.

GitHub provides additional document on [forking a repository](https://help.github.com/articles/fork-a-repo/) and
[creating a pull request](https://help.github.com/articles/creating-a-pull-request/).

## Local Development

Follow the guide below to begin local development on the tool. This relies on local [boto3 and AWS CLI configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html).

```shell
# Create a python venv for this project
python -m venv .venv
source .venv/bin/activate

# Install critter from current dir in editable mode and other development dependencies
pip install --upgrade -r requirements-dev.txt

# Show the help to verify your install is working as expected
critter -h

# Deploy the example Config rules from ./examples/config-rules/ to an AWS account (requires AWS CLI).
# Specify an existing S3 bucket in the AWS account. CloudFormation template resources (Lambda function code)
# will be uploaded to this bucket before the Config rules are deployed using CloudFormation. See
# ./deploy-rules.sh to learn more about this process.
./deploy-rules.sh <s3-bucket-name>

# Run the example test stacks with a mixture of arguments to verify functionality
critter examples/test-stacks/cw-loggroup-retention-period.yml \
  --trigger-rule-evaluation \
  --stack-tags '[{"Key": "CritterCustomTagKey1", "Value": "CritterCustomTagValue1"}, {"Key": "CritterCustomTagKey2", "Value": "CritterCustomTagValue2"}]'
critter examples/test-stacks/ec2-role-required-policies.yml \
  --trigger-rule-evaluation \
  --capabilities CAPABILITY_IAM \
  --delete-stack Never \
  --stack-name Critter-Ec2RoleRequiredPolicies

# Run unit tests
python -m pytest -s -vv
```

Be sure to manually test for expected test successes _and_ expected test failures. Code changes should also be run thru [`black`](https://github.com/psf/black) and [`flake8`](https://github.com/pycqa/flake8) for formatting and linting.

```shell
black .
flake8 $(find * -type f -name '*.py')
```

## Finding contributions to work on
Looking at the existing issues is a great way to find something to contribute on. As our projects, by default, use the default GitHub issue labels (enhancement/bug/duplicate/help wanted/invalid/question/wontfix), looking at any 'help wanted' issues is a great place to start.


## Code of Conduct
This project has adopted the [Amazon Open Source Code of Conduct](https://aws.github.io/code-of-conduct).
For more information see the [Code of Conduct FAQ](https://aws.github.io/code-of-conduct-faq) or contact
opensource-codeofconduct@amazon.com with any additional questions or comments.


## Security issue notifications
If you discover a potential security issue in this project we ask that you notify AWS/Amazon Security via our [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public github issue.


## Licensing

See the [LICENSE](LICENSE) file for our project's licensing. We will ask you to confirm the licensing of your contribution.
