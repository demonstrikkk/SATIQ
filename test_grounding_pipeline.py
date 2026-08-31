import urllib.request, json, time
asset_id='asset_image-1788180086860-735035344.png'
data=json.dumps({'query':'Provide the bounding box for the forest patch','asset_ids':[asset_id],'assets':[{'asset_id':asset_id,'modality':'optical','crs':'EPSG:32617','gsd':10}]}).encode()
req=urllib.request.Request('http://127.0.0.1:8000/api/v1/task', data=data, headers={'Content-Type':'application/json'})
r=urllib.request.urlopen(req, timeout=10)
j=json.loads(r.read().decode())
sid=j['session_id']
print('sid', sid)
for i in range(30):
    time.sleep(1)
    r2=urllib.request.urlopen(f'http://127.0.0.1:8000/api/v1/task/{sid}', timeout=5)
    j2=json.loads(r2.read().decode())
    status=j2.get('status')
    events=j2.get('events',[])
    print(f"poll {i} status {status} events {len(events)}")
    if status in ('completed','failed'):
        import json as js
        print(js.dumps(j2, indent=2)[:5000])
        res=j2.get('result') or {}
        print('---answer---')
        print(res.get('answer_text','')[:1000] if res else 'no result')
        print('---artifacts---')
        print(res.get('artifacts'))
        print('---error---')
        print(res.get('error'))
        break
