import asyncio
import websockets
import json

async def test():
    uri = "wss://ws.dexscreener.com/solana"
    try:
        async with websockets.connect(uri) as ws:
            print("✅ متصل بـ DexScreener - جاري الاستماع...")
            await ws.send(json.dumps({"type": "subscribe", "channel": "newPairs"}))
            async for msg in ws:
                print(msg)
                break
    except Exception as e:
        print(f"❌ خطأ: {e}")

asyncio.run(test())