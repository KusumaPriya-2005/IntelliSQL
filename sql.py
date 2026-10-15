"""Optional CLI bootstrap. Safe to run repeatedly: never overwrites existing data."""
from db_manager import DB_PATH, initialize_if_needed

if __name__ == "__main__":
    result = initialize_if_needed(DB_PATH)
    print(result.status, "-", result.message)
