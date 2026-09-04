import urllib.request, json

HOST = 'https://inventory-hshaquib007.aws-ap-south-1.turso.io'
TOKEN = 'eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODg1NDAzMjcsImlkIjoiMDFhMDZkNGYtODYwMS03NzM4LWJhMWEtNDhiODY0MzFmMDBjIiwia2lkIjoib1llTExYZXBuaFA3SGhwMjZXODdyWWRENjRGdGFqb2hWZGxtUTR6bXpKUSIsInJpZCI6ImFlN2NlOTAzLTY0NjUtNDUzMi1iN2I2LWExMDljNjY5ZjhhZiJ9.KwEaeGTnAbEqRQq2A_8LbHDqLlUmR09PJP-iGEy7F1ezl-enmUs61VrSd4acpONS3kD6-Rwxj3qhX1WjjmYzDg'

tables = ['item_master','job_master','bom','bom_lines','grn','grn_lines','prn','prn_lines','pmi','pmi_lines']
for t in tables:
    payload = json.dumps({'requests':[{'type':'execute','stmt':{'sql':f'SELECT COUNT(*) FROM "{t}"'}}]}).encode()
    req = urllib.request.Request(f'{HOST}/v2/pipeline', data=payload, headers={'Authorization':f'Bearer {TOKEN}','Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        r = json.loads(resp.read().decode())
        count = r['results'][0]['response']['result']['rows'][0][0]
        print(f'  {t}: {count}')
