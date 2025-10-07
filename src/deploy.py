import json
import time
import zipfile
from io import BytesIO
import uuid
from botocore.exceptions import ClientError
import sys
import os
sys.path.append(os.path.dirname(__file__))
from config import *

def create_lambda_role():
    """Create IAM role for Lambda function"""
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    inline_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AmazonRedshiftDataAPIPolicy",
                "Effect": "Allow",
                "Action": "redshift-data:ExecuteStatement",
                "Resource": "*"
            },
            {
                "Sid": "AmazonSecretsManagerPolicy",
                "Effect": "Allow",
                "Action": "secretsmanager:GetSecretValue",
                "Resource": "*"
            }
        ]
    }

    try:
        existing_role = iam_client.get_role(RoleName=lambda_function_role)
        print(f"Role {lambda_function_role} already exists")
        lambda_iam_role = existing_role['Role']
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            print(f"Creating new role: {lambda_function_role}")
            lambda_iam_role = iam_client.create_role(
                RoleName=lambda_function_role,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy_document)
            )

            print("Waiting for role to be created...")
            waiter = iam_client.get_waiter('role_exists')
            waiter.wait(
                RoleName=lambda_function_role,
                WaiterConfig={'Delay': 5, 'MaxAttempts': 10}
            )

            iam_client.attach_role_policy(
                RoleName=lambda_function_role,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
            )

            iam_client.put_role_policy(
                RoleName=lambda_function_role,
                PolicyName=f"{lambda_function_role}-inline-policy",
                PolicyDocument=json.dumps(inline_policy)
            )

            print(f"Successfully created role: {lambda_function_role}")
        else:
            raise e

    return lambda_iam_role

def create_lambda_function(lambda_iam_role):
    """Create or update Lambda function"""
    s = BytesIO()
    z = zipfile.ZipFile(s, 'w')
    z.write("src/lambda_function.py")
    z.close()
    zip_content = s.getvalue()

    try:
        lambda_function = lambda_client.create_function(
            FunctionName=lambda_function_name,
            Runtime='python3.12',
            Timeout=180,
            Role=lambda_iam_role['Arn'],
            Code={'ZipFile': zip_content},
            Handler='lambda_function.lambda_handler'
        )
        print(f"Lambda function '{lambda_function_name}' created successfully.")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceConflictException':
            print(f"Lambda function '{lambda_function_name}' already exists. Updating code.")
            lambda_client.update_function_code(
                FunctionName=lambda_function_name,
                ZipFile=zip_content
            )
            lambda_function = lambda_client.get_function(
                FunctionName=lambda_function_name
            )
            print(f"Lambda function '{lambda_function_name}' updated successfully.")
        else:
            print(f"An unexpected error occurred: {e}")
            raise e

    return lambda_function

