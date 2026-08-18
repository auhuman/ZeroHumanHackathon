#!/usr/bin/env python3
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from clients.terac_client import TeracClient

async def main():
    api_key = os.getenv("TERAC_API_KEY")
    if not api_key:
        print("Error: TERAC_API_KEY environment variable not set.")
        sys.exit(1)

    print("Initializing Terac Client...")
    client = TeracClient(api_key=api_key)
    print("Deleting all opportunities in Terac account via Terac MCP...")
    summary = await client.delete_all_opportunities()

    print("\n--- Deletion Summary ---")
    print(f"Total Deleted: {summary['deleted_count']}")
    print(f"Total Stopped: {summary['stopped_count']}")
    print(f"Total Failed:  {summary['failed_count']}")

if __name__ == "__main__":
    asyncio.run(main())
