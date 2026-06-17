import sqlite3, json
db = sqlite3.connect('C:\\Users\\KID\\.zcode\\cli\\db\\db.sqlite')
db.text_factory = str

# Get latest assistant text
r = db.execute("""
    SELECT p.data FROM part p
    JOIN message m ON p.message_id = m.id
    WHERE json_extract(p.data, '$.type') = 'text'
    AND json_extract(m.info, '$.role') = 'assistant'
    ORDER BY p.id DESC LIMIT 1
""").fetchone()
if r:
    d = json.loads(r[0])
    text = d.get('text', '')
    print(text[:500])
else:
    print('(no messages yet)')

db.close()
