import json
import logging
import sys
import time
from datetime import datetime, timezone
from threading import Thread

import redis
from bson import ObjectId
from bson.code import Code
from flask import Flask, request
from flask_jwt_extended import jwt_required, JWTManager
from pymongo import MongoClient
from web3 import Web3

from compile_voters import abi, bytecode
from configuration import Configuration
from utils import role_check, uuid_check

director = Flask(__name__)
director.config.from_object(Configuration)
JWTManager(director)

mongo_client = MongoClient(Configuration.MONGO_URI)
assets_collection = mongo_client[Configuration.MONGO_DATABASE][Configuration.MONGO_ASSETS_COLLECTION]

web3 = Web3(Web3.HTTPProvider(Configuration.BLOCKCHAIN_URL))

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

director.logger.addHandler(handler)
director.logger.setLevel(logging.INFO)


@director.route('/pending_orders', methods=['GET'])
@jwt_required()
@role_check('director')
def pending_orders():
    orders = []

    with redis.Redis(host=Configuration.REDIS_HOST, port=Configuration.REDIS_PORT) as redis_client:
        for order in redis_client.lrange('orders', 0, -1):
            orders.append(json.loads(order))
    return { 'orders': orders }, 200


@director.route('/decision', methods=['POST'])
@jwt_required()
@role_check('director')
def decision():
    request_data = request.json or {}

    if 'uuid' not in request_data or request_data['uuid'] == '':
        return {  'message': 'Field uuid is missing.' }, 400

    if not uuid_check(request_data['uuid']):
        return { 'message': 'Invalid uuid.' }, 400

    asset = None
    matched_item = None

    with redis.Redis(host=Configuration.REDIS_HOST, port=Configuration.REDIS_PORT) as redis_client:
        items = redis_client.lrange('orders', 0, -1)
        for item in items:
            json_item = json.loads(item)
            if json_item['uuid'] == request_data['uuid']:
                asset = json_item
                matched_item = item.decode('utf-8') if isinstance(item, bytes) else item
                break

    if asset is None:
        return { 'message': 'Invalid uuid.' }, 400

    if 'voters' not in request_data or len(request_data['voters']) == 0:
        return { 'message': 'Field voters is missing.' }, 400

    voters = request_data['voters']
    for voter in voters:
        if not Web3.is_address(voter):
            return { 'message': 'Invalid voter address.' }, 400

    if len(voters) % 2 == 0:
        return { 'message': 'Even number of voters.' }, 400

    vote_contract = web3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = vote_contract.constructor(voters).transact(
        {
            'from': web3.eth.accounts[0]
        }
    )
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = receipt.contractAddress

    contract = web3.eth.contract(address=contract_address, abi=abi)

    gas_price = web3.eth.gas_price

    approve_transactions = {}
    reject_transactions = {}
    for voter in voters:
        nonce = web3.eth.get_transaction_count(voter)
        approve_transactions[voter] = contract.functions.vote(True).build_transaction(
            {
                'from': voter,
                'nonce': nonce,
                'gasPrice': gas_price
            }
        )
        reject_transactions[voter] = contract.functions.vote(False).build_transaction(
            {
                'from': voter,
                'nonce': nonce,
                'gasPrice': gas_price
            }
        )

    with redis.Redis(host=Configuration.REDIS_HOST, port=Configuration.REDIS_PORT) as redis_client:
        redis_client.hset(
            'vote_contracts',
            request_data['uuid'],
            json.dumps(
                {
                    'contract_address': contract_address,
                    'asset': asset,
                    'redis_item': matched_item,
                    'abi': abi
                }
            )
        )

    return {
        'contract_address': contract_address,
        'approve_transaction': approve_transactions[voters[0]],
        'reject_transaction': reject_transactions[voters[0]],
        'approve_transactions': approve_transactions,
        'reject_transactions': reject_transactions
    }, 200


