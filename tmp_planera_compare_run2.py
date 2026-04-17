import json
from dataclasses import asdict
from core.db import init_engine
from core.planera_v2.comparison import compare_current_planera_vs_v2_day

init_engine('sqlite:///dev.db', force=True)
scenario = {
    'tenant_id': 1,
    'site_id': 'site-null',
    'iso_date': '2025-03-03',
    'meal_key': 'lunch',
}
comp = compare_current_planera_vs_v2_day(
    tenant_id=scenario['tenant_id'],
    site_id=scenario['site_id'],
    iso_date=scenario['iso_date'],
    meal_key=scenario['meal_key'],
    departments=[('dep-A', 'dep-A')],
)
print(json.dumps({'scenario': scenario, 'comparison': asdict(comp)}, indent=2, sort_keys=True))
