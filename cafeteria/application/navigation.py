from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


def get_query_state(request: HttpRequest) -> dict[str, str]:
    search_query = request.GET.get("q") or request.POST.get("q") or ""
    selected_category = request.GET.get("category") or request.POST.get("category") or ""
    modal = request.GET.get("modal") or request.POST.get("modal") or ""
    return {
        "q": search_query.strip(),
        "category": selected_category.strip(),
        "modal": modal.strip(),
    }


def index_url_with_state(request: HttpRequest, **overrides: str) -> str:
    state = get_query_state(request)
    for key, value in overrides.items():
        state[key] = value

    cleaned_state = {key: value for key, value in state.items() if value}
    base_url = reverse("cafeteria:index")
    return f"{base_url}?{urlencode(cleaned_state)}" if cleaned_state else base_url


def redirect_to_index(request: HttpRequest, **overrides: str) -> HttpResponse:
    return redirect(index_url_with_state(request, **overrides))


def set_modal_feedback(request: HttpRequest, feedback_type: str, text: str) -> None:
    request.session["modal_feedback"] = {
        "type": feedback_type,
        "text": text,
    }
    request.session.modified = True


def pop_modal_feedback(request: HttpRequest) -> dict | None:
    if "modal_feedback" not in request.session:
        return None

    return request.session.pop("modal_feedback")
