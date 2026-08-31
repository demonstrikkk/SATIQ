from openai import OpenAI
cli=OpenAI(base_url='http://localhost:11434/v1', api_key='ollama', timeout=30)
prompt='You are Satiq router. Classify Query: "Provide the bounding box for the forest patch" into ONE word from: vqa, grounding, change_vqa'
try:
    r=cli.chat.completions.create(model='qwen3.5:9b', messages=[{'role':'user','content': prompt}], temperature=0, max_tokens=50)
    print('response', repr((r.choices[0].message.content or '')[:800]))
    print('finish', r.choices[0].finish_reason)
    print('len', len(r.choices[0].message.content or ''))
    # Try native generate
    import urllib.request, json
    data=json.dumps({"model":"qwen3.5:9b","prompt":prompt,"stream":False}).encode()
    req=urllib.request.Request('http://localhost:11434/api/generate', data=data, headers={'Content-Type':'application/json'})
    r2=urllib.request.urlopen(req, timeout=20)
    j2=json.loads(r2.read().decode())
    print('native', j2['response'][:500])
except Exception as e:
    import traceback; traceback.print_exc()
