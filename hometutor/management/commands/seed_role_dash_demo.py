from decimal import Decimal
from datetime import timedelta
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.utils import timezone

from hometutor.models import (
    DemoRequest,
    EngagementDispute,
    SessionAttendance,
    TutorEngagement,
    TutorProfile,
)
from hometutor_payments.models import MarketplaceOrder
from hometutor_payments.services import apply_marketplace_payment_success
from users.models import CustomUser, Notification


class Command(BaseCommand):
    help = "Seed realistic role dashboard demo flow data (idempotent)."

    def handle(self, *args, **options):
        now = timezone.now()

        # Core demo users for all dashboard roles.
        student, _ = CustomUser.objects.get_or_create(
            username="demo_student",
            defaults={
                "email": "demo_student@example.com",
                "role": CustomUser.Role.STUDENT,
                "state": "GJ",
            },
        )
        parent, _ = CustomUser.objects.get_or_create(
            username="demo_parent",
            defaults={
                "email": "demo_parent@example.com",
                "role": CustomUser.Role.PARENT,
                "state": "GJ",
            },
        )
        tutor_user_1, _ = CustomUser.objects.get_or_create(
            username="demo_tutor_1",
            defaults={
                "email": "demo_tutor_1@example.com",
                "role": CustomUser.Role.TUTOR,
                "state": "GJ",
            },
        )
        tutor_user_2, _ = CustomUser.objects.get_or_create(
            username="demo_tutor_2",
            defaults={
                "email": "demo_tutor_2@example.com",
                "role": CustomUser.Role.TUTOR,
                "state": "GJ",
            },
        )
        city_admin, _ = CustomUser.objects.get_or_create(
            username="demo_city_admin",
            defaults={
                "email": "demo_city_admin@example.com",
                "role": CustomUser.Role.CITY_ADMIN,
                "state": "GJ",
            },
        )
        global_admin, _ = CustomUser.objects.get_or_create(
            username="demo_global_admin",
            defaults={
                "email": "demo_global_admin@example.com",
                "role": CustomUser.Role.GLOBAL_ADMIN,
                "state": "DL",
            },
        )

        # Keep password simple for local testing accounts.
        for u in [student, parent, tutor_user_1, tutor_user_2, city_admin, global_admin]:
            if not u.has_usable_password():
                u.set_password("test1234")
                u.save(update_fields=["password"])

        # Tutor listings linked to tutor users.
        tutor_1, _ = TutorProfile.objects.get_or_create(
            user=tutor_user_1,
            defaults={
                "display_name": "Rahul Sharma",
                "slug": "rahul-sharma-demo",
                "city": "Ahmedabad",
                "area": "Satellite",
                "pincode": "380015",
                "subjects": "Math, Physics",
                "teaching_mode": TutorProfile.TeachingMode.HYBRID,
                "languages": "English, Hindi, Gujarati",
                "classes_label": "Class 9-12 · CBSE",
                "teaches_from": 9,
                "teaches_to": 12,
                "fee_label": "from ₹6500/mo",
                "bio": "I help students improve in Math and Physics through structured practice.",
                "rating_display": Decimal("4.8"),
                "reviews_count": 42,
                "verification_status": TutorProfile.VerificationStatus.APPROVED,
                "is_featured_home": True,
            },
        )
        tutor_2, _ = TutorProfile.objects.get_or_create(
            user=tutor_user_2,
            defaults={
                "display_name": "Priya Desai",
                "slug": "priya-desai-demo",
                "city": "Ahmedabad",
                "area": "Bodakdev",
                "pincode": "380054",
                "subjects": "Chemistry, Biology",
                "teaching_mode": TutorProfile.TeachingMode.ONLINE,
                "languages": "English, Hindi",
                "classes_label": "Class 10-12 · CBSE/NEET",
                "teaches_from": 10,
                "teaches_to": 12,
                "fee_label": "from ₹7200/mo",
                "bio": "Focused NEET foundation mentoring for Biology and Chemistry.",
                "rating_display": Decimal("4.7"),
                "reviews_count": 35,
                "verification_status": TutorProfile.VerificationStatus.APPROVED,
                "is_featured_home": True,
            },
        )

        # Pending verification profile for city/global admin queues.
        draft_user, _ = CustomUser.objects.get_or_create(
            username="demo_tutor_pending",
            defaults={
                "email": "demo_tutor_pending@example.com",
                "role": CustomUser.Role.TUTOR,
                "state": "GJ",
            },
        )
        pending_tutor, _ = TutorProfile.objects.get_or_create(
            user=draft_user,
            defaults={
                "display_name": "Karan Patel",
                "slug": "karan-patel-pending",
                "city": "Ahmedabad",
                "area": "Navrangpura",
                "subjects": "English, Social Science",
                "teaching_mode": TutorProfile.TeachingMode.OFFLINE,
                "languages": "English, Hindi, Gujarati",
                "classes_label": "Class 6-10",
                "teaches_from": 6,
                "teaches_to": 10,
                "fee_label": "from ₹4800/mo",
                "verification_status": TutorProfile.VerificationStatus.PENDING,
            },
        )
        TutorProfile.objects.filter(pk=pending_tutor.pk).update(updated_at=now - timedelta(days=3))

        # Student -> Tutor flow data: pending, accepted, declined.
        pending_demo, _ = DemoRequest.objects.get_or_create(
            tutor=tutor_1,
            requester=student,
            message="Need support in Algebra and Physics numericals.",
            defaults={"status": DemoRequest.Status.PENDING, "contact_phone": "9999991111"},
        )
        DemoRequest.objects.filter(pk=pending_demo.pk).update(created_at=now - timedelta(days=2))

        accepted_demo, _ = DemoRequest.objects.get_or_create(
            tutor=tutor_2,
            requester=student,
            message="Need NEET prep guidance.",
            defaults={
                "status": DemoRequest.Status.ACCEPTED,
                "scheduled_at": now + timedelta(days=1),
                "contact_phone": "9999992222",
            },
        )
        declined_demo, _ = DemoRequest.objects.get_or_create(
            tutor=tutor_2,
            requester=parent,
            message="Need weekend classes for child.",
            defaults={
                "status": DemoRequest.Status.DECLINED,
                "decline_reason": "No weekend slots available currently.",
                "contact_phone": "9999993333",
            },
        )

        # Engagements.
        engagement_active, _ = TutorEngagement.objects.get_or_create(
            demo_request=accepted_demo,
            defaults={
                "tutor_profile": tutor_2,
                "student": student,
                "status": TutorEngagement.Status.ACTIVE,
                "parent_confirmed_at": now - timedelta(days=1),
                "tutor_confirmed_at": now - timedelta(days=1),
                "mutual_confirmed_at": now - timedelta(days=1),
            },
        )
        TutorEngagement.objects.filter(pk=engagement_active.pk).update(status=TutorEngagement.Status.ACTIVE)

        # Sessions for attendance-driven metrics.
        SessionAttendance.objects.get_or_create(
            engagement=engagement_active,
            scheduled_for=now - timedelta(days=1),
            defaults={
                "status": SessionAttendance.AttendanceStatus.PRESENT,
                "tutor_note": "Good session; focus on organic chemistry revision.",
                "marked_by": tutor_user_2,
            },
        )
        SessionAttendance.objects.get_or_create(
            engagement=engagement_active,
            scheduled_for=now + timedelta(days=2),
            defaults={
                "status": SessionAttendance.AttendanceStatus.RESCHEDULED,
                "tutor_note": "Rescheduled to weekend due to exam.",
                "marked_by": tutor_user_2,
            },
        )

        # Dispute for admin queues.
        dispute, _ = EngagementDispute.objects.get_or_create(
            engagement=engagement_active,
            raised_by=student,
            reason="Need clarification on class timing confirmation.",
            defaults={"status": EngagementDispute.Status.OPEN},
        )
        EngagementDispute.objects.filter(pk=dispute.pk).update(updated_at=now - timedelta(hours=30))

        # Marketplace payment + tutor ledger.
        order, _ = MarketplaceOrder.objects.get_or_create(
            engagement=engagement_active,
            defaults={
                "payer": student,
                "amount_gross": Decimal("5000.00"),
                "platform_fee_amount": Decimal("750.00"),
                "tutor_credit_amount": Decimal("4250.00"),
                "razorpay_order_id": f"order_demo_{uuid4().hex[:18]}",
                "status": MarketplaceOrder.Status.PENDING,
            },
        )
        if order.status != MarketplaceOrder.Status.SUCCESS:
            apply_marketplace_payment_success(
                order,
                payment_id=f"pay_demo_{uuid4().hex[:14]}",
                signature="demo_signature",
            )

        # Parent pending payment sample (active engagement without successful order).
        parent_demo, _ = DemoRequest.objects.get_or_create(
            tutor=tutor_1,
            requester=parent,
            message="Parent-managed request for class 8 child.",
            defaults={
                "status": DemoRequest.Status.ACCEPTED,
                "scheduled_at": now + timedelta(days=2),
                "contact_phone": "9999994444",
            },
        )
        parent_eng, _ = TutorEngagement.objects.get_or_create(
            demo_request=parent_demo,
            defaults={
                "tutor_profile": tutor_1,
                "student": parent,
                "status": TutorEngagement.Status.ACTIVE,
                "parent_confirmed_at": now - timedelta(hours=12),
                "tutor_confirmed_at": now - timedelta(hours=12),
                "mutual_confirmed_at": now - timedelta(hours=12),
            },
        )
        TutorEngagement.objects.filter(pk=parent_eng.pk).update(status=TutorEngagement.Status.ACTIVE)

        # Notifications for timeline on student dashboard.
        Notification.objects.get_or_create(
            user=student,
            message="Your demo with Priya Desai is accepted. Confirm and proceed to payment.",
            defaults={"link": "/hometutor/my/requests/"},
        )
        Notification.objects.get_or_create(
            user=student,
            message="Session reminder: upcoming class in 24 hours.",
            defaults={"link": "/hometutor/my/requests/"},
        )

        self.stdout.write(self.style.SUCCESS("Role dashboard demo data seeded successfully."))
        self.stdout.write("Test accounts (password: test1234):")
        self.stdout.write(" - demo_student")
        self.stdout.write(" - demo_parent")
        self.stdout.write(" - demo_tutor_1")
        self.stdout.write(" - demo_tutor_2")
        self.stdout.write(" - demo_city_admin")
        self.stdout.write(" - demo_global_admin")
