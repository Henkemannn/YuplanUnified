python check_tenants_sites.py
Write-Host "----"
python -c "import sqlite3; con=sqlite3.connect('dev.db'); cur=con.cursor(); cur.execute('select count(*) from tenants'); print('tenants_count=', cur.fetchone()[0]); cur.execute('select count(*) from sites'); print('sites_count=', cur.fetchone()[0]); con.close()"