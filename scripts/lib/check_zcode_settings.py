import sqlite3, json
db = sqlite3.connect(r'C:\Users\KID\.zcode\cli\db\db.sqlite')
db.row_factory = sqlite3.Row
rows = db.execute('SELECT * FROM local_setting').fetchall()
print('Settings count:', len(rows))
for r in rows:
    d = dict(r)
    val = str(d['value'])[:80] if d['value'] else '(empty)'
    print(f'{d["namespace"]}:{d["key"]} = {val}')
db.close()
