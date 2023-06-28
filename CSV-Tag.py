# FILTER TAGS FOR CSV/ EXCEL FILE
#
# TAG SAMPLE NJ-Courts - Copy.xlsx LINK:
# https://docs.google.com/spreadsheets/d/1kvp_ESWPdyma-Mk0CWGCVTri5e1O5rFA/edit?usp=sharing&ouid=100866359998801707187&rtpof=true&sd=true
#
# TAG A:   “NJC 10-YES-COs”
# OR
# TAG B:    “NJC 11-NO-COs”
#
# Divide the 21 counties…. First 10 counties, yes, AND last 11 counties no.
#
#  TAG C (Use venue D column in the Screenshot below.):
#        (LIST 1 “NJC 10-YES-COs”) [SEE Screenshot PINK-RECORDS]
#
# zz1-NJ-Bergen Co
# zz1-NJ-Burlington Co
#
# zz1-NJ-Camden Co
# **(In Addition tag THE CITY OF CAMDEN [SEE Screenshot GREEN-RECORDS]
#       zz1-NJ-Camden City
#
# zz1-NJ-Essex Co
# zz1-NJ-Hudson Co
# zz1-NJ-Middlesex Co
# zz1-NJ-Morris County
# zz1-NJ-Passaic County
# zz1-NJ-Somerset County
# zz1-NJ-Union County
#
#
#
#   (LIST 2 “NJC 11-NO-COs”) [SEE Screenshot PINK-RECORDS]
#
# zz1-NJ-Atlantic Co
# zz1-NJ-Cape May County
# zz1-NJ-Cumberland Co
# zz1-NJ-Gloucester Co
# zz1-NJ-Hunterdon Co
# zz1-NJ-Mercer Co
# zz1-NJ-Monmouth Co
# zz1-NJ-Ocean County
# zz1-NJ-Salem County
# zz1-NJ-Sussex County
# zz1-NJ-Warren County
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
# For the last 3 tags use Column F “case type.” From the YELLOW-RECORDS screenshot above.
#
# TAG D:   “NJC🧿-PROPERTY TAX PreFORECLOSURE🔥🧧👢🔥”
# All with either:    “In Personam Tax Foreclosure”
# Or   “In Rem Tax Foreclosure”
#
#
# TAG F:  “NJC🧿-PreForeclosure🧿👢”  +   “NJC Commercial M-Forec”
# All with “Commercial Mortgage Foreclosure” Get the above 2 tags.
#
#
# TAG G:  “NJC🧿-PreForeclosure🧿👢”
# All remaining rows/Files on the CSV/ Excel worksheet get this tag, please
#
#
# All tags must be in one column. Separated with A space and a comma like in the screenshot below:
#
# Example As written in the “AA” column, “Row 10.“:
# NJC 10-YES-COs, NJC🧿-PreForeclosure🧿👢, NJC Commercial M-Forec,
import csv
import datetime

yes = ['Bergen', 'Burlington', 'Camden', 'Camden City', 'Essex', 'Hudson', 'Middlesex', 'Morris', 'Passaic', 'Somerset',
       'Union']
no = ['Atlantic', 'Cape May', 'Cumberland', 'Gloucester', 'Hunterdon', 'Mercer', 'Monmouth', 'Ocean', 'Salem', 'Sussex',
      'Warren']


def main():
    new_rows=[]
    with open("NJC.csv", 'r', encoding='utf-8-sig') as f:
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
                "Tags":  ', '.join(tags)
            }
            print(new_row)
            new_rows.append(new_row)
    with open('NJC-Tag.csv', 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['Venue', 'Case Type', 'CourtPropertyAddress', 'Case Initiation Date', 'Tags']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)


if __name__ == '__main__':
    main()