def finish_vote(vote_data, approved):
    asset = vote_data['asset']

    with redis.Redis(host=Configuration.REDIS_HOST, port=Configuration.REDIS_PORT) as redis_client:
        redis_client.lrem('orders', 1, vote_data['redis_item'])

    if not approved:
        return

    if asset['order_type'] == 'BUY':
        assets_collection.insert_one(
            {
                'name': asset['name'],
                'categories': asset['categories'],
                'buying_price': asset['buying_price'],
                'buying_date': datetime.now(timezone.utc),
                'info': asset['info']
            }
        )
    elif asset['order_type'] == 'SELL':
        assets_collection.update_one(
            { '_id': ObjectId(asset['id']) },
            {
                '$set':
                    {
                        'selling_price': asset['selling_price'],
                        'selling_date': datetime.now(timezone.utc)
                    }
            }
        )


def blockchain_listener():
    director.logger.info('Blockchain listener started')
    while True:
        try:
            with redis.Redis(host=Configuration.REDIS_HOST, port=Configuration.REDIS_PORT) as redis_client:
                contracts = redis_client.hgetall('vote_contracts')

                for uuid, value in contracts.items():
                    vote_data = json.loads(value)
                    contract = web3.eth.contract(address=vote_data['contract_address'], abi=vote_data['abi'])
                    ended = contract.functions.ended().call()

                    if ended:
                        approved = contract.functions.approved().call()
                        director.logger.info(f'Vote finished {uuid}, approved={approved}')
                        finish_vote(vote_data, approved)

                        redis_client.hdel('vote_contracts', uuid)

        except Exception as e:
            director.logger.error(f'Blockchain listener error: {e}')

        time.sleep(5)


listener = Thread(target=blockchain_listener, daemon=True)
listener.start()


@director.route('/report2', methods=['GET'])
@jwt_required()
@role_check('director')
def report2():
    pipeline = [
        {
            '$unwind': '$categories'
        },
        {
            '$group': {
                '_id': '$categories',
                'spent': {
                    '$sum': '$buying_price'
                },
                'earned': {
                    '$sum': {
                        '$cond': [
                            {
                                '$ifNull': [
                                    '$selling_date',
                                    False
                                ]
                            },
                            '$selling_price',
                            0
                        ]
                    }
                }
            }
        },
        {
            '$project': {
                '_id': 0,
                'category': '$_id',
                'spent': 1,
                'earned': 1
            }
        },
        {
            '$sort': {
                'earned': -1,
                'spent': 1,
                'category': 1
            }
        }
    ]

    statistics = list(assets_collection.aggregate(pipeline))
    return { 'statistics': statistics }, 200


@director.route('/report', methods=['GET'])
@jwt_required()
@role_check('director')
def report():
    map_func = Code('''
        function () {
            var earned = 0;
            if (this.selling_date) {
                earned = this.selling_price;
            }
            for (var i = 0; i < this.categories.length; i++) {
                emit(
                    this.categories[i],
                    {
                        spent:this.buying_price,
                        earned:earned
                    }
                );
            }
        }
    ''')
    reduce_func = Code('''
        function (key, values) {
            var result = { spent: 0, earned: 0 };
            values.forEach(function (value) {
                result.spent += value.spent;
                result.earned += value.earned;
            });
            return result;
        }
    ''')
    result = mongo_client[Configuration.MONGO_DATABASE].command(
        'mapReduce',
        Configuration.MONGO_ASSETS_COLLECTION,
        map=map_func,
        reduce=reduce_func,
        out={ 'inline': 1 }
    )
    statistics = [
        {
            'category': item['_id'],
            'spent': item['value']['spent'],
            'earned': item['value']['earned']
        }
        for item in result['results']
    ]
    statistics.sort(
        key=lambda x:
        (
            -x['earned'],
            x['spent'],
            x['category']
        )
    )
    return { 'statistics': statistics }, 200


@director.route('/modification1', methods=['GET'])
def modification1():
    map_func = Code('''
        function () {
            for (var i = 0; i < this.categories.length; i++) {
                emit(this.categories[i], 1)
            }
        }
    ''')
    reduce_func = Code('''
        function (key, values) {
            return { key: values.length }
        }
    ''')
    result = mongo_client[Configuration.MONGO_DATABASE].command(
        'mapReduce',
        Configuration.MONGO_ASSETS_COLLECTION,
        map=map_func,
        reduce=reduce_func,
        out={'inline': 1}
    )
    return result, 200


@director.route('/modification2', methods=['GET'])
def modification2():
    asset = assets_collection.find_one(
        { 'selling_price': { '$exists': True } },
        sort=[('selling_price', -1)]
    )

    if asset is None:
        return { 'message': 'No sold assets found.' }, 404

    asset['_id'] = str(asset['_id'])
    return asset, 200


@director.route('/modification3', methods=['GET'])
def modification3():
    asset = assets_collection.find_one(
        { 'selling_price': { '$exists': True } },
        sort=[('selling_price', 1)]
    )

    if asset is None:
        return { 'message': 'No sold assets found.' }, 404

    asset['_id'] = str(asset['_id'])
    return asset, 200


@director.route('/modification4', methods=['GET'])
def modification4():
    pipeline = [
        {
            '$match': { 'selling_price': { '$exists': True } }
        },
        {
            '$group': {
                '_id': None,
                'average_selling_price': { '$avg': '$selling_price' }
            }
        }
    ]

    result = list(assets_collection.aggregate(pipeline))

    if not result:
        return { 'message': 'No sold assets found.' }, 404

    return { 'average_selling_price': result[0]['average_selling_price'] }, 200


@director.route('/modification5', methods=['GET'])
def modification5():
    assets = list(
        assets_collection.find(
            { 'selling_price': { '$exists': True } },
            sort=[('selling_price', -1)],
            limit=2
        )
    )

    if len(assets) < 2:
        return { 'message': 'Not enough sold assets found.' }, 404

    asset = assets[1]
    asset['_id'] = str(asset['_id'])
    return asset, 200


@director.route('/modification6', methods=['GET'])
def modification6():
    pipeline = [
        {
            '$match': { 'selling_price': { '$exists': True } }
        },
        {
            '$project': {
                'name': 1,
                'categories': 1,
                'buying_price': 1,
                'selling_price': 1,
                'profit': { '$subtract': ['$selling_price', '$buying_price'] }
            }
        },
        {
            '$sort': { 'profit': -1 }
        },
        {
            '$limit': 1
        }
    ]

    result = list(assets_collection.aggregate(pipeline))

    if not result:
        return { 'message': 'No sold assets found.' }, 404

    asset = result[0]
    asset['_id'] = str(asset['_id'])
    return asset, 200


@director.route('/modification7', methods=['GET'])
def modification7():
    map_func = Code('''
        function () {
            if (this.selling_price !== undefined) {
                emit('average_selling_price', { sum: this.selling_price, count: 1 })
            }
        }
    ''')
    reduce_func = Code('''
        function (key, values) {
            var result = { sum: 0, count: 0 };
            values.forEach(function (value) {
                result.sum += value.sum;
                result.count += value.count;
            });
            return result;
        }
    ''')
    finalize_func = Code('''
        function (key, value) {
            return value.sum / value.count;
        }
    ''')
    result = mongo_client[Configuration.MONGO_DATABASE].command(
        'mapReduce',
        Configuration.MONGO_ASSETS_COLLECTION,
        map=map_func,
        reduce=reduce_func,
        finalize=finalize_func,
        out={'inline': 1}
    )

    if not result['results']:
        return { 'message': 'No sold assets found.' }, 404

    return { 'average_selling_price': result['results'][0]['value'] }, 200


@director.route('/modification8', methods=['GET'])
def modification8():
    map_func = Code('''
        function () {
            if (this.selling_price !== undefined) {
                emit('most_profitable', {
                    id: this._id,
                    name: this.name,
                    categories: this.categories,
                    buying_price: this.buying_price,
                    selling_price: this.selling_price,
                    profit: this.selling_price - this.buying_price
                })
            }
        }
    ''')
    reduce_func = Code('''
        function (key, values) {
            var best = values[0];
            values.forEach(function (value) {
                if (value.profit > best.profit) {
                    best = value;
                }
            });
            return best;
        }
    ''')
    result = mongo_client[Configuration.MONGO_DATABASE].command(
        'mapReduce',
        Configuration.MONGO_ASSETS_COLLECTION,
        map=map_func,
        reduce=reduce_func,
        out={'inline': 1}
    )

    if not result['results']:
        return { 'message': 'No sold assets found.' }, 404

    asset = result['results'][0]['value']
    asset['id'] = str(asset['id'])
    return asset, 200


@director.route('/', methods=['GET'])
def index():
    return 'Hello from director 3'


if __name__ == '__main__':
    director.run(host='0.0.0.0', port=5002)
