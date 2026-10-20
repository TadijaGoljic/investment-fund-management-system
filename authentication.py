import re

from flask import Flask, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

from configuration import Configuration
from models import database, User

authentication = Flask(__name__)
authentication.config.from_object(Configuration)
JWTManager(authentication)
database.init_app(authentication)

with authentication.app_context():
    database.create_all()
    if User.query.filter_by(role='director').first() is None:
        director = User(
            forename='Scrooge',
            surname='McDuck',
            email='onlymoney@gmail.com',
            password='evenmoremoney',
            role='director'
        )
        database.session.add(director)
        database.session.commit()

EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'


@authentication.route('/register', methods=['POST'])
def register():
    request_data = request.json or {}

    for field in ['forename', 'surname', 'email', 'password']:
        if field not in request_data or len(request_data[field]) == 0:
            return {'message': f'Field {field} is missing.'}, 400

    if not re.match(EMAIL_REGEX, request_data['email']):
        return {'message': 'Invalid email.'}, 400

    if len(request_data['password']) < 8:
        return {'message': 'Invalid password.'}, 400

    if User.query.filter_by(email=request_data['email']).first() is not None:
        return {'message': 'Email already exists.'}, 400

    new_user = User(
        forename=request_data['forename'],
        surname=request_data['surname'],
        email=request_data['email'],
        password=request_data['password'],
        role='employee',
    )
    database.session.add(new_user)
    database.session.commit()

    return '', 200


@authentication.route('/login', methods=['POST'])
def login():
    request_data = request.json or {}

    for field in ['email', 'password']:
        if field not in request_data or len(request_data[field]) == 0:
            return {'message': f'Field {field} is missing.'}, 400

    if not re.match(EMAIL_REGEX, request_data['email']):
        return {'message': 'Invalid email.'}, 400

    user = User.query.filter_by(
        email=request_data['email'],
        password=request_data['password'],
    ).first()
    if user is None:
        return {'message': 'Invalid credentials.'}, 400

    claims = {
        'forename': user.forename,
        'surname': user.surname,
        'email': user.email,
        'role': user.role
    }
    access_token = create_access_token(identity=user.email, additional_claims=claims)
    return {'accessToken': access_token}, 200


@authentication.route('/delete', methods=['POST'])
@jwt_required()
def delete():
    email = get_jwt_identity()

    user = User.query.filter_by(email=email).first()
    if user is None:
        return {'message': 'Unknown user.'}, 400

    database.session.delete(user)
    database.session.commit()
    return '', 200


@authentication.route('/', methods=['GET'])
def index():
    return 'Hello from authentication'
