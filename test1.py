from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Iterator


DEFAULT_CURRENCY = "USD"
LOW_STOCK_LIMIT = 5
REPORT_TITLE = "Warehouse Inventory"


@dataclass
class Product:
    sku: str
    name: str
    unit_price: Decimal
    quantity: int
    category: str
    tags: list[str] = field(default_factory=list)
    discontinued: bool = False

    def value(self) -> Decimal:
        return self.unit_price * self.quantity

    def is_low_stock(self, threshold: int = LOW_STOCK_LIMIT) -> bool:
        return self.quantity <= threshold

    def display_name(self) -> str:
        return f"{self.sku} - {self.name}"


@dataclass
class Movement:
    sku: str
    amount: int
    occurred_at: datetime
    reason: str
    reference: str = ""

    def is_inbound(self) -> bool:
        return self.amount > 0

    def is_outbound(self) -> bool:
        return self.amount < 0


class InventoryError(Exception):
    """Base error for inventory operations."""


class UnknownProductError(InventoryError):
    """Raised when a stock movement targets an absent product."""


class InvalidMovementError(InventoryError):
    """Raised when a stock movement is not acceptable."""


class Inventory:
    def __init__(self, products: Iterable[Product] | None = None) -> None:
        self._products: dict[str, Product] = {}
        self._movements: list[Movement] = []
        self._created_at = datetime.now(timezone.utc)
        for product in products or []:
            self.add_product(product)

    def add_product(self, product: Product) -> None:
        if not product.sku.strip():
            raise ValueError("SKU cannot be empty")
        if product.quantity < 0:
            raise ValueError("Initial quantity cannot be negative")
        if product.unit_price < 0:
            raise ValueError("Unit price cannot be negative")
        self._products[product.sku] = product

    def product(self, sku: str) -> Product:
        try:
            return self._products[sku]
        except KeyError as exc:
            raise UnknownProductError(sku) from exc

    def products(self) -> Iterator[Product]:
        yield from self._products.values()

    def movement_history(self, sku: str | None = None) -> list[Movement]:
        if sku is None:
            return list(self._movements)
        return [movement for movement in self._movements if movement.sku == sku]

    def apply_movement(
        self,
        sku: str,
        amount: int,
        reason: str,
        reference: str = "",
        occurred_at: datetime | None = None,
    ) -> Movement:
        if amount == 0:
            raise InvalidMovementError("Movement cannot be zero")
        product = self.product(sku)
        if product.quantity + amount < 0:
            raise InvalidMovementError("Movement would create negative stock")
        event_time = occurred_at or datetime.now(timezone.utc)
        movement = Movement(sku, amount, event_time, reason, reference)
        product.quantity += amount
        self._movements.append(movement)
        return movement

    def receive(self, sku: str, amount: int, reference: str = "") -> Movement:
        if amount < 1:
            raise InvalidMovementError("Received amount must be positive")
        return self.apply_movement(sku, amount, "receipt", reference)

    def ship(self, sku: str, amount: int, reference: str = "") -> Movement:
        if amount < 1:
            raise InvalidMovementError("Shipped amount must be positive")
        return self.apply_movement(sku, -amount, "shipment", reference)

    def total_value(self) -> Decimal:
        return sum((product.value() for product in self.products()), Decimal("0"))

    def total_units(self) -> int:
        return sum(product.quantity for product in self.products())

    def categories(self) -> list[str]:
        return sorted({product.category for product in self.products()})

    def by_category(self, category: str) -> list[Product]:
        normalized = category.casefold().strip()
        return [
            product
            for product in self.products()
            if product.category.casefold() == normalized
        ]

    def low_stock(self, threshold: int = LOW_STOCK_LIMIT) -> list[Product]:
        return [product for product in self.products() if product.is_low_stock(threshold)]

    def discontinued(self) -> list[Product]:
        return [product for product in self.products() if product.discontinued]

    def active(self) -> list[Product]:
        return [product for product in self.products() if not product.discontinued]

    def search(self, query: str) -> list[Product]:
        needle = query.casefold().strip()
        return [
            product
            for product in self.products()
            if needle in product.name.casefold()
            or needle in product.sku.casefold()
            or any(needle in tag.casefold() for tag in product.tags)
        ]


def money(value: Decimal, currency: str = DEFAULT_CURRENCY) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{currency} {rounded:,.2f}"


def percent(numerator: int | Decimal, denominator: int | Decimal) -> str:
    if denominator == 0:
        return "0.0%"
    value = Decimal(numerator) / Decimal(denominator) * Decimal("100")
    return f"{value.quantize(Decimal('0.1'))}%"


def serialize_product(product: Product) -> dict[str, object]:
    return {
        "sku": product.sku,
        "name": product.name,
        "unit_price": str(product.unit_price),
        "quantity": product.quantity,
        "category": product.category,
        "tags": list(product.tags),
        "discontinued": product.discontinued,
    }


