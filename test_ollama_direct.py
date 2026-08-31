import ollama
print("testing ollama chat")
try:
    r=ollama.chat(model='qwen3.5:9b', messages=[{'role':'user','content':'Classify into ONE word: vqa, grounding, change_vqa. Query: Provide the bounding box for the forest patch'}])
    print(repr(r['message']['content'][:800]))
    print("done")
except Exception as e:
    import traceback
    traceback.print_exc()
