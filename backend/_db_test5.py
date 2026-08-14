import asyncio, psycopg
urls = [
  ("pooler-5678", "postgresql://postgres:Keerkar0222%40@aws-0-us-east-1.pooler.supabase.com:6543/postgres"),
  ("pooler-5432", "postgresql://postgres:Keerkar0222%40@aws-0-us-east-1.pooler.supabase.com:5432/postgres"),
]
async def main():
    for label, url in urls:
        try:
            c = await psycopg.AsyncConnection.connect(url, connect_timeout=20)
            async with c.cursor() as cur:
                await cur.execute("select version()")
                print(label, "OK:", (await cur.fetchone())[0][:50])
            await c.close()
        except Exception as e:
            print(label, "FAIL:", str(e)[:150])
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
