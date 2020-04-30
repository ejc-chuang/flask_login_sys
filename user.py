#! /usr/bin/env python3

# internal import
from db import get_db

class User:
    def __init__(self, email=None, name=None, password=None):
        self.name = name
        self.email = email
        self.password = password

    @staticmethod
    def get(unique_id):
        db = get_db()

        user = db.execute(
            "SELECT * FROM members WHERE email = ?", (unique_id,)
        ).fetchone()

        if not user:
            return None

        user = User(
                    email=user[0],
                    name=user[1],
                    password=user[2]
                )

        return user

    @staticmethod
    def create(email, name, password):
        db = get_db()

        # TODO shlould I do try catch here?
        db.execute(
            '''
            INSERT INTO members(email,username,userpassword)
            VALUES(?, ?, ?)
            ''', (email, name, password,)
        )

        db.commit()

    @staticmethod
    def validate(email, password):
        db = get_db()

        user = db.execute(
            "SELECT * FROM members WHERE email = ?", (email,)
        ).fetchone()

        if not user:
            return False
        else:
            if user[2] == password:
                return True
            else:
                return False

