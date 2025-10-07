from config import bedrock_agent_client, agent_name

def update_action_group():
    """Update existing action group with correct parameter type"""
    # Find agent by name
    paginator = bedrock_agent_client.get_paginator('list_agents')
    agent_id = None
    for page in paginator.paginate():
        for agent_summary in page.get('agentSummaries', []):
            if agent_summary['agentName'] == agent_name:
                agent_id = agent_summary['agentId']
                break
        if agent_id:
            break
    
    if not agent_id:
        print(f"Agent '{agent_name}' not found")
        return
    
    # List action groups
    action_groups = bedrock_agent_client.list_agent_action_groups(
        agentId=agent_id,
        agentVersion='DRAFT'
    )
    
    action_group_id = None
    for ag in action_groups['actionGroupSummaries']:
        if ag['actionGroupName'] == 'DEActionGroup':
            action_group_id = ag['actionGroupId']
            break
    
    if not action_group_id:
        print("Action group not found")
        return
    
    # Update action group with correct parameter type
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
    
    response = bedrock_agent_client.update_agent_action_group(
        agentId=agent_id,
        agentVersion='DRAFT',
        actionGroupId=action_group_id,
        actionGroupName='DEActionGroup',
        functionSchema={
            'functions': agent_functions
        },
        description='Actions for optimisation of performance'
    )
    
    print("Action group updated successfully")
    
    # Prepare agent
    bedrock_agent_client.prepare_agent(agentId=agent_id)
    print("Agent prepared")

if __name__ == "__main__":
    update_action_group()