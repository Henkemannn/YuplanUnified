from portal.department.models import (
    DepartmentPortalWeekPayload,
    validate_portal_week_payload,
)


def test_department_portal_week_payload_structure():
    payload: DepartmentPortalWeekPayload = {
        "department_id": "11111111-2222-3333-4444-555555555555",
        "department_name": "Avd 1",
        "site_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "site_name": "Midsommargården",
        "year": 2025,
        "week": 47,
        "facts": {
            "note": "Inga risrätter",
            "residents_default_lunch": 10,
            "residents_default_dinner": 8,
        },
        "progress": {"days_with_choice": 1, "total_days": 7},
        "etag_map": {
            "menu_choice": "W/\"menu-choice:dept:11111111:v4\"",
            "weekview": "W/\"weekview:dept:11111111:year:2025:week:47:v9\"",
        },
        "days": [
            {
                "date": "2025-11-17",
                "weekday_name": "Måndag",
                "menu": {
                    "lunch_alt1": "Köttbullar med potatis",
                    "lunch_alt2": "Fiskgratäng",
                    "dessert": "Pannacotta",
                    "dinner": "Smörgås och soppa",
                },
                "choice": {"selected_alt": "Alt1"},
                "flags": {"alt2_lunch": True},
                "residents": {"lunch": 10, "dinner": 8},
                "diets_summary": {
                    "lunch": [
                        {"diet_type_id": "gluten", "diet_name": "Gluten", "count": 2},
                        {"diet_type_id": "laktos", "diet_name": "Laktos", "count": 1},
                    ],
                    "dinner": [],
                },
            }
        ],
    }

    # Should not raise
    validate_portal_week_payload(payload)
