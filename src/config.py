import boto3
import logging

# Setting logger
logging.basicConfig(format='[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Getting boto3 clients for required AWS services
sts_client = boto3.client('sts')
iam_client = boto3.client('iam')
lambda_client = boto3.client('lambda')
bedrock_agent_client = boto3.client('bedrock-agent')
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')

# Configuration variables
session = boto3.session.Session()
region = session.region_name
account_id = sts_client.get_caller_identity()["Account"]

# Create inference profile for specific model
inference_profile = "amazon.nova-lite-v1:0"
foundation_model = inference_profile[3:]

# Configuration variables
suffix = f"{region}-{account_id}"
agent_name = "de_oncall_agent_function_def"
agent_bedrock_allow_policy_name = f"{agent_name}-ba-{suffix}"
agent_role_name = f'AmazonBedrockExecutionRoleForAgents_{agent_name}'
agent_description = "Agent for providing Date Engineer on call to help troubleshoot"
agent_instruction = "You are an DE agent, helping DE have peace during oncall"
agent_action_group_name = "DEActionGroup"
agent_action_group_description = "Actions for optimisation of performance"
agent_alias_name = f"{agent_name}-alias"
lambda_function_role = f'{agent_name}-lambda-role-{suffix}'
lambda_function_name = f'{agent_name}-{suffix}'