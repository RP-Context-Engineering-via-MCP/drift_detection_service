"""
SQL Query Executor Script

Execute any SQL query against the database and display results.
Usage:
    python scripts/query_db.py                    # Interactive mode
    python scripts/query_db.py "SELECT * FROM users"  # Direct query
"""

import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any

# Add parent directory to path to import app modules
sys.path.insert(0, '.')

from app.config import get_settings


def execute_query(query: str) -> tuple[List[Dict[str, Any]], int]:
    """
    Execute a SQL query and return results.
    
    Args:
        query: SQL query string
        
    Returns:
        Tuple of (results list, affected rows count)
    """
    settings = get_settings()
    
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute(query)
        
        # Check if query returns results (SELECT, RETURNING, etc.)
        if cursor.description:
            results = [dict(row) for row in cursor.fetchall()]
            conn.commit()
            return results, len(results)
        else:
            # For INSERT, UPDATE, DELETE without RETURNING
            affected = cursor.rowcount
            conn.commit()
            return [], affected
            
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def display_results(results: List[Dict[str, Any]], affected_rows: int, query: str):
    """
    Display query results in a formatted table.
    
    Args:
        results: List of result dictionaries
        affected_rows: Number of affected rows
        query: Original query string
    """
    print("\n" + "="*80)
    print(f"QUERY: {query[:200]}{'...' if len(query) > 200 else ''}")
    print("="*80)
    
    if results:
        # Display as simple table
        headers = list(results[0].keys())
        
        # Calculate column widths
        col_widths = {}
        for header in headers:
            col_widths[header] = len(str(header))
            for row in results:
                col_widths[header] = max(col_widths[header], len(str(row[header])))
        
        # Print header
        header_line = " | ".join(str(h).ljust(col_widths[h]) for h in headers)
        print(header_line)
        print("-" * len(header_line))
        
        # Print rows
        for row in results:
            row_line = " | ".join(str(row[col]).ljust(col_widths[col]) for col in headers)
            print(row_line)
        
        print(f"\n✓ {len(results)} row(s) returned")
    elif affected_rows > 0:
        print(f"✓ {affected_rows} row(s) affected")
    else:
        print("✓ Query executed successfully (no rows returned or affected)")
    
    print("="*80 + "\n")


def interactive_mode():
    """Run in interactive mode - prompt for queries continuously."""
    print("="*80)
    print("SQL Query Executor - Interactive Mode")
    print("="*80)
    print("Enter SQL queries (type 'exit' or 'quit' to stop)")
    print("Multi-line queries: end with semicolon ';'")
    print("="*80 + "\n")
    
    while True:
        try:
            # Read query (support multi-line)
            query_lines = []
            print("SQL> ", end="")
            
            while True:
                line = input()
                if line.lower().strip() in ['exit', 'quit']:
                    print("\nGoodbye!")
                    return
                    
                query_lines.append(line)
                
                # Check if query is complete (ends with semicolon)
                if line.strip().endswith(';'):
                    break
                    
                print("  -> ", end="")
            
            query = ' '.join(query_lines).strip()
            
            if not query:
                continue
            
            # Execute and display
            results, affected = execute_query(query)
            display_results(results, affected, query)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ ERROR: {e}\n")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Direct query mode
        query = ' '.join(sys.argv[1:])
        try:
            results, affected = execute_query(query)
            display_results(results, affected, query)
        except Exception as e:
            print(f"❌ ERROR: {e}")
            sys.exit(1)
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()
