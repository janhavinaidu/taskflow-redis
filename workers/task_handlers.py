import time
import random


def handle_payment(payload: dict) -> dict:
    """Simulate payment confirmation processing."""
    time.sleep(random.uniform(3, 6))
    amount = payload.get("amount", 0)
    if random.random() < 0.05:  # 5% chance of failure for realism
        raise Exception(f"Payment gateway timeout for amount {amount}")
    return {"status": "confirmed", "amount": amount, "transaction_id": f"TXN-{random.randint(10000,99999)}"}


def handle_image(payload: dict) -> dict:
    """Simulate image resize/processing."""
    time.sleep(random.uniform(3, 6))
    filename = payload.get("filename", "unknown.jpg")
    if random.random() < 0.05:
        raise Exception(f"Image processing failed for {filename}")
    return {"status": "resized", "filename": filename, "dimensions": "800x600"}


def handle_report(payload: dict) -> dict:
    """Simulate report generation."""
    time.sleep(random.uniform(3, 6))
    report_type = payload.get("report_type", "generic")
    if random.random() < 0.05:
        raise Exception(f"Report generation failed for type {report_type}")
    return {"status": "generated", "report_type": report_type, "file": f"report_{random.randint(1000,9999)}.pdf"}


def handle_digest(payload: dict) -> dict:
    """Simulate weekly digest email sending."""
    time.sleep(random.uniform(3, 6))
    recipients = payload.get("recipients", 0)
    if random.random() < 0.05:
        raise Exception(f"Email delivery failed for {recipients} recipients")
    return {"status": "sent", "recipients": recipients, "open_rate": f"{random.randint(20,60)}%"}


TASK_HANDLERS = {
    "payment":  handle_payment,
    "image":    handle_image,
    "report":   handle_report,
    "digest":   handle_digest,
}