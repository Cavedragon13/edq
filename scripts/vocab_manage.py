#!/usr/bin/env python3
"""
Vocab Word Database Manager
============================

Manages the vocab word database with week/day sequencing.

Usage:
    vocab_manage.py add "reluctant" "you don't really want to"
    vocab_manage.py list
    vocab_manage.py list --week 12
    vocab_manage.py show reluctant
    vocab_manage.py export --week 12
    vocab_manage.py export-batch words.json
    vocab_manage.py delete reluctant
    vocab_manage.py stats
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Database file
DB_FILE = Path("/srv/containers/edq/data/vocab_database.json")

# Day sequence (Mon-Fri only, no weekends)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def load_database() -> Dict:
    """Load the word database from disk."""
    if not DB_FILE.exists():
        return {
            "metadata": {
                "created": datetime.utcnow().isoformat(),
                "last_modified": datetime.utcnow().isoformat(),
                "total_words": 0,
                "current_week": 1,
                "current_day": "Mon"
            },
            "words": []
        }

    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_database(db: Dict):
    """Save the word database to disk."""
    db["metadata"]["last_modified"] = datetime.utcnow().isoformat()
    db["metadata"]["total_words"] = len(db["words"])

    # Ensure data directory exists
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def spell_word(word: str) -> str:
    """Convert word to spelled-out format (e.g., 'cat' -> 'C-A-T')."""
    return "-".join(word.upper())


def get_next_position(db: Dict) -> tuple[int, str]:
    """Get the next available week and day position."""
    if not db["words"]:
        return 1, "Mon"

    # Get the last word's position
    last_word = db["words"][-1]
    last_week = last_word["week"]
    last_day = last_word["day"]

    # Advance to next day
    day_index = WEEKDAYS.index(last_day)

    if day_index < len(WEEKDAYS) - 1:
        # Same week, next day
        return last_week, WEEKDAYS[day_index + 1]
    else:
        # New week, Monday
        return last_week + 1, "Mon"


def find_word(db: Dict, word_id: str) -> Optional[Dict]:
    """Find a word by ID."""
    for word in db["words"]:
        if word["id"].lower() == word_id.lower():
            return word
    return None


def add_word(word: str, micro_context: str, week: Optional[int] = None, day: Optional[str] = None):
    """Add a new word to the database."""
    db = load_database()

    # Check for duplicates
    if find_word(db, word):
        print(f"❌ Word '{word}' already exists in database")
        return False

    # Auto-assign position if not specified
    if week is None or day is None:
        auto_week, auto_day = get_next_position(db)
        week = week or auto_week
        day = day or auto_day

    # Validate day
    if day not in WEEKDAYS:
        print(f"❌ Invalid day: {day}. Must be one of: {', '.join(WEEKDAYS)}")
        return False

    # Create word entry
    word_entry = {
        "id": word.lower(),
        "word": word,
        "spelling": spell_word(word),
        "micro_context_en": micro_context,
        "week": week,
        "day": day,
        "added": datetime.utcnow().isoformat(),
        "translations": {
            "es": None,
            "vi": None,
            "id": None
        },
        "translation_status": "pending"
    }

    db["words"].append(word_entry)
    db["metadata"]["current_week"] = week
    db["metadata"]["current_day"] = day

    save_database(db)

    print(f"✓ Added '{word}' to Week {week}, {day}")
    print(f"  Spelling: {word_entry['spelling']}")
    print(f"  Context: {micro_context}")

    return True


def list_words(week: Optional[int] = None, day: Optional[str] = None):
    """List all words, optionally filtered by week/day."""
    db = load_database()

    if not db["words"]:
        print("📭 No words in database yet")
        return

    words = db["words"]

    # Apply filters
    if week is not None:
        words = [w for w in words if w["week"] == week]

    if day is not None:
        words = [w for w in words if w["day"] == day]

    if not words:
        print(f"📭 No words found for filters: week={week}, day={day}")
        return

    # Print table
    print(f"\n{'Week':<6} {'Day':<5} {'Word':<15} {'Micro Context':<40} {'Status':<12}")
    print("─" * 80)

    for word in words:
        status_icon = {
            "pending": "⏳",
            "translated": "✓",
            "approved": "✓✓"
        }.get(word.get("translation_status", "pending"), "?")

        print(
            f"{word['week']:<6} "
            f"{word['day']:<5} "
            f"{word['word']:<15} "
            f"{word['micro_context_en']:<40} "
            f"{status_icon} {word.get('translation_status', 'pending'):<10}"
        )

    print(f"\nTotal: {len(words)} words")


def show_word(word_id: str):
    """Show detailed information for a specific word."""
    db = load_database()
    word = find_word(db, word_id)

    if not word:
        print(f"❌ Word '{word_id}' not found")
        return False

    print(f"\n=== {word['word'].upper()} ===")
    print(f"ID:            {word['id']}")
    print(f"Spelling:      {word['spelling']}")
    print(f"Week:          {word['week']}")
    print(f"Day:           {word['day']}")
    print(f"Context (EN):  {word['micro_context_en']}")
    print(f"Status:        {word.get('translation_status', 'pending')}")
    print(f"Added:         {word.get('added', 'unknown')}")

    print("\nTranslations:")
    for lang, trans in word.get("translations", {}).items():
        if trans:
            print(f"  {lang.upper()}: {trans}")
        else:
            print(f"  {lang.upper()}: (not translated)")

    return True


def export_week(week: int, output_file: Optional[str] = None):
    """Export a specific week's words for batch translation."""
    db = load_database()
    week_words = [w for w in db["words"] if w["week"] == week]

    if not week_words:
        print(f"❌ No words found for week {week}")
        return False

    # Format for translation pipeline
    export_data = [
        {
            "id": w["id"],
            "word": w["word"],
            "micro_context_en": w["micro_context_en"]
        }
        for w in week_words
    ]

    # Determine output file
    if not output_file:
        output_file = f"/srv/containers/edq/data/week_{week:02d}_batch.json"

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"✓ Exported {len(export_data)} words from Week {week}")
    print(f"  File: {output_path}")
    print(f"\nReady for translation:")
    print(f"  python3 scripts/vocab_translate_qa.py --batch {output_path} --langs es,vi,id")

    return True


