# printing/printer.py
# Handles label printing via browser print dialog

from printing.label import Label


def prepare_label(buyer_username, item_name, price, order_id=None):
    """
    Prepare label data for browser printing.
    Returns a Label object with all necessary data.
    Browser print dialog handles the actual printing.
    """
    label = Label(
        buyer_username=buyer_username,
        item_name=item_name,
        price=float(price),
        order_id=order_id
    )
    return label.to_dict()


def print_label_browser(buyer_username, item_name, price, order_id=None):
    """
    Prepare label for browser print dialog.
    The actual print() call is triggered from JavaScript.
    Returns label data to populate the print template.
    """
    return prepare_label(buyer_username, item_name, price, order_id)