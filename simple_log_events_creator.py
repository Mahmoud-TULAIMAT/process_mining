import csv
import datetime
import random

# Function to generate a random timestamp
def random_timestamp(start_date):
    random_days = random.randint(0, 30)
    return start_date + datetime.timedelta(days=random_days)

# Function to create CSV content
def create_csv_content(events, start_date):
    content = []
    current_timestamp = random_timestamp(start_date)
    id_counter = 1

    for sequence, count in events:
        for _ in range(count):
            for item in sequence.split(','):
                # Adjusted to match the desired format: case_id, activity_name, timestamp
                content.append([f'{id_counter:04d}', item, current_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')])
                
            current_timestamp += datetime.timedelta(days=1)
            id_counter += 1

    return content

# Function to write the content to a CSV file
def write_csv(filename, content):
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Updated header to match the desired format
        writer.writerow(['case_id', 'activity_name', 'timestamp'])
        writer.writerows(content)

# Event logs with the simplest one added at the beginning
logs = [
    ([
        ("a,b,c,d", 3),
        ("a,c,b,d", 2),
        ("a,e,d", 1)
    ], 'simplest_log'),
    ([
        ("a,b,c,e", 5),
        ("a,c,b,e", 4),
        ("a,b,c,d,b,c,e", 3),
        ("a,c,b,d,b,c,e", 2),
        ("a,b,c,d,c,b,e", 10),
        ("a,c,b,d,c,b,d,b,c,e", 1)
    ], 'log1'),
    ([
        ("a,c,e,g", 2),
        ("a,e,c,g", 3),
        ("b,d,f,g", 2),
        ("b,f,d,g", 4)
    ], 'log2'),
    ([
        ("a,c,d", 4),
        ("b,c,e", 4)
    ], 'log3'),
    ([
        ("a,b,a,b", 5),
        ("a,c", 2)
    ], 'log4'),
    ([
        ("a,b,c,e", 10),
        ("a,c,b,e", 5),
        ("a,d,e", 1)
    ], 'log5'),
    ([
        ("a,b", 35),
        ("b,a", 15)
    ], 'log6'),
    ([
        ("a", 10),
        ("a,b", 8),
        ("a,c,b", 6),
        ("a,c,c,b", 6),
        ("a,c,c,c,b", 6)
    ], 'log7'),
    ([
        ("a,b,e,f", 2),
        ("a,b,e,c,d,b,f", 3),
        ("a,b,c,e,d,b,f", 2),
        ("a,b,c,d,e,b,f", 4),
        ("a,e,b,c,d,b,f", 3)
    ], 'log8')
]

# Base timestamp (start date for random timestamp generation)
base_date = datetime.datetime.now()

# Process each log
for events, filename_prefix in logs:
    content = create_csv_content(events, base_date)
    write_csv(f'C:\\projects\\Process mining\\event logs\\{filename_prefix}.csv', content)
    # Update base_date for the next log to maintain sequential dates
    base_date += datetime.timedelta(days=1)
