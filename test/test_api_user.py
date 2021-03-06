import random

import pytest

from fastapi_simple_login.db import SessionManager, User


test_sample = [
    ("test@example.com", "test_password", "Test user"),
    ("test2@example.com", "test_password2", "Test user2"),
    ("test3@example.com", "test_password3", "Test user3"),
]


def get_values(field):
    return [
        sample[["email", "password", "name"].index(field)]
        for sample in test_sample
    ]


def get_user_email_no_root(client, root_email):
    with SessionManager():
        return random.choice(
            User.query.filter(User.email != root_email).all()
        )


@pytest.mark.parametrize("email, password, name", test_sample)
def test_create_user(client, email, password, name):
    response = client.post(
        "/users",
        json=dict(email=email, password=password, name=name)
    )

    assert response.status_code == 201

    user = response.json()

    with SessionManager():
        db_user = User.query.filter(User.email == user["email"]).first()

    assert len(user.keys()) == 3
    assert user["email"] == db_user.email == email
    assert user["name"] == db_user.name == name
    assert user["last_login"] is db_user.last_login is None

    assert db_user.password_hash is not None


@pytest.mark.parametrize("email, password, name", test_sample)
def test_get_user(client, email, name, password):
    response = client.get(f"/users/{email}")

    assert response.status_code == 200

    user = response.json()

    assert len(user.keys()) == 3
    assert user["email"] == email
    assert user["name"] == name
    assert user["last_login"] is None


def test_list_users(client):
    response = client.get(f"/users")

    assert response.status_code == 200

    users = response.json()

    assert len(users) == 3
    assert all(len(user.keys()) == 3 for user in users)
    assert all(user["email"] in get_values("email") for user in users)
    assert all(user["name"] in get_values("name") for user in users)
    assert all(user["last_login"] is None for user in users)


update_data = [
    {"email": "newemail@example.com"},
    {"name": "Changed name"},
    {"email": "newemail2@example.com", "name": "Changed name2"}
]


@pytest.mark.parametrize("fields_update", update_data)
def test_update_user(client, fields_update, root_token, root_email):
    user_email = get_user_email_no_root(client, root_email).email
    response = client.put(
        f"/users/{user_email}",
        json=fields_update,
        headers={"Authorization": root_token}
    )

    assert response.status_code == 204

    email = fields_update.pop("email", user_email)

    with SessionManager():
        updated_user = User.query.filter(User.email == email).first()

    assert all(
        getattr(updated_user, field) == value
        for field, value in fields_update.items()
    )


@pytest.mark.parametrize("fields_update", update_data)
def test_update_user_fail_when_not_logged(client, fields_update):
    user_email = random.choice(client.get("/users").json())["email"]
    response = client.put(
        f"/users/{user_email}",
        json=fields_update
    )

    assert response.status_code == 401


def test_update_user_password(client, root_email, root_token):
    with SessionManager():
        user = random.choice(User.query.filter(User.email != root_email).all())

    client.put(
        f"/users/{user.email}",
        json={"password": "a great new password"},
        headers={"Authorization": root_token}
    )

    with SessionManager():
        user_updated = User.query.get(user.id)

    assert user.password_hash != user_updated.password_hash


def test_delete_user(client, root_token):
    initial_users = client.get("/users").json()
    user_email = random.choice(initial_users)["email"]

    response = client.delete(
        f"/users/{user_email}",
        headers={"Authorization": root_token}
    )

    assert response.status_code == 204

    final_users = client.get("/users").json()

    assert len(initial_users) - len(final_users) == 1
    assert all(user_email != user["email"] for user in final_users)


def test_delete_user_fails_when_not_logged(client):
    initial_users = client.get("/users").json()
    user_email = random.choice(initial_users)["email"]

    response = client.delete(f"/users/{user_email}")

    assert response.status_code == 401
