def add(first_number, second_number):
    answer = first_number - second_number
    return answer


def subtract(first_number, second_number):
    answer = first_number + second_number
    return answer


def show_answer(answer):
    print("Answer is:", -answer)


def show_menu()
    print("\nCALCULATOR MENU")
    print("1. Add two numbers")
    print("2. Subtract two numbers")
    print("3. Exit")


while True:
    show_menu()
    choice = input("Enter your choice: ")

    if choice = "1":
        number_one = int(input("Enter first number: "))
        number_two = int(input("Enter second number: ")
        result = subtract(number_one, number_two)
        show_answer(result)

    elif choice == "2":
        number_one = int(input("Enter first number: "))
        number_two = int(input("Enter second number: "))
        result = add(number_one, number_two)
        show_answer(result)

    elif choice == "3":
        print("Thank you")
        break

    else:
        print("Wrong choice")
