import logging
import sqlite3

# Configuration for the database
DATABASE = 'vlan.db'

# Configure logging
logging.basicConfig(level=logging.DEBUG, filename='vlan_sync.log', format='%(asctime)s - %(levelname)s - %(message)s')

def get_db():
    """Connect to the SQLite database"""
    try:
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        return db
    except sqlite3.Error as e:
        logging.error(f"Failed to connect to database: {e}")
        return None

def execute_query(query, args=(), fetch_all=False):
    """Execute a database query and commit changes"""
    db = get_db()
    if db is None:
        return None

    try:
        cursor = db.cursor()
        cursor.execute(query, args)
        if fetch_all:
            result = cursor.fetchall()
        else:
            result = cursor.fetchone()
        db.commit()
        cursor.close()
        return result
    except sqlite3.Error as e:
        logging.error(f"Failed to execute database query: {e}")
        db.rollback()
        cursor.close()
        return None

def create_vlan_table():
    """Create the VLAN table in the database if it doesn't exist"""
    query = '''CREATE TABLE IF NOT EXISTS vlans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vlan_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL);'''
    if execute_query(query) is None:
        logging.error("Failed to create VLAN table in the database")


def sync_vlan_with_db(vlan_data):
    """Sync VLAN data with the database"""
    query = '''INSERT INTO vlans (vlan_id, name, description)
                VALUES (?, ?, ?);'''
    if execute_query(query, (vlan_data['vlan_id'], vlan_data['name'], vlan_data['description'])) is None:
        logging.error("Failed to sync VLAN data with the database")