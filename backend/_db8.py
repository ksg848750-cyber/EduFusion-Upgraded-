import asyncio, psycopg
ref = "wnwyegaiiwudqaahjyme"
candidates = [
  ("ap-south-1:5432", f"postgresql://postgres.{ref}:Keerkar0222%40@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"),
  ("ap-south-1:6543", f"postgresql://postgres.{ref}:Keerkar0222%40@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"),
]
async def main():
    for label, url in candidates:
        try:
            c = await psycopg.AsyncConnection.connect(url, connect_timeout=20, sslmode="require")
            async with c.cursor() as cur:
                await cur.execute("select version()")
                print(label, "OK:", (await cur.fetchone())[0][:50])
            await c.close()
        except Exception as e:
            print(label, "FAIL:", str(e)[:200])
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
