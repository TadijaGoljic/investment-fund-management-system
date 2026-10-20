import os
from datetime import timedelta


class Configuration:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///investment_fund.db')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES_HOURS', '1')))
    MONGO_HOST = os.environ.get('MONGO_HOST', 'mongo')
    MONGO_PORT = os.environ.get('MONGO_PORT', '27017')
    MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
    MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
    MONGO_DATABASE = os.environ.get('MONGO_DATABASE', 'investment_fund')
    MONGO_ASSETS_COLLECTION = os.environ.get('MONGO_ASSETS_COLLECTION', 'assets')
    MONGO_URI = 'mongodb://' + (f'{MONGO_USERNAME}:{MONGO_PASSWORD}@' if MONGO_USERNAME and MONGO_PASSWORD else '') + f'{MONGO_HOST}:{MONGO_PORT}/'
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
    BLOCKCHAIN_HOST = os.environ.get('BLOCKCHAIN_HOST', 'ganache')
    BLOCKCHAIN_PORT = os.environ.get('BLOCKCHAIN_PORT', '8545')
    BLOCKCHAIN_URL = os.environ.get('BLOCKCHAIN_URL', f'http://{BLOCKCHAIN_HOST}:{BLOCKCHAIN_PORT}')