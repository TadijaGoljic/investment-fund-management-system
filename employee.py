import json
import logging
import sys
import uuid
from datetime import datetime

import redis
from bson import ObjectId
from bson.errors import InvalidId
from flask import Flask, request
from flask_jwt_extended import jwt_required, JWTManager
from pymongo import MongoClient

from configuration import Configuration
from utils import role_check

employee = Flask(__name__)
employee.config.from_object(Configuration)
JWTManager(employee)

mongo_client = MongoClient(Configuration.MONGO_URI)
assets_collection = mongo_client[Configuration.MONGO_DATABASE][Configuration.MONGO_ASSETS_COLLECTION]

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

employee.logger.addHandler(handler)
employee.logger.setLevel(logging.INFO)


@employee.route('/search', methods=['POST'])
@jwt_required()
@role_check('employee')
def search():
    request_data = request.json or {}
    query = {}

    if 'name' in request_data:
        query['name'] = {'$regex': request_data['name']}

    if 'category' in request_data:
        query['categories'] = request_data['category']

    if 'buying_date' in request_data:
        query['buying_date'] = {
            '$gt': datetime.fromisoformat(request_data['buying_date'].replace('Z', '+00:00'))
        }

    if 'selling_date' in request_data:
        query['selling_date'] = {
            '$exists': True,
            '$lt': datetime.fromisoformat(request_data['selling_date'].replace('Z', '+00:00'))
        }

    for f in request_data.get('info_filters', []):
        field = 'info.' + f['field']
        query[field] = {'$' + f['operator']: f['value']}

    assets = []
    for doc in assets_collection.find(query):
        asset = {
            'id': str(doc['_id']),
            'name': doc['name'],
            'categories': doc['categories'],
            'buying_date': doc['buying_date'].isoformat(),
            'buying_price': doc['buying_price'],
            'info': doc.get('info', {}),
        }
        if doc.get('selling_date') is not None:
            asset['selling_date'] = doc['selling_date'].isoformat()
            asset['selling_price'] = doc['selling_price']
        assets.append(asset)

    return {'assets': assets}, 200


@employee.route('/create_buy_order', methods=['POST'])
@jwt_required()
@role_check('employee')
def create_buy_order():
    request_data = request.json or {}

    if 'name' not in request_data or len(request_data['name']) == 0:
        return {'message': 'Field name is missing.'}, 400

    if 'categories' not in request_data:
        return {'message': 'Field categories is missing.'}, 400

    if 'buying_price' not in request_data:
        return {'message': 'Field buying_price is missing.'}, 400

    if 'info' not in request_data:
        return {'message': 'Field info is missing.'}, 400

    if len(request_data['categories']) == 0:
        return {'message': 'Categories list is empty.'}, 400

    if request_data['buying_price'] <= 0:
        return {'message': 'Invalid buying price.'}, 400

    buying_data = {
        'uuid': str(uuid.uuid4()),
        'order_type': 'BUY',
        'name': request_data['name'],
        'categories': request_data['categories'],
        'buying_price': request_data['buying_price'],
        'info': request_data['info']
    }

    with redis.Redis(host=Configuration.REDIS_HOST, port=Configuration.REDIS_PORT) as redis_client:
        redis_client.lpush('orders', json.dumps(buying_data))
        employee.logger.info('push')

    return '', 200


@employee.route('/create_sell_order', methods=['POST'])
@jwt_required()
@role_check('employee')
def create_sell_order():
    request_data = request.json or {}

    if 'id' not in request_data or len(request_data['id']) == 0:
        return {'message': 'Field id is missing.'}, 400

    if 'selling_price' not in request_data:
        return {'message': 'Field selling_price is missing.'}, 400

    try:
        asset = assets_collection.find_one({'_id': ObjectId(request_data['id'])})
        if asset is None:
            return {'message': 'Invalid id.'}, 400
    except InvalidId:
        return {'message': 'Invalid id.'}, 400

    if request_data['selling_price'] <= 0:
        return {'message': 'Invalid selling price.'}, 400

    selling_data = {
        'uuid': str(uuid.uuid4()),
        'order_type': 'SELL',
        'id': request_data['id'],
        'selling_price': request_data['selling_price'],
    }

    with redis.Redis(host=Configuration.REDIS_HOST, port=Configuration.REDIS_PORT) as redis_client:
        redis_client.lpush('orders', json.dumps(selling_data))
        employee.logger.info('push')

    return '', 200


@employee.route('/', methods=['GET'])
def index():
    return 'Hello from employee'
