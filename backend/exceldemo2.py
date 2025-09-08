import os
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import re
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Date, Numeric, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pymysql

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MySQL数据库配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "root"
MYSQL_DB = "shenpangzi"

# 创建数据库连接
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# 定义数据模型
class HongshanShixiaoDelivery(Base):
    __tablename__ = 'hongshan_shixiao_delivery'

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_date = Column(Date, nullable=False, comment='送货日期')
    ordering_unit = Column(String(100), nullable=False, comment='订货单位')
    delivery_unit = Column(String(100), nullable=False, comment='送货单位')
    serial_number = Column(Integer, nullable=False, comment='序号')
    product_name = Column(String(100), nullable=False, comment='商品名称')
    specification = Column(String(50), comment='规格')
    quantity = Column(Numeric(10, 2), nullable=False, comment='数量')
    unit = Column(String(20), nullable=False, comment='单位')
    supplier_price = Column(Numeric(10, 2), nullable=False, comment='供应商报价')
    discount_rate = Column(Numeric(5, 2), nullable=False, comment='折扣率(%)')
    settlement_price = Column(Numeric(10, 2), nullable=False, comment='结算价')
    amount = Column(Numeric(12, 2), nullable=False, comment='金额')
    created_time = Column(TIMESTAMP, server_default='CURRENT_TIMESTAMP', comment='创建时间')
    updated_time = Column(TIMESTAMP, server_default='CURRENT_TIMESTAMP', onupdate='CURRENT_TIMESTAMP',
                          comment='更新时间')


# 创建表（如果不存在）
Base.metadata.create_all(bind=engine)

UPLOAD_DIR = "excelfile"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def is_delivery_note(df: pd.DataFrame) -> bool:
    """检查表格是否为送货单"""
    if df.empty:
        return False

    header_text = ' '.join(str(cell) for cell in df.iloc[0].values if pd.notna(cell))
    delivery_keywords = ['送货单', '送货时间', '订货单位', '送货单位', '商品名称', '数量', '单价', '金额']
    return any(keyword in header_text for keyword in delivery_keywords)


def extract_delivery_info(df: pd.DataFrame) -> Dict[str, Any]:
    """提取送货单信息"""
    info = {
        'delivery_date': None,
        'order_unit': None,
        'delivery_unit': None,
        'products': []
    }

    # 查找送货时间、订货单位、送货单位
    for _, row in df.iterrows():
        row_text = ' '.join(str(cell) for cell in row.values if pd.notna(cell))

        # 提取送货日期
        if '送货时间' in row_text or '日期' in row_text:
            date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})', row_text)
            if date_match:
                date_str = date_match.group(1)
                try:
                    if '年' in date_str:
                        info['delivery_date'] = datetime.strptime(date_str, '%Y年%m月%d日').date()
                    else:
                        info['delivery_date'] = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    continue

        # 提取订货单位
        if '订货单位' in row_text:
            unit_match = re.search(r'订货单位[：:]\s*(.+)', row_text)
            if unit_match:
                info['order_unit'] = unit_match.group(1).strip()

        # 提取送货单位
        if '送货单位' in row_text:
            delivery_match = re.search(r'送货单位[：:]\s*(.+)', row_text)
            if delivery_match:
                info['delivery_unit'] = delivery_match.group(1).strip()

    return info


