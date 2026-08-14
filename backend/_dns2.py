import json, urllib.request
for host in ["db.wnwyegaiiwudqaahjyme.supabase.co"]:
    url = "https://dns.google/resolve?name=" + host + "&type=A"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    print(host, "->", data.get("Answer", "NO A RECORD"))
