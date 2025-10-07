import uuid
import json
from config import bedrock_agent_runtime_client, bedrock_agent_client, agent_name, logger

def get_agent_info():
    """Get agent ID and alias ID from existing deployment"""
    # Find agent by name
    paginator = bedrock_agent_client.get_paginator('list_agents')
    for page in paginator.paginate():
        for agent_summary in page.get('agentSummaries', []):
            if agent_summary['agentName'] == agent_name:
                agent_id = agent_summary['agentId']
                
                # Get agent alias
                aliases_response = bedrock_agent_client.list_agent_aliases(agentId=agent_id)
                agent_alias_id = aliases_response['agentAliasSummaries'][0]['agentAliasId']
                
                return agent_id, agent_alias_id
    
    raise Exception(f"Agent '{agent_name}' not found")

def test_agent(agent_id, agent_alias_id, query="Check table metadata for splittest table"):
    """Test the deployed agent"""
    session_id = str(uuid.uuid1())
    
    agentResponse = bedrock_agent_runtime_client.invoke_agent(
        inputText=query,
        agentId=agent_id,
        agentAliasId=agent_alias_id, 
        sessionId=session_id,
        enableTrace=True, 
        endSession=False
    )
    print(query)
    event_stream = agentResponse['completion']
    
    for event in event_stream:        
        if 'chunk' in event:
            data = event['chunk']['bytes']
            agent_answer = data.decode('utf8')
            print(agent_answer)
            return agent_answer
        elif 'trace' in event:
            print(f"Trace: {event['trace']}")

if __name__ == "__main__":
    agent_id, agent_alias_id = get_agent_info()
    print(f"Using Agent ID: {agent_id}, Alias ID: {agent_alias_id}")
    
    result = test_agent(agent_id, agent_alias_id)
    print(f"Agent response: {result}")