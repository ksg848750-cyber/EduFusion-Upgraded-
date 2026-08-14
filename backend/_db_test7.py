import asyncio, psycopg
ref = "wnwyegaiiwudqaahjyme"
regions = ["ap-south-1","us-east-1","us-west-1","eu-west-1","eu-central-1","ap-northeast-1","ap-southeast-1","ap-southeast-2","sa-east-1","ca-central-1"]
async def try_one(label, url):
    try:
        c = await psycopg.AsyncConnection.connect(url, connect_timeout=15)
        async with c.cursor() as cur:
            await cur.execute("select version()")
            print(label, "OK:", (await cur.fetchone())[0][:40])
        await c.close()
        return True
    except Exception as e:
        return False
async def main():
    for r in regions:
        url = f"postgresql://postgres.{ref}:Keerkar0222%40@aws-0-{r}.pooler.supabase.com:5432/postgres"
        ok = await try_one(r, url)
        if ok: break
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
