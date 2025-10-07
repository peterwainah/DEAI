import os
import json
import boto3
import botocore 
import botocore.session as bc
from botocore.client import Config
import redshift_connector

def check_table_metadata(table_name):
    secret_name = os.environ['SecretId']  # getting SecretId from Environment variables
    session = boto3.session.Session()
    region = session.region_name
    
    # Initializing Secret Manager's client    
    client = session.client(
        service_name='secretsmanager',
        region_name=region
    )
    
    get_secret_value_response = client.get_secret_value(
        SecretId=secret_name
    )
    secret_arn = get_secret_value_response['ARN']
    
    secret = get_secret_value_response['SecretString']
    print(secret)
    
    secret_json = json.loads(secret)
    print(secret_json)
    
    cluster_id = secret_json['dbClusterIdentifier']

    # Initializing Botocore client
    bc_session = bc.get_session()
    
    session = boto3.Session(
        botocore_session=bc_session,
        region_name=region
    )
    print(session)
    
    if table_name:
        # SQL query
        sql_query = f"""
        select stats_off from svv_table_info
        where "table"='{table_name}'
        """
        
        conn = redshift_connector.connect(
            host=secret_json['host'],
            database='dev',
            user=secret_json['username'],
            password=secret_json['password'],
            port=secret_json['port']
        )

        cursor = conn.cursor()
        print(sql_query)
        cursor.execute(sql_query)
        response = cursor.fetchall()

        if response:
            table_metadata = response[0][0]  # Unpack the tuple and get the value
            
            # If stats_off > 10, run ANALYZE
            if table_metadata > 10:
                analyze_query = f"ANALYZE {table_name};"
                print(f"Running ANALYZE on {table_name}")
                cursor.execute(analyze_query)
                conn.commit()
                result_msg = f"Table {table_name} had stats_off={table_metadata}. ANALYZE completed."
            else:
                result_msg = f"Table {table_name} stats_off={table_metadata}. No ANALYZE needed."
            
            conn.close()
            return result_msg
        else:
            return_msg = f"No metadata found for table_name {table_name}"
            print(return_msg)
            conn.close()
            return return_msg
    else:
        raise Exception(f"No table_name provided")
    
    # Close the database connection
    conn.close()


def lambda_handler(event, context):
    agent = event['agent']
    actionGroup = event['actionGroup']
    function = event['function']
    parameters = event.get('parameters', [])
    responseBody = {
        "TEXT": {
            "body": "Error, no function was called"
        }
    }

    if function == 'check_table_metadata':
        print(f"Received parameters: {parameters}")
        table_name = None
        for param in parameters:
            if param["name"] == "table_name":
                table_name = param["value"]
        
        print(f"Extracted table_name: {table_name}")
        if not table_name:
            raise Exception("Missing mandatory parameter: table_name")
        table_metadata = check_table_metadata(table_name)
        responseBody = {
            'TEXT': {
                "body": f"table design metadata for table {table_name}: {table_metadata}"
            }
        }
           
    action_response = {
        'actionGroup': actionGroup,
        'function': function,
        'functionResponse': {
            'responseBody': responseBody
        }
    }

    function_response = {'response': action_response, 'messageVersion': event['messageVersion']}
    print("Response: {}".format(function_response))

    return function_response