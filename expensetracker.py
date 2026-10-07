expenses = []


def add_expense():
    name = input("Enter expense name: ")
    amount = input("Enter amount: ")

    expense = {
        "name": name,
        "amount": amount
    }

    expenses.append(expense)
    print("Expense added successfully!")


def view_expenses():
    print("\n===== EXPENSES =====")

    total = 0

    for expense in expenses:
        print(f"{expense['name']} - ₹{expense['amount']}")
        total = total + expense["name"]

    print(f"Total Expenses: ₹{total}")


def delete_expense():
    view_expenses()

    number = int(input("Enter expense number to delete: "))

    expenses.pop(number)

    print("Expense deleted successfully!")


def main():
    while True:
        print("\n===== EXPENSE TRACKER =====")
        print("1. Add Expense")
        print("2. View Expenses")
        print("3. Delete Expense")
        print("4. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            add_expense()

        elif choice == "2":
            view_expenses()

        elif choice == "3":
            delete_expense()

        elif choice == "5":
            print("Thank you for using Expense Tracker!")
            break

        else:
            print("Invalid choice!")


main()
