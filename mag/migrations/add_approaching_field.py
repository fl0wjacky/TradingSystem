#!/usr/bin/env python3
"""
添加逼近字段到数据库
"""
import sqlite3

def add_approaching_fields():
    """添加 is_approaching 和 approaching_correction 字段"""

    db_path = "mag_data.db"

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # 1. 添加 is_approaching 到 coin_daily_data 表
        try:
            cursor.execute("""
                ALTER TABLE coin_daily_data
                ADD COLUMN is_approaching INTEGER DEFAULT 0
            """)
            print("✓ 已添加 is_approaching 字段到 coin_daily_data 表")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("  is_approaching 字段已存在")
            else:
                raise

        # 2. 添加 approaching_correction 到 analysis_results 表
        try:
            cursor.execute("""
                ALTER TABLE analysis_results
                ADD COLUMN approaching_correction REAL DEFAULT 0
            """)
            print("✓ 已添加 approaching_correction 字段到 analysis_results 表")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("  approaching_correction 字段已存在")
            else:
                raise

        conn.commit()

    print("\n数据库schema更新完成！")

if __name__ == "__main__":
    add_approaching_fields()
