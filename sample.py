def calculate_average(numbers):
    total = 0

    for num in numbers:
        total += num

    average = total / len(numbers)

    return average


nums = [10, 20, 30, 40, 50]

print("Numbers:", nums)
print("Average:", calculate_average(nums))

if calculate_average(nums) > 30:
    print("The average is high")
else:
    print("The average is low")
