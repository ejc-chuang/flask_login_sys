#! /usr/bin/env python3

# external import
from flask import Flask, redirect, request, url_for, render_template
from oauthlib.oauth2 import WebApplicationClient, OAuth2Error
import requests
import json
import sqlite3
import re
from flask_mail import Mail, Message

# internal import
from user import User
from db import init_db_command

app = Flask(__name__)
app.secret_key = 'super secret key'
app.config.from_object('config')

mail = Mail(app)

GOOGLE_CLIENT_ID = app.config['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = app.config['GOOGLE_CLIENT_SECRET']
GOOGLE_DISCOVERY_URL = app.config['GOOGLE_DISCOVERY_URL']

try:
    init_db_command()
except sqlite3.OperationalError:
    # Assume it's already been created
    pass


def login_successful():
    # Not quite sure what token should be...
    return '{token:"XXX"}'


def sent_email(email):
    msg = Message(
                "Register Notification",
                recipients=[email]
                )
    msg.body = "Thank you for your registration"
    mail.send(msg)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return '''
                <a class="button" href="glogin">Google Login</a></br>
                <a class="button" href="flogin">Facebook Login</a></br>
                <a class="button" href="elogin">Email Login</a></br>
                <form action='login' method='POST'>
                    <input type='text' name='name' id='name' placeholder='name'
                     required /></br>
                    <input type='text' name='email' id='email' placeholder=
                    'email' required /></br>
                    <input type='password' name='password' id='password'
                    placeholder='password' required/></br>
                    <input type='password' name='password2' id='password2'
                    placeholder='password' required/></br>
                    <input type='submit' name='submit' value = 'Register'/>
                </form>
                {}
            '''.format(request.args.get('emessage', ''))
    else:
        user = User(
                    email=request.form['email'],
                    name=request.form['name'],
                    password=request.form['password']
                    )

        p = re.compile(r"[^@]+@[^@]+\.[^@]+")

        if not p.match(user.email):
            return redirect(
                url_for(
                    'login',
                    emessage='The email is not valid'
                    )
                )

        if User.get(user.email):
            return redirect(
                url_for(
                    'login',
                    emessage='The email is used already.'
                    )
                )

        if len(user.password) < 8:
            return redirect(
                url_for(
                    'login',
                    emessage='The password is shorter than 8.'
                    )
                )

        if request.form['password'] != request.form['password2']:
            return redirect(
                url_for(
                    'login',
                    emessage='The passwords are incorrect.'
                    )
                )

        User.create(user.email, user.name, user.password)
        sent_email(user.email)

        return '{} account is created.'.format(user.name)


@app.route('/flogin')
def flogin():
    return render_template(
                        'f_login.html',
                        appId=app.config['FACEBOOK_CLIENT_ID'],
                        version=app.config['FACEBOOK_SDK_VERSION'],
                        )


@app.route('/flogin/callback')
def fcallback():
    if request.args.get('email'):
        user = User.get(request.args.get('email'))
        if user is None:
            User.create(
                request.args.get('email'),
                request.args.get('name'),
                request.args.get('id')
                )
            sent_email(request.args.get('email'))
            return '{} account is created.'.format(request.args.get('name'))
        else:
            return login_successful()
    else:
        e = {"error": request.args.get('e')}
        return json.dumps(e)


@app.route('/elogin')
def elogin():
    return '''
        <form action='elogin/callback' method='POST'>
            <input type='text' name='email' id='email' placeholder='email'
            required/></br>
            <input type='password' name='password' id='password' placeholder=
            'password' required /></br>
            <input type='submit' name='submit' value='Login'/>
        </form>
        {}
        '''.format(request.args.get('emessage', ''))


@app.route('/elogin/callback', methods=['POST'])
def ecallback():
    user = User(
                request.form['email'],
                None,
                request.form['password'],
                )

    if User.validate(user.email, user.password):
        return login_successful()
    else:
        return redirect(url_for('elogin', emessage='Login fail'))


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


client = WebApplicationClient(GOOGLE_CLIENT_ID)


@app.route('/glogin')
def glogin():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    # redirect to authorization endpoint and users have to consent
    return redirect(request_uri)


@app.route('/glogin/callback')
def gcallback():
    # get the authorization code
    code = request.args.get("code")

    # send the code to token_endpoint for client token
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )

    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # check if the token is valid.
    try:
        client.parse_request_body_response(json.dumps(token_response.json()))
    except OAuth2Error as e:
        return json.dumps({"error": e})

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return json.dumps(
            {"error": "User email not available or not verified by Google."}
            )

    user = User.get(users_email)
    if user is None:
        User.create(users_email, users_name, unique_id)
        sent_email(users_email)
        return '{} account is created.'.format(users_name)
    else:
        return login_successful()


if __name__ == "__main__":
    app.run(ssl_context='adhoc')