def export_batch(output_file: str, status: str = "pending"):
    """Export all words with a specific status for batch processing."""
    db = load_database()
    filtered_words = [w for w in db["words"] if w.get("translation_status") == status]

    if not filtered_words:
        print(f"❌ No words with status '{status}'")
        return False

    export_data = [
        {
            "id": w["id"],
            "word": w["word"],
            "micro_context_en": w["micro_context_en"]
        }
        for w in filtered_words
    ]

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"✓ Exported {len(export_data)} words with status '{status}'")
    print(f"  File: {output_path}")

    return True


def delete_word(word_id: str):
    """Delete a word from the database."""
    db = load_database()
    word = find_word(db, word_id)

    if not word:
        print(f"❌ Word '{word_id}' not found")
        return False

    db["words"] = [w for w in db["words"] if w["id"].lower() != word_id.lower()]
    save_database(db)

    print(f"✓ Deleted '{word}' from database")
    return True


def show_stats():
    """Show database statistics."""
    db = load_database()

    if not db["words"]:
        print("📭 Database is empty")
        return

    # Count by week
    weeks = {}
    for word in db["words"]:
        week = word["week"]
        weeks[week] = weeks.get(week, 0) + 1

    # Count by status
    statuses = {}
    for word in db["words"]:
        status = word.get("translation_status", "pending")
        statuses[status] = statuses.get(status, 0) + 1

    # Count by day
    days = {day: 0 for day in WEEKDAYS}
    for word in db["words"]:
        day = word["day"]
        days[day] = days.get(day, 0) + 1

    print("\n=== Vocab Database Statistics ===")
    print(f"\nTotal Words: {len(db['words'])}")
    print(f"Current Position: Week {db['metadata']['current_week']}, {db['metadata']['current_day']}")
    print(f"Last Modified: {db['metadata']['last_modified']}")

    print("\n--- By Week ---")
    for week in sorted(weeks.keys()):
        print(f"  Week {week:2d}: {weeks[week]} words")

    print("\n--- By Day ---")
    for day in WEEKDAYS:
        print(f"  {day}: {days[day]} words")

    print("\n--- By Status ---")
    for status, count in statuses.items():
        print(f"  {status}: {count} words")


def main():
    parser = argparse.ArgumentParser(description="Vocab Word Database Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Add word
    add_parser = subparsers.add_parser("add", help="Add a new word")
    add_parser.add_argument("word", help="The word to add")
    add_parser.add_argument("context", help="Micro-context (English)")
    add_parser.add_argument("--week", type=int, help="Assign to specific week")
    add_parser.add_argument("--day", help="Assign to specific day (Mon-Fri)")

    # List words
    list_parser = subparsers.add_parser("list", help="List all words")
    list_parser.add_argument("--week", type=int, help="Filter by week")
    list_parser.add_argument("--day", help="Filter by day")

    # Show word details
    show_parser = subparsers.add_parser("show", help="Show word details")
    show_parser.add_argument("word", help="Word ID to show")

    # Export week
    export_parser = subparsers.add_parser("export", help="Export week for batch translation")
    export_parser.add_argument("--week", type=int, required=True, help="Week number to export")
    export_parser.add_argument("--output", help="Output file path")

    # Export batch
    batch_parser = subparsers.add_parser("export-batch", help="Export words by status")
    batch_parser.add_argument("output", help="Output file path")
    batch_parser.add_argument("--status", default="pending", help="Filter by status (default: pending)")

    # Delete word
    delete_parser = subparsers.add_parser("delete", help="Delete a word")
    delete_parser.add_argument("word", help="Word ID to delete")

    # Stats
    subparsers.add_parser("stats", help="Show database statistics")

    args = parser.parse_args()

    # Route commands
    if args.command == "add":
        add_word(args.word, args.context, args.week, args.day)

    elif args.command == "list":
        list_words(args.week, args.day)

    elif args.command == "show":
        show_word(args.word)

    elif args.command == "export":
        export_week(args.week, args.output)

    elif args.command == "export-batch":
        export_batch(args.output, args.status)

    elif args.command == "delete":
        delete_word(args.word)

    elif args.command == "stats":
        show_stats()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
