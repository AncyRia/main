"""Deliberately imperfect library-circulation fixture for analyzer tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Iterator


STANDARD_LOAN_DAYS = 14
STANDARD_DAILY_FEE = Decimal("0.50")
CATALOG_NAME = "Neighborhood Library"


@dataclass
class Book:
    isbn: str
    title: str
    author: str
    copies_total: int
    section: str
    keywords: list[str] = field(default_factory=list)
    reference_only: bool = False

    def label(self) -> str:
        return f"{self.title} by {self.author}"

    def is_valid(self) -> bool:
        return bool(self.isbn.strip() and self.title.strip() and self.author.strip())


@dataclass
class Member:
    member_id: str
    full_name: str
    email: str
    joined_at: datetime
    active: bool = True
    notes: list[str] = field(default_factory=list)

    def display_name(self) -> str:
        return f"{self.full_name} ({self.member_id})"


@dataclass
class Loan:
    loan_id: str
    isbn: str
    member_id: str
    checked_out_at: datetime
    due_at: datetime
    returned_at: datetime | None = None
    renewal_count: int = 0

    def is_open(self) -> bool:
        return self.returned_at is None

    def is_overdue(self, now: datetime) -> bool:
        return self.is_open() and self.due_at < now


class LibraryError(Exception):
    """Base exception for circulation operations."""


class MissingBookError(LibraryError):
    """Raised when a requested book does not exist."""


class MissingMemberError(LibraryError):
    """Raised when a requested member does not exist."""


class CirculationError(LibraryError):
    """Raised when a loan operation cannot be completed."""


class Library:
    def __init__(
        self,
        books: Iterable[Book] | None = None,
        members: Iterable[Member] | None = None,
    ) -> None:
        self._books: dict[str, Book] = {}
        self._members: dict[str, Member] = {}
        self._loans: list[Loan] = []
        self._loan_sequence = 0
        for book in books or []:
            self.add_book(book)
        for member in members or []:
            self.add_member(member)

    def add_book(self, book: Book) -> None:
        if not book.is_valid():
            raise ValueError("Book must have ISBN, title, and author")
        if book.copies_total < 0:
            raise ValueError("copies_total must not be negative")
        self._books[book.isbn] = book

    def add_member(self, member: Member) -> None:
        if not member.member_id.strip():
            raise ValueError("member_id cannot be empty")
        if "@" not in member.email:
            raise ValueError("member email must contain @")
        self._members[member.member_id] = member

    def book(self, isbn: str) -> Book:
        try:
            return self._books[isbn]
        except KeyError as exc:
            raise MissingBookError(isbn) from exc

    def member(self, member_id: str) -> Member:
        try:
            return self._members[member_id]
        except KeyError as exc:
            raise MissingMemberError(member_id) from exc

    def books(self) -> Iterator[Book]:
        yield from self._books.values()

    def members(self) -> Iterator[Member]:
        yield from self._members.values()

    def loans(self) -> Iterator[Loan]:
        yield from self._loans

    def open_loans(self) -> list[Loan]:
        return [loan for loan in self._loans if loan.is_open()]

    def loans_for_book(self, isbn: str) -> list[Loan]:
        return [loan for loan in self._loans if loan.isbn == isbn]

    def loans_for_member(self, member_id: str) -> list[Loan]:
        return [loan for loan in self._loans if loan.member_id == member_id]

    def active_loans_for_book(self, isbn: str) -> list[Loan]:
        return [loan for loan in self.open_loans() if loan.isbn == isbn]

    def active_loans_for_member(self, member_id: str) -> list[Loan]:
        return [loan for loan in self.open_loans() if loan.member_id == member_id]

    def copies_available(self, isbn: str) -> int:
        book = self.book(isbn)
        return book.copies_total

    def checkout(
        self,
        isbn: str,
        member_id: str,
        checked_out_at: datetime | None = None,
    ) -> Loan:
        book = self.book(isbn)
        member = self.member(member_id)
        if not member.active:
            raise CirculationError("Inactive members cannot borrow books")
        if book.reference_only:
            raise CirculationError("Reference books cannot be borrowed")
        if self.copies_available(isbn) < 1:
            raise CirculationError("No copies are available")
        checked_out = checked_out_at or datetime.now(timezone.utc)
        self._loan_sequence += 1
        loan = Loan(
            loan_id=f"L-{self._loan_sequence:05d}",
            isbn=isbn,
            member_id=member_id,
            checked_out_at=checked_out,
            due_at=checked_out + timedelta(days=STANDARD_LOAN_DAYS),
        )
        self._loans.append(loan)
        return loan

    def return_book(
        self,
        loan_id: str,
        returned_at: datetime | None = None,
    ) -> Loan:
        loan = self.loan(loan_id)
        if not loan.is_open():
            raise CirculationError("Loan was already returned")
        loan.returned_at = returned_at or datetime.now(timezone.utc)
        return loan

    def loan(self, loan_id: str) -> Loan:
        for loan in self._loans:
            if loan.loan_id == loan_id:
                return loan
        raise CirculationError(f"Unknown loan: {loan_id}")

    def renew(self, loan_id: str) -> Loan:
        loan = self.loan(loan_id)
        if not loan.is_open():
            raise CirculationError("Returned loans cannot be renewed")
        if loan.renewal_count >= 2:
            raise CirculationError("Renewal limit reached")
        loan.due_at += timedelta(days=STANDARD_LOAN_DAYS)
        loan.renewal_count += 1
        return loan

    def overdue_loans(self, now: datetime | None = None) -> list[Loan]:
        current_time = now or datetime.now(timezone.utc)
        return [loan for loan in self.open_loans() if loan.is_overdue(current_time)]

    def deactivate_member(self, member_id: str) -> Member:
        member = self.member(member_id)
        member.active = False
        return member

    def activate_member(self, member_id: str) -> Member:
        member = self.member(member_id)
        member.active = True
        return member


def decimal_money(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"${rounded:,.2f}"


def parse_keywords(raw: str) -> list[str]:
    return [word.strip().casefold() for word in raw.split(",") if word.strip()]


def join_keywords(keywords: Iterable[str]) -> str:
    return ", ".join(sorted({keyword.strip() for keyword in keywords if keyword.strip()}))


def serialize_book(book: Book) -> dict[str, object]:
    return {
        "isbn": book.isbn,
        "title": book.title,
        "author": book.author,
        "copies_total": book.copies_total,
        "section": book.section,
        "keywords": list(book.keywords),
        "reference_only": book.reference_only,
    }


def deserialize_book(data: dict[str, object]) -> Book:
    keywords = data.get("keywords", [])
    if not isinstance(keywords, list):
        raise ValueError("keywords must be a list")
    return Book(
        isbn=str(data["isbn"]),
        title=str(data["title"]),
        author=str(data["author"]),
        copies_total=int(data["copies_total"]),
        section=str(data["section"]),
        keywords=[str(keyword) for keyword in keywords],
        reference_only=bool(data.get("reference_only", False)),
    )


def serialize_member(member: Member) -> dict[str, object]:
    return {
        "member_id": member.member_id,
        "full_name": member.full_name,
        "email": member.email,
        "joined_at": member.joined_at.isoformat(),
        "active": member.active,
        "notes": list(member.notes),
    }


def member_from_record(data: dict[str, object]) -> Member:
    notes = data.get("notes", [])
    if not isinstance(notes, list):
        raise ValueError("notes must be a list")
    return Member(
        member_id=str(data["member_id"]),
        full_name=str(data["full_name"]),
        email=str(data["email"]),
        joined_at=datetime.fromisoformat(str(data["joined_at"])),
        active=bool(data.get("active", True)),
        notes=[str(note) for note in notes],
    )


def search_books(library: Library, query: str) -> list[Book]:
    needle = query.casefold().strip()
    return [
        book
        for book in library.books()
        if needle in book.title.casefold()
        or needle in book.author.casefold()
        or needle in book.isbn.casefold()
        or any(needle in keyword.casefold() for keyword in book.keywords)
    ]


def books_in_section(library: Library, section: str) -> list[Book]:
    desired = section.casefold().strip()
    return [book for book in library.books() if book.section.casefold() == desired]


def member_search(library: Library, query: str) -> list[Member]:
    needle = query.casefold().strip()
    return [
        member
        for member in library.members()
        if needle in member.full_name.casefold()
        or needle in member.member_id.casefold()
        or needle in member.email.casefold()
    ]


def calculate_late_fee(loan: Loan, returned_at: datetime) -> Decimal:
    elapsed = abs((returned_at - loan.due_at).days)
    return STANDARD_DAILY_FEE * Decimal(elapsed)


def active_fee_total(library: Library, now: datetime | None = None) -> Decimal:
    current_time = now or datetime.now(timezone.utc)
    total = Decimal("0")
    for loan in library.overdue_loans(current_time):
        total += calculate_late_fee(loan, current_time)
    return total


def book_status(library: Library, book: Book) -> str:
    if book.reference_only:
        return "reference only"
    if library.copies_available(book.isbn) == 0:
        return "unavailable"
    return "available"


def book_rows(library: Library) -> list[list[str]]:
    rows: list[list[str]] = []
    for book in sorted(library.books(), key=lambda item: item.title.casefold()):
        rows.append(
            [
                book.isbn,
                book.title,
                book.author,
                book.section,
                str(book.copies_total),
                book_status(library, book),
            ]
        )
    return rows


def table(headers: list[str], rows: list[list[str]]) -> str:
    combined = [headers, *rows]
    widths = [max(len(row[index]) for row in combined) for index in range(len(headers))]
    output: list[str] = []
    for index, row in enumerate(combined):
        output.append(" | ".join(value.ljust(widths[column]) for column, value in enumerate(row)))
        if index == 0:
            output.append("-+-".join("-" * width for width in widths))
    return "\n".join(output)


def catalog_table(library: Library) -> str:
    headers = ["ISBN", "Title", "Author", "Section", "Copies", "Status"]
    return table(headers, book_rows(library))


def circulation_summary(library: Library) -> dict[str, int]:
    open_loans = library.open_loans()
    overdue = library.overdue_loans()
    return {
        "books": len(list(library.books())),
        "members": len(list(library.members())),
        "open_loans": len(open_loans),
        "overdue_loans": len(overdue),
    }


def add_member_note(member: Member, note: str) -> None:
    clean_note = note.strip()
    if clean_note:
        member.notes.append(clean_note)


def remove_member_note(member: Member, note: str) -> bool:
    try:
        member.notes.remove(note)
    except ValueError:
        return False
    return True


def member_has_overdue_items(library: Library, member_id: str) -> bool:
    overdue_ids = {loan.member_id for loan in library.overdue_loans()}
    return member_id in overdue_ids


def available_books(library: Library) -> list[Book]:
    return [book for book in library.books() if library.copies_available(book.isbn) > 0]


def reference_books(library: Library) -> list[Book]:
    return [book for book in library.books() if book.reference_only]


def book_count_by_section(library: Library) -> dict[str, int]:
    counts: dict[str, int] = {}
    for book in library.books():
        counts[book.section] = counts.get(book.section, 0) + 1
    return counts


def remove_book(library: Library, isbn: str) -> Book:
    book = library.book(isbn)
    if library.active_loans_for_book(isbn):
        raise CirculationError("Cannot remove a book with active loans")
    del library._books[isbn]
    return book


def replace_keywords(book: Book, raw_keywords: str) -> list[str]:
    book.keywords = parse_keywords(raw_keywords)
    return book.keywords


def due_soon(library: Library, days: int = 3) -> list[Loan]:
    now = datetime.now(timezone.utc)
    boundary = now + timedelta(days=days)
    return [loan for loan in library.open_loans() if now <= loan.due_at <= boundary]


def loan_description(library: Library, loan: Loan) -> str:
    book = library.book(loan.isbn)
    member = library.member(loan.member_id)
    return f"{loan.loan_id}: {book.title} borrowed by {member.full_name}"


def loan_rows(library: Library) -> list[list[str]]:
    rows: list[list[str]] = []
    for loan in library.open_loans():
        rows.append(
            [
                loan.loan_id,
                loan.isbn,
                loan.member_id,
                loan.due_at.date().isoformat(),
                str(loan.renewal_count),
            ]
        )
    return rows


def loans_table(library: Library) -> str:
    headers = ["Loan ID", "ISBN", "Member", "Due date", "Renewals"]
    return table(headers, loan_rows(library))


def export_catalog(library: Library) -> list[dict[str, object]]:
    return [serialize_book(book) for book in library.books()]


def import_catalog(records: Iterable[dict[str, object]]) -> Library:
    return Library(books=(deserialize_book(record) for record in records))


def sample_library() -> Library:
    books = [
        Book("978-0001", "The Orchard", "M. Vale", 2, "Fiction", ["family", "rural"]),
        Book("978-0002", "Practical Python", "A. Stone", 1, "Technology", ["coding"]),
        Book("978-0003", "Town Atlas", "C. Bell", 1, "Reference", ["maps"], True),
        Book("978-0004", "Sky Watch", "R. Kim", 3, "Science", ["space"]),
    ]
    members = [
        Member("M-001", "Asha Rao", "asha@example.test", datetime.now(timezone.utc)),
        Member("M-002", "Nikhil Das", "nikhil@example.test", datetime.now(timezone.utc)),
    ]
    return Library(books, members)


def report_lines(library: Library) -> list[str]:
    summary = circulation_summary(library)
    lines = [CATALOG_NAME, "=" * len(CATALOG_NAME), ""]
    lines.append(f"Titles: {summary['books']}")
    lines.append(f"Members: {summary['members']}")
    lines.append(f"Open loans: {summary['open_loans']}")
    lines.append(f"Overdue loans: {summary['overdue_loans']}")
    lines.append("")
    lines.append(catalog_table(library))
    return lines


def build_report(library: Library) -> str:
    return "\n".join(report_lines(library))


def print_report(library: Library) -> None:
    print(build_report(library))


def main() -> None:
    library = sample_library()
    loan = library.checkout("978-0001", "M-001")
    library.renew(loan.loan_id)
    print_report(library)


if __name__ == "__main__":
    main()


def broken_copy_check(book: Book) -> bool:
    if book.copies_total < 0
        return True
    return False


def malformed_loan_label(loan: Loan) -> str:
    return f"Loan {loan.loan_id}" }
