import os
import sys

import httpx
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    url = os.environ.get("KEEPALIVE_URL")
    if not url:
        print("KEEPALIVE_URL is required", file=sys.stderr)
        return 1

    try:
        response = httpx.get(url, timeout=90, follow_redirects=True)
    except httpx.HTTPError as exc:
        print(f"Keepalive request failed: {exc}", file=sys.stderr)
        return 1

    status = response.status_code
    # A 4xx still proves the host woke up and handled the request.
    if status >= 500:
        print(f"Keepalive request reached host but returned {status}", file=sys.stderr)
        return 1

    print(f"Keepalive request sent successfully: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
