import boto3
import json
from boto3.dynamodb.conditions import Attr
import datetime

print('Loading function')
dynamo = boto3.client('dynamodb')
table_name = "Options"

def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }

def respond2(statusCode, res=None):
    return {
        'statusCode': statusCode,
        'body': json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }

def deleteOptions_handler(event, context):
    #print("Received event: " + json.dumps(event, indent=2))
    #evt = json.dumps(event, indent=2)
    key = event['pathParameters']['optionsKey']
    return doDelete(key)
    #return respond(None, "{'message:', 'lars was here'}")

def expiredOptions_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    operation = event['httpMethod']
    #resourcePath = event['requestContext']['resourcePath']
    if operation == 'GET':
        payload = event['queryStringParameters']
        return doExpired(payload)
    else:
        return respond(None, "{'message:', 'Not supported ' }")

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    operations = {
        'DELETE': lambda dynamo, x: dynamo.delete_item(TableName=table_name, **x),
        'GET': lambda dynamo, x: dynamo.scan(TableName=table_name, **x) if x else dynamo.scan(TableName=table_name),
        'POST': lambda dynamo, x: dynamo.put_item(TableName=table_name, **x),
        'PUT': lambda dynamo, x: dynamo.update_item(TableName=table_name, **x),
    }

    operation = event['httpMethod']
    #resourcePath = event['requestContext']['resourcePath']
    #print("resourcePath: " + resourcePath)

    if operation == 'GET':
        payload = event['queryStringParameters']
        return doGet(payload)
    else:
        return respond(None, "{'message:', 'Not supported '}")

def doGet(payload):
    print("doGet enter ", payload)
    #r = dynamo.scan(TableName=table_name)
    if payload == None:
        r = dynamo.scan(TableName=table_name)
    #else:
        #r = dynamo.scan(TableName=table_name, payload)

    return respond(None, r)

def doExpired(payload):
    print("doExpired enter ", payload)
    dynamo = boto3.resource('dynamodb')
    table = dynamo.Table('Options')
    #TODO fix date

    now = datetime.datetime.now()
    snow = now.strftime("%Y/%m/%d")

    r = table.scan(TableName=table_name,
                    FilterExpression=Attr('expirationDate').lt(snow))
    #return respond(None, "{'message:', 'get expired'}")
    return respond(None, r["Items"])
    #TODO error handling

def doDelete(key):
    #print("doDelete enter ", key)
    dynamo = boto3.resource('dynamodb')
    table = dynamo.Table('Options')
    try:
        r = table.delete_item(Key={"nameTypePrice": key})
        print("doDelete r: ", r)
    except Exception as err:
        print("doDelete: error: ", err )
        return respond2(404, "{'message:', 'error: " + str(err) + "'}")

    #did this work?
    #return 200 on success and return key
    #return 404 if failed and the key + error message
    return respond2(200, "{'message:', 'Delete successful for " + key + "'}")
