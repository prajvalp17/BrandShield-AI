
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
    # 1. Official app: exact registered package ID
    {
        "app_id": "app_1",
        "name": "AcmePay",
        "publisher": "Acme Technologies",
        "description": (
            "Official mobile payment application for AcmePay customers"
        ),
        "package_id": "com.acme.pay",
        "expected": "official",
    },

    # 2. Brand lookalike with a copied description
    {
        "app_id": "app_2",
        "name": "AcmePay Support",
        "publisher": "Unknown Publisher",
        "description": (
            "Official mobile payment application for AcmePay customers"
        ),
        "package_id": "com.unknown.acmepay",
        "expected": "review",
    },

    # 3. Unrelated app from an unrecognized publisher
    {
        "app_id": "app_3",
        "name": "Garden Planner",
        "publisher": "Green Apps",
        "description": "Plan and organize your garden",
        "package_id": "com.green.garden",
        "expected": "low_risk",
    },

    # 4. Missing publisher and description
    {
        "app_id": "app_4",
        "name": "Weather Tracker",
        "package_id": "com.weather.tracker",
        "expected": "low_risk",
    },

    # 5. Some name similarity, but unrelated description
    {
        "app_id": "app_5",
        "name": "AcmePay Rewards",
        "publisher": "Unknown Publisher",
        "description": (
            "A casual game to earn points and unlock prizes"
        ),
        "package_id": "com.games.rewards",
        "expected": "low_risk",
    },
]


def run_tests():
    passed = 0
    failed = 0

    for test in test_apps:
        app = {
            key: value
            for key, value in test.items()
            if key != "expected"
        }

        expected = test["expected"]

        try:
            result = detect_app(app, brand)
            actual = result["classification"]
            score = result["risk_score"]

            success = actual == expected

            status = "PASS" if success else "FAIL"

            print(
                f"{status} | {test['app_id']} | "
                f"Expected: {expected} | "
                f"Actual: {actual} | Score: {score}"
            )
            print("Reasons:", result["reasons"])
            print()

            if success:
                passed += 1
            else:
                failed += 1

        except Exception as error:
            print(
                f"FAIL | {test['app_id']} | "
                f"Error: {error}"
            )
            print()
            failed += 1

    print("=" * 50)
    print(
        f"Results: {passed} passed, {failed} failed, "
        f"{len(test_apps)} total"
    )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    run_tests()
