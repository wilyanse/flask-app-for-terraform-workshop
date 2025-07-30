from flask import Flask, request, jsonify
import boto3
import uuid
from datetime import datetime
import os
from decimal import Decimal
import json

# Custom JSON encoder to handle Decimal types
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

app = Flask(__name__)
app.json_encoder = DecimalEncoder

# Initialize DynamoDB client and S3 client
region = os.environ.get('AWS_REGION', 'us-west-2')
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'products-table')
bucket_name = os.environ.get('S3_BUCKET_NAME', None)

dynamodb = boto3.resource('dynamodb', region_name=region)
table = dynamodb.Table(table_name)

if bucket_name is not None:
    s3 = boto3.client('s3', region_name=region)

@app.route('/products', methods=['POST'])
def create_product():
    try:
        # Accept both JSON and form data
        if request.is_json:
            data = request.get_json()
            image = None
        else:
            data = request.form.to_dict()
            image = request.files.get('image')

        required_fields = ['product_name', 'price', 'brand_name', 'quantity_available']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        product_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        # Upload image to S3 if provided
        image_url = None
        if image and image.filename:
            extension = os.path.splitext(image.filename)[1]
            s3_key = f'products/{product_id}{extension}'
            s3.upload_fileobj(
                image,
                bucket_name,
                s3_key,
                ExtraArgs={'ContentType': image.content_type}
            )
            image_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"

        item = {
            'product_id': product_id,
            'product_name': data['product_name'],
            'price': Decimal(str(data['price'])),
            'brand_name': data['brand_name'],
            'quantity_available': int(data['quantity_available']),
            'created_at': timestamp
        }

        if image_url:
            item['image_url'] = image_url
            item['image_key'] = s3_key

        table.put_item(Item=item)

        return jsonify({
            'message': 'Product created successfully',
            'product_id': product_id,
            'image_url': image_url
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/products', methods=['GET'])
def get_products():
    try:
        # Scan the table to get all products
        response = table.scan()
        products = response.get('Items', [])
        
        # Sort products by created_at timestamp
        sorted_products = sorted(products, key=lambda x: x.get('created_at', ''))
        
        return jsonify(sorted_products), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/form', methods=['GET'])
def product_form():
    return '''
    <html>
        <head><title>Create Product</title></head>
        <body>
            <h1>Create a Product</h1>
            <form action="/products" method="post" enctype="multipart/form-data">
                <label>Product Name:</label><br>
                <input type="text" name="product_name" required><br><br>

                <label>Price:</label><br>
                <input type="number" step="0.01" name="price" required><br><br>

                <label>Brand Name:</label><br>
                <input type="text" name="brand_name" required><br><br>

                <label>Quantity Available:</label><br>
                <input type="number" name="quantity_available" required><br><br>

                <label>Product Image:</label><br>
                <input type="file" name="image"><br><br>

                <input type="submit" value="Create Product">
            </form>
        </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))