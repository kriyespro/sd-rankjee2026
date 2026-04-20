from django.core.management.base import BaseCommand

from hometutor.models import DemoRequest, EngagementDispute, SessionAttendance, TutorEngagement, TutorProfile
from hometutor_payments.models import MarketplaceOrder, TutorLedgerEntry, TutorPayoutRequest
from users.models import CustomUser, Notification


class Command(BaseCommand):
    help = "Clear role dashboard demo seed data created by seed_role_dash_demo."

    def handle(self, *args, **options):
        usernames = [
            "demo_student",
            "demo_parent",
            "demo_tutor_1",
            "demo_tutor_2",
            "demo_city_admin",
            "demo_global_admin",
            "demo_tutor_pending",
        ]
        users = list(CustomUser.objects.filter(username__in=usernames))
        user_ids = [u.id for u in users]

        tutor_profiles = TutorProfile.objects.filter(user_id__in=user_ids)
        tutor_ids = list(tutor_profiles.values_list("id", flat=True))

        demo_qs = DemoRequest.objects.filter(
            tutor_id__in=tutor_ids
        ) | DemoRequest.objects.filter(
            requester_id__in=user_ids
        )
        demo_ids = list(demo_qs.values_list("id", flat=True).distinct())

        eng_qs = TutorEngagement.objects.filter(
            demo_request_id__in=demo_ids
        ) | TutorEngagement.objects.filter(
            tutor_profile_id__in=tutor_ids
        ) | TutorEngagement.objects.filter(
            student_id__in=user_ids
        )
        eng_ids = list(eng_qs.values_list("id", flat=True).distinct())

        order_qs = MarketplaceOrder.objects.filter(engagement_id__in=eng_ids)
        payout_qs = TutorPayoutRequest.objects.filter(tutor_profile_id__in=tutor_ids)
        TutorLedgerEntry.objects.filter(marketplace_order__in=order_qs).delete()
        TutorLedgerEntry.objects.filter(payout__in=payout_qs).delete()
        payout_qs.delete()
        order_qs.delete()
        SessionAttendance.objects.filter(engagement_id__in=eng_ids).delete()
        EngagementDispute.objects.filter(engagement_id__in=eng_ids).delete()
        TutorEngagement.objects.filter(id__in=eng_ids).delete()
        DemoRequest.objects.filter(id__in=demo_ids).delete()
        Notification.objects.filter(user_id__in=user_ids).delete()
        TutorProfile.objects.filter(id__in=tutor_ids).delete()
        CustomUser.objects.filter(id__in=user_ids).delete()

        self.stdout.write(self.style.SUCCESS("Role dashboard demo data cleared successfully."))
