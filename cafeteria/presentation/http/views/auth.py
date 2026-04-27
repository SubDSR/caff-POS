from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from cafeteria.infrastructure.persistence.mysql import catalog


logger = logging.getLogger(__name__)


def _password_matches(raw_password: str, encoded_password: str) -> bool:
    try:
        return check_password(raw_password, encoded_password)
    except ValueError:
        logger.warning("Stored POS password hash is malformed and was ignored")
        return False


def login_view(request: HttpRequest) -> HttpResponse:
    if request.session.get("is_logged_in"):
        return redirect("cafeteria:index")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        if username and password:
            try:
                account = catalog.get_pos_account_by_email(username)
            except catalog.MySQLCatalogError:
                messages.error(request, "No se pudo conectar a la base de datos MySQL")
                return render(request, "cafeteria/pages/login.html")

            if account and account["activa"] and _password_matches(password, account["password_hash"]):
                try:
                    catalog.touch_pos_account_access(account["correo"])
                except catalog.MySQLCatalogError:
                    messages.warning(request, "Se inició sesión, pero no se pudo registrar el último acceso")

                request.session["is_logged_in"] = True
                request.session["pos_account_email"] = account["correo"]
                request.session["pos_module_name"] = account["nombre_modulo"]
                request.session.modified = True
                messages.success(request, "Sesión iniciada correctamente")
                return redirect("cafeteria:index")

            messages.error(request, "Credenciales inválidas")
        else:
            messages.error(request, "Debe ingresar correo y contraseña")

    return render(request, "cafeteria/pages/login.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    request.session["is_logged_in"] = False
    request.session.pop("pos_account_email", None)
    request.session.pop("pos_module_name", None)
    request.session.modified = True
    messages.info(request, "Sesión cerrada")
    return redirect("cafeteria:login")
