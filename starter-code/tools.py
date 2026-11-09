import json
import os
from typing import List, Dict, Any
from datetime import datetime

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "raw-data")

# ---------------------------------------------------------------------------
# Tool #1: search_product_catalog
# TODO: Hoàn thiện hàm này — đọc file product_catalog.json, lọc theo category và max_price.
# ---------------------------------------------------------------------------

def search_product_catalog(category: str, max_price: int = 999999999999) -> List[Dict[str, Any]]:
    """
    Tra cứu sản phẩm/dịch vụ Vingroup theo danh mục và giá tối đa.
    
    Args:
        category: Loại sản phẩm ('xe_dien' hoặc 'du_lich').
        max_price: Giá tối đa (VNĐ). Mặc định không giới hạn.
    
    Returns:
        Danh sách sản phẩm phù hợp điều kiện.
    """
    catalog_file = os.path.join(RAW_DATA_DIR, "product_catalog.json")
    if not os.path.exists(catalog_file):
        return []

    try:
        with open(catalog_file, "r", encoding="utf-8") as f:
            products = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(products, list):
        return []

    normalized_category = (category or "").strip().lower()
    try:
        limit = int(max_price)
    except (TypeError, ValueError):
        limit = 999999999999

    results = []
    for product in products:
        if not isinstance(product, dict):
            continue
        if str(product.get("category", "")).lower() != normalized_category:
            continue
        if int(product.get("price_vnd", 0)) <= limit:
            results.append(product)
    return results


# ---------------------------------------------------------------------------
# Tool #2: submit_support_ticket
# TODO: Hoàn thiện hàm này — tạo ticket mới và lưu vào support_tickets.json.
# ---------------------------------------------------------------------------

def submit_support_ticket(
    customer_name: str,
    issue_description: str,
    priority: str = "medium"
) -> Dict[str, Any]:
    """
    Ghi nhận yêu cầu hỗ trợ của khách hàng vào hệ thống ticket.
    
    Args:
        customer_name: Tên khách hàng.
        issue_description: Mô tả vấn đề cần hỗ trợ.
        priority: Mức độ ưu tiên ('low', 'medium', 'high'). Mặc định 'medium'.
    
    Returns:
        Thông tin ticket vừa tạo bao gồm ticket_id, status.
    """
    tickets_file = os.path.join(RAW_DATA_DIR, "support_tickets.json")

    existing_tickets = []
    if os.path.exists(tickets_file):
        try:
            with open(tickets_file, "r", encoding="utf-8") as f:
                existing_tickets = json.load(f)
        except (OSError, json.JSONDecodeError):
            existing_tickets = []

    if not isinstance(existing_tickets, list):
        existing_tickets = []

    priority_value = str(priority or "medium").strip().lower()
    if priority_value not in {"low", "medium", "high"}:
        priority_value = "medium"

    today = datetime.now().strftime("%Y%m%d")
    daily_count = 0
    for ticket in existing_tickets:
        ticket_id = str(ticket.get("ticket_id", ""))
        if ticket_id.startswith(f"TK-{today}-"):
            daily_count += 1
    ticket_id = f"TK-{today}-{daily_count + 1:03d}"

    new_ticket = {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "issue_description": issue_description,
        "priority": priority_value,
        "status": "open",
        "created_at": datetime.now().isoformat(timespec="seconds") + "+07:00",
        "category": "general"
    }

    existing_tickets.append(new_ticket)

    with open(tickets_file, "w", encoding="utf-8") as f:
        json.dump(existing_tickets, f, indent=2, ensure_ascii=False)

    return {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "issue_description": issue_description,
        "priority": priority_value,
        "status": "open",
        "message": f"Ticket {ticket_id} đã được tạo thành công."
    }


# ---------------------------------------------------------------------------
# TOOL_DEFINITIONS — JSON Schemas mô tả cho LLM
# TODO: Định nghĩa JSON Schema cho từng tool (name, description, parameters).
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "search_product_catalog",
        "description": "Tra cứu sản phẩm hoặc dịch vụ Vingroup theo danh mục và giá tối đa.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Loại sản phẩm: 'xe_dien' hoặc 'du_lich'.",
                    "enum": ["xe_dien", "du_lich"]
                },
                "max_price": {
                    "type": "integer",
                    "description": "Giá tối đa tính bằng VNĐ."
                }
            },
            "required": ["category"]
        }
    },
    {
        "name": "submit_support_ticket",
        "description": "Ghi nhận yêu cầu hỗ trợ của khách hàng vào hệ thống ticket.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Tên khách hàng cần hỗ trợ."
                },
                "issue_description": {
                    "type": "string",
                    "description": "Mô tả chi tiết vấn đề cần hỗ trợ."
                },
                "priority": {
                    "type": "string",
                    "description": "Mức độ ưu tiên: low, medium, high.",
                    "enum": ["low", "medium", "high"]
                }
            },
            "required": ["customer_name", "issue_description"]
        }
    }
]


# ---------------------------------------------------------------------------
# TOOL_MAP — Ánh xạ tên tool → hàm thực thi
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "search_product_catalog": search_product_catalog,
    "submit_support_ticket": submit_support_ticket
}