def create_bedrock_policy():
    """Create Bedrock policy for agent"""
    bedrock_agent_bedrock_allow_policy_statement = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AmazonBedrockAgentBedrockFoundationModelPolicy",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": [
                    f"arn:aws:bedrock:*::foundation-model/{foundation_model}",
                    f"arn:aws:bedrock:*:*:inference-profile/{inference_profile}"
                ]
            },
            {
                "Sid": "AmazonBedrockAgentBedrockGetInferenceProfile",
                "Effect": "Allow",
                "Action": [
                    "bedrock:GetInferenceProfile",
                    "bedrock:ListInferenceProfiles",
                    "bedrock:UseInferenceProfile"
                ],
                "Resource": [
                    f"arn:aws:bedrock:*:*:inference-profile/{inference_profile}"
                ]
            }
        ]
    }

    bedrock_policy_json = json.dumps(bedrock_agent_bedrock_allow_policy_statement)

    try:
        agent_bedrock_policy = iam_client.create_policy(
            PolicyName=agent_bedrock_allow_policy_name,
            PolicyDocument=bedrock_policy_json
        )
        print(f"IAM policy '{agent_bedrock_allow_policy_name}' created successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"IAM policy '{agent_bedrock_allow_policy_name}' already exists. Skipping creation.")
            agent_bedrock_policy = {
                'Policy': {
                    'Arn': f'arn:aws:iam::{account_id}:policy/{agent_bedrock_allow_policy_name}'
                }
            }
        else:
            raise e

    return agent_bedrock_policy

def create_agent_role(agent_bedrock_policy):
    """Create IAM role for Bedrock agent"""
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }]
    }

    try:
        assume_role_policy_document_json = json.dumps(assume_role_policy_document)
        agent_role = iam_client.create_role(
            RoleName=agent_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            agent_role = iam_client.get_role(RoleName=agent_role_name)
        else:
            raise e

    time.sleep(10)
    
    iam_client.attach_role_policy(
        RoleName=agent_role_name,
        PolicyArn=agent_bedrock_policy['Policy']['Arn']
    )

    return agent_role

def create_bedrock_agent(agent_role):
    """Create Bedrock agent"""
    time.sleep(30)

    try:
        response = bedrock_agent_client.create_agent(
            agentName=agent_name,
            agentResourceRoleArn=agent_role['Role']['Arn'],
            description=agent_description,
            idleSessionTTLInSeconds=1800,
            foundationModel=inference_profile,
            instruction=agent_instruction,
        )
        agent_id = response['agent']['agentId']
        print(f"Agent '{agent_name}' created successfully with ID: {agent_id}")
    except ClientError as e:
        print(f"Could not create agent. Attempting to find existing agent with name '{agent_name}'.")

        agent_id = None
        try:
            paginator = bedrock_agent_client.get_paginator('list_agents')
            for page in paginator.paginate():
                for agent_summary in page.get('agentSummaries', []):
                    if agent_summary['agentName'] == agent_name:
                        print(f"Found existing agent with ID: {agent_summary['agentId']}")
                        agent_id = agent_summary['agentId']
                        break
                if agent_id:
                    break
        except ClientError as list_e:
            print(f"An error occurred while listing agents: {list_e}")
            raise list_e
        
        if agent_id is None:
            print("Could not find an existing agent with that name.")
            raise e

    return agent_id

def create_action_group(agent_id, lambda_function):
    """Create agent action group"""
    agent_functions = [
        {
            'name': 'check_table_metadata',
            'description': 'get optimisation statistics for table',
            'parameters': {
                "table_name": {
                    "description": "the name of the table to get optimisation statistics",
                    "required": True,
                    "type": "string"
                }
            }
        }
    ]

    time.sleep(30)

    try:
        agent_action_group_response = bedrock_agent_client.create_agent_action_group(
            agentId=agent_id,
            agentVersion='DRAFT',
            actionGroupName=agent_action_group_name,
            actionGroupExecutor={
                'lambda': lambda_function['Configuration']['FunctionArn']
            },
            functionSchema={
                'functions': agent_functions
            },
            description=agent_action_group_description
        )
        print("Action group created successfully.")
        
        if 'agentActionGroup' in agent_action_group_response:
            print(f"Action Group ID: {agent_action_group_response['agentActionGroup']['actionGroupId']}")
        else:
            print("Action group created, but ID not found in response")

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        error_message = e.response.get('Error', {}).get('Message')

        if error_code == 'ConflictException':
            print(f"Conflict Error: {error_message}")
            print("An action group with this name already exists. Please use a different name.")
        else:
            print(f"An unexpected AWS client error occurred: {error_code} - {error_message}")
            raise

def add_lambda_permission(agent_id):
    """Add permission for Bedrock to invoke Lambda"""
    try:
        response = lambda_client.add_permission(
            FunctionName=lambda_function_name,
            StatementId='allow_bedrock',
            Action='lambda:InvokeFunction',
            Principal='bedrock.amazonaws.com',
            SourceArn=f"arn:aws:bedrock:{region}:{account_id}:agent/{agent_id}"
        )
    except lambda_client.exceptions.ResourceConflictException:
        print("Permission already exists - no need to add it again")

def prepare_agent(agent_id):
    """Prepare the agent"""
    response = bedrock_agent_client.prepare_agent(agentId=agent_id)
    print(response)
    return response

def get_agent_alias(agent_id):
    """Get agent alias"""
    aliases_response = bedrock_agent_client.list_agent_aliases(agentId=agent_id)
    agent_alias_id = aliases_response['agentAliasSummaries'][0]['agentAliasId']
    print(f"Agent Alias ID: {agent_alias_id}")
    return agent_alias_id

def main():
    """Main deployment function"""
    print("Starting deployment...")
    
    # Create Lambda role and function
    lambda_iam_role = create_lambda_role()
    lambda_function = create_lambda_function(lambda_iam_role)
    
    # Create Bedrock policy and agent role
    agent_bedrock_policy = create_bedrock_policy()
    agent_role = create_agent_role(agent_bedrock_policy)
    
    # Create Bedrock agent
    agent_id = create_bedrock_agent(agent_role)
    
    # Create action group
    create_action_group(agent_id, lambda_function)
    
    # Add Lambda permission
    add_lambda_permission(agent_id)
    
    # Prepare agent
    prepare_agent(agent_id)
    
    # Get agent alias
    agent_alias_id = get_agent_alias(agent_id)
    
    print(f"Deployment completed successfully!")
    print(f"Agent ID: {agent_id}")
    print(f"Agent Alias ID: {agent_alias_id}")

if __name__ == "__main__":
    main()