import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
import requests

API_URL = "https://ultimosismo.igp.gob.pe/api/ultimo-sismo/ajaxb/{year}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
LIMITE = 10


def obtener_sismos(year):
    response = requests.get(API_URL.format(year=year), headers=HEADERS, timeout=15)
    response.raise_for_status()
    # parse_float=Decimal porque DynamoDB no acepta float
    return json.loads(response.text, parse_float=Decimal)


def lambda_handler(event, context):
    lima = timezone(timedelta(hours=-5))
    year = datetime.now(lima).year

    try:
        sismos = obtener_sismos(year)
        # Si recién empezó el año y hay pocos registros, completar con el año anterior
        if len(sismos) < LIMITE:
            sismos = sismos + obtener_sismos(year - 1)
    except requests.RequestException as e:
        return {'statusCode': 502, 'body': f'Error al consultar la API del IGP: {e}'}

    if not sismos:
        return {'statusCode': 404, 'body': 'La API no devolvió registros'}

    # Si el primer registro resulta ser el más antiguo, usa sismos[-LIMITE:]
    ultimos = sismos[:LIMITE]

    dynamodb = boto3.resource('dynamodb')
    db_table = dynamodb.Table('TablaWebScrapping')

    # Borrar los elementos anteriores (con paginación del scan)
    items = []
    scan = db_table.scan()
    items.extend(scan['Items'])
    while 'LastEvaluatedKey' in scan:
        scan = db_table.scan(ExclusiveStartKey=scan['LastEvaluatedKey'])
        items.extend(scan['Items'])

    with db_table.batch_writer() as batch:
        for each in items:
            batch.delete_item(Key={'id': each['id']})

    # Insertar los 10 más recientes
    rows = []
    for i, sismo in enumerate(ultimos, start=1):
        row = dict(sismo)
        row['#'] = i
        row['id'] = str(uuid.uuid4())
        db_table.put_item(Item=row)
        rows.append(row)

    return {
        'statusCode': 200,
        'body': json.dumps(rows, default=str)
    }