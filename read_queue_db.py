import sqlite3

for db in [r"E:\2026数模\B题\CUMCM2026B\Jammers-simulator\JammersSimulatorData\formal-statistics-queue.sqlite3",
           r"E:\2026数模\B题\CUMCM2026B\Jammers-simulator\JammersSimulatorData\upload-queue.sqlite3"]:
    print(f"===== {db} =====")
    try:
        con = sqlite3.connect(db)
        cur = con.cursor()
        tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print("tables:", tables)
        for (t,) in tables:
            cols = cur.execute(f"PRAGMA table_info({t})").fetchall()
            print(f"--- {t}: cols = {[c[1] for c in cols]}")
            try:
                rows = cur.execute(f"SELECT * FROM {t}").fetchall()
                for r in rows[:10]:
                    print("  ", r)
            except Exception as e:
                print("  err:", e)
        con.close()
    except Exception as e:
        print("open error:", e)
    print()