"""Start the UnderCover Agent on one claim from the command line.

uv run -m agent CLM-1001
"""

import argparse

from dotenv import load_dotenv

from agent.agents import decide_claim


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim", help="the claim to work, such as CLM-1001")
    print(decide_claim(parser.parse_args().claim))


if __name__ == "__main__":
    main()
