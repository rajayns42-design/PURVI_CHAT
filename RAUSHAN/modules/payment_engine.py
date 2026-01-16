import razorpay
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET")

razor = razorpay.Client(
    auth=(os.getenv("RAZORPAY_KEY"), os.getenv("RAZORPAY_SECRET"))
)

PLANS = {
    "basic": 99,
    "gf": 199,
    "soulmate": 399,
    "lifetime": 999
}

def create_stripe_session(amount, user_id):
    return stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "inr",
                "product_data": {"name": "Girlfriend Bot Premium"},
                "unit_amount": amount * 100,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"https://t.me/YOUR_BOT?start=success_{user_id}",
        cancel_url=f"https://t.me/YOUR_BOT?start=cancel",
    )

def create_razorpay_order(amount):
    return razor.order.create({
        "amount": amount * 100,
        "currency": "INR",
        "payment_capture": 1
    })
