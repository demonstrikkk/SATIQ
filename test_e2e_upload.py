import urllib.request, json, mimetypes, uuid, pathlib, http.client, io, time

# Login
data=json.dumps({'username':'demo','password':'demo'}).encode()
req=urllib.request.Request('http://127.0.0.1:4000/api/auth/login', data=data, headers={'Content-Type':'application/json'})
r=urllib.request.urlopen(req, timeout=5)
j=json.loads(r.read().decode())
token=j['token']
print('login ok', j['user'])

# Upload
boundary = '----WebKitFormBoundary' + uuid.uuid4().hex[:16]
filepath = r'C:\Users\aarav\Downloads\SATIQ\test_user_image.png'
filename = 'test_user_image.png'
with open(filepath, 'rb') as f:
    file_data = f.read()
body = io.BytesIO()
body.write(f'--{boundary}\r\n'.encode())
body.write(f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode())
body.write(f'Content-Type: {mimetypes.guess_type(filename)[0] or "image/png"}\r\n\r\n'.encode())
body.write(file_data)
body.write(f'\r\n--{boundary}--\r\n'.encode())
body_bytes = body.getvalue()

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': f'multipart/form-data; boundary={boundary}',
}
conn = http.client.HTTPConnection('127.0.0.1', 4000, timeout=10)
conn.request('POST', '/api/upload', body_bytes, headers)
resp = conn.getresponse()
data = resp.read().decode()
print('upload status', resp.status)
print(data[:1200])
if resp.status != 200:
    exit(1)
j2 = json.loads(data)
asset = j2['asset']
asset_id = asset['asset_id']
print(f"asset_id: {asset_id}")
print(f"url: {asset['url']}")
# Check gateway storage
import pathlib
gw_path = pathlib.Path(r"C:\Users\aarav\Downloads\SATIQ\gateway\upload") / asset['filename']
print(f"gateway file exists: {gw_path.exists()} {gw_path}")
# Check orchestrator ingest
import pathlib as pl
ingest_base = pl.Path(r"C:\Users\aarav\Downloads\SATIQ\orchestrator\storage\ingest")
found = list(ingest_base.rglob("*.tif"))
print(f"orchestrator ingest found: {len(found)} {found[:2]}")

# Query via gateway
time.sleep(1)
query = "Describe the land cover in this image in detail"
payload = json.dumps({"query": query, "asset_ids": [asset_id]}).encode()
req2 = urllib.request.Request('http://127.0.0.1:4000/api/query', data=payload, headers={'Content-Type':'application/json', 'Authorization': f'Bearer {token}'})
try:
    r2 = urllib.request.urlopen(req2, timeout=10)
    j3 = json.loads(r2.read().decode())
    print(f"query created: {j3}")
    exec_id = j3['execution_id']
    # Poll execution
    for i in range(30):
        time.sleep(2)
        req3 = urllib.request.Request(f'http://127.0.0.1:4000/api/query/{exec_id}/stream', headers={'Authorization': f'Bearer {token}', 'Accept': 'text/event-stream'})
        # Use polling via execution manager's GET /api/query/{id} is via gateway? Actually gateway's stream is SSE
        # For simplicity, poll orchestrator directly
        try:
            # Try to get orchestrator task via gateway's execution events? Use gateway's execution polling via direct fetch of orchestrator
            # Instead, poll gateway's execution via its own API? The gateway's execution manager stores events.
            # We can poll the gateway's stream endpoint with fetch
            import http.client
            conn2 = http.client.HTTPConnection('127.0.0.1', 4000, timeout=10)
            conn2.request('GET', f'/api/query/{exec_id}/stream', headers={'Authorization': f'Bearer {token}'})
            # This is SSE, not easy to parse via http.client, so just check via orchestrator's task status
            # Find orchestrator session_id from gateway's execution? The gateway's execution forwards to orchestrator with session_id = exec_id? Actually agentic provider creates session_id and returns it.
            # We can list orchestrator tasks by trying to fetch from orchestrator directly via asset query
            pass
        except Exception as e:
            print(f"poll error {e}")
        # Check orchestrator health for tasks
        try:
            import urllib.request as ur
            # List orchestrator executions via direct query to orchestrator's task list? Not available, so check gateway's execution status via direct memory?
            # For now, just wait and then check gateway's execution final status via polling its own endpoint (we need to use the gateway's execution manager's status)
            # The gateway's execution status can be inferred by trying to GET the stream again
            pass
        except Exception:
            pass
        print(f"poll {i} waiting...")
    print("done polling")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"query failed {e}")
