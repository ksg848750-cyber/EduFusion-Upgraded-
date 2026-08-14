import asyncio, psycopg
def urlencode(s):
    import urllib.parse
    return urllib.parse.quote(s, safe="")
candidates = [
    ("bracketed", "postgresql://postgres:%5BKeerkar0222%40%5D@db.wnwyegaiiwudqaahjyme.supabase.co:5432/postgres"),
    ("plain",     "postgresql://postgres:Keerkar0222%40@db.wnwyegaiiwudqaahjyme.supabase.co:5432/postgres"),
]
async def try_conn(label, url):
    try:
        c = await psycopg.AsyncConnection.connect(url, connect_timeout=15)
        async with c.cursor() as cur:
            await cur.execute("select 1")
            await cur.fetchone()
        await c.close()
        print(label, "CONNECT OK")
    except Exception as e:
        print(label, "FAIL:", repr(e)[:120])
async def main():
    for label, url in candidates:
        await try_conn(label, url)
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
