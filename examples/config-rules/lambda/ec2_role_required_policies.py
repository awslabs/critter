# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import boto3
import json
import os

config = boto3.client("config", region_name=os.environ["AWS_REGION"])


def handler(event, context):
    print(json.dumps({"Message": "Received event", "event": event}))
    ie = json.loads(event["invokingEvent"])
    ci = ie["configurationItem"]

    print(json.dumps({"Message": "Evaluating configuration item", "configurationItem": ci}))

    # Evaluation template
    evaluation = {
        "ComplianceResourceType": ci["resourceType"],
        "ComplianceResourceId": ci["resourceId"],
        "OrderingTimestamp": ci["configurationItemCaptureTime"],
    }

    # Evaluate resource as NOT_APPLICABLE, NON_COMPLIANT, or COMPLIANT
    if ci["resourceType"] != "AWS::IAM::Role":
        evaluation["ComplianceType"] = "NOT_APPLICABLE"
    elif ci["configurationItemStatus"] == "ResourceDeleted":
        evaluation["ComplianceType"] = "NOT_APPLICABLE"
    elif not ci["configuration"]["instanceProfileList"]:
        evaluation["ComplianceType"] = "NOT_APPLICABLE"
        evaluation["Annotation"] = "Role has no associated instance profiles"
    else:
        attached_policy_arns = [p["policyArn"] for p in ci["configuration"]["attachedManagedPolicies"]]
        missing = []
        for required in json.loads(event["ruleParameters"])["requiredAwsManagedPolicyArns"]:
            if required not in attached_policy_arns:
                missing.append(required)
        if missing:
            evaluation["ComplianceType"] = "NON_COMPLIANT"
            evaluation["Annotation"] = f"Missing required attached policies: {missing}"
        else:
            evaluation["ComplianceType"] = "COMPLIANT"

    print(json.dumps({"Message": "Submitting evaluation", "evaluation": evaluation}))

    res = config.put_evaluations(
        Evaluations=[evaluation],
        ResultToken=event["resultToken"],
    )

    if res["FailedEvaluations"]:
        raise Exception(f"ERROR - Failed evaluations: {res['FailedEvaluations']}")
