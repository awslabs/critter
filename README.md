# `critter` - AWS *C*onfig *R*ule *I*ntegration *T*es*TER*

`critter` enables AWS Config rule integration testing. Use it to validate that AWS Config rules evaluate resources as expected.

Customers use [AWS Config rules](https://docs.aws.amazon.com/config/latest/developerguide/evaluate-config.html) to evaluate their AWS resources against their own unique compliance and governance requirements. `critter` is a command line tool that enables a continuous integration workflow to validate that Config rules evaluate resources as expected. This is essential to guaranteeing compliance within AWS accounts, especially when you consider the potential impact of unexpected behavior from Config rule auto-remediations.

This project is in MVP phase - it is functional but the api may change significantly before release `1.0`.

## Overview

Usage of `critter` within the Config rule development workflow looks like this:

1. Developer writes [Config custom rule evaluation Lambda function code](https://docs.aws.amazon.com/config/latest/developerguide/evaluate-config_develop-rules.html) that evaluates AWS resources.
   - [Example Config custom rules Python code](./examples/config-rules/lambda/)
   - `critter` can also test [Config _managed_ rules](https://docs.aws.amazon.com/config/latest/developerguide/evaluate-config_use-managed-rules.html)
1. Developer deploys their Config rule and Lambda function.
   - [CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-config-configrule.html), [the RDK (Rule Development Kit)](https://github.com/awslabs/aws-config-rdk), or [Terraform](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/config_config_rule) can be used to deploy Config rules.
   - [Example Config rules CloudFormation templates](./examples/config-rules/)
1. Developer creates a CloudFormation template that defines test resources to be evaluated by the Config rule
   - [Example `critter` test CloudFormation templates](./examples/test-stacks/)
   - The template declares a few outputs that will be used by `critter`
     ```yaml
     Resources:
       CompliantResource1:
         # ...
       CompliantResource2:
         # ...
       NonCompliantResource1:
         # ...
       NonCompliantResource2:
         # ...

     Outputs:
       ConfigRuleName:
         Value: my-custom-config-rule
       CompliantResourceIds:
         Value: !Sub "${CompliantResource1.Id},${CompliantResource2.Id}"
       NonCompliantResourceIds:
         Value: !Sub "${NonCompliantResource1.Id},${NonCompliantResource2.Id}"
     ```
1. Developer triggers `critter` from the command line (or from within a CI/CD system). `critter` then ...
   1. Deploys the `critter` test CloudFormation stack
   1. Waits for the resources to be evaluated by the Config rule
   1. Validates that resources declared in output `CompliantResourceIds` were evaluated as `COMPLIANT` and resources declared in output `NonCompliantResourceIds` were evaluated as `NON_COMPLIANT`
   1. Deletes the `critter` test CloudFormation stack
1. Developer is confident their Config rule will evaluate resources as expected!

## Install

Install with [Python `pip`](https://docs.python.org/3/installing/index.html):

```shell
pip install critter
```

After `critter` is installed, you can verify the installation by showing the help: [`critter -h`](#cli-options).

## Usage

1. Deploy an AWS Config rule. The rule can be a managed rule or a custom rule that utilizes an AWS Lambda function for resource valuation.
1. Create a `critter` test CloudFormation template (i.e. `my-test-template.yml`) that deploys at least one resource you expect the rule to evaluate as `COMPLIANT` and at least one resource you expect the rule to evaluate as `NON_COMPLIANT`.
1. Declare the following `Outputs` in the `critter` test CloudFormation template ([documentation below](#test-cloudformation-stack-outputs)):
   1. `ConfigRuleName`: The name of the Config rule to test
   1. `CompliantResourceIds`: A comma separated list of one or more AWS Config resource IDs expected to be evaluated as `COMPLIANT`.
   1. `NonCompliantResourceIds`: A comma separated list of one or more AWS Config resource IDs expected to be evaluated as `NON_COMPLIANT`.
1. `critter TEMPLATE` (i.e. `critter ./my-test-template.yml`) deploys the `critter` test CloudFormation stack and validates the resource evaluations.
   - `critter` AWS integration is configured with [standard `boto3` configuration (environment variables and the `~/.aws/config` file)](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html).
   - The `critter` test CloudFormation stack will be deleted after testing `OnSuccess` by default (i.e. if all tests pass). This behavior can be controlled with `--delete-stack`.

## Continuous Integration

To understand how `critter` can be utilized in a Continuous Integration (CI) workflow to automatically test changes to AWS Config rules, see [the AWS CodeBuild CI example in `examples/ci-pipelines/aws-codebuild/`](./examples/ci-pipelines/aws-codebuild/).

## AWS Config Resource IDs

Most AWS resources have an `id` attribute (or similar) that is used as the AWS Config resource ID. For EC2 instances, resource IDs are the EC2 instance IDs (i.e. `i-111111111aaaaaaaa,i-222222222bbbbbbbb`). For VPC security groups, the resource ID is the security group ID (i.e. `sg-333333333cccccccc`). For IAM roles, the resource ID is the role ID (i.e. `AROAJI4AVVEXAMPLE`, which can be retrieved in a CloudFormation template using `Fn::Sub '${MyIamRole.RoleId}'`).

Generally, resource IDs can be obtained using the CloudFormation intrinsic `Ref` function with the resource's logical name. To confirm which attribute is used as a resource's Config resource ID, there are a few options:
- Browse resources in [the AWS Config console](https://console.aws.amazon.com/config/home?region=us-east-1#/resources)
- Browse resources using [the AWS CLI: `aws configservice list-discovered-resources --resource-type AWS::EC2::Instance`](https://docs.aws.amazon.com/cli/latest/reference/configservice/list-discovered-resources.html)
- See the `resourceId` field on example configuration items [here](https://github.com/awslabs/aws-config-rdk/tree/master/rdk/template/example_ci).

## `critter` Test CloudFormation Stack Outputs

See [example `critter` test CloudFormation templates in the `./examples/test-stacks/`](./examples/test-stacks/). Below is an explanation of each of the supported test stack outputs. Note that CloudFormation stack outputs are always strings.

- `ConfigRuleName`
  - AWS Config rule name to be tested. Be sure the rule is already deployed within the account and Region the `critter` test CloudFormation stack will be deployed to.
  - Example values:
    - `"my-custom-config-rule"`
- `CompliantResourceIds`
  - A comma separated list of one or more AWS Config resource IDs expected to be evaluated as `COMPLIANT`. At least one of `CompliantResourceIds` and `NonCompliantResourceIds` must be output.
  - Typically generated with `!Sub "${CompliantResource1.Id},${CompliantResource2.Id}"`
  - Example values:
    - `"i-11111111111111111"`
    - `"sg-22222222222222222,sg-33333333333333333"`
- `NonCompliantResourceIds`
  - A comma separated list of one or more AWS Config resource IDs expected to be evaluated as `NON_COMPLIANT`. At least one of `CompliantResourceIds` and `NonCompliantResourceIds` must be output.
  - Typically generated with `!Sub "${NonCompliantResource1.Id},${NonCompliantResource2.Id}"`
  - Example values:
    - `"sg-11111111111111111"`
    - `"i-22222222222222222,i-33333333333333333"`
- `DelayAfterDeploy`
  - Seconds to delay after `critter` test CloudFormation stack create or update. If the test stack is already deployed and no update occurs, the delay will be skipped.
  - Example values:
    - `"60"`
- `SkipWaitForResourceRecording`
  - Skip waiting for resources to be recorded in Config. Useful if Config rule is testing resources not natively supported by Config.
  - Allowed values:
    - `"True"`
    - `"False"` (default behavior)

## CLI Options

_Warning - This documentation may become out of date until the api stabilizes. Show the up to date help with `critter -h`._

```
$ critter -h
usage: critter [-h] [--trigger-rule-evaluation] [--stack-name STACK-NAME] [--stack-tags '[{"Key": "TagKey", "Value": "TagValue"}, ...]']
               [--capabilities CAPABILITY [CAPABILITY ...]] [--delete-stack {Always,OnSuccess,Never}]
               TEMPLATE

critter - AWS Config Rule Integration TesTER

positional arguments:
  TEMPLATE              CloudFormation template(s) to test already deployed Config rule

optional arguments:
  -h, --help            show this help message and exit
  --trigger-rule-evaluation
                        Trigger Config rule evaluation after CloudFormation stack deployment. Useful for periodic evaluation rules. Also ensures the rule
                        evaluation occured after stack deployment.
  --stack-name STACK-NAME
                        CloudFormation stack name (default is generated from TEMPLATE file name)
  --stack-tags '[{"Key": "TagKey", "Value": "TagValue"}, ...]'
                        Tags to associate with the CloudFormation stack formatted as a JSON string
  --capabilities CAPABILITY [CAPABILITY ...]
                        CloudFormation capabilities needed to deploy the stack (i.e. CAPABILITY_IAM, CAPABILITY_NAMED_IAM)
  --delete-stack {Always,OnSuccess,Never}
                        Test outcome that should trigger CloudFormation stack delete (default: OnSuccess)
```

## Contributing and Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.
