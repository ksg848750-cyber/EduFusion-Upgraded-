import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        # psycopg async cannot run on Windows' default ProactorEventLoop.
        loop="app.loop:selector_loop_factory",
    )