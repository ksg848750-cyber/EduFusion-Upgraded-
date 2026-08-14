import asyncio, selectors, psycopg
async def main():
    try:
        c = await psycopg.AsyncConnection.connect(
            "postgresql://postgres:[Keerkar0222@]@db.wnwyegaiiwudqaahjyme.supabase.co:5432/postgres",
            connect_timeout=15)
        async with c.cursor() as cur:
            await cur.execute("select version();")
            row = await cur.fetchone()
            print("CONNECTED:", row[0][:60])
        await c.close()
    except Exception as e:
        print("FAILED:", repr(e))
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