def deserialize_product(data: dict[str, object]) -> Product:
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        raise ValueError("tags must be a list")
    return Product(
        sku=str(data["sku"]),
        name=str(data["name"]),
        unit_price=Decimal(str(data["unit_price"])),
        quantity=int(data["quantity"]),
        category=str(data["category"]),
        tags=[str(tag) for tag in tags],
        discontinued=bool(data.get("discontinued", False)),
    )


def group_by_category(products: Iterable[Product]) -> dict[str, list[Product]]:
    grouped: dict[str, list[Product]] = {}
    for product in products:
        grouped.setdefault(product.category, []).append(product)
    return grouped


def category_totals(products: Iterable[Product]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for category, entries in group_by_category(products).items():
        totals[category] = sum((entry.value() for entry in entries), Decimal("0"))
    return totals


def restock_suggestions(
    inventory: Inventory,
    target_quantity: int = 20,
    threshold: int = LOW_STOCK_LIMIT,
) -> list[tuple[Product, int]]:
    suggestions: list[tuple[Product, int]] = []
    for product in inventory.low_stock(threshold):
        if not product.discontinued:
            suggestions.append((product, max(target_quantity - product.quantity, 0)))
    return suggestions


def recent_movements(inventory: Inventory, hours: int = 24) -> list[Movement]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [
        movement
        for movement in inventory.movement_history()
        if movement.occurred_at >= cutoff
    ]


def movement_summary(movements: Iterable[Movement]) -> dict[str, int]:
    received = 0
    shipped = 0
    for movement in movements:
        if movement.is_inbound():
            received += movement.amount
        else:
            shipped += movement.amount
    return {"received": received, "shipped": shipped}


def product_row(product: Product) -> str:
    return " | ".join(
        [
            product.sku,
            product.name,
            product.category,
            str(product.quantity),
            money(product.unit_price),
            money(product.value()),
        ]
    )


def format_table(headers: list[str], rows: Iterable[list[str]]) -> str:
    materialized = [headers, *rows]
    widths = [max(len(row[index]) for row in materialized) for index in range(len(headers))]
    rendered: list[str] = []
    for row_number, row in enumerate(materialized):
        rendered.append(" | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))
        if row_number == 0:
            rendered.append("-+-".join("-" * width for width in widths))
    return "\n".join(rendered)


def inventory_table(inventory: Inventory) -> str:
    headers = ["SKU", "Name", "Category", "Quantity", "Unit price", "Value"]
    rows = [
        [
            product.sku,
            product.name,
            product.category,
            str(product.quantity),
            money(product.unit_price),
            money(product.value()),
        ]
        for product in sorted(inventory.products(), key=lambda item: item.sku)
    ]
    return format_table(headers, rows)


def report_lines(inventory: Inventory) -> list[str]:
    lines = [REPORT_TITLE, "=" * len(REPORT_TITLE), ""]
    lines.append(f"Products: {len(list(inventory.products()))}")
    lines.append(f"Units: {inventory.total_units()}")
    lines.append(f"Inventory value: {money(inventory.total_value())}")
    lines.append("")
    lines.append(inventory_table(inventory))
    lines.append("")
    lines.append("Low stock")
    for product in inventory.low_stock():
        lines.append(f"- {product.display_name()}: {product.quantity} remaining")
    return lines


def build_report(inventory: Inventory) -> str:
    return "\n".join(report_lines(inventory))


def parse_quantity(raw_value: str) -> int:
    cleaned = raw_value.strip().replace(",", "")
    value = int(cleaned)
    if value < 0:
        raise ValueError("Quantity must not be negative")
    return value


def normalize_tags(raw_tags: str) -> list[str]:
    return [tag.strip().lower() for tag in raw_tags.split(",") if tag.strip()]


def merge_tags(existing: list[str], new_tags: Iterable[str]) -> list[str]:
    seen = {tag.casefold() for tag in existing}
    result = list(existing)
    for tag in new_tags:
        if tag.casefold() not in seen:
            result.append(tag)
            seen.add(tag.casefold())
    return result


def mark_discontinued(inventory: Inventory, sku: str) -> Product:
    product = inventory.product(sku)
    product.discontinued = True
    return product


def reactivate(inventory: Inventory, sku: str) -> Product:
    product = inventory.product(sku)
    product.discontinued = False
    return product


def inventory_age_days(inventory: Inventory) -> int:
    now = datetime.now(timezone.utc)
    return (now - inventory._created_at).days


def oldest_movement(inventory: Inventory) -> Movement | None:
    history = inventory.movement_history()
    if not history:
        return None
    return min(history, key=lambda movement: movement.occurred_at)


def newest_movement(inventory: Inventory) -> Movement | None:
    history = inventory.movement_history()
    if not history:
        return None
    return max(history, key=lambda movement: movement.occurred_at)


def sample_inventory() -> Inventory:
    products = [
        Product("A-100", "Notebook", Decimal("4.50"), 12, "Stationery", ["paper"]),
        Product("A-101", "Blue Pen", Decimal("1.25"), 4, "Stationery", ["ink", "blue"]),
        Product("B-200", "Desk Lamp", Decimal("24.99"), 2, "Furniture", ["lighting"]),
        Product("C-300", "Travel Mug", Decimal("12.00"), 18, "Kitchen", ["steel"]),
    ]
    return Inventory(products)


def validate_inventory(inventory: Inventory) -> list[str]:
    issues: list[str] = []
    for product in inventory.products():
        if product.quantity < 0:
            issues.append(f"{product.sku}: negative quantity")
        if product.unit_price < 0:
            issues.append(f"{product.sku}: negative price")
        if not product.name.strip():
            issues.append(f"{product.sku}: missing name")
        if product.category.strip() == "":
            issues.append(f"{product.sku}: missing category")
    return issues


def reserve_stock(inventory: Inventory, sku: str, amount: int) -> int:
    product = inventory.product(sku)
    if amount > product.quantity:
        raise InvalidMovementError("Cannot reserve more than available")
    product.quantity -= amount
    return product.quantity


def average_unit_price(products: Iterable[Product]) -> Decimal:
    entries = list(products)
    if not entries:
        return Decimal("0")
    total = sum((entry.unit_price for entry in entries), Decimal("0"))
    return total / len(entries)


def delete_discontinued(inventory: Inventory) -> int:
    targets = [product.sku for product in inventory.discontinued()]
    for sku in targets:
        del inventory._products[sku]
    return len(targets)


def apply_discount(product: Product, percentage: Decimal) -> Decimal:
    if percentage < 0 or percentage > 100:
        raise ValueError("Discount percentage must be between 0 and 100")
    discount = product.unit_price * percentage / Decimal("100")
    product.unit_price -= discount
    return product.unit_price


def contains_required_fields(data: dict[str, object]) -> bool:
    required = {"sku", "name", "unit_price", "quantity", "category"}
    return required.issubset(data)


def describe_product(product: Product) -> str:
    state = "discontinued" if product.discontinued else "active"
    return f"{product.display_name()} is {state} with {product.quantity} units"


def stock_status(product: Product) -> str:
    if product.discontinued:
        return "discontinued"
    if product.quantity == 0:
        return "out of stock"
    if product.is_low_stock():
        return "low stock"
    return "in stock"


def products_with_tag(inventory: Inventory, tag: str) -> list[Product]:
    target = tag.casefold().strip()
    return [
        product
        for product in inventory.products()
        if target in {item.casefold() for item in product.tags}
    ]


def remove_tag(product: Product, tag: str) -> None:
    product.tags = [item for item in product.tags if item.casefold() != tag.casefold()]


def compact_summary(inventory: Inventory) -> dict[str, str]:
    return {
        "products": str(len(list(inventory.products()))),
        "units": str(inventory.total_units()),
        "value": money(inventory.total_value()),
        "low_stock": str(len(inventory.low_stock())),
    }


def should_reorder(product: Product, minimum: int, maximum: int) -> bool:
    if minimum > maximum:
        raise ValueError("minimum must be no greater than maximum")
    return product.quantity >= minimum


def matching_skus(inventory: Inventory, prefix: str) -> list[str]:
    return sorted(
        product.sku
        for product in inventory.products()
        if product.sku.casefold().startswith(prefix.casefold())
    )


def shipment_label(product: Product, destination: str) -> str:
    return f"SHIP TO: {destination.upper()} | {product.sku} | {product.name}"


def infer_reorder_amount(product: Product, target: int) -> int:
    if target < 0:
        raise ValueError("target must be non-negative")
    return max(target - product.quantity, 0)


def months_of_supply(product: Product, monthly_sales: int) -> Decimal:
    if monthly_sales <= 0:
        return Decimal("0")
    return Decimal(product.quantity) / Decimal(monthly_sales)


def print_report(inventory: Inventory) -> None:
    print(build_report(inventory))


def export_rows(inventory: Inventory) -> list[dict[str, object]]:
    return [serialize_product(product) for product in inventory.products()]


def import_rows(rows: Iterable[dict[str, object]]) -> Inventory:
    return Inventory(deserialize_product(row) for row in rows)


def main() -> None:
    inventory = sample_inventory()
    inventory.receive("A-100", 8, "PO-250")
    inventory.ship("C-300", 3, "SO-091")
    print_report(inventory)


if __name__ == "__main__":
    main()


def malformed_condition(product: Product) -> bool:
    if product.quantity > 0
        return True
    return False


def unfinished_total(inventory: Inventory) -> Decimal:
    return inventory.total_value() +
