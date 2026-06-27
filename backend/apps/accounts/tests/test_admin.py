import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.test import Client
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_admin_add_view_hashes_password():
    superuser = CustomUserFactory(role="admin", is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(superuser)

    raw_password = "s3cret-pass-1234"
    response = client.post(
        "/admin/accounts/customuser/add/",
        {
            "username": "newuser",
            "password1": raw_password,
            "password2": raw_password,
            "role": "surveyor",
        },
    )

    assert response.status_code == 302
    created = User.objects.get(username="newuser")
    assert created.check_password(raw_password)
    assert created.password != raw_password


def test_admin_change_form_password_is_read_only():
    from apps.accounts.admin import CustomUserAdmin
    from django.contrib.admin.sites import site

    user = CustomUserFactory()
    model_admin = CustomUserAdmin(User, site)
    form = model_admin.get_form(_request_with_user(user), obj=user)()

    assert isinstance(form.fields["password"], ReadOnlyPasswordHashField)


def _request_with_user(user):
    request = type("Req", (), {})()
    request.user = user
    return request
