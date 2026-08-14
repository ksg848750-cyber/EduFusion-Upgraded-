import asyncio, psycopg
ref = "wnwyegaiiwudqaahjyme"
regions = ["us-east-1","us-west-1","eu-central-1","eu-west-1","eu-west-2","ap-south-1","ap-northeast-1","ap-southeast-1","ap-southeast-2","sa-east-1","ca-central-1","us-east-2","us-west-2","eu-north-1","ap-east-1"]
async def try_one(label, url):
    try:
        c = await psycopg.AsyncConnection.connect(url, connect_timeout=12, sslmode="require")
        async with c.cursor() as cur:
            await cur.execute("select version()")
            print(label, "OK:", (await cur.fetchone())[0][:40])
        await c.close()
        return True
    except Exception as e:
        msg = str(e)
        if "ENOTFOUND" in msg or "tenant" in msg.lower():
            print(label, "no-tenant")
        elif "timeout" in msg.lower() or "timed" in msg.lower():
            print(label, "timeout")
        else:
            print(label, "other:", msg[:80])
        return False
async def main():
    for r in regions:
        url = f"postgresql://postgres.{ref}:Keerkar0222%40@aws-0-{r}.pooler.supabase.com:5432/postgres"
        if await try_one(r, url): break
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
