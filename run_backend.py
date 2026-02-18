import asyncio
import sys
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_backend")

async def main():
    if sys.platform == 'win32':
        logger.info("FORCING ProactorEventLoopPolicy for Windows...")
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    config = uvicorn.Config("backend.main:app", host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    
    logger.info("Starting Uvicorn Server...")
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
