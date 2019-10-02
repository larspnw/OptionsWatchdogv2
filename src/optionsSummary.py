import boto3
import json
from boto3.dynamodb.conditions import Attr

table_name = "Options"
print('Loading function')
dynamo = boto3.resource('dynamodb')
table = dynamo.Table(table_name)

def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }

def lambda_handler(event, context):

    #TODO catch errors and respond accordingly

    res = table.scan(
        FilterExpression=Attr("type").eq("put"))
    puts = res['Items']

    res = table.scan(
        FilterExpression=Attr("type").eq("call"))
    calls = res['Items']

    return {
        "statusCode": 200,
        "body": json.dumps({
            "summary": "active puts/calls: " + str(len(puts)) + " / " + str(len(calls)),
        }),
    }
