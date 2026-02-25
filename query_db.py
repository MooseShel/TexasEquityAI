import os
import psycopg2
from urllib.parse import urlparse

db_url = "postgresql://postgres:!EmmaNasma1981@db.dvnqlqbshzdnaqmsmbqr.supabase.co:5432/postgres"
result = urlparse(db_url)
username = result.username
password = result.password
database = result.path[1:]
hostname = result.hostname
port = result.port

try:
    conn = psycopg2.connect(
        database=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    cur = conn.cursor()
    
    print("--- 935 Lamonte Ln by Account ---")
    cur.execute("SELECT account_number, address, neighborhood_code, building_area FROM properties WHERE account_number = '0660460450034';")
    for row in cur.fetchall():
        print(row)
        
    print("\n--- Properties on Lamonte Ln ---")
    cur.execute("SELECT account_number, address, neighborhood_code, building_area FROM properties WHERE address ILIKE '%LAMONTE LN%' LIMIT 20;")
    for row in cur.fetchall():
        print(row)
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
