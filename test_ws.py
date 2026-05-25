import asyncio
import websockets
import json

async def test():
    uri = "wss://pumpportal.fun/api/data"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"method": "subscribeNewToken"}))
        print("✅ متصل - جاري الاستماع...")
        async for msg in ws:
            data = json.loads(msg)
            if data.get("type") == "newToken":
                print(f"🆕 عملة جديدة: {data.get('name')} ({data.get('symbol')})")
                print(f"   عقد: {data.get('mint')}")
                break

asyncio.run(test())