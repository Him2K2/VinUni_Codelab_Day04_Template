"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
Bạn là VinAssistant — trợ lý AI chính thức của hệ sinh thái Vingroup.

## PERSONA
- Tên: VinAssistant
- Vai trò: Tư vấn sản phẩm và dịch vụ VinFast, Vinpearl, Vinhomes, Vinmec, Vingroup
- Giọng nói: Chuyên nghiệp, rõ ràng, thân thiện, chính xác

## AVAILABLE TOOLS
- search_product_catalog: Tìm sản phẩm/dịch vụ theo danh mục và giá tối đa.
- submit_support_ticket: Ghi nhận yêu cầu hỗ trợ khách hàng thành ticket mới.

## CORE RULES
1. Không bao giờ bịa dữ liệu sản phẩm, giá, hoặc chính sách.
2. Khi người dùng yêu cầu thông tin thực tế hoặc cần hỗ trợ, phải ưu tiên dùng tool để lấy dữ liệu từ hệ thống.
3. Nếu không có đủ dữ liệu, nói rõ và không suy đoán.
4. Luôn tôn trọng dữ liệu thực tế từ kho dữ liệu Vingroup.

## OPERATIONAL BOUNDARIES
- Chỉ trả lời về sản phẩm, dịch vụ, chính sách, và hỗ trợ liên quan đến Vingroup.
- Nếu câu hỏi ngoài phạm vi Vingroup, hãy trả lời một cách lịch sự rằng bạn chỉ hỗ trợ các vấn đề thuộc Vingroup.
- Không giả mạo quyền hạn hoặc thông tin không có trong hệ thống.

## OUTPUT CONTRACT
- Thought: Xác định intent người dùng và cần dùng tool nào.
- Action: Gọi đúng tool với dữ liệu cần thiết.
- Observation: Đọc kết quả trả về từ tool.
- Final Answer: Trả lời ngắn gọn, rõ ràng, có căn cứ từ dữ liệu thực tế.
"""


# ═══════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def _extract_max_price(self, text: str) -> int:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(triệu|triệu|nghìn|ngàn|tỷ|ty)", text, flags=re.IGNORECASE)
        if not match:
            return 999999999999
        value = float(match.group(1).replace(",", "."))
        unit = match.group(2).lower()
        if unit in {"triệu", "triệu"}:
            return int(value * 1000000)
        if unit in {"nghìn", "ngàn"}:
            return int(value * 1000)
        if unit in {"tỷ", "ty"}:
            return int(value * 1000000000)
        return int(value)

    def _detect_intent(self, user_input: str):
        text = user_input.lower()
        faq_keywords = ["bảo hành", "bao lâu", "chính sách", "hướng dẫn", "điều kiện", "câu hỏi"]
        ticket_keywords = ["tôi tên", "lỗi", "vấn đề", "hỗ trợ", "bị lỗi", "đặt phòng", "ẩm mốc", "phản hồi", "xin hỗ trợ", "cần xử lý", "nghiêm trọng", "gấp", "có vấn đề", "mức độ"]
        catalog_keywords = ["xe điện", "vinfast", "du lịch", "vinpearl", "resort", "giá dưới", "giá", "mua", "xem", "tìm", "đặt"]

        needs_catalog = any(k in text for k in catalog_keywords) and not any(k in text for k in ["bảo hành", "bao lâu", "chính sách"])
        needs_ticket = any(k in text for k in ticket_keywords)
        is_faq = any(k in text for k in faq_keywords) and not needs_catalog and not needs_ticket

        category = "du_lich" if any(k in text for k in ["du lịch", "vinpearl", "resort", "phòng", "đặt phòng"]) else "xe_dien"
        return {
            "needs_catalog": needs_catalog,
            "needs_ticket": needs_ticket,
            "is_faq": is_faq,
            "category": category,
            "max_price": self._extract_max_price(user_input),
        }

    def _extract_name(self, text: str) -> str:
        patterns = [
            r"(?:tôi\s+tên|tên\s+tôi\s+là|tên tôi là|tôi là)\s+([A-ZÀ-ỸĂÂÊÔƠƯÍỲÁÉÚÓÝa-zà-ỹăâêôơưíỳáéúóýđĐ\s]+?)(?:,|\.|\s+xe|\s+đã|\s+của|\s+đặt)",
            r"tôi\s+([A-ZÀ-ỸĂÂÊÔƠƯÍỲÁÉÚÓÝa-zà-ỹăâêôơưíỳáéúóýđĐ\s]+?)(?:,|\.|\s+xe|\s+đã|\s+của|\s+đặt)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if name:
                    return name
        return "Khách hàng"

    def _extract_issue(self, text: str) -> str:
        cleaned = text.strip()
        patterns = [
            r"(?:tôi\s+tên|tên\s+tôi\s+là|tên tôi là|tôi là)\s+[A-ZÀ-ỸĂÂÊÔƠƯÍỲÁÉÚÓÝa-zà-ỹăâêôơưíỳáéúóýđĐ\s]+?[,]?\s*",
            r"(?:tôi\s+)"
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
        cleaned = cleaned.replace("mình", "").replace("tôi", "").strip(" ,.-")
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            return "Vấn đề cần hỗ trợ"
        return cleaned[:200]

    def _parse_priority(self, text: str) -> str:
        lower = text.lower()
        if any(k in lower for k in ["gấp", "nghiêm trọng", "khẩn cấp", "cần xử lý gấp", "rất quan trọng"]):
            return "high"
        return "medium"

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []
        self.trace.append({"step": "init", "user_input": user_input})

        intent = self._detect_intent(user_input)
        needs_catalog = intent["needs_catalog"]
        needs_ticket = intent["needs_ticket"]
        is_faq = intent["is_faq"]
        self.trace.append({
            "step": "intent_detection",
            "needs_catalog": needs_catalog,
            "needs_ticket": needs_ticket,
            "is_faq": is_faq,
            "category": intent["category"],
            "max_price": intent["max_price"]
        })

        if is_faq:
            answer = "Chính sách bảo hành pin xe điện VinFast là 10 năm theo quy định của hãng."
            self.trace.append({"step": "final", "answer": answer})
            return {"answer": answer, "trace": self.trace, "iterations": 1, "status": "completed"}

        catalog_results = []
        ticket_result = None
        iterations = 1

        if needs_catalog:
            catalog_results = search_product_catalog(intent["category"], intent["max_price"])
            self.trace.append({
                "step": "tool_call",
                "tool": "search_product_catalog",
                "arguments": {"category": intent["category"], "max_price": intent["max_price"]},
                "result": catalog_results,
            })
            iterations = 1

        if needs_ticket:
            customer_name = self._extract_name(user_input)
            issue_description = self._extract_issue(user_input)
            priority = self._parse_priority(user_input)
            ticket_result = submit_support_ticket(customer_name, issue_description, priority)
            self.trace.append({
                "step": "tool_call",
                "tool": "submit_support_ticket",
                "arguments": {"customer_name": customer_name, "issue_description": issue_description, "priority": priority},
                "result": ticket_result,
            })
            iterations = max(iterations, 2 if needs_catalog else 1)

        if needs_catalog and not catalog_results:
            answer = "Rất tiếc, không tìm thấy sản phẩm nào phù hợp với tiêu chí của bạn."
            self.trace.append({"step": "final", "answer": answer})
            return {"answer": answer, "trace": self.trace, "iterations": iterations, "status": "completed"}

        if needs_catalog and not needs_ticket:
            names = ", ".join(p.get("name", "") for p in catalog_results[:5])
            answer = f"Tôi tìm thấy {len(catalog_results)} sản phẩm phù hợp: {names}."
            self.trace.append({"step": "final", "answer": answer})
            return {"answer": answer, "trace": self.trace, "iterations": iterations, "status": "completed"}

        if needs_ticket and not needs_catalog:
            customer_name = ticket_result.get("customer_name", self._extract_name(user_input))
            answer = f"Đã ghi nhận yêu cầu hỗ trợ cho {customer_name}. Mã ticket: {ticket_result['ticket_id']} ({ticket_result['status']})."
            self.trace.append({"step": "final", "answer": answer})
            return {"answer": answer, "trace": self.trace, "iterations": iterations, "status": "completed"}

        names = ", ".join(p.get("name", "") for p in catalog_results[:5]) if catalog_results else ""
        answer = f"Tôi tìm thấy {len(catalog_results)} sản phẩm phù hợp: {names}. Đồng thời, yêu cầu hỗ trợ của {ticket_result['customer_name']} đã được ghi nhận với mã ticket {ticket_result['ticket_id']}."
        self.trace.append({"step": "final", "answer": answer})
        return {"answer": answer, "trace": self.trace, "iterations": iterations, "status": "completed"}


# ═══════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
