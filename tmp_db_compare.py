import os, sqlite3, json
candidates = ['dev.db','instance/dev.db']
out=[]
for p in candidates:
    if not os.path.exists(p):
        continue
    info={'path':p,'size':os.path.getsize(p)}
    try:
        conn=sqlite3.connect(p)
        cur=conn.cursor()
        def cnt(t):
            try:
                return cur.execute(f'select count(*) from {t}').fetchone()[0]
            except Exception:
                return None
        info['weekview_residents_count']=cnt('weekview_residents_count')
        info['weekview_registrations']=cnt('weekview_registrations')
        info['departments']=cnt('departments')
        conn.close()
    except Exception as e:
        info['error']=str(e)
    out.append(info)
print(json.dumps(out, indent=2))
