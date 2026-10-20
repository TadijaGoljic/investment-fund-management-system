from typing import Any

from flask_sqlalchemy import SQLAlchemy

database = SQLAlchemy()


class User(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    forename = database.Column(database.String(256), nullable=False)
    surname = database.Column(database.String(256), nullable=False)
    email = database.Column(database.String(256), nullable=False, unique=True)
    password = database.Column(database.String(256), nullable=False)
    role = database.Column(database.String(256), nullable=False)

    def __init__(self, forename, surname, email, password, role, **kw: Any):
        super().__init__(**kw)
        self.forename = forename
        self.surname = surname
        self.email = email
        self.password = password
        self.role = role
