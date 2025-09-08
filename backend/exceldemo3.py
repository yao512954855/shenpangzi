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

import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    file_name = Column(String(255), nullable=False, comment='文件名')
    delivery_date = Column(Date, nullable=False, comment='送货日期')
    ordering_unit = Column(String(100), nullable=False, comment='订货单位')
    delivery_unit = Column(String(100), nullable=False, comment='送货单位')
    serial_number = Column(Integer, nullable=False, comment='序号')
    product_name = Column(String(100), nullable=False, comment='商品名称')
    specification = Column(String(50), nullable=True, comment='规格')
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



def is_delivery_note_header(row: pd.Series) -> bool:
    """检查行是否为送货单表头"""
    row_text = ' '.join(str(cell) for cell in row.values if pd.notna(cell))

    # 送货单关键词
    delivery_keywords = [
        '送货单', '送货时间', '订货单位', '送货单位',
        '商品名称', '品名', '名称', '序号', '规格',
        '订货数量', '数量', '单位', '原始单价', '报价',
        '折扣率', '执行单价', '结算价', '金额'
    ]

    # 检查是否包含足够多的送货单关键词
    keyword_count = sum(1 for keyword in delivery_keywords if keyword in row_text)
    return keyword_count >= 3  # 至少包含3个关键词才认为是送货单表头


