import os
from pathlib import Path


def main():
    target = Path(__file__).resolve().parent / "create_credit_requests.py"
    if target.exists():
        os.remove(target)
        print(f"{target.name} supprimé.")
    else:
        print(f"{target.name} n’existe pas.")


if __name__ == "__main__":
    main()
