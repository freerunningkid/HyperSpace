import sqlite3, json, time, uuid

db = sqlite3.connect('C:\\Users\\KID\\.zcode\\cli\\db\\db.sqlite')

# Get current session
sid = db.execute('SELECT id FROM session ORDER BY time_updated DESC LIMIT 1').fetchone()
if sid:
    print('Session:', sid[0])
else:
    print('No session')
    db.close()
    exit(1)

session_id = sid[0]

# Check column names
mcols = [d[1] for d in db.execute('PRAGMA table_info("message")').fetchall()]
pcols = [d[1] for d in db.execute('PRAGMA table_info("part")').fetchall()]
print('msg cols:', mcols)
print('part cols:', pcols)

# Get latest message to set parent
last_msg = db.execute('SELECT id FROM message WHERE session_id=? ORDER BY id DESC LIMIT 1', (session_id,)).fetchone()
if last_msg:
    print('Last msg:', last_msg[0])
    parent_id = last_msg[0]
else:
    parent_id = None
    
db.close()
print('Parent:', parent_id)
