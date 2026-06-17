import sqlite3, json, time, uuid

db = sqlite3.connect('C:\\Users\\KID\\.zcode\\cli\\db\\db.sqlite')
session_id = 'sess_1523ad43-912a-483c-85ce-e3b7b8fdf06e'
parent_id = None

# Get parent (last user msg)
r = db.execute('SELECT id FROM message WHERE session_id=? ORDER BY id DESC LIMIT 1', (session_id,)).fetchone()
if r:
    parent_id = r[0]
    print('Parent:', parent_id)

# Generate IDs
ts = int(time.time() * 1000)
msg_id = 'msg_mqix_' + uuid.uuid4().hex[:20]

# Insert message
msg_data = json.dumps({
    'role': 'assistant',
    'time': {'created': ts, 'completed': ts + 500},
    'parentID': parent_id,
    'modelID': 'deepseek-v4-flash',
    'providerID': 'deepseek',
    'mode': 'build',
    'agent': 'zcode-agent',
    'path': {'cwd': 'D:\\Agent-ZCode', 'root': 'D:\\Agent-ZCode'},
    'cost': 0,
    'tokens': {'total': 100, 'input': 50, 'output': 50, 'reasoning': 0, 'cache': {'read': 0, 'write': 0}},
    'finish': 'stop'
})

db.execute('INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?,?,?,?,?)',
    (msg_id, session_id, ts, ts + 500, msg_data))

# Insert parts (step-start + text + reasoning + step-finish)
part_id1 = 'part_mqix_' + uuid.uuid4().hex[:20]
part1 = json.dumps({'type': 'step-start'})
db.execute('INSERT INTO part (id, message_id, session_id, time_created, time_updated, data) VALUES (?,?,?,?,?,?)',
    (part_id1, msg_id, session_id, ts, ts, part1))

part_id2 = 'part_mqix_' + uuid.uuid4().hex[:20]
text = '这是一条从 SQLite 直接写入的测试消息~ 😊 以后我给你发消息不用抢焦点，直接写数据库就行。'
part2 = json.dumps({'type': 'text', 'text': text})
db.execute('INSERT INTO part (id, message_id, session_id, time_created, time_updated, data) VALUES (?,?,?,?,?,?)',
    (part_id2, msg_id, session_id, ts, ts + 300, part2))

part_id3 = 'part_mqix_' + uuid.uuid4().hex[:20]
part3 = json.dumps({'type': 'step-finish', 'reason': 'stop', 'cost': 0, 'tokens': {'total': 100, 'input': 50, 'output': 50}})
db.execute('INSERT INTO part (id, message_id, session_id, time_created, time_updated, data) VALUES (?,?,?,?,?,?)',
    (part_id3, msg_id, session_id, ts + 300, ts + 500, part3))

db.commit()
db.close()
print('Message inserted:', msg_id)
print('Text:', text[:100])
