import uuid
from functools import wraps

from flask_jwt_extended import jwt_required, get_jwt


def role_check(role):
    def decorator(function):
        @jwt_required()
        @wraps(function)
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            if role in claims['role']:
                return function(*args, **kwargs)
            else:
                return {'msg': 'Missing Authorization Header'}, 401
        return wrapper
    return decorator


def uuid_check(value):
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
