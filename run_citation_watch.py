import argparse

import uvicorn

from citation_watch.citation_api import initialize


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the developer-tools citation collector")
    parser.add_argument("command", choices=["init", "serve"])
    args = parser.parse_args()
    if args.command == "init":
        initialize()
        print("citation collection ready")
        return
    uvicorn.run("citation_watch.citation_api:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