def extract_products(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """提取商品信息"""
    products = []

    # 查找商品表格的开始行
    start_row = -1
    for i, row in df.iterrows():
        row_values = [str(cell).strip() for cell in row.values if pd.notna(cell)]
        if any(keyword in row_values for keyword in ['商品名称', '品名', '名称']):
            start_row = i
            break

    if start_row == -1:
        return products

    # 提取列索引
    header_row = df.iloc[start_row]
    column_mapping = {}
    for j, cell in enumerate(header_row.values):
        cell_str = str(cell).strip() if pd.notna(cell) else ''
        if '商品名称' in cell_str or '品名' in cell_str:
            column_mapping['product_name'] = j
        elif '序号' in cell_str:
            column_mapping['serial_number'] = j
        elif '规格' in cell_str:
            column_mapping['specification'] = j
        elif '数量' in cell_str:
            column_mapping['quantity'] = j
        elif '单位' in cell_str:
            column_mapping['unit'] = j
        elif '供应商报价' in cell_str or '报价' in cell_str:
            column_mapping['supplier_price'] = j
        elif '折扣率' in cell_str:
            column_mapping['discount_rate'] = j
        elif '结算价' in cell_str or '执行单价' in cell_str:
            column_mapping['settlement_price'] = j
        elif '金额' in cell_str:
            column_mapping['amount'] = j

    # 提取商品数据
    for i in range(start_row + 1, len(df)):
        row = df.iloc[i]
        if pd.isna(row.iloc[0]) or '总金额' in str(row.iloc[0]) or '合计' in str(row.iloc[0]):
            break

        try:
            product = {
                'serial_number': int(
                    row.iloc[column_mapping['serial_number']]) if 'serial_number' in column_mapping else 0,
                'product_name': str(
                    row.iloc[column_mapping['product_name']]).strip() if 'product_name' in column_mapping else '',
                'specification': str(
                    row.iloc[column_mapping['specification']]).strip() if 'specification' in column_mapping else '',
                'quantity': float(re.sub(r'[^\d.]', '', str(
                    row.iloc[column_mapping['quantity']]))) if 'quantity' in column_mapping else 0,
                'unit': str(row.iloc[column_mapping['unit']]).strip() if 'unit' in column_mapping else '',
                'supplier_price': float(re.sub(r'[^\d.]', '', str(
                    row.iloc[column_mapping['supplier_price']]))) if 'supplier_price' in column_mapping else 0,
                'discount_rate': float(re.sub(r'[^\d.]', '', str(
                    row.iloc[column_mapping['discount_rate']]))) if 'discount_rate' in column_mapping else 100,
                'settlement_price': float(re.sub(r'[^\d.]', '', str(
                    row.iloc[column_mapping['settlement_price']]))) if 'settlement_price' in column_mapping else 0,
                'amount': float(
                    re.sub(r'[^\d.]', '', str(row.iloc[column_mapping['amount']]))) if 'amount' in column_mapping else 0
            }

            if product['product_name'] and not product['product_name'].startswith('序号'):
                products.append(product)
        except ValueError:
            continue

    return products


def save_to_database(delivery_info: Dict[str, Any], products: List[Dict[str, Any]]) -> bool:
    """将数据保存到MySQL数据库"""
    db = SessionLocal()
    try:
        for product in products:
            delivery = HongshanShixiaoDelivery(
                delivery_date=delivery_info['delivery_date'],
                ordering_unit=delivery_info['order_unit'] or '未知',
                delivery_unit=delivery_info['delivery_unit'] or '未知',
                serial_number=product['serial_number'],
                product_name=product['product_name'],
                specification=product['specification'],
                quantity=product['quantity'],
                unit=product['unit'],
                supplier_price=product['supplier_price'],
                discount_rate=product['discount_rate'],
                settlement_price=product['settlement_price'],
                amount=product['amount']
            )
            db.add(delivery)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"数据库保存失败: {e}")
        return False
    finally:
        db.close()


def process_excel_file(file_path: str) -> Dict[str, Any]:
    """处理单个Excel文件"""
    result = {
        'file_name': os.path.basename(file_path),
        'delivery_info': None,
        'products': [],
        'saved_to_db': False,
        'error': None
    }

    try:
        excel_file = pd.ExcelFile(file_path)
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)

            if is_delivery_note(df):
                delivery_info = extract_delivery_info(df)
                products = extract_products(df)

                if delivery_info['delivery_date'] and products:
                    result['delivery_info'] = delivery_info
                    result['products'] = products

                    # 保存到数据库
                    if save_to_database(delivery_info, products):
                        result['saved_to_db'] = True
    except Exception as e:
        result['error'] = str(e)

    return result


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    if len(files) > 100:
        raise HTTPException(status_code=400, detail="最多只能上传100个文件")

    for file in files:
        if not file.filename.endswith('.xls') and not file.filename.endswith('.xlsx'):
            raise HTTPException(status_code=400, detail="只能上传.xls或.xlsx文件")

    saved_files = []
    file_paths = []
    process_results = []

    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        saved_files.append(file.filename)
        file_paths.append(file_path)

    # 处理Excel文件并保存到数据库
    for file_path in file_paths:
        result = process_excel_file(file_path)
        process_results.append(result)

    # 统计处理结果
    success_count = sum(1 for r in process_results if r['saved_to_db'])
    error_count = len(process_results) - success_count

    return {
        "message": f"文件处理完成，成功保存{success_count}个，失败{error_count}个",
        "files": saved_files,
        "process_results": process_results
    }


@app.get("/check-price-inconsistencies")
async def check_price_inconsistencies():
    """检查数据库中价格不一致的商品"""
    db = SessionLocal()
    try:
        # 查询所有记录
        records = db.query(HongshanShixiaoDelivery).all()

        # 按日期和商品名称分组
        date_product_map = {}
        for record in records:
            key = (record.delivery_date, record.product_name)
            if key not in date_product_map:
                date_product_map[key] = []
            date_product_map[key].append({
                'id': record.id,
                'ordering_unit': record.ordering_unit,
                'delivery_unit': record.delivery_unit,
                'settlement_price': float(record.settlement_price),
                'created_time': record.created_time
            })

        # 找出价格不一致的商品
        inconsistencies = []
        for (date, product_name), items in date_product_map.items():
            prices = set(item['settlement_price'] for item in items)
            if len(prices) > 1:
                inconsistencies.append({
                    'delivery_date': date.strftime('%Y-%m-%d'),
                    'product_name': product_name,
                    'price_variations': list(prices),
                    'records': items
                })

        return {
            "count": len(inconsistencies),
            "inconsistencies": inconsistencies
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询数据库时出错: {str(e)}")
    finally:
        db.close()

@app.delete("/delete/{filename}")
async def delete_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        os.remove(file_path)
        return {"message": f"文件 {filename} 已删除", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件时出错: {str(e)}")


@app.get("/files")
async def list_files():
    if not os.path.exists(UPLOAD_DIR):
        return {"files": []}

    files = [f for f in os.listdir(UPLOAD_DIR)
             if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    return {"files": files}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)