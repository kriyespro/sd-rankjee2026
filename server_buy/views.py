import logging
import uuid
from decimal import Decimal

import razorpay.errors as rz_errors
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from payments.services import get_razorpay_client, make_dummy_order_id, razorpay_dummy_mode
from users.models import CustomUser

from .forms import StudentServerBuyForm
from .models import ServerPackage, StudentServerOrder
from .services import quote_for_package_id

logger = logging.getLogger(__name__)


def _is_student(user) -> bool:
    return getattr(user, "role", None) == CustomUser.Role.STUDENT


def _student_only(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('users:login')}?next={request.path}")
    if not _is_student(request.user):
        return HttpResponseForbidden("This page is only for student accounts.")
    return None


def _student_only_api(request):
    """For fetch/JSON endpoints: never return HTML redirects or plain 403 bodies."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated. Refresh the page and sign in again."}, status=401)
    if not _is_student(request.user):
        return JsonResponse({"error": "This checkout is only for student accounts."}, status=403)
    return None


def _pricing_snapshot_json_safe(quote: dict) -> dict:
    """JSONField-safe copy (Decimals and similar types)."""

    def _conv(o):
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, dict):
            return {k: _conv(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_conv(v) for v in o]
        return o

    return _conv(quote)


def _quote_from_request(request):
    return quote_for_package_id(request.GET.get("package"))


def _selection_complete(get_dict) -> bool:
    return bool((get_dict.get("package") or "").strip())


@login_required
@require_GET
def checkout(request):
    gate = _student_only(request)
    if gate:
        return gate

    packages = list(ServerPackage.objects.filter(is_active=True).order_by("sort_order", "id"))
    if not packages:
        return render(
            request,
            "server_buy/checkout.jinja",
            {
                "form": None,
                "packages": [],
                "pricing_missing": True,
                "payment_dummy": razorpay_dummy_mode(),
                "show_admin_hint": request.user.is_superuser,
                "admin_packages_url": "/sd/server_buy/serverpackage/",
                "admin_orders_url": "/sd/server_buy/studentserverorder/",
            },
        )

    quote = None
    if _selection_complete(request.GET):
        try:
            quote = _quote_from_request(request)
        except ValidationError:
            quote = None

    return render(
        request,
        "server_buy/checkout.jinja",
        {
            "packages": packages,
            "pricing_missing": False,
            "payment_dummy": razorpay_dummy_mode(),
            "quote": quote,
            "verify_url": reverse("server_buy:verify_payment"),
            "create_order_url": reverse("server_buy:create_order"),
            "quote_url": reverse("server_buy:quote_partial"),
            "success_url": reverse("dashboard:index") + "?server_paid=1",
            "show_admin_hint": request.user.is_superuser,
            "admin_packages_url": "/sd/server_buy/serverpackage/",
            "admin_orders_url": "/sd/server_buy/studentserverorder/",
        },
    )


@login_required
@require_GET
def quote_partial(request):
    gate = _student_only(request)
    if gate:
        return gate

    if not _selection_complete(request.GET):
        return render(
            request,
            "server_buy/partials/_quote.jinja",
            {"quote": None, "error": None, "incomplete": True},
        )

    try:
        quote = _quote_from_request(request)
    except ValidationError as exc:
        err = exc.messages[0] if hasattr(exc, "messages") else str(exc)
        return render(
            request,
            "server_buy/partials/_quote.jinja",
            {"quote": None, "error": err},
        )

    return render(
        request,
        "server_buy/partials/_quote.jinja",
        {"quote": quote, "error": None},
    )


@require_POST
def create_order(request):
    # Do not use @login_required here — it redirects to HTML login and breaks fetch().json().
    gate = _student_only_api(request)
    if gate:
        return gate

    try:
        return _create_order_body(request)
    except Exception as exc:
        logger.exception("server_buy create_order unexpected error: %s", exc)
        return JsonResponse(
            {"error": "Server error while creating the payment order. Please try again."},
            status=500,
        )


def _create_order_body(request):
    form = StudentServerBuyForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"error": form.errors.as_text()}, status=400)

    pkg = form.cleaned_data["package"]
    try:
        quote = quote_for_package_id(pkg.id)
    except ValidationError as exc:
        msg = exc.messages[0] if hasattr(exc, "messages") else str(exc)
        return JsonResponse({"error": msg}, status=400)

    total_inr = quote["total_inr"]
    amount_paise = int(total_inr * 100)
    if amount_paise < 100:
        return JsonResponse(
            {"error": "Total must be at least ₹1 (100 paise) for Razorpay checkout."},
            status=400,
        )

    domain_name = form.cleaned_data["domain_name"].strip()
    desc = f"{quote['title']} — {domain_name}"
    snapshot = _pricing_snapshot_json_safe(quote)

    if razorpay_dummy_mode():
        rid = make_dummy_order_id()
        try:
            StudentServerOrder.objects.create(
                user=request.user,
                domain_name=domain_name,
                package=pkg,
                total_inr=total_inr,
                pricing_snapshot=snapshot,
                razorpay_order_id=rid,
            )
        except Exception as exc:
            logger.exception("server_buy create_order DB error (dummy): %s", exc)
            return JsonResponse(
                {"error": "Could not save your order. Try again or contact support."},
                status=500,
            )
        return JsonResponse(
            {
                "checkout_mode": "dummy",
                "order_id": rid,
                "amount": amount_paise,
                "currency": "INR",
                "key": "rzp_test_DUMMYLOCAL",
                "name": "RankJee — dedicated server",
                "description": desc,
                "user_name": request.user.username,
                "user_email": request.user.email or "",
            }
        )

    client = get_razorpay_client()
    if not client:
        return JsonResponse({"error": "Razorpay is not configured."}, status=400)

    receipt = f"srv_{uuid.uuid4().hex}"[:40]
    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": "1",
    }
    try:
        razorpay_order = client.order.create(data=order_data)
    except rz_errors.BadRequestError as e:
        msg = str(e)
        lower = msg.lower()
        if any(
            w in lower
            for w in ("authentication", "credential", "unauthorized", "not authorised")
        ):
            return JsonResponse({"error": msg}, status=401)
        return JsonResponse({"error": msg}, status=400)
    except (rz_errors.GatewayError, rz_errors.ServerError) as e:
        return JsonResponse({"error": str(e)}, status=500)

    try:
        StudentServerOrder.objects.create(
            user=request.user,
            domain_name=domain_name,
            package=pkg,
            total_inr=total_inr,
            pricing_snapshot=snapshot,
            razorpay_order_id=razorpay_order["id"],
        )
    except Exception as exc:
        logger.exception("server_buy create_order DB error (live): %s", exc)
        return JsonResponse(
            {"error": "Could not save your order. Try again or contact support."},
            status=500,
        )
    return JsonResponse(
        {
            "checkout_mode": "live",
            "order_id": razorpay_order["id"],
            "amount": amount_paise,
            "currency": razorpay_order.get("currency", "INR"),
            "key": settings.RAZORPAY_KEY_ID,
            "name": "RankJee — dedicated server",
            "description": desc,
            "user_name": request.user.username,
            "user_email": request.user.email or "",
        }
    )


@require_POST
def verify_payment(request):
    gate = _student_only_api(request)
    if gate:
        return gate

    params_dict = {
        "razorpay_order_id": request.POST.get("razorpay_order_id"),
        "razorpay_payment_id": request.POST.get("razorpay_payment_id"),
        "razorpay_signature": request.POST.get("razorpay_signature"),
    }
    if not params_dict["razorpay_order_id"]:
        return JsonResponse({"status": "failed", "error": "Missing order id"}, status=400)

    try:
        order = StudentServerOrder.objects.get(razorpay_order_id=params_dict["razorpay_order_id"])
    except StudentServerOrder.DoesNotExist:
        return JsonResponse({"status": "failed", "error": "Order not found"}, status=400)

    if order.user_id != request.user.id:
        return JsonResponse({"status": "failed", "error": "Forbidden"}, status=403)

    if order.status != StudentServerOrder.Status.PENDING:
        return JsonResponse({"status": "success", "message": "Already processed"})

    if razorpay_dummy_mode():
        order.razorpay_payment_id = params_dict["razorpay_payment_id"] or "pay_dummy"
        order.razorpay_signature = params_dict["razorpay_signature"] or "dummy"
        order.status = StudentServerOrder.Status.SUCCESS
        order.save(
            update_fields=["razorpay_payment_id", "razorpay_signature", "status", "updated_at"]
        )
        return JsonResponse({"status": "success"})

    client = get_razorpay_client()
    if not client:
        return JsonResponse({"status": "failed", "error": "Razorpay not configured"}, status=400)

    if not params_dict["razorpay_payment_id"] or not params_dict["razorpay_signature"]:
        return JsonResponse(
            {"status": "failed", "error": "Missing payment id or signature"},
            status=400,
        )

    try:
        client.utility.verify_payment_signature(params_dict)
    except rz_errors.SignatureVerificationError as e:
        order.status = StudentServerOrder.Status.FAILED
        order.save(update_fields=["status", "updated_at"])
        return JsonResponse({"status": "failed", "error": str(e)}, status=400)

    order.razorpay_payment_id = params_dict["razorpay_payment_id"]
    order.razorpay_signature = params_dict["razorpay_signature"]
    order.status = StudentServerOrder.Status.SUCCESS
    order.save(
        update_fields=[
            "razorpay_payment_id",
            "razorpay_signature",
            "status",
            "updated_at",
        ]
    )
    return JsonResponse({"status": "success"})
