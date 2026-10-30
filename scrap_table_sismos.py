import requests
from bs4 import BeautifulSoup
import boto3
import uuid

def lambda_handler(event, context):
    # URL de la página web que contiene la tabla
    url = "https://ultimosismo.igp.gob.pe/productos/reportes-sismicos"

    # Realizar la solicitud HTTP a la página web
    response = requests.get(url)
    if response.status_code != 200:
        return {
            'statusCode': response.status_code,
            'body': 'Error al acceder a la página web'
        }

    # Parsear el contenido HTML de la página web
    soup = BeautifulSoup(response.content, 'html.parser')

    # Encontrar la tabla en el HTML
    table = soup.find('table')
    if not table:
        return {
            'statusCode': 404,
            'body': 'No se encontró la tabla en la página web'
        }

    # Extraer los encabezados de la tabla
    headers = [header.text for header in table.find_all('th')]

    # Extraer solo las 10 primeras filas (omitiendo el encabezado)
    rows = []
    for row in table.find_all('tr')[1:11]:
        cells = row.find_all('td')
        rows.append({headers[i+1]: cell.text for i, cell in enumerate(cells)})

    # Guardar los datos en DynamoDB
    dynamodb = boto3.resource('dynamodb')
    db_table = dynamodb.Table('TablaWebScrappingSismos')

    # Eliminar todos los elementos de la tabla antes de agregar los nuevos
    scan = db_table.scan()
    with db_table.batch_writer() as batch:
        for each in scan['Items']:
            batch.delete_item(
                Key={
                    'id': each['id']
                }
            )

    # Insertar los nuevos datos
    for i, row in enumerate(rows, start=1):
        row['#'] = i
        row['id'] = str(uuid.uuid4())  # Generar un ID único para cada entrada
        db_table.put_item(Item=row)

    # Retornar el resultado como JSON
    return {
        'statusCode': 200,
        'body': rows
    }
