from django.contrib import admin
from django.utils import timezone

from .models import MarketplaceOrder, TutorLedgerEntry, TutorPayoutRequest
from .services import apply_payout_paid


@admin.register(MarketplaceOrder)
class MarketplaceOrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'razorpay_order_id',
        'payer',
        'amount_gross',
        'platform_fee_amount',
        'tutor_credit_amount',
        'status',
        'paid_at',
    )
    list_filter = ('status',)
    raw_id_fields = ('engagement', 'payer')
    readonly_fields = ('created_at', 'paid_at', 'webhook_event_id')


@admin.register(TutorLedgerEntry)
class TutorLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'tutor_profile', 'amount', 'balance_after', 'description', 'created_at')
    list_filter = ('tutor_profile',)
    raw_id_fields = ('tutor_profile', 'marketplace_order', 'payout')
    readonly_fields = ('created_at',)


@admin.register(TutorPayoutRequest)
class TutorPayoutRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'tutor_profile', 'amount', 'status', 'bank_reference', 'paid_at', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('tutor_profile',)
    readonly_fields = ('created_at', 'paid_at')

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = (
                TutorPayoutRequest.objects.filter(pk=obj.pk)
                .values_list('status', flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        if obj.status == TutorPayoutRequest.Status.PAID:
            if not obj.paid_at:
                obj.paid_at = timezone.now()
                obj.save(update_fields=['paid_at'])
            if old_status != TutorPayoutRequest.Status.PAID:
                apply_payout_paid(obj)
