import asyncio, psycopg, socket, os
url = "postgresql://postgres:Keerkar0222%40@db.wnwyegaiiwudqaahjyme.supabase.co:5432/postgres"
print("resolve:", socket.getaddrinfo("db.wnwyegaiiwudqaahjyme.supabase.co", 5432))
async def main():
    try:
        c = await psycopg.AsyncConnection.connect(url, connect_timeout=20)
        async with c.cursor() as cur:
            await cur.execute("select version()")
            print("CONNECT OK:", (await cur.fetchone())[0][:60])
        await c.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
