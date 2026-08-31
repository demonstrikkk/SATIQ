import urllib.request, json, time, pathlib
asset_id = "asset_image-1788180086860-735035344.png"
data=json.dumps({'query':'Describe the land cover in this image in detail','asset_ids':[asset_id],'assets':[{'asset_id':asset_id,'modality':'optical','crs':'EPSG:32617','gsd':10}]}).encode()
req=urllib.request.Request('http://127.0.0.1:8000/api/v1/task', data=data, headers={'Content-Type':'application/json'})
try:
    r=urllib.request.urlopen(req, timeout=10)
    j=json.loads(r.read().decode())
    print('orchestrator task created', j)
    sid=j['session_id']
    for i in range(25):
        time.sleep(1)
        r2=urllib.request.urlopen(f'http://127.0.0.1:8000/api/v1/task/{sid}', timeout=5)
        j2=json.loads(r2.read().decode())
        print(f"poll {i} status {j2.get('status')} events {len(j2.get('events',[]))}")
        if j2.get('status') in ('completed','failed'):
            res=j2.get('result',{})
            print('final_result keys', list(res.keys()))
            import json as js
            print(js.dumps(res, indent=2)[:3000])
            if res.get('answer_text'):
                print('answer_text', res['answer_text'][:1000])
            print('error' if res.get('error') else 'no error')
            break
except Exception as e:
    import traceback
    traceback.print_exc()
