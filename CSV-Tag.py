import csv
import datetime
import json

yes = ['Bergen', 'Burlington', 'Camden', 'Camden City', 'Essex', 'Hudson', 'Middlesex', 'Morris', 'Passaic', 'Somerset',
       'Union']
no = ['Atlantic', 'Cape May', 'Cumberland', 'Gloucester', 'Hunterdon', 'Mercer', 'Monmouth', 'Ocean', 'Salem', 'Sussex',
      'Warren']
fieldnames = ['Venue', 'Case Type', 'CourtPropertyAddress', 'Case Initiation Date', 'Case Status', "CourtBusinessName",
              "CourtNameType", "CourtFirstName", "CourtMiddleName", "CourtLastName", "StateTaxBusinessName",
              "CourtNormalizedPropertyAddress", "Sift1PropStreet", "Sift1PropCity", "Sift1PropState", "Sift1PropZip",
              'Tags', 'Comments']


def main():
    new_rows = []
    infile = input("Enter the input file name: ")
    outfile = input("Enter the output file name: ")
    with open(infile, 'r', encoding='utf-8-sig') as f:
        csv_file = csv.DictReader(f)
        for row in csv_file:
            # print(row)
            tags = []
            if "Camden City" in row['CourtPropertyAddress']:
                tags.append('NJC 11-NO-COs')
            elif row['Venue'] in yes:
                tags.append('NJC 10-YES-COs')
            elif row['Venue'] in no:
                tags.append('NJC 11-NO-COs')

            tags.append(f'zz1-NJ-{row["Venue"]} Co')
            tags.append(f'zz0-NJ-{row["Case Status"]} Co')

            if row['Case Type'] == 'In Personam Tax Foreclosure' or row['Case Type'] == 'In Rem Tax Foreclosure':
                tags.append('NJC🧿-PROPERTY TAX PreFORECLOSURE🔥🧧👢🔥')
            elif row['Case Type'] == 'Commercial Mortgage Foreclosure':
                tags.append('NJC🧿-PreForeclosure🧿👢')
                tags.append('NJC Commercial M-Forec')
            else:
                tags.append('NJC🧿-PreForeclosure🧿👢')
            date = datetime.datetime.strptime(row['Case Initiation Date'], '%Y-%m-%d')
            tags.append(f'LP Bot NJCF {date.strftime("%Y-%m")} 🟦🤖')
            tags.append(f'zz_NJC_{date.strftime("%Y-%m-%d")}')
            new_row = {
                "Venue": row['Venue'],
                "Case Type": row['Case Type'],
                "CourtPropertyAddress": row['CourtPropertyAddress'],
                "Case Initiation Date": row['Case Initiation Date'],
                "Case Status": row['Case Status'],
                "Tags": ', '.join(tags),
                # "Comments": json.dumps(json.loads(row['Comments']), indent=4)
            }
            for field in fieldnames:
                if field not in new_row:
                    new_row[field] = row[field]
            print(new_row)
            new_row['Comments'] = json.dumps(new_row.copy(), indent=4)
            new_rows.append(new_row)
    with open(outfile, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)


if __name__ == '__main__':
    main()
