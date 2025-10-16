#!/usr/bin/env python3
"""
修复AAVE被错误标记为美股的问题
"""
import sqlite3

def fix_aave_us_stock():
    """将AAVE的is_us_stock标记从1改为0"""
    db_path = "mag_data.db"

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # 查看修改前的状态
        cursor.execute("SELECT COUNT(*) FROM coin_daily_data WHERE coin = 'AAVE' AND is_us_stock = 1")
        count_before = cursor.fetchone()[0]

        print(f"修复前: AAVE 有 {count_before} 条记录被标记为美股")

        # 修复
        cursor.execute("""
            UPDATE coin_daily_data
            SET is_us_stock = 0
            WHERE coin = 'AAVE'
        """)

        affected = cursor.rowcount
        conn.commit()

        # 查看修改后的状态
        cursor.execute("SELECT COUNT(*) FROM coin_daily_data WHERE coin = 'AAVE' AND is_us_stock = 1")
        count_after = cursor.fetchone()[0]

        print(f"✓ 已修复 {affected} 条记录")
        print(f"修复后: AAVE 有 {count_after} 条记录被标记为美股")

if __name__ == "__main__":
    fix_aave_us_stock()
