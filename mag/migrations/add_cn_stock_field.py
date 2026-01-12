#!/usr/bin/env python3
"""
添加国内A股标记字段到数据库
"""
import sqlite3

def add_cn_stock_field():
    """添加 is_cn_stock 字段到 coin_daily_data 表"""

    db_path = "mag_data.db"

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # 添加 is_cn_stock 到 coin_daily_data 表
        try:
            cursor.execute("""
                ALTER TABLE coin_daily_data
                ADD COLUMN is_cn_stock INTEGER DEFAULT 0
            """)
            print("✓ 已添加 is_cn_stock 字段到 coin_daily_data 表")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("  is_cn_stock 字段已存在")
            else:
                raise

        conn.commit()

    print("\n数据库schema更新完成！")
    print("\n说明：")
    print("  - is_cn_stock=1 表示国内A股资产")
    print("  - 国内A股资产不参与对标链验证")
    print("  - 国内A股资产不应用美股/BTC/龙头币修正")

if __name__ == "__main__":
    add_cn_stock_field()
