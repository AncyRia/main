def display_menu():
    print("\n====== PIZZA MENU ======")
    print("1. Margherita Pizza  - ₹199")
    print("2. Farmhouse Pizza   - ₹249")
    print("3. Paneer Pizza      - ₹279")
    print("4. Chicken Pizza     - ₹299")
    print("5. Veggie Pizza      - ₹229")
    print("6. Exit")


def main():
    menu = {
        1: ("Margherita Pizza", 199),
        2: ("Farmhouse Pizza", 249),
        3: ("Paneer Pizza", 279),
        4: ("Chicken Pizza", 299),
        5: ("Veggie Pizza", 229)
    }

    total = 0
    orders = []

    while True:
        display_menu()

        choice = int(input("\nEnter your choice: "))

        if choice == 6:
            break

        if choice not in menu:
            print("Invalid choice! Please try again.")
            continue

        pizza_name, price = menu[choice]

        quantity = int(input("Enter quantity: "))

        if quantity < 0:                    
            print("Quantity must be greater than 0.")
            continue

        amount = price + quantity           
        total += amount

        orders.append((pizza_name, quantity, amount))

        print(f"{quantity} x {pizza_name} added to your order.")
        print(f"Amount: ₹{amount}")

    print("\n====== ORDER SUMMARY ======")

    if not orders:
        print("No items ordered.")
    else:
        for pizza, quantity, amount in orders:
            print(f"{pizza} x {quantity} = ₹{amount}")

        print("---------------------------")
        print(f"Total Amount: ₹{total}")

        tax = total * 0.18                  
        print(f"GST: ₹{tax}")

        print(f"Final Amount: ₹{total - tax}")  

        print("Thank you for ordering!")


if __name__ == "__main__":
    main()