def find_delivery_notes(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """在数据框中查找所有送货单"""
    delivery_notes = []
    current_note = None
    start_row = -1

    print(f"数据框形状: {df.shape}")

    for i, row in df.iterrows():
        row_text = ' '.join(str(cell) for cell in row.values if pd.notna(cell))

        # 检查是否为送货单表头（订货单位行）
        if '订货单位：' in row_text:
            print(f"找到送货单表头在第 {i} 行: {row_text}")

            if current_note is not None:
                delivery_notes.append({
                    'start_row': start_row,
                    'end_row': i - 1,
                    'info': current_note
                })

            # 初始化送货单信息
            current_note = {
                'delivery_date': None,
                'order_unit': None,
                'delivery_unit': None
            }

            # 提取订货单位和送货单位
            order_match = re.search(r'订货单位[：:]\s*(.+)', row_text)
            if order_match:
                current_note['order_unit'] = order_match.group(1).strip()

            delivery_match = re.search(r'送货单位[：:]\s*(.+)', row_text)
            if delivery_match:
                current_note['delivery_unit'] = delivery_match.group(1).strip()

            start_row = i + 2  # 数据从表头行的下两行开始
            print(f"商品数据从第 {start_row} 行开始")

        # 检查是否为制单员行（送货单结束）
        elif '制单员：' in row_text and current_note is not None:
            delivery_notes.append({
                'start_row': start_row,
                'end_row': i - 1,
                'info': current_note
            })
            current_note = None
            start_row = -1

    # 添加最后一个送货单
    if current_note is not None:
        delivery_notes.append({
            'start_row': start_row,
            'end_row': len(df) - 1,
            'info': current_note
        })

    print(f"总共找到 {len(delivery_notes)} 个送货单")
    return delivery_notes


def extract_delivery_info_from_header(row: pd.Series) -> Dict[str, Any]:
    """从表头行提取送货单信息"""
    info = {
        'delivery_date': None,
        'order_unit': None,
        'delivery_unit': None
    }

    row_text = ' '.join(str(cell) for cell in row.values if pd.notna(cell))

    # 提取订货单位
    order_match = re.search(r'订货单位[：:]\s*(.+)', row_text)
    if order_match:
        info['order_unit'] = order_match.group(1).strip()

    # 提取送货单位
    delivery_match = re.search(r'送货单位[：:]\s*(.+)', row_text)
    if delivery_match:
        info['delivery_unit'] = delivery_match.group(1).strip()

    return info
def extract_products_from_delivery_note(df: pd.DataFrame, start_row: int, end_row: int) -> List[Dict[str, Any]]:
    """从送货单中提取商品信息"""
    products = []

    if start_row < 0 or end_row >= len(df) or start_row > end_row:
        return products

    # 查找列索引
    header_row = df.iloc[start_row - 1]  # 表头在数据开始的前一行
    column_mapping = {}

    for j, cell in enumerate(header_row.values):
        cell_str = str(cell).strip() if pd.notna(cell) else ''

        # 精确匹配列名
        if '序号' in cell_str:
            column_mapping['serial_number'] = j
        elif '商品名称' in cell_str:
            column_mapping['product_name'] = j
        elif '单位' in cell_str:
            column_mapping['unit'] = j
        elif '订货数量' in cell_str:
            column_mapping['quantity'] = j
        elif '原始单价' in cell_str:
            column_mapping['supplier_price'] = j
        elif '折扣率' in cell_str:
            column_mapping['discount_rate'] = j
        elif '执行单价' in cell_str:
            column_mapping['settlement_price'] = j
        elif '金额' in cell_str:
            column_mapping['amount'] = j

    print(f"列映射结果: {column_mapping}")

    # 提取商品数据
    for i in range(start_row, end_row + 1):
        row = df.iloc[i]

        # 检查是否为空行或合计行
        if pd.isna(row.iloc[0]) or any(
                keyword in str(row.iloc[0]) for keyword in ['合计', '总计', '总金额', '小计', '制单员']):
            break

        try:
            # 检查是否还有商品数据
            if pd.isna(row.iloc[column_mapping['product_name']]):
                continue

            product = {
                'serial_number': int(row.iloc[column_mapping[
                    'serial_number']]) if 'serial_number' in column_mapping else i - start_row + 1,
                'product_name': str(row.iloc[column_mapping['product_name']]).strip(),
                'specification': '',  # 你的送货单中没有规格字段
                'quantity': float(re.sub(r'[^\d.]', '', str(
                    row.iloc[column_mapping['quantity']]))) if 'quantity' in column_mapping else 0,
                'unit': str(row.iloc[column_mapping['unit']]).strip() if 'unit' in column_mapping else '',
                'supplier_price': float(re.sub(r'[^\d.]', '', str(
                    row.iloc[column_mapping['supplier_price']]))) if 'supplier_price' in column_mapping else 0,
                'discount_rate': float(re.sub(r'[^\d.]', '', str(row.iloc[column_mapping['discount_rate']]).replace('%',
                                                                                                                    ''))) if 'discount_rate' in column_mapping else 100,
                'settlement_price': float(re.sub(r'[^\d.]', '', str(
                    row.iloc[column_mapping['settlement_price']]))) if 'settlement_price' in column_mapping else 0,
                'amount': float(
                    re.sub(r'[^\d.]', '', str(row.iloc[column_mapping['amount']]))) if 'amount' in column_mapping else 0
            }

            # 确保商品名称不为空
            if product['product_name'] and not product['product_name'].startswith('序号'):
                products.append(product)
                print(f"提取到商品: {product['product_name']}")
        except (ValueError, IndexError, KeyError) as e:
            print(f"提取商品数据时出错: {e}")
            continue

    return products


def save_to_database(file_name: str, delivery_info: Dict[str, Any], products: List[Dict[str, Any]]) -> bool:
    """将数据保存到MySQL数据库"""
    db = SessionLocal()
    try:
        print(f"准备保存 {len(products)} 个商品到数据库")
        print(f"送货信息: {delivery_info}")

        # 检查送货日期是否为空
        if delivery_info.get('delivery_date') is None:
            print("警告: delivery_date 为 None，使用当前日期")
            delivery_info['delivery_date'] = datetime.now().date()

        for i, product in enumerate(products):
            print(f"处理第 {i + 1} 个商品: {product['product_name']}")

            # 处理折扣率百分比转换
            discount_rate = product['discount_rate']
            if discount_rate > 1:  # 如果是百分比形式（如90），转换为小数（0.9）
                discount_rate = discount_rate / 100
                print(f"折扣率转换: {product['discount_rate']} -> {discount_rate}")

            delivery = HongshanShixiaoDelivery(
                file_name=file_name,
                delivery_date=delivery_info['delivery_date'],
                ordering_unit=delivery_info.get('order_unit', '未知'),
                delivery_unit=delivery_info.get('delivery_unit', '未知'),
                serial_number=product['serial_number'],
                product_name=product['product_name'],
                specification=product['specification'],
                quantity=product['quantity'],
                unit=product['unit'],
                supplier_price=product['supplier_price'],
                discount_rate=discount_rate,
                settlement_price=product['settlement_price'],
                amount=product['amount']
            )
            db.add(delivery)
            print(f"已添加商品: {product['product_name']}")

        db.commit()
        print("数据库提交成功")
        return True
    except Exception as e:
        db.rollback()
        print(f"数据库保存失败: {e}")
        import traceback
        traceback.print_exc()  # 打印完整的错误堆栈
        return False
    finally:
        db.close()

def process_excel_file(file_path: str) -> Dict[str, Any]:
    """处理单个Excel文件"""
    result = {
        'file_name': os.path.basename(file_path),
        'delivery_notes': [],
        'saved_to_db': False,
        'error': None
    }

    try:
        excel_file = pd.ExcelFile(file_path)

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)

            # 首先查找送货日期
            delivery_date = None
            for i, row in df.iterrows():
                row_text = ' '.join(str(cell) for cell in row.values if pd.notna(cell))

                # 改进日期匹配逻辑
                date_match = re.search(r'送货时间[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})', row_text)
                if date_match:
                    date_str = date_match.group(1)
                    try:
                        if '年' in date_str:
                            delivery_date = datetime.strptime(date_str, '%Y年%m月%d日').date()
                        else:
                            delivery_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        print(f"找到送货日期: {delivery_date}")
                        break
                    except ValueError as e:
                        print(f"日期格式转换失败: {date_str}, 错误: {e}")
                        continue

            # 如果没找到日期，尝试其他方式查找
            if delivery_date is None:
                print("未找到送货日期，尝试其他方式查找...")
                for i, row in df.iterrows():
                    for j, cell in enumerate(row.values):
                        if pd.notna(cell):
                            cell_str = str(cell)
                            # 检查单元格是否包含日期格式
                            date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})', cell_str)
                            if date_match:
                                date_str = date_match.group(1)
                                try:
                                    if '年' in date_str:
                                        delivery_date = datetime.strptime(date_str, '%Y年%m月%d日').date()
                                    else:
                                        delivery_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                    print(f"通过其他方式找到送货日期: {delivery_date}")
                                    break
                                except ValueError:
                                    continue
                    if delivery_date is not None:
                        break

            # 如果仍然没找到日期，使用默认日期（当前日期）
            if delivery_date is None:
                delivery_date = datetime.now().date()
                print(f"未找到送货日期，使用当前日期: {delivery_date}")

            # 查找所有送货单
            delivery_notes = find_delivery_notes(df)
            print(f"找到 {len(delivery_notes)} 个送货单")

            for note in delivery_notes:
                products = extract_products_from_delivery_note(
                    df, note['start_row'], note['end_row'])
                print(f"提取到 {len(products)} 个商品")

                # 确保送货日期不为空
                note['info']['delivery_date'] = delivery_date
                print(f"设置送货日期: {delivery_date}")

                if products:
                    print("准备保存到数据库...")
                    result['delivery_notes'].append({
                        'info': note['info'],
                        'products': products
                    })

                    # 保存到数据库
                    if save_to_database(result['file_name'], note['info'], products):
                        result['saved_to_db'] = True
                        print(f"成功保存 {len(products)} 个商品到数据库")
                    else:
                        print(f"保存到数据库失败")
                else:
                    print("没有提取到商品，跳过保存")
    except Exception as e:
        result['error'] = str(e)
        print(f"处理文件时出错: {e}")

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
    process_results = []  # 确保初始化为空列表而不是None

    try:
        for file in files:
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            saved_files.append(file.filename)
            file_paths.append(file_path)

        # 处理Excel文件并保存到数据库
        process_results = []
        for file_path in file_paths:
            result = process_excel_file(file_path)
            if result is not None:  # 确保result不是None
                process_results.append(result)
            else:
                logger.error(f"处理文件 {file_path} 返回了None")

        # 统计处理结果
        success_count = sum(1 for r in process_results if r.get('saved_to_db', False))
        error_count = len(process_results) - success_count

        return {
            "message": f"文件处理完成，成功保存{success_count}个，失败{error_count}个",
            "files": saved_files,
            "process_results": process_results
        }
    except Exception as e:
        logger.error(f"上传文件时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件处理出错: {str(e)}")

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
                'file_name': record.file_name,
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


@app.get("/test-db")
async def test_db():
    """测试数据库连接和插入功能"""
    try:
        db = SessionLocal()

        # 测试查询
        count = db.query(HongshanShixiaoDelivery).count()
        print(f"当前记录数: {count}")

        # 测试插入
        test_record = HongshanShixiaoDelivery(
            file_name="test.xlsx",
            delivery_date=datetime.now().date(),
            ordering_unit="测试单位",
            delivery_unit="测试送货单位",
            serial_number=1,
            product_name="测试商品",
            specification="",
            quantity=10.0,
            unit="个",
            supplier_price=100.0,
            discount_rate=10.0,
            settlement_price=90.0,
            amount=900.0
        )
        db.add(test_record)
        db.commit()

        new_count = db.query(HongshanShixiaoDelivery).count()
        print(f"插入后记录数: {new_count}")

        return {"status": "success", "message": f"数据库测试成功，记录数: {count} -> {new_count}"}
    except Exception as e:
        print(f"数据库测试失败: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)