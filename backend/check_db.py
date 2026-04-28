import sqlite3
import json

conn = sqlite3.connect('test_traces.db')
c = conn.cursor()

print("=" * 80)
print("REASONING TRACES DATABASE CONTENTS")
print("=" * 80)

c.execute("SELECT COUNT(*) FROM reasoning_traces")
total = c.fetchone()[0]
print(f"\nTotal traces in database: {total}\n")

c.execute("SELECT classifier_name, COUNT(*) FROM reasoning_traces GROUP BY classifier_name")
for classifier, count in c.fetchall():
    print(f"  {classifier:12}: {count} trace(s)")

print("\n" + "=" * 80)
print("TRACE DETAILS")
print("=" * 80)

c.execute("SELECT id, classifier_name, entity_type, entity_id, created_at FROM reasoning_traces")
for row in c.fetchall():
    print(f"\n[{row[0]}] {row[1]:10} {row[2]:15} entity_id={row[3]}")
    print(f"    created: {row[4]}")

print("\n" + "=" * 80)
print("SAMPLE TRACE DATA (First Trace)")
print("=" * 80)

c.execute("SELECT trace_data FROM reasoning_traces LIMIT 1")
trace_json = c.fetchone()[0]
data = json.loads(trace_json)
print(json.dumps(data, indent=2)[:1000])
print("...")

conn.close()
print("\n✅ TRACES ARE PERSISTED IN DATABASE!")
