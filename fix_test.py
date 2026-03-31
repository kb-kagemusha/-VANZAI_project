import re

t = open('tests/test_recalculation.py', 'r', encoding='utf-8').read()

# 残りの Actual( ... ) パターンを見つけて置き換え
pattern = r'actual = Actual\(\s+assignment_id=assignment\.id,\s+worker_id=worker\.id,\s+work_date=date\(2026, 1, 15\),\s+start_time=time\(9, 0\),\s+end_time=time\(17, 0\),\s+calc_minutes_total=480,\s+calc_minutes_break=0,\s+calc_minutes_billable=480,\s+applied_price_sales=Decimal\("(\d+)"\),\s+applied_price_outsource=Decimal\("(\d+)"\),\s+status=ActualStatus\.ACTIVE,\s+period_key="202601",\s+\)\s+db_session\.add\(actual\)\s+db_session\.flush\(\)'

def replacer(match):
    sales = match.group(1)
    outsource = match.group(2)
    return f'''actual = create_test_actual(
            db_session, assignment, project, worker, role,
            work_date=date(2026, 1, 15),
            price_sales=Decimal("{sales}"),
            price_outsource=Decimal("{outsource}"),
        )'''

t = re.sub(pattern, replacer, t)

open('tests/test_recalculation.py', 'w', encoding='utf-8').write(t)
print('Updated')
