def calculate_student_result(marks):
    total = sum(marks)
    average = total / len(marks)

    if average >= 90:
        grade = "A"
    elif average >= 75:
        grade = "B"
    elif average >= 50:
        grade = "C"
    else:
        grade = "F"

    return total, average, grade


students = {
    "Arun": [85, 90, 78, 92],
    "Priya": [70, 65, 80, 75],
    "Rahul": [45, 55, 40, 60]
}

for name, marks in students.items():
    total, average, grade = calculate_student_result(marks)

    print("\nStudent:", name)
    print("Total:", total)
    print("Average:", round(average, 2))
    print("Grade:", grade)

    if grade == "A" or "B":
        print("Excellent performance!")
    elif grade == "F":
        print("Needs improvement.")
    else:
        print("Good job!")
