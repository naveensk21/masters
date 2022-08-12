import json


# data without 'bad' labels
clean_dataset_file_path = 'clean_combined_data.json'

# data with label support
label_support_file_path = 'label_support.json'


with open(clean_dataset_file_path) as fp:
    dataset_json = json.load(fp)


counters = {}
# count labels support
for datapoint in dataset_json:
    labels = datapoint["labels"]
    for label in labels:
        if counters.get(label) is not None:
            counters[label] += 1
        else:
            counters[label] = 1


for label, occurances_count in counters.items():
    if occurances_count > 40:
        print(f"{occurances_count}: {label}")


with open(label_support_file_path, "w") as fp:
    json.dump(counters, fp)
    print(f"Stored the support in: {label_support_file_path}")
