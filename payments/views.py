import razorpay
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from django.utils import timezone
from .models import SubscriptionPlan, UserSubscription, PaymentOrder

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def plans_view(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    return render(request, 'payments/plans.jinja', {'plans': plans})

@login_required
def create_order(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    
    # Razorpay amount is in paise (100 paise = 1 INR)
    amount_paise = int(plan.price * 100)
    
    order_data = {
        'amount': amount_paise,
        'currency': 'INR',
        'payment_capture': '1' # Auto-capture
    }
    
    try:
        razorpay_order = client.order.create(data=order_data)
        
        # Save to our DB
        PaymentOrder.objects.create(
            user=request.user,
            plan=plan,
            amount=plan.price,
            razorpay_order_id=razorpay_order['id']
        )
        
        return JsonResponse({
            'order_id': razorpay_order['id'],
            'amount': amount_paise,
            'key': settings.RAZORPAY_KEY_ID,
            'name': plan.name,
            'description': plan.description,
            'user_name': request.user.username,
            'user_email': request.user.email
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@login_required
def verify_payment(request):
    if request.method == "POST":
        params_dict = {
            'razorpay_order_id': request.POST.get('razorpay_order_id'),
            'razorpay_payment_id': request.POST.get('razorpay_payment_id'),
            'razorpay_signature': request.POST.get('razorpay_signature')
        }
        
        try:
            # Verify signature
            client.utility.verify_payment_signature(params_dict)
            
            # Update PaymentOrder
            order = PaymentOrder.objects.get(razorpay_order_id=params_dict['razorpay_order_id'])
            order.razorpay_payment_id = params_dict['razorpay_payment_id']
            order.razorpay_signature = params_dict['razorpay_signature']
            order.status = 'SUCCESS'
            order.save()
            
            # Create/Update UserSubscription
            SubscriptionPlan = order.plan
            end_date = timezone.now() + timedelta(days=SubscriptionPlan.duration_days)
            
            sub, created = UserSubscription.objects.get_or_create(user=request.user)
            sub.plan = SubscriptionPlan
            sub.end_date = end_date
            sub.is_active = True
            sub.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            # Mark order as failed
            try:
                order = PaymentOrder.objects.get(razorpay_order_id=request.POST.get('razorpay_order_id'))
                order.status = 'FAILED'
                order.save()
            except:
                pass
            return JsonResponse({'status': 'failed', 'error': str(e)}, status=400)
    
    return HttpResponseBadRequest()
