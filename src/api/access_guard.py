"""Common guards for APIs whose original authorization used fixed role lists."""
from fastapi import HTTPException
from src.models.enums import Permission as P
from src.services.auth import has_permission


def guard_request(user, request):
    path = request.url.path
    read = request.method == "GET"
    rules = {
        "/api/ocr": (P.OCR_READ, P.OCR_WRITE),
        "/api/inventory": (P.OCR_READ, P.OCR_WRITE),
        "/api/order-requests": (P.ORDER_READ, P.ORDER_WRITE),
        "/api/registration-links": (P.REGISTRATION_READ, P.REGISTRATION_WRITE),
        "/api/registrations": (P.REGISTRATION_READ, P.REGISTRATION_WRITE),
        "/api/registration-requests": (P.REGISTRATION_READ, P.REGISTRATION_WRITE),
        "/api/aggregation/sales": (P.INVOICE_READ, P.INVOICE_READ),
        "/api/aggregation/outsource": (P.PAYOUT_READ, P.PAYOUT_READ),
        "/api/dashboard": (P.DASHBOARD_READ, P.DASHBOARD_READ),
        "/api/invoices": (P.INVOICE_READ, P.INVOICE_READ),
        "/api/payouts": (P.PAYOUT_READ, P.PAYOUT_READ),
        "/api/price-sales": (P.PRICE_READ, P.PRICE_READ),
        "/api/price-outsource": (P.PRICE_READ, P.PRICE_READ),
        "/api/price-rules": (P.PRICE_READ, P.PRICE_READ),
        "/api/projects": (P.PROJECT_READ, P.PROJECT_READ),
        "/api/shift-slots": (P.SHIFT_READ, P.SHIFT_READ),
        "/api/assignments": (P.ASSIGNMENT_READ, P.ASSIGNMENT_READ),
        "/api/actuals": (P.ACTUAL_READ, P.ACTUAL_READ),
        "/api/expenses": (P.EXPENSE_READ, P.EXPENSE_READ),
    }
    for prefix, permissions in rules.items():
        if path == prefix or path.startswith(prefix + "/"):
            if not has_permission(user, permissions[0 if read else 1]):
                raise HTTPException(403, "この機能への権限がありません")
    # Bank information is not part of field management, even though MASTER_READ
    # is needed to resolve names on project/assignment screens.
    if "/bank-accounts" in path and not has_permission(user, P.PAYOUT_READ):
        raise HTTPException(403, "銀行口座情報への権限がありません")
