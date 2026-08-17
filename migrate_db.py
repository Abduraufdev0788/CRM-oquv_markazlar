import sqlite3

try:
    conn = sqlite3.connect('app/crm.db')
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE groups ADD COLUMN teacher_salary_pct NUMERIC(5,2) NOT NULL DEFAULT 40.00")
    conn.commit()
    print("Column added successfully")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
