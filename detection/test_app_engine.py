
from app_engine import detect_app


brand = {
    "name": "AcmePay",
    "official_package_ids": ["com.acme.pay"],
    "official_publishers": ["Acme Technologies"],
    "official_descriptions": [
        "Official mobile payment application for AcmePay customers"
    ],
}

test_apps = [
    {
        "app_id": "app_1",
        "name": "AcmePay",
        "publisher": "Acme Technologies",
        "description": "Official mobile payment application for AcmePay customers",
        "package_id": "com.acme.pay",
    },
    {
        "app_id": "app_2",
        "name": "AcmePay Support",
        "publisher": "Unknown Publisher",
        "description": "Official mobile payment application for AcmePay customers",
        "package_id": "com.unknown.acmepay",
    },
    {
        "app_id": "app_3",
        "name": "Garden Planner",
        "publisher": "Green Apps",
        "description": "Plan and organize your garden",
        "package_id": "com.green.garden",
    },
]

for app in test_apps:
    result = detect_app(app, brand)
    print(result["app_id"], result["classification"], result["risk_score"])
    print("Reasons:", result["reasons"])
    print()
