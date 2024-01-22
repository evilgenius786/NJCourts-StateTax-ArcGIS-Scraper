import csv
import datetime
import json
import os.path
import re
import time
import traceback
from time import sleep

import chromedriver_autoinstaller
# import chromedriver_binary_sync
import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

t = 1
timeout = 10

lastrun = {"StartYear": 22, "EndYear": 22, "StartNumber": 1, "EndNumber": 100, "CurrentYear": 22, "CurrentNumber": 1}
if os.path.isfile("LastRun.json"):
    with open("LastRun.json", 'r') as infile:
        lastrun = json.load(infile)
    # print("LastRun.json found")
    # print(json.dumps(lastrun, indent=4))
download_dir = rf"{os.getcwd()}\downloads"
tax_dir = "ALL TAX-F AGGREGATE"
jdir = "ALL NJ-Court FORC DEFAULT"
filter_dir = "All NJ-COURT Filtered Forc"
other_dir = "Did NOT FILTER"
changeddir = "changed"
scrapedcsv = "NJ-Courts.csv"
debug = os.path.isfile("debug")
# debug = False
test = False
headless = False
images = True
maximize = False
incognito = False
encoding = 'utf-8-sig'
nj_url = 'https://portal.njcourts.gov/CIVILCaseJacketWeb/pages/civilCaseSearch.faces'
disclaimer = "https://portal.njcourts.gov/webcivilcj/CIVILCaseJacketWeb/pages/publicAccessDisclaimer.faces"
count = 1
tdh = "https://www.taxdatahub.com"
cpash = "County%20Property%20Assessment%20Search%20Hub"
tax_data_url = {
    "Burlington": "623af8995103551060110abc",
    "Camden": "60d088c3d3501df3b0e45ddb",
    "Essex": "6229fbf0ce4aef911f9de7bc",
    "Middlesex": "623085dd284c51d4d32ff9fe",
}

yes = ['Bergen', 'Burlington', 'Camden', 'Camden City', 'Essex', 'Hudson', 'Middlesex', 'Morris', 'Passaic', 'Somerset',
       'Union', 'Hunterdon', 'Monmouth', 'Ocean', 'Sussex', 'Warren']
# Add these counties but exempt certain cities:
#
# Atlantic Co        NO:   Atlantic City,   NO Mays landing
# Mercer Co         NO: TRENTON
# Gloucester Co   NO:     Paulsboro, Westville and Woodbury
# -
# you must add the property new tag    18-YES-COs
no_cities = {
    "Atlantic": ["Atlantic City", "Mays Landing"],
    "Mercer": ["Trenton"],
    "Gloucester": ["Paulsboro", "Westville", "Woodbury"]
}
no = ['Atlantic', 'Cape May', 'Cumberland', 'Gloucester', 'Mercer', 'Salem']


def getTag(row):
    tags = []
    if "Camden City" in row['CourtPropertyAddress']:
        tags.append('NJC 11-NO-COs')
    elif row['Venue'] in yes:
        tags.append('NJC 18-YES-COs')
    # elif row['Sift1PropCity']
    elif row['Venue'] in no_cities:
        if row['Sift1PropCity'] in no_cities[row['Venue']]:
            tags.append('NJC 11-NO-COs')
        else:
            tags.append('NJC 18-YES-COs')
    elif row['Venue'] in no:
        tags.append('NJC 11-NO-COs')
    if "Sift1PropCity" in row and row['Sift1PropCity'] != row['Sift1MailingCity'] and row['Sift1MailingCity'] != "":
        tags.append('Absentee_Owners_BOT')
    tags.append(f'zz1-NJ-{row["Venue"]} Co')
    # zz0-NJ-Closed
    # zz0-NJ-Dismissed
    tags.append(f'zz0-NJ-{row["Case Status"]} Co')

    if row['Case Type'] == 'In Personam Tax Foreclosure' or row['Case Type'] == 'In Rem Tax Foreclosure':
        tags.append('NJC🧿-PROPERTY TAX PreFORECLOSURE🔥🧧👢🔥')
    elif row['Case Type'] == 'Commercial Mortgage Foreclosure':
        tags.append('NJC🧿-PreForeclosure🧿👢')
        tags.append('NJC Commercial M-Forec')
    elif row['Case Type'] =="Residential Mortgage Foreclosure":
        tags.append('NJC🧿-PreForeclosure🧿👢')
        tags.append('z-Reverse Mortgage (njc)')
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
        "Tags": ', '.join(tags)
    }
    print(new_row)
    return ', '.join(tags)


if os.path.isfile("fieldnames.txt"):
    with open('fieldnames.txt') as ffile:
        fieldnames = ffile.read().splitlines()
else:
    fieldnames = ["Docket Number", "Case Caption", "Court", "Venue", "Case Initiation Date", "Case Type", "Case Status",
                  "Disposition Date", "Case Disposition", "CourtBusinessName", "CourtNameType", "CourtFirstName",
                  "CourtMiddleName", "CourtLastName", "CourtNameExtra", "StateTaxBusinessName", "StateTaxNameType",
                  "StateTaxFirstName", "StateTaxMiddleName", "StateTaxLastName", "StateTaxNameExtra",
                  "TaxDataHubBusinessName", "TaxDataHubNameType", "TaxDataHubFirstName", "TaxDataHubMiddleName",
                  "TaxDataHubLastName", "TaxDataHubNameExtra", "NjParcelsBusinessName", "NjParcelsNameType",
                  "NjParcelsFirstName", "NjParcelsMiddleName", "NjParcelsLastName", "NjParcelsNameExtra",
                  "CourtPropertyAddress", "CourtNormalizedPropertyAddress", "Sift1PropStreet", "Sift1PropCity",
                  "Sift1PropState", "Sift1PropZip", "TaxDataHubPropertyAddress", "TaxDataHubPropertyAddressStreet",
                  "TaxDataHubPropertyAddressCity", "TaxDataHubPropertyAddressState", "TaxDataHubPropertyAddressZip",
                  "TaxDataHubPropertyAddressCounty", "TaxDataHubPropertyNormalizedAddress", "StateTaxPropertyAddress",
                  "StateTaxPropertyAddressStreet", "StateTaxPropertyAddressCity", "StateTaxPropertyAddressState",
                  "StateTaxPropertyAddressZip", "StateTaxPropertyAddressCounty", "StateTaxPropertyNormalizedAddress",
                  "ArcGisPropertyAddress", "ArcGisPropertyAddressStreet", "ArcGisPropertyAddressCity",
                  "ArcGisPropertyAddressState", "ArcGisPropertyAddressZip", "ArcGisPropertyAddressCounty",
                  "ArcGisPropertyNormalizedAddress", "NjParcelsPropertyAddress", "NjParcelsPropertyAddressStreet",
                  "NjParcelsPropertyAddressCity", "NjParcelsPropertyAddressState", "NjParcelsPropertyAddressZip",
                  "NjParcelsPropertyAddressCounty", "NjParcelsPropertyNormalizedAddress", "Sift2PropStreet",
                  "Sift2PropCity", "Sift2PropState", "Sift2PropZip", "StateTax_Owner", "StateTaxMailingAddress",
                  "StateTaxMailingAddressStreet", "StateTaxMailingAddressCity", "StateTaxMailingAddressState",
                  "StateTaxMailingAddressZip", "StateTaxMailingNormalizedAddress", "ArcGisMailingAddress",
                  "ArcGisMailingAddressStreet", "ArcGisMailingAddressCity", "ArcGisMailingAddressState",
                  "ArcGisMailingAddressZip", "ArcGisMailingNormalizedAddress", "Sift1MailingStreet", "Sift1MailingCity",
                  "Sift1MailingState", "Sift1MailingZip", "TaxDataHubMailingAddress", "TaxDataHubMailingAddressStreet",
                  "TaxDataHubMailingAddressCity", "TaxDataHubMailingAddressState", "TaxDataHubMailingAddressZip",
                  "TaxDataHubMailingNormalizedAddress", "NjParcelsMailingAddress", "NjParcelsMailingAddressStreet",
                  "NjParcelsMailingAddressCity", "NjParcelsMailingAddressState", "NjParcelsMailingAddressZip",
                  "NjParcelsMailingNormalizedAddress", "Label", "Property Type", "StateTax_URL", "StateTax_APN",
                  "StateTax_Block", "StateTax_Square Ft", "StateTax_Lot", "StateTax_Year Built", "StateTax_Land Desc",
                  "StateTax_Bldg Desc", "StateTax_Updated", "StateTax_Zone", "ArcGis_PAMS_PIN", "ArcGis_PCL_MUN",
                  "ArcGis_PCLBLOCK", "ArcGis_PCLLOT", "ArcGis_PROP_CLASS", "ArcGis_LAND_VAL", "ArcGis_IMPRVT_VAL",
                  "ArcGis_NET_VALUE", "ArcGis_LAST_YR_TX", "ArcGis_DEED_DATE", "ArcGis_SALE_PRICE", "ArcGis_PCL_PBDATE",
                  "ArcGis_PCL_GUID", "Comments", "Tags"]
    with open('fieldnames.txt', 'w') as ffile:
        ffile.write("\n".join(fieldnames))


def processJson(f):
    file = f"./{jdir}/{f}"
    print(f"Processing {file}")
    with open(file) as jfile:
        data = json.load(jfile)
    properties = data['Tabs']['Properties'].copy()
    if len(properties) > 0:
        print(f"Found {len(properties)} properties in {file}")
        del data['Tabs']['Properties']
        for property_ in properties:
            data.update(property_)
            updated_data = flatten_json(data)
            try:
                updated_data.update(
                    breakNormalizeAddress(updated_data["CourtNormalizedPropertyAddress"], "Sift1", "Prop"))
                if "Case Initiation Date" in data and data["Case Initiation Date"] != "":
                    updated_data["Case Initiation Date"] = datetime.datetime.strptime(data["Case Initiation Date"],
                                                                                      "%m/%d/%Y").strftime("%Y-%m-%d")
                if "Disposition Date" in data and data["Disposition Date"] != "":
                    updated_data["Disposition Date"] = datetime.datetime.strptime(data["Disposition Date"],
                                                                                  "%m/%d/%Y").strftime("%Y-%m-%d")
                if "StateTax_Updated" in updated_data and updated_data["StateTax_Updated"] != "":
                    updated_data["StateTax_Updated"] = datetime.datetime.strptime(
                        updated_data["StateTax_Updated"].strip(),
                        "%m/%d/%y").strftime("%Y-%m-%d")
                if "ArcGis_DEED_DATE" in updated_data and updated_data["ArcGis_DEED_DATE"] != "":
                    updated_data["ArcGis_DEED_DATE"] = datetime.datetime.strptime(updated_data["ArcGis_DEED_DATE"],
                                                                                  "%y%m%d").strftime("%Y-%m-%d")
                if "Case Caption" in data and "Vs" in data["Case Caption"]:
                    name = data["Case Caption"].split("Vs")[1].strip()
                    updated_data['CourtBusinessName'] = name
                    updated_data.update(getName(name, "Court"))
                if "NjParcels" in data and data["NjParcels"]:
                    details = data["NjParcels"]
                    updated_data['NjParcelsBusinessName'] = details['fn']
                    updated_data.update(getName(updated_data['NjParcelsBusinessName'], "NjParcels"))
                    nj_parcels_mail_addr = f"{details['street-address']}, {details['locality']}, {details['postcode']}"
                    updated_data['NjParcelsMailingAddress'] = nj_parcels_mail_addr
                    try:
                        updated_data['NjParcelsMailingAddressStreet'] = details['street-address']
                        city_state = details['locality'].split()
                        updated_data['NjParcelsMailingAddressCity'] = getCity(" ".join(city_state[:-1]))
                        updated_data['NjParcelsMailingAddressState'] = city_state[-1]
                        updated_data['NjParcelsMailingAddressZip'] = details['postcode']
                    except:
                        print(data['NjParcels'])
                        traceback.print_exc()
                    updated_data['NjParcelsMailingNormalizedAddress'] = getGoogleAddress(nj_parcels_mail_addr)
                    dist = data['NjParcels']['District']
                    dist = " ".join(dist.split()[1:]) if dist.split()[0].isnumeric() else dist
                    if "County" not in data['NjParcels']:
                        data['NjParcels']['County'] = ""
                    csz = f"{dist} {data['NjParcels']['County']}, NJ"
                    prop_street = details['cadastre'].split("is Block")[0]
                    nj_parcels_prop_addr = f"{prop_street}, {csz}"
                    updated_data['NjParcelsPropertyAddress'] = nj_parcels_prop_addr
                    try:
                        updated_data['NjParcelsPropertyAddressStreet'] = prop_street
                        updated_data['NjParcelsPropertyAddressCity'] = getCity(dist)
                        updated_data['NjParcelsPropertyAddressState'] = "NJ"
                        updated_data['NjParcelsPropertyAddressZip'] = ""
                        updated_data['NjParcelsPropertyAddressCounty'] = data['County']
                    except:
                        traceback.print_exc()
                    updated_data['NjParcelsPropertyNormalizedAddress'] = getGoogleAddress(
                        nj_parcels_prop_addr)
                # if "NjPropertyRecords" in data and data["NjPropertyRecords"]:
                #     details = data["NjPropertyRecords"]
                #     updated_data['NjPropertyRecordsBusinessName'] = details['Owner(s)']
                #     updated_data.update(getName(updated_data['NjPropertyRecordsBusinessName'], "NjPropertyRecords"))
                #     nj_prop_rec_mail_addr = f"{details['Mailing Address']}, {details['City State Zip']}"
                #     updated_data['NjPropertyRecordsMailingAddress'] = nj_prop_rec_mail_addr
                #     try:
                #         updated_data['NjPropertyRecordsMailingAddressStreet'] = details['Mailing Address']
                #         city_state_zip = details['City State Zip'].split()
                #         updated_data['NjPropertyRecordsMailingAddressCity'] = getCity(city_state_zip[0])
                #         updated_data['NjPropertyRecordsMailingAddressState'] = city_state_zip[-2]
                #         updated_data['NjPropertyRecordsMailingAddressZip'] = city_state_zip[-1]
                #     except:
                #         print(data['NjPropertyRecords'])
                #         traceback.print_exc()
                #     updated_data['NjPropertyRecordsMailingNormalizedAddress'] = getGoogleAddress(nj_prop_rec_mail_addr)
                #     dist = data['NjPropertyRecords']['District']
                #     dist = " ".join(dist.split()[1:]) if dist.split()[0].isnumeric() else dist
                #     if "County" not in data['NjPropertyRecords']:
                #         data['NjPropertyRecords']['County'] = ""
                #     csz = details['PropertyCityStateZip']
                #     nj_prop_rec_prop_addr = f"{details['PropertyStreet']}, {csz}"
                #     updated_data['NjPropertyRecordsPropertyAddress'] = nj_prop_rec_prop_addr
                #     try:
                #         updated_data['NjPropertyRecordsPropertyAddressStreet'] = details['PropertyStreet']
                #         updated_data['NjPropertyRecordsPropertyAddressCity'] = getCity(dist)
                #         updated_data['NjPropertyRecordsPropertyAddressCounty'] = data['County']
                #         updated_data['NjPropertyRecordsPropertyAddressState'] = "NJ"
                #         updated_data['NjPropertyRecordsPropertyAddressZip'] = ""
                #     except:
                #         traceback.print_exc()
                #     updated_data['NjPropertyRecordsPropertyNormalizedAddress'] = getGoogleAddress(
                #         nj_prop_rec_prop_addr)
                #     updated_data.update(
                #         breakNormalizeAddress(updated_data["NjPropertyRecordsPropertyNormalizedAddress"], "Sift2", 'Prop'))
                if "TaxDataHub" in data and data["TaxDataHub"] and "Details" in data["TaxDataHub"]:
                    details = data["TaxDataHub"]["Details"]
                    if "OwnerName" in details:
                        updated_data['TaxDataHubBusinessName'] = details['OwnerName']
                        updated_data.update(getName(updated_data['TaxDataHubBusinessName'], "TaxDataHub"))
                    tax_data_hub_mail_addr = f"{details['OwnerStreet']}, {details['OwnerCityState']}, {details['OwnerZip']}"
                    updated_data['TaxDataHubMailingAddress'] = tax_data_hub_mail_addr
                    try:
                        updated_data['TaxDataHubMailingAddressStreet'] = details['OwnerStreet']
                        city_state = details['OwnerCityState'].split(" ")
                        updated_data['TaxDataHubMailingAddressCity'] = getCity(" ".join(city_state[:-1]))
                        updated_data['TaxDataHubMailingAddressState'] = city_state[-1]
                        updated_data['TaxDataHubMailingAddressZip'] = details['OwnerZip']
                    except:
                        print(data['TaxDataHub'])
                        traceback.print_exc()
                    updated_data['TaxDataHubMailingNormalizedAddress'] = getGoogleAddress(tax_data_hub_mail_addr)
                    dist = data['TaxDataHub']['District']
                    dist = " ".join(dist.split()[1:]) if dist.split()[0].isnumeric() else dist
                    if "County" not in data['TaxDataHub']:
                        data['TaxDataHub']['County'] = ""
                    tax_data_hub_prop_addr = f"{details['PropertyLocation']}, {dist}, {data['TaxDataHub']['County']}"
                    updated_data['TaxDataHubPropertyAddress'] = tax_data_hub_prop_addr
                    try:
                        updated_data['TaxDataHubPropertyAddressStreet'] = details['PropertyLocation']
                        updated_data['TaxDataHubPropertyAddressCity'] = getCity(dist)
                        updated_data['TaxDataHubPropertyAddressState'] = "NJ"
                        updated_data['TaxDataHubPropertyAddressZip'] = ""
                        updated_data['TaxDataHubPropertyAddressCounty'] = data['County']
                    except:
                        traceback.print_exc()
                    updated_data['TaxDataHubPropertyNormalizedAddress'] = getGoogleAddress(tax_data_hub_prop_addr)
                if "StateTax" in data and data["StateTax"]:
                    tl = 'Tax List Details - Current Year'
                    if "Owner" in data['StateTax']:
                        updated_data['StateTaxBusinessName'] = data['StateTax']['Owner']
                        updated_data.update(getName(updated_data['StateTaxBusinessName'], "StateTax"))
                    elif tl in data['StateTax'] and "Owner" in data['StateTax'][tl]:
                        updated_data['StateTaxBusinessName'] = data['StateTax'][tl]['Owner']
                        updated_data.update(getName(updated_data['StateTaxBusinessName'], "StateTax"))
                    state_tax_mail_addr = f"{data['StateTax']['Street']}, {data['StateTax']['City State']}"
                    updated_data['StateTaxMailingAddress'] = state_tax_mail_addr
                    try:
                        updated_data['StateTaxMailingAddressStreet'] = data['StateTax']['Street']
                        if "," not in data['StateTax']['City State']:
                            data['StateTax']['City State'] = data['StateTax']['City State'].replace("     ", ", ")
                        if "," not in data['StateTax']['City State']:
                            data['StateTax']['City State'] = data['StateTax']['City State'].replace(" ", ", ", 1)
                        data['StateTax']['City State'] = data['StateTax']['City State'].replace(", , ", ", ")
                        updated_data['StateTaxMailingAddressCity'] = getCity(data['StateTax']['City State'].split(",")[
                                                                                 0].strip())
                        updated_data['StateTaxMailingAddressState'] = \
                            data['StateTax']['City State'].split(",")[1].split()[
                                0].strip()
                        updated_data['StateTaxMailingAddressZip'] = \
                            data['StateTax']['City State'].split(",")[1].split()[
                                1].strip()
                    except:
                        print(data['StateTax'])
                        traceback.print_exc()
                    updated_data['StateTaxMailingNormalizedAddress'] = getGoogleAddress(state_tax_mail_addr)
                    dist = data['StateTax']['District']
                    dist = " ".join(dist.split()[1:]) if dist.split()[0].isnumeric() else dist
                    if "County" not in data['StateTax']:
                        data['StateTax']['County'] = ""
                    state_tax_prop_addr = f"{data['StateTax']['Prop Loc']}, {dist}, {data['StateTax']['County']}"
                    updated_data['StateTaxPropertyAddress'] = state_tax_prop_addr
                    try:
                        updated_data['StateTaxPropertyAddressStreet'] = data['StateTax']['Prop Loc']
                        updated_data['StateTaxPropertyAddressCity'] = getCity(dist)
                        updated_data['StateTaxPropertyAddressState'] = "NJ"
                        updated_data['StateTaxPropertyAddressZip'] = ""
                        updated_data['StateTaxPropertyAddressCounty'] = data['County']
                    except:
                        traceback.print_exc()
                    updated_data['StateTaxPropertyNormalizedAddress'] = getGoogleAddress(state_tax_prop_addr)
                if "ArcGis" in data and data["ArcGis"]:
                    # print("Processing ARCGIS")
                    if "CITY_STATE" not in data['ArcGis']:
                        updated_data['ArcGisMailingAddress'] = "Unknown"
                        # continue
                    elif "UNKNOWN" in data['ArcGis']['CITY_STATE'] or "UNKNOWN" in data['ArcGis']['ST_ADDRESS']:
                        updated_data['ArcGisMailingAddress'] = "Unknown"
                        # continue
                    else:
                        if "," not in data['ArcGis']['CITY_STATE']:
                            data['ArcGis']['CITY_STATE'] = data['ArcGis']['CITY_STATE'].replace(" ", ", ")
                        arcgis_mail_addr = f"{data['ArcGis']['ST_ADDRESS']}, {data['ArcGis']['CITY_STATE']}"
                        updated_data['ArcGisMailingAddress'] = arcgis_mail_addr
                        try:
                            updated_data['ArcGisMailingAddressStreet'] = data['ArcGis']['ST_ADDRESS'].strip()
                            updated_data['ArcGisMailingAddressCity'] = getCity(
                                data['ArcGis']['CITY_STATE'].split(",")[0].strip())
                            updated_data['ArcGisMailingAddressState'] = data['ArcGis']['CITY_STATE'].split(",")[
                                1].strip()
                            updated_data['ArcGisMailingAddressZip'] = data['ArcGis']['ZIP_CODE']
                        except:
                            print(data['ArcGis'])
                            traceback.print_exc()
                        updated_data['ArcGisMailingNormalizedAddress'] = getGoogleAddress(arcgis_mail_addr)
                        updated_data.update(
                            breakNormalizeAddress(updated_data["ArcGisMailingNormalizedAddress"], "Sift1", 'Mailing'))
                        arcgis_prop_addr = f"{data['ArcGis']['PROP_LOC']}, {data['ArcGis']['MUN_NAME']}, {data['ArcGis']['COUNTY']}"
                        updated_data['ArcGisPropertyAddress'] = arcgis_prop_addr
                        try:
                            updated_data['ArcGisPropertyAddressStreet'] = data['ArcGis']['PROP_LOC']
                            updated_data['ArcGisPropertyAddressCity'] = getCity(data['ArcGis']['MUN_NAME'].title())
                            updated_data['ArcGisPropertyAddressState'] = "NJ"
                            updated_data['ArcGisPropertyAddressCounty'] = data['County']
                            updated_data['ArcGisPropertyAddressZip'] = ""
                        except:
                            traceback.print_exc()
                        updated_data['ArcGisPropertyNormalizedAddress'] = getGoogleAddress(arcgis_prop_addr)
            except:
                print(f"Error processing {file} {property_}")
                traceback.print_exc()
                # input("Press any key...")
            newfile = f"./CSV_json/CSV-{f.replace('/', '_').replace('.json', '')}-{data['Label'].replace('/', '_')}.json"
            if test:
                print(updated_data.keys())

            append(updated_data, newfile)
    else:
        newfile = f"./CSV_json/CSV-{f}.json".replace("/", "_")
        updated_data = flatten_json(data)

        append(updated_data, newfile)
    if not test:
        convert(scrapedcsv)
        CategorizeJson(f)


def getCity(city):
    for word in ['Twnshp', 'City', 'Boro', 'Twp', 'Borough', 'Township']:
        city = city.replace(word, '')
    return city


def getTaxDataHub(county, district, block, lot, qual=None):
    print(f"Fetching TaxDataHub records for {county}/{district}/{block}/{lot}")
    district_number = getDistrictCode(county, district)
    if district_number is None:
        print(f"District code not found for {county}/{district}")
        return
    did = f"{district_number}_{block}_{lot}"
    if qual is not None:
        did = f"{did}_{qual}"
    url = f"{tdh}/{tax_data_url[county]}/{county}-{cpash}/details?id={did}"
    print(url)
    data = {"County": county, "District": district, "URL": url}
    soup = BeautifulSoup(requests.get(url).text, "html.parser")
    script = soup.find_all('script')[-3].text
    for line in script.splitlines()[2:-5]:
        if "DetailField" in line:
            continue
        data[line.strip().split()[0].split(".")[1]] = json.loads(line.split("=", 1)[1].strip()[:-1])
    # print(json.dumps(data, indent=4))
    with open(f"./TaxDataHub/{county}-{district}-{block}-{lot}-TaxDataHub.json", "w") as jfile:
        json.dump(data, jfile, indent=4)
    return data


def getNJactb(county, district, block, lot, district_number=None, qual=None):
    try:
        data = {"County": county, "District": district}
        print(f"Fetching NJATCB records for {county}/{district}/{block}/{lot}")
        if district_number is None:
            district_number = getDistrictCode(county, district)
            if district_number is None:
                print(f"District code not found for {county}/{district}")
                return
        else:
            print(f"Got municipality code {district_number}!!")
        headers = {'User-Agent': 'Mozilla/5.0'}
        req_data = {
            'ms_user': 'monm',
            'passwd': 'data',
            'srch_type': '1',
            'select_cc': district_number,
            'district': district_number,
            'adv': '1',
            'out_type': '1',
            'ms_ln': '50',
            'p_loc': '',
            'owner': '',
            'block': block,
            'lot': lot,
            'qual': qual if qual is not None else '',
        }
        response = requests.post('https://tax1.co.monmouth.nj.us/cgi-bin/inf.cgi', headers=headers, data=req_data)
        soup = BeautifulSoup(response.text, 'lxml')
        if len(soup.find_all("a")) > 0:
            print(f"Found {len(soup.find_all('a'))} record(s) for {block}/{lot}/{district}.")
            url = f'https://tax1.co.monmouth.nj.us/cgi-bin/{soup.find_all("a")[0]["href"]}'
            print(f"Fetching data from {url}")
            content = requests.get(url).text
            soup = BeautifulSoup(content, 'lxml')
            data['URL'] = url
            data['APN'] = getApn(url)
            # data['Qual'] = getApn(url).split()[0]
            # input(data)
            table = soup.find_all('table')
            for key, val in zip(table[0].find_all("font", {"color": "BLACK"}),
                                soup.find_all("font", {"color": "FIREBRICK"})):
                if len(key.text.strip()) > 0 and len(val.text.strip()) > 0:
                    data[key.text.strip().replace(":", "")] = val.text.strip().replace("&nbsp", "")
            ths = [td.text.strip() for td in table[1].find("tr").find_all("td")]
            data["Sr1a"] = []
            for tr in table[1].find_all("tr")[1:]:
                row = {}
                for td, th in zip(tr.find_all("td"), ths):
                    row[th] = td.text.strip() if td.find(
                        "a") is None else f'https://tax1.co.monmouth.nj.us/cgi-bin/{td.find("a")["href"]}'
                data["Sr1a"].append(row)
            data["TAX-LIST-HISTORY"] = []
            ths = [td.text.strip() for td in table[2].find_all("tr")[1].find_all("td")]
            trs = table[2].find_all("tr")[2:-1]
            for i in range(0, len(trs), 4):
                row = {}
                for td, th in zip(trs[i].find_all("td"), ths):
                    if th == "Land/Imp/Tot":
                        row[th] = [td.text.strip()]
                        row[th].append(trs[i + 1].find_all("td")[2].text.strip())
                        row[th].append(trs[i + 2].find_all("td")[2].text.strip())
                        row[th] = " | ".join(row[th])
                    elif td.text.strip() != "&nbsp":
                        row[th] = td.text.replace("&nbsp", "").strip()
                data["TAX-LIST-HISTORY"].append(row)
            # print(json.dumps(data, indent=4))
            with open(f"./StateTax/{county}-{district}-{block}-{lot}-NJATCB.json", "w") as jfile:
                json.dump(data, jfile, indent=4)
            return data
        else:
            print("No data found!")
            return None
    except:
        print(f"Error {county}/{district}/{block}/{lot}")
        traceback.print_exc()
        return None


#
# def getNjPropertyRecords(driver, county, district, block, lot, qual=None):
#     try:
#         driver.get('https://njpropertyrecords.com')
#         time.sleep(1)
#         print(f"Fetching NJPropertyRecords for {county}/{district}/{block}/{lot}")
#         district_num = getDistrictCode(county, district)
#         if district_num is None:
#             print(f"District code not found for {county}/{district}")
#             return
#         term = f"{district_num}_{block}_{lot}"
#         if qual is not None:
#             term += f"_{qual}"
#         url = f"https://njpropertyrecords.com/property/{term}"
#         print(url)
#         driver.get(url)
#         time.sleep(1)
#         for i in range(60):
#             if "Checking if the site connection is secure" in driver.page_source:
#                 time.sleep(1)
#                 print('Checking if the site connection is secure')
#             else:
#                 break
#         if "Checking if the site connection is secure" in driver.page_source:
#             print("Error in fetching NJ Property Records")
#             return
#         if "Property Page Limit Reached" in driver.page_source:
#             print("NJ Property Records Property Page Limit Reached, Please turn on VPN or change IP!!")
#             return
#         soup = BeautifulSoup(driver.page_source, 'lxml')
#         h1 = soup.find('h1')
#         data = {
#             "County": county,
#             "District": district,
#             "URL": url,
#             'PropertyStreet': h1.text.strip(),
#             "PropertyCityStateZip": h1.parent.find('div').text.strip()
#         }
#         for i in ['overview', 'public-records']:
#             try:
#                 for ov in soup.find('div', {'id': i}).find_all('div')[3].find_all('div'):
#                     if ov.find('div') is None:
#                         continue
#                     for line in ov.find('div').find_all("div"):
#                         if "Login" in line.text:
#                             continue
#                         l = line.find_all('div')
#                         if len(l) > 1:
#                             data[l[0].text] = l[1].text
#             except:
#                 traceback.print_exc()
#         data['County'] = county
#         # print(json.dumps(data, indent=4))
#         with open(f"./NjPropertyRecords/{county}-{district}-{block}-{lot}-NJPR.json", "w") as jfile:
#             json.dump(data, jfile, indent=4)
#         return data
#     except:
#         traceback.print_exc()
#         return None


def getNjParcels(county, district, block, lot, qual=None):
    print(f"Fetching NjParcels records for {county}/{district}/{block}/{lot}")
    district_num = getDistrictCode(county, district)
    if district_num is None:
        print(f"Invalid District {county}/{district}")
        return
    term = f"{district_num}/{block}/{lot}"
    if qual is not None:
        term += f"/{qual}"
    url = f"https://njparcels.com/property/{term}"
    print(url)
    try:
        soup = BeautifulSoup(requests.get(url).content, 'lxml')
    except:
        url += "/CONDO"
        print(url)
        try:
            soup = BeautifulSoup(requests.get(url).content, 'lxml')
        except:
            return None
    data = {"County": county, "District": district, "URL": url}
    try:
        data["cadastre"] = soup.find("p", {"class": "cadastre"}).text
    except:
        print(f"Invalid parcel {county}/{district}/{block}/{lot} {url}")
        traceback.print_exc()
        return None
    for field in ['fn', 'street-address', 'locality', 'postcode']:
        data[field] = soup.find('span', {'class': field}).text if soup.find('span', {'class': field}) else ""

    for tr in soup.find('table').find_all('tr'):
        if tr.find('th') is None:
            continue
        data[tr.find('th').text] = tr.find('td').text
    data['description'] = "\n".join([p.text for p in soup.find('div', {'class': 'col-md-7'}).find_all('p')])
    # print(json.dumps(data, indent=4))
    with open(f"./NjParcels/{county}-{district}-{block}-{lot}-NjParcels.json", "w") as jfile:
        json.dump(data, jfile, indent=4)
    return data


def getOcean(district, block, lot, qual=None):
    try:
        print(f"Fetching records for Ocean/{district}/{block}/{lot}")
        headers = {'user-agent': 'Mozilla/5.0'}
        district_num = getDistrictCode("Ocean", district)
        if district_num is None:
            return None
        url = 'https://tax.co.ocean.nj.us/frmTaxBoardTaxListSearch.aspx'
        s = requests.Session()
        soup = BeautifulSoup(s.get(url, headers=headers).content, 'lxml')
        req_data = {
            '__VIEWSTATE': soup.find("input", {"id": "__VIEWSTATE"})["value"],
            '__VIEWSTATEGENERATOR': soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
            '__EVENTVALIDATION': soup.find("input", {"id": "__EVENTVALIDATION"})["value"],
            'ctl00$LogoFreeholders$FreeholderHistory$FreeholderAccordion_AccordionExtender_ClientState': '-1',
            'ctl00$MainContent$cmbDistrict': int(district_num[2:]),
            'ctl00$MainContent$txtBlock': block,
            'ctl00$MainContent$txtLot': lot,
            'ctl00$MainContent$btnSearch': 'Search'
        }
        response = requests.post('https://tax.co.ocean.nj.us/frmTaxBoardTaxListSearch', headers=headers, data=req_data)
        soup = BeautifulSoup(response.content, 'lxml')
        table = soup.find("table", {"id": "MainContent_m_DataTable"})
        if table is None:
            print(f"==No data found for district ({district_num}) Ocean/{district}/{block}/{lot}")
            return None
        if qual is not None:
            href = ""
            for tr in soup.find('table', {'id': 'MainContent_m_DataTable'}):
                if tr.find('td') is None:
                    continue
                if qual in tr.text:
                    href = tr.find('a')['href']
                    break
            if href == "":
                print(f"==No data found for district ({district_num}) Ocean/{district}/{block}/{lot}")
                return None
        else:
            ahrefs = table.find_all("a", {"target": "_blank"})
            print(f"Found {len(ahrefs)} records")
            href = ahrefs[0]["href"]
            href = f"https://tax.co.ocean.nj.us/{href}"
        print(f"Working on url ({block}/{lot}) {href}")
        content = requests.get(href).content
        soup = BeautifulSoup(content, 'lxml')
        data = {"URL": url, "County": "Ocean", "District": district}
        for table in soup.find("table", {"id": "MainContent_PulledContentTable"}).find_all("table"):
            if table.find_all("tr")[1].find("td", {"class": "PageTxtBlue"}):
                name = table.find("tr").text.strip()
                data[name] = {}
                for tr in table.find_all("tr")[1:]:
                    tds = tr.find_all("td")
                    for i in range(0, len(tds) - 1, 2):
                        if tds[i].text != "" and tds[i + 1].text != "":
                            data[name][tds[i].text.strip().replace(":", "")] = tds[i + 1].text.strip()
            else:
                name = table.find("tr").text.strip()
                data[name] = []
                ths = [th.text.strip() for th in table.find_all("tr")[1].find_all("td")]
                for tr in table.find_all("tr")[2:]:
                    row = {}
                    for td, th in zip(tr.find_all("td"), ths):
                        row[th.replace(":", "")] = td.text.strip()
                    data[name].append(row)
        # print(json.dumps(data, indent=4))
        city_state = data['Tax List Details - Current Year']['City/State'].split()
        data['Street'] = data['Tax List Details - Current Year']['Mailing address']
        data['City State'] = f"{' '.join(city_state[:-2])}, {' '.join(city_state[-2:])}"
        data['Prop Loc'] = data['Tax List Details - Current Year']['Location']
        with open(f"StateTax/Ocean-{district}-{block}-{lot}.json", "w") as ofile:
            json.dump(data, ofile, indent=4)
        return data
    except:
        print(f"Error {district}/{block}/{lot}")
        traceback.print_exc()
        return None


def getArcGis(county, district, block, lot, qual=None):
    try:
        attrib = {"County": county, "District": district}
        print(f"Fetching ARCGIS records for {county}/{district}/{block}/{lot}")
        districts = getArcGIS()
        try:
            for dist in districts[county.upper()]:
                if dist.startswith(district.upper().split()[0]):
                    district = dist
            if district.upper() not in districts[county.upper()]:
                print(f"District not found! {county}/{district}/{block}/{lot}")
                return None
        except KeyError:
            print(f"Invalid county/district: {county}/{district}")
            return None
        countyMunicipality = f"{county.upper()} - {district.title()}"
        params = (
            ('f', 'json'),
            ('env:outSR', '102100'),
            ('countyMunicipality', countyMunicipality),
            ('block', block),
            ('queryType', 'Exact Match'),
            ('lot', lot),
            ("qual", qual)
        )
        url = 'https://mapsdep.nj.gov/arcgis/rest/services/Tasks/BlockLotFinder/GPServer/BlockLotFinder/execute'
        res = requests.get(url, params=params).json()
        if 'results' not in res.keys():
            print(f"No results found for {county}-{district}-{block}/{lot}")
            # print(json.dumps(res, indent=4))
            return None
        attrib.update(res['results'][0]['value']['features'][0]['attributes'])
        # attrib['County'] = county
        # attrib['District'] = district
        for a in [k for k in attrib.keys()]:
            if attrib[a] is None:
                del attrib[a]
        # print(json.dumps(attrib, indent=4))
        if "CITY_STATE" in attrib and "," not in attrib['CITY_STATE']:
            city_State = attrib['CITY_STATE'].split()
            attrib['CITY_STATE'] = " ".join(city_State[:-1]) + f", {city_State[-1]}"
        with open(f"ArcGis/{county}-{district}-{block}-{lot}-ARCGIS.json", 'w') as outfile:
            json.dump(attrib, outfile, indent=4)
        return attrib
    except:
        print(f"Error {county}/{district}/{block}/{lot}")
        traceback.print_exc()
        return None


def getData(soup, driver, n, y):
    data = {
        "Docket Number": soup.find('span', {"id": "CaseNumberTitlePanel"}).text.split(":")[1].strip(),
        "Case Caption": soup.find('span', {"id": "idCaseTitle"}).text,
    }
    for td in soup.find("table", {"id": "caseSummaryPanel_F"}).find_all("td"):
        try:
            data[td.find('span', {"class": "ValueField"}).text.strip().replace(":", "")] = td.find('span', {
                "class": "LabelField"}).text.strip()
        except:
            # print("error", td)
            pass
    tabs_data = {}
    if not test:
        downloadPdf(driver)
    for li in soup.find('ul', {"role": "tablist"}).find_all("li", {"role": "tab"}):
        tab = li.text.split('\u00a0')[0].strip()
        tabs_data[tab] = []
        li_div = soup.find('div', {"id": li["aria-controls"]})
        for h3 in li_div.find_all('h3', {"role": "tab"}):
            h3_div = soup.find('div', {"id": h3["aria-controls"]})
            h3_txt = h3.find('span', {"class": "LabelField"}).text
            tab_data = {"Label": h3_txt.strip()}
            for val, label in zip(h3_div.find_all('span', {"class": "ValueField"}),
                                  h3_div.find_all('span', {"class": "LabelField"})):
                tab_data[val.text.strip().replace(":", "")] = label.text.strip()
            if tab == "Properties":
                block, lots, qual = getBlockLotQual(tab_data["Label"].replace(":", ""))
                if qual == "":
                    qual = None
                county = tab_data["County"]
                district = tab_data["Municipality"].split("-")[1].strip()
                for lot in lots:
                    if str(lot).endswith(".0"):
                        lot = int(lot)
                    if county in tax_data_url.keys():
                        tab_data["TaxDataHub"] = getTaxDataHub(county, district, block, lot, qual)
                    elif county == "Ocean":
                        tab_data["StateTax"] = getOcean(district, block, lot, qual)
                    else:
                        tab_data["StateTax"] = getNJactb(county, district, block, lot,
                                                         tab_data["Municipality"].split("-")[0].strip(), qual)
                    if county in ['Middlesex', 'Essex']:
                        tab_data["StateTax"] = getNJactb(county, district, block, lot,
                                                         tab_data["Municipality"].split("-")[0].strip(), qual)
                    tab_data['ArcGis'] = getArcGis(county, district, block, lot, qual)
                    tab_data['NjParcels'] = getNjParcels(county, district, block, lot, qual)
                    # tab_data['NjPropertyRecords'] = getNjPropertyRecords(driver, county, district, block, lot, qual)
                    tab_data['CourtNormalizedPropertyAddress'] = getGoogleAddress(tab_data["Street Address"], county,
                                                                                  district)

                    tab_data[
                        'CourtPropertyAddress'] = f"{tab_data['Street Address']},{tab_data['Municipality'].split('-')[1]}, {tab_data['County']}"

                    tab_data["Label"] = tab_data["Label"].replace(":", "")
                tabs_data[tab].append(tab_data)
    # if tabs_data["Properties"]:
    #     property0 = tabs_data["Properties"][0]

    data["Tabs"] = tabs_data
    data['CaseActions'] = []
    table = soup.find('table', {"id": "caseActionTbId2"})
    ths = [th.text for th in table.find_all('th')]
    for tr in table.find_all('tr'):
        tds = [td.text for td in tr.find_all("td")]
        case = {}
        for i in range(len(ths)):
            try:
                case[ths[i].strip().replace(":", "")] = tds[i].strip()
            except:
                pass
        if case != {}:
            data['CaseActions'].append(case)
    # pprint(json.dumps(data, indent=4))
    jf = f"./{jdir}/{y}-{n}.json"
    if isValid(data):
        if isValidDocket(data):
            if os.path.isfile(jf):
                with open(jf) as jfile:
                    jdata = json.load(jfile)
                if jdata == data:
                    pprint("Nothing changed!")
                else:
                    pprint("Data changed!")
                    changefile = f"./{changeddir}/{y}-{n}--{str(datetime.datetime.now()).replace(':', '-')}.json"
                    with open(changefile, 'w') as jfile:
                        json.dump(data, jfile, indent=4)
                    with open(jf, 'w') as jfile:
                        json.dump(data, jfile, indent=4)
                    # createCsv(data)
            # try:
            #     driver.find_element(By.TAG_NAME, 'body').screenshot(f"./{ss}/{data['Docket Number']}.png")
            # except:
            #     pass
            else:
                with open(jf, 'w') as jfile:
                    json.dump(data, jfile, indent=4)
                processJson(f"{y}-{n}.json")
                # createCsv(data)
        else:
            pprint(f"Not required docket {data['Docket Number']}")
            # with open(jf.replace(jdir, "notreq") + ".json", 'w') as jfile:
            #     json.dump(data, jfile, indent=4)
    else:
        pass
        # with open(nrfile, 'a') as nfile:
        #     nfile.write(f"{y}-{n}\n")
        # notrequired.append(f"{y}-{n}")
        # pprint(f"Not required {data['Docket Number']}")
        # with open(jf.replace(jdir, "notreq") + ".json", 'w') as jfile:
        #     json.dump(data, jfile, indent=4)
    if test:
        return data
    downloaded = False
    for i in range(10):
        time.sleep(1)
        if os.path.isfile(rf"{download_dir}\CivilCaseJacket.pdf"):
            downloaded = True
            break
        print(f"Downloading CivilCaseJacket.pdf ({i})...")
    if downloaded:
        print(f"CivilCaseJacket.pdf downloaded!, renaming to {y}-{n}-complaint.pdf")
        if os.path.isfile(rf"{download_dir}/{y}-{n}-complaint.pdf"):
            os.remove(rf"{download_dir}/{y}-{n}-complaint.pdf")
        os.rename(rf"{download_dir}/CivilCaseJacket.pdf", rf"{download_dir}/{y}-{n}-complaint.pdf")
    else:
        print("Error downloading CivilCaseJacket.pdf")
    return data


def processNjCourts(dockets=None):
    if dockets is not None:
        num_years = dockets
    elif not os.path.isfile("LastRun.json"):
        lastrun['StartNumber'] = int(input("Enter starting number: "))
        lastrun['EndNumber'] = int(input("Enter ending number: "))
        lastrun['StartYear'] = int(input("Enter starting year: "))
        lastrun['EndYear'] = int(input("Enter ending year: "))
        lastrun['CurrentYear'] = lastrun['StartYear']
        lastrun['CurrentNumber'] = lastrun['StartNumber']
        with open("LastRun.json", "w") as outfile:
            json.dump(lastrun, outfile, indent=4)
        nums = range(lastrun['StartNumber'], lastrun['EndNumber'] + 1)
        years = range(lastrun['CurrentYear'], lastrun['EndYear'] + 1)
        num_years = [(num, year) for year in years for num in nums]
    else:
        print("Resuming from last run")
        print(json.dumps(lastrun, indent=4))
        nums = range(lastrun['StartNumber'], lastrun['EndNumber'] + 1)
        years = range(lastrun['CurrentYear'], lastrun['EndYear'] + 1)
        num_years = [(num, year) for year in years for num in nums]
    print("Connecting to Chrome...")
    driver = getChromeDriver()
    print("Connected!")
    # if "portal.njcourts.gov" not in driver.current_url:
    #     driver.get(nj_url)
    #     if "Enter user ID and password" in driver.page_source:
    #         driver.delete_all_cookies()
    #         driver.get(disclaimer)
    #     time.sleep(3)
    # checkDisclaimer(driver)
    input(
        "Please goto https://portal.njcourts.gov/webcivilcj/CIVILCaseJacketWeb/pages/publicAccessDisclaimer.faces\nthen goto https://portal.njcourts.gov/webcivilcj/CIVILCaseJacketWeb/pages/civilCaseSearch.faces and press enter when done:")
    for n, y in num_years:
        if y == lastrun['CurrentYear'] and n < lastrun['CurrentNumber'] and not debug:
            print(f"Skipping {y}-{n}")
            continue
        # if f"{y}-{n}" in notrequired:
        #     pprint(f"Number {n} Year {y} not required!")
        #     continue
        try:
            time.sleep(1)
            checkMax(driver)
            sptries = 1
            while "Search By Docket Number" not in driver.page_source:
                pprint("Waiting for search page...")
                sptries += 1
                while "Enter user ID and password" in driver.page_source:
                    driver.delete_all_cookies()
                    driver.get(disclaimer)
                    time.sleep(1)
                    pprint("Reloading...")
                    checkDisclaimer(driver)
                if sptries % 10 == 0:
                    driver.get(nj_url)
                    sptries = 1
                sleep(1)
            fillInfo(driver, n, y)
            if "Case not found" in driver.page_source:
                pprint("Case not found")
            else:
                tries = 0
                req = True
                while "Case Caption" not in driver.page_source:
                    pprint("Waiting for result page...")
                    try:
                        driver.find_element(By.XPATH, '//*[@id="searchByDocForm:searchBtnDummy"]').click()
                    except:
                        traceback.print_exc()
                    tries += 1
                    if "captcha-solver-info" in driver.page_source or tries % 5 == 0:
                        try:
                            driver.refresh()
                            req = fillInfo(driver, n, y)
                        except:
                            pass
                        tries = 1
                    elif "You have been logged off as your user session expired" in driver.page_source:
                        pprint("You have been logged off as your user session expired.")
                        click(driver, '//a[text()=" here"]')
                    sleep(1)
                if req:
                    getData(BeautifulSoup(driver.page_source, 'lxml'), driver, n, y)
                    # CategorizeJson()
                lastrun['CurrentYear'] = y
                lastrun['CurrentNumber'] = n
                with open("LastRun.json", "w") as outfile:
                    json.dump(lastrun, outfile, indent=4)
        except:
            traceback.print_exc()
            pprint(f"Error {y} {n}")
            with open("error.txt", "a") as f:
                f.write(f"{y},{n}\n")
        driver.get(nj_url)


def getGoogleAddress(street, county="", district=""):
    addr = f"{street} {county} {district}".title()
    for word in ['Twnshp', 'City', 'Boro', 'Twp', 'Borough', 'Township']:
        addr = addr.replace(word, '')
    if test:
        print('Returning default address')
        return addr
    url = f"https://www.google.com/search?q={addr}"
    print(f"Getting Google Address {url}")
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
         "Chrome/104.0.0.0 Safari/537.36"
    soup = BeautifulSoup(requests.get(url, headers={'user-agent': ua}).text, 'lxml')
    try:
        div = soup.find("div", {"class": "vk_sh vk_bk"})
        address = f'{div.find("div").text}, ' \
                  f'{div.find("span").text}'
        print(f"Found {address}")
        return address
    except:
        print(f"No address found {url}")
        with open("google-address.html", "w", encoding='utf8') as outfile:
            outfile.write(soup.prettify())
        # print(soup)
        return ""


def breakNormalizeAddress(addr, source, type_):
    if addr == "":
        print(f"Empty address!! {source},{type_}")
        return {}
    try:
        print(f"Processing address: {addr}")
        address = addr.split(',')
        data = {
            f'{source}{type_}Street': address[0].strip(),
            f'{source}{type_}City': address[1].strip(),
            f'{source}{type_}State': address[2].split()[0].strip(),
            f'{source}{type_}Zip': address[2].split()[1].strip()
        }
        return data
    except:
        traceback.print_exc()
        return {}


def main():
    initialize()
    if test:
        processAllJson()
        exit()
    if not os.path.isfile("LastRun.json"):
        option = input("1 to get cases from NJ Courts\n2 to search state/district/block/lot: ")
    else:
        option = "1"
    if option == "1":
        processNjCourts()
        # uploadCSV(sheet_headers, scrapedcsv)
    elif option == "2":
        SearchBlockLot()
    else:
        print("Invalid option")


def waitCaptcha(driver):
    time.sleep(5)
    fillagain = False
    captchacount = 1
    print("Waiting for captcha...")
    while "Captcha solved!" not in driver.page_source and "captcha-solver-info" in driver.page_source:
        pprint(f"Solving captcha ({captchacount})....")
        captchacount += 1
        if captchacount > 60:
            pprint("Reloading...")
            driver.refresh()
            sleep(3)
            captchacount = 1
            fillagain = True
        sleep(1)
    sleep(1)
    return fillagain


def checkMax(driver):
    while "maximum number of concurrent users." in driver.page_source:
        pprint("Case Jacket Public Access has reached the maximum number "
               "of concurrent users. Please try again later.")
        driver.get(nj_url)
        time.sleep(1)


def fillInfo(driver, n, y):
    # if f"{y}-{n}" in notrequired:
    #     pprint(f"Number {n} Year {y} not required!")
    #     return False
    pprint(f"Number {n} Year {y}")
    sendkeys(driver, '//*[@id="searchByDocForm:idCivilDocketNum"]', n)
    sendkeys(driver, '//*[@id="searchByDocForm:idCivilDocketYear"]', y)
    time.sleep(1)
    if waitCaptcha(driver):
        sendkeys(driver, '//*[@id="searchByDocForm:idCivilDocketNum"]', n)
        sendkeys(driver, '//*[@id="searchByDocForm:idCivilDocketYear"]', y)
        time.sleep(1)
    try:
        driver.find_element(By.XPATH, '//*[@id="searchByDocForm:searchBtnDummy"]').click()
    except:
        pprint("Search page captcha manually solved!")
    time.sleep(2)
    return True


def checkDisclaimer(driver):
    time.sleep(1)
    while "Disclaimer" in driver.page_source:
        time.sleep(1)
        waitCaptcha(driver)
        try:
            click(driver, '//*[@id="disclaimerform:button"]', True)
        except:
            pprint("Disclaimer captcha manually solved!")
        time.sleep(1)


def getName(name: str, source: str):
    data = {f"{source}BusinessName": name}
    newdata = {}
    if "Blk" in name or "Block" in name or "Lot" in name:
        return data
    try:
        if len(name.strip().split()) == 1:
            return data
        name = name.replace("+", "&")
        if '.' in name:
            name = name.replace('.', '')
        if "," in name and ", " not in name:
            name = name.replace(",", ", ")
        if "&" in name:
            data[f'{source}NameExtra'] = name.split("&")[1].strip()
            name = name.split("&")[0].strip()
        if "/" in name:
            data[f'{source}NameExtra'] = name.split("/")[1].strip()
            name = name.split("/")[0].strip()
        for extra in ['Jr', 'EST OF']:
            if extra in name:
                data[f'{source}NameExtra'] = extra
                name = name.replace(extra, "").strip()
        if "Executri" in name:
            data[f'{source}NameExtra'] = name.split(",")[1]
            data[f'{source}FirstName'] = name.split(",")[0].split()[0]
            data[f'{source}LastName'] = name.split(",")[0].split()[-1]
            data[f'{source}NameType'] = "GOVT OWNED"
        elif "Her Heirs" in name:
            data[f'{source}NameExtra'] = "Her Heirs"
            name = name.replace("Her Heirs", "").strip()
            if "," in name:
                data[f'{source}FirstName'] = name.split(",")[-1]
                data[f'{source}LastName'] = name.split(",")[0]
            else:
                data[f'{source}FirstName'] = f"{name.split()[-1]} Jr"
                data[f'{source}LastName'] = name.split()[0]
        elif "His Heirs" in name:
            data[f'{source}NameExtra'] = "Jr"
            name = name.replace("His Heirs", "").strip()
            if "," in name:
                data[f'{source}FirstName'] = name.split(",")[-1]
                data[f'{source}LastName'] = name.split(",")[0]
            else:
                data[f'{source}FirstName'] = f"{name.split()[-1]} Jr"
                data[f'{source}LastName'] = name.split()[0]
        elif "vs state of" in name.lower():
            data[f'{source}NameType'] = "GOVT OWNED"
        elif " llc" in name.lower() or " inc" in name.lower() or " asso" in name.lower() or "corp" in name.lower() or "company" in name.lower():
            data[f'{source}NameType'] = "Company"
        elif "-" in name and len(name.split()) == 2:
            data[f"{source}FirstName"] = name.split()[0]
            data[f"{source}LastName"] = name.split()[1]
        elif len(name.split()) == 2:
            if "," in name:
                data[f"{source}FirstName"] = name.split(",")[-1]
                data[f"{source}LastName"] = name.split(",")[0]
            else:
                data[f"{source}FirstName"] = name.split()[0]
                data[f"{source}LastName"] = name.split()[-1]
        elif len(name.split()) == 3 and len(name.strip().split()[1]) < 3:
            data[f"{source}FirstName"] = name.split()[0]
            data[f"{source}MiddleName"] = name.split()[1]
            data[f"{source}LastName"] = name.split()[2]
        elif len(name.split()) == 3 and len(name.split()[1]) > 2:
            data[f"{source}FirstName"] = name.split()[1]
            data[f"{source}LastName"] = name.split()[0]
            data[f"{source}MiddleName"] = name.split()[2]
        elif len(name.split()) == 4 and len(name.strip().split()[-1]) == 1:
            data[f"{source}FirstName"] = name.split()[0]
            data[f"{source}MiddleName"] = name.split()[1]
            data[f"{source}LastName"] = name.split()[2]
            data[f"{source}NameExtra"] = name.split()[3]
        elif len(name.split()) > 1 and name.split()[1][-1] == "," and len(name.split(",")[0].split()) == 2 and len(
                name.split(",")[1].split()) == 2:
            data[f"{source}FirstName"] = name.split()[0]
            data[f"{source}LastName"] = name.split()[1][:-1]
            data[f"{source}MiddleName"] = name.split(",")[1]
        elif name.split()[0][-1] == ",":
            data[f'{source}FirstName'] = name.split()[0][:-1]
            data[f'{source}LastName'] = name.split(",")[1].split()[0]
            if len(name.split(",")[1].split()) > 2:
                data[f'{source}MiddleName'] = name.split(",")[1].split()[1]
        print(json.dumps(data, indent=4))

    except:
        print(len(name.split()))
        traceback.print_exc()
        print(f"Error in name {name}")
    for key, val in data.items():
        if val:
            newdata[key] = val.replace(',', '').strip()
    return newdata


def getDistrictCode(county, district):
    county_codes = getDistrictCodes()
    try:
        for key1 in county_codes.keys():
            if key1.upper() in county.upper() or county.upper() in key1.upper():
                for key2 in county_codes[key1].keys():
                    if key2.upper() in district.upper() or district.upper() in key2.upper():
                        print(f"Found district code {county_codes[key1][key2]}")
                        return county_codes[key1][key2]
    except:
        print(f"Invalid District {county}/{district}")
        return None


def downloadPdf(driver):
    if os.path.isfile(rf"{download_dir}/CivilCaseJacket.pdf"):
        print("Deleting old PDF!!")
        os.remove(rf"{download_dir}/CivilCaseJacket.pdf")
    # driver = getChromeDriver()
    table = driver.find_element(By.XPATH, "//table[@id='caseActionTbId2']")
    for tr in table.find_elements(By.XPATH, './/tr[@role="row"]')[1:]:
        # print(tr.text)
        if tr.find_element(By.XPATH, './/td[@class="caseActCol3"]').text.startswith("Complaint"):
            # print(tr.find_element(By.XPATH, './/td[@class="caseActCol3"]').text)
            tr.find_element(By.XPATH, './/td[@class="caseActCol2"]/a').click()
            time.sleep(1)
            form = driver.find_element(By.XPATH, '//form[@id="documentDetails"]')
            form.find_element(By.XPATH, './/input[@type="checkbox"]').click()
            time.sleep(3)
            driver.find_element(By.XPATH, '//input[@id="documentDetails:savePrintButton"]').click()
            time.sleep(1)


def logo():
    os.system('color 0a')
    print(r"""
           _  __    __  _____                 __     
          / |/ /__ / / / ___/___  __ __ ____ / /_ ___
         /    // // / / /__ / _ \/ // // __// __/(_-<
        /_/|_/ \___/  \___/ \___/\_,_//_/   \__//___/
===============================================================
                   NJ Court data scraper by:
                http://github.com/evilgenius786
===============================================================
[+] Automated
[+] Solves captcha using 2captcha
[+] JSON output
[+] CSV output
[+] Alert on new data
[+] Error handling
_______________________________________________________________
""")


def initialize():
    # global notrequired
    logo()
    if debug:
        print("Make sure Selenium Chrome is running...")
    for directory in [jdir, changeddir, filter_dir,
                      'StateTax', 'ArcGis', 'CSV_json', 'TaxDataHub', 'NjParcels'
                      # "notreq", ss,  'NjPropertyRecords'
                      ]:
        if not os.path.isdir(directory):
            os.mkdir(directory)
    # if not os.path.isfile(nrfile):
    #     with open(nrfile, 'w') as nfile:
    #         nfile.write("")
    if not os.path.isfile(scrapedcsv):
        with open(scrapedcsv, 'w', newline='',
                  encoding=encoding,
                  # errors="ignore"
                  ) as sfile:
            csv.DictWriter(sfile, fieldnames=fieldnames).writeheader()
    # with open(nrfile) as nfile:
    #     notrequired = nfile.read().splitlines()


def CategorizeJson(file):
    casetypes = ['Residential', 'Personam', 'Rem', 'Commercial', 'STRICT', 'Condominium', 'Time Share', 'FAIR']
    with open(f"./{jdir}/{file}") as jfile:
        data = json.load(jfile)
    found = False
    for casetype in casetypes:
        if casetype.lower() in data['Case Type'].lower():
            found = True
            print(f"'{casetype}' found in ({data['Case Type']}) ({data['Docket Number']})")
            if not os.path.isdir(f"./{filter_dir}/{casetype}"):
                os.mkdir(f"./{filter_dir}/{casetype}")
            with open(f"./{filter_dir}/{casetype}/{file}", 'w') as jfile:
                json.dump(data, jfile, indent=4)
            if casetype == 'Personam' or casetype == 'Rem':
                if not os.path.isdir(f"./{filter_dir}/{tax_dir}"):
                    os.mkdir(f"./{filter_dir}/{tax_dir}")
                with open(f"./{filter_dir}/{tax_dir}/{file}", 'w') as jfile:
                    json.dump(data, jfile, indent=4)
    if not found:
        print(f"Nothing found ({data['Case Type']}) ({data['Docket Number']})")
        if not os.path.isdir(f"./{filter_dir}/{other_dir}"):
            os.mkdir(f"./{filter_dir}/{other_dir}")
        with open(f"./{filter_dir}/{other_dir}/{file}", 'w') as nfile:
            json.dump(data, nfile, indent=4)


def processBlockLot(data, row):
    print(f"Working on {row}")
    if row['county'] in tax_data_url.keys():
        data["TaxDataHub"] = getTaxDataHub(row['county'], row['district'], row['block'], row['lot'])
    elif row['county'] == "Ocean":
        data["StateTax"] = getOcean(row['district'], row['block'], row['lot'])
    else:
        data["StateTax"] = getNJactb(row['county'], row['district'], row['block'], row['lot'])
    data['ArcGis'] = getArcGis(row['county'], row['district'], row['block'], row['lot'])


def processDocketNums():
    initialize()
    # driver = getChromeDriver()
    # getData(BeautifulSoup(driver.page_source, "html.parser"), driver, "010235", "22")
    # convert('NJ-Courts.csv')
    # exit()
    if os.path.isfile('Dockets.txt'):
        num_year = []
        with open('Dockets.txt', 'r') as f:
            for line in f:
                doc = line[4:].strip().split("-")
                num_year.append((doc[0], doc[1]))
        num_year = list(set(num_year))
        processNjCourts(num_year)


def getApn(url):
    apn = url.split("&l02=")[1].replace("_________M", "").replace('____', '-0000-')
    return f"{apn[2:4]} {apn[4:]}"


def processAllJson():
    for f in os.listdir(jdir)[1:2]:
        if not f.endswith(".json"):
            continue
        processJson(f)
    convert(scrapedcsv)


def convert(filename):
    pd.read_csv(filename,
                encoding=encoding
                # encoding_errors="ignore"
                ).to_excel(filename.replace("csv", "xlsx"), index=False)


def CategorizeAllJson():
    for f in os.listdir(jdir):
        if not f.endswith(".json"):
            continue
        CategorizeJson(f)


def SearchBlockLot():
    if os.path.isfile("block-lot.csv"):
        with open("block-lot.csv", 'r', encoding='utf-8-sig') as ifile:
            # print(infile.read())
            reader = csv.DictReader(ifile)
            data = {}
            for row in reader:
                processBlockLot(data, row)
                processBlockLot(data, row)
    else:
        print("No block-lot.csv file found")


def getChromeDriver(proxy=None):
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    print("PDF Download directory: " + download_dir)
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    if debug:
        # print("Connecting existing Chrome for debugging...")
        options.debugger_address = "127.0.0.1:9222"
    else:
        options.add_experimental_option('prefs', {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        })
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument('--user-data-dir=C:/Selenium/NJCourts')
    if not images:
        # print("Turning off images to save bandwidth")
        options.add_argument("--blink-settings=imagesEnabled=false")
    if headless:
        # print("Going headless")
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080")
    if maximize:
        # print("Maximizing Chrome ")
        options.add_argument("--start-maximized")
    if proxy:
        # print(f"Adding proxy: {proxy}")
        options.add_argument(f"--proxy-server={proxy}")
    if incognito:
        # print("Going incognito")
        options.add_argument("--incognito")
    # chromedriver_autoinstaller.install()
    # chromedriver_autoinstall.install()
    # chromedriver_binary_sync.download()
    return webdriver.Chrome(options=options,service=Service(chromedriver_autoinstaller.install()))


def getFirefoxDriver():
    options = webdriver.FirefoxOptions()
    if not images:
        # print("Turning off images to save bandwidth")
        options.set_preference("permissions.default.image", 2)
    if incognito:
        # print("Enabling incognito mode")
        options.set_preference("browser.privatebrowsing.autostart", True)
    if headless:
        # print("Hiding Firefox")
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080")
    return webdriver.Firefox(options)


def isValidDocket(data):
    return True


def isValid(data):
    return True


def flatten_json(y):
    out = {}

    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '_')
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)
    return out


def append(updated_data, newfile):
    updated_data['Tags'] = getTag(updated_data)
    updated_data['Comments'] = json.dumps(updated_data.copy(), indent=4)
    with open(newfile, 'w') as jfile:
        json.dump(updated_data, jfile, indent=4)
    with open(scrapedcsv, 'a', newline='',
              encoding=encoding
              # errors="ignore"
              ) as sfile:
        csv.DictWriter(sfile, fieldnames=fieldnames, extrasaction='ignore').writerow(updated_data)


def click(driver, xpath, js=False):
    print(f"Clicking {xpath}")
    if js:
        driver.execute_script("arguments[0].click();", getElement(driver, xpath))
    else:
        WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()


def getText(driver, xpath):
    try:
        return getElement(driver, xpath).text.strip()
    except:
        return ""


def getElement(driver, xpath):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))


def sendkeys(driver, xpath, keys, js=False):
    if js:
        driver.execute_script(f"arguments[0].value='{keys}';", getElement(driver, xpath))
    else:
        ele = getElement(driver, xpath)
        ele.clear()
        ele.send_keys(keys)


def pprint(msg):
    m = f'{str(datetime.datetime.now()).split(".")[0]} | {msg}'
    print(m)


def processNames():
    with open('names.txt', 'r') as ifile:
        names = ifile.read().splitlines()
    for name in names:
        getName(name, "")


def checkNJATCB():
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'DNT': '1',
        'Origin': 'https://tax1.co.monmouth.nj.us',
        'Pragma': 'no-cache',
        'Referer': 'https://tax1.co.monmouth.nj.us/cgi-bin/prc6.cgi?menu=index&ms_user=monm&passwd=data&district=1301&mode=11',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="111", "Not(A:Brand";v="8", "Chromium";v="111"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }

    data = {
        'ms_user': 'monm',
        'passwd': 'data',
        'srch_type': '1',
        'select_cc': '1301',
        'district': '1301',
        'adv': '1',
        'out_type': '1',
        'ms_ln': '50',
        'p_loc': '',
        'owner': '',
        'block': '1',
        'lot': '1',
        'qual': ''
    }

    response = requests.post('https://tax1.co.monmouth.nj.us/cgi-bin/inf.cgi', headers=headers, data=data)
    print(response.text)


def getArcGIS():
    return {
        "ATLANTIC": [
            "ABSECON CITY",
            "ATLANTIC CITY",
            "BRIGANTINE CITY",
            "BUENA BOROUGH",
            "BUENA VISTA TOWNSHIP",
            "CORBIN CITY",
            "EGG HARBOR CITY",
            "EGG HARBOR TOWNSHIP",
            "ESTELL MANOR CITY",
            "FOLSOM BOROUGH",
            "GALLOWAY TOWNSHIP",
            "HAMILTON TOWNSHIP",
            "HAMMONTON TOWN",
            "LINWOOD CITY",
            "LONGPORT BOROUGH",
            "MARGATE CITY",
            "MULLICA TOWNSHIP",
            "NORTHFIELD CITY",
            "PLEASANTVILLE CITY",
            "PORT REPUBLIC CITY",
            "SOMERS POINT CITY",
            "VENTNOR CITY",
            "WEYMOUTH TOWNSHIP"
        ],
        "BERGEN": [
            "ALLENDALE BOROUGH",
            "ALPINE BOROUGH",
            "BERGENFIELD BOROUGH",
            "BOGOTA BOROUGH",
            "CARLSTADT BOROUGH",
            "CLIFFSIDE PARK BOROUGH",
            "CLOSTER BOROUGH",
            "CRESSKILL BOROUGH",
            "DEMAREST BOROUGH",
            "DUMONT BOROUGH",
            "EAST RUTHERFORD BOROUGH",
            "EDGEWATER BOROUGH",
            "ELMWOOD PARK BOROUGH",
            "EMERSON BOROUGH",
            "ENGLEWOOD CITY",
            "ENGLEWOOD CLIFFS BOROUGH",
            "FAIR LAWN BOROUGH",
            "FAIRVIEW BOROUGH",
            "FORT LEE BOROUGH",
            "FRANKLIN LAKES BOROUGH",
            "GARFIELD CITY",
            "GLEN ROCK BOROUGH",
            "HACKENSACK CITY",
            "HARRINGTON PARK BOROUGH",
            "HASBROUCK HEIGHTS BOROUGH",
            "HAWORTH BOROUGH",
            "HILLSDALE BOROUGH",
            "HO-HO-KUS BOROUGH",
            "LEONIA BOROUGH",
            "LITTLE FERRY BOROUGH",
            "LODI BOROUGH",
            "LYNDHURST TOWNSHIP",
            "MAHWAH TOWNSHIP",
            "MAYWOOD BOROUGH",
            "MIDLAND PARK BOROUGH",
            "MONTVALE BOROUGH",
            "MOONACHIE BOROUGH",
            "NEW MILFORD BOROUGH",
            "NORTH ARLINGTON BOROUGH",
            "NORTHVALE BOROUGH",
            "NORWOOD BOROUGH",
            "OAKLAND BOROUGH",
            "OLD TAPPAN BOROUGH",
            "ORADELL BOROUGH",
            "PALISADES PARK BOROUGH",
            "PARAMUS BOROUGH",
            "PARK RIDGE BOROUGH",
            "RAMSEY BOROUGH",
            "RIDGEFIELD BOROUGH",
            "RIDGEFIELD PARK VILLAGE",
            "RIDGEWOOD VILLAGE",
            "RIVER EDGE BOROUGH",
            "RIVER VALE TOWNSHIP",
            "ROCHELLE PARK TOWNSHIP",
            "ROCKLEIGH BOROUGH",
            "RUTHERFORD BOROUGH",
            "SADDLE BROOK TOWNSHIP",
            "SADDLE RIVER BOROUGH",
            "SOUTH HACKENSACK TOWNSHIP",
            "TEANECK TOWNSHIP",
            "TENAFLY BOROUGH",
            "TETERBORO BOROUGH",
            "UPPER SADDLE RIVER BOROUGH",
            "WALDWICK BOROUGH",
            "WALLINGTON BOROUGH",
            "WASHINGTON TOWNSHIP",
            "WESTWOOD BOROUGH",
            "WOOD-RIDGE BOROUGH",
            "WOODCLIFF LAKE BOROUGH",
            "WYCKOFF TOWNSHIP"
        ],
        "BURLINGTON": [
            "BASS RIVER TOWNSHIP",
            "BEVERLY CITY",
            "BORDENTOWN CITY",
            "BORDENTOWN TOWNSHIP",
            "BURLINGTON CITY",
            "BURLINGTON TOWNSHIP",
            "CHESTERFIELD TOWNSHIP",
            "CINNAMINSON TOWNSHIP",
            "DELANCO TOWNSHIP",
            "DELRAN TOWNSHIP",
            "EASTAMPTON TOWNSHIP",
            "EDGEWATER PARK TOWNSHIP",
            "EVESHAM TOWNSHIP",
            "FIELDSBORO BOROUGH",
            "FLORENCE TOWNSHIP",
            "HAINESPORT TOWNSHIP",
            "LUMBERTON TOWNSHIP",
            "MANSFIELD TOWNSHIP",
            "MAPLE SHADE TOWNSHIP",
            "MEDFORD LAKES BOROUGH",
            "MEDFORD TOWNSHIP",
            "MOORESTOWN TOWNSHIP",
            "MOUNT HOLLY TOWNSHIP",
            "MOUNT LAUREL TOWNSHIP",
            "NEW HANOVER TOWNSHIP",
            "NORTH HANOVER TOWNSHIP",
            "PALMYRA BOROUGH",
            "PEMBERTON BOROUGH",
            "PEMBERTON TOWNSHIP",
            "RIVERSIDE TOWNSHIP",
            "RIVERTON BOROUGH",
            "SHAMONG TOWNSHIP",
            "SOUTHAMPTON TOWNSHIP",
            "SPRINGFIELD TOWNSHIP",
            "TABERNACLE TOWNSHIP",
            "WASHINGTON TOWNSHIP",
            "WESTAMPTON TOWNSHIP",
            "WILLINGBORO TOWNSHIP",
            "WOODLAND TOWNSHIP",
            "WRIGHTSTOWN BOROUGH"
        ],
        "CAMDEN": [
            "AUDUBON BOROUGH",
            "AUDUBON PARK BOROUGH",
            "BARRINGTON BOROUGH",
            "BELLMAWR BOROUGH",
            "BERLIN BOROUGH",
            "BERLIN TOWNSHIP",
            "BROOKLAWN BOROUGH",
            "CAMDEN CITY",
            "CHERRY HILL TOWNSHIP",
            "CHESILHURST BOROUGH",
            "CLEMENTON BOROUGH",
            "COLLINGSWOOD BOROUGH",
            "GIBBSBORO BOROUGH",
            "GLOUCESTER CITY",
            "GLOUCESTER TOWNSHIP",
            "HADDON HEIGHTS BOROUGH",
            "HADDON TOWNSHIP",
            "HADDONFIELD BOROUGH",
            "HI-NELLA BOROUGH",
            "LAUREL SPRINGS BOROUGH",
            "LAWNSIDE BOROUGH",
            "LINDENWOLD BOROUGH",
            "MAGNOLIA BOROUGH",
            "MERCHANTVILLE BOROUGH",
            "MOUNT EPHRAIM BOROUGH",
            "OAKLYN BOROUGH",
            "PENNSAUKEN TOWNSHIP",
            "PINE HILL BOROUGH",
            "PINE VALLEY BOROUGH",
            "RUNNEMEDE BOROUGH",
            "SOMERDALE BOROUGH",
            "STRATFORD BOROUGH",
            "TAVISTOCK BOROUGH",
            "VOORHEES TOWNSHIP",
            "WATERFORD TOWNSHIP",
            "WINSLOW TOWNSHIP",
            "WOODLYNNE BOROUGH"
        ],
        "CAPE MAY": [
            "AVALON BOROUGH",
            "CAPE MAY CITY",
            "CAPE MAY POINT BOROUGH",
            "DENNIS TOWNSHIP",
            "LOWER TOWNSHIP",
            "MIDDLE TOWNSHIP",
            "NORTH WILDWOOD CITY",
            "OCEAN CITY",
            "SEA ISLE CITY",
            "STONE HARBOR BOROUGH",
            "UPPER TOWNSHIP",
            "WEST CAPE MAY BOROUGH",
            "WEST WILDWOOD BOROUGH",
            "WILDWOOD CITY",
            "WILDWOOD CREST BOROUGH",
            "WOODBINE BOROUGH"
        ],
        "CUMBERLAND": [
            "BRIDGETON CITY",
            "COMMERCIAL TOWNSHIP",
            "DEERFIELD TOWNSHIP",
            "DOWNE TOWNSHIP",
            "FAIRFIELD TOWNSHIP",
            "GREENWICH TOWNSHIP",
            "HOPEWELL TOWNSHIP",
            "LAWRENCE TOWNSHIP",
            "MAURICE RIVER TOWNSHIP",
            "MILLVILLE CITY",
            "SHILOH BOROUGH",
            "STOW CREEK TOWNSHIP",
            "UPPER DEERFIELD TOWNSHIP",
            "VINELAND CITY"
        ],
        "ESSEX": [
            "BELLEVILLE TOWNSHIP",
            "BLOOMFIELD TOWNSHIP",
            "CALDWELL BOROUGH",
            "CEDAR GROVE TOWNSHIP",
            "CITY OF ORANGE TOWNSHIP",
            "EAST ORANGE CITY",
            "ESSEX FELLS BOROUGH",
            "FAIRFIELD TOWNSHIP",
            "GLEN RIDGE BOROUGH",
            "IRVINGTON TOWNSHIP",
            "LIVINGSTON TOWNSHIP",
            "MAPLEWOOD TOWNSHIP",
            "MILLBURN TOWNSHIP",
            "MONTCLAIR TOWNSHIP",
            "NEWARK CITY",
            "NORTH CALDWELL BOROUGH",
            "NUTLEY TOWNSHIP",
            "ROSELAND BOROUGH",
            "SOUTH ORANGE VILLAGE TOWNSHIP",
            "VERONA TOWNSHIP",
            "WEST CALDWELL TOWNSHIP",
            "WEST ORANGE TOWNSHIP"
        ],
        "GLOUCESTER": [
            "CLAYTON BOROUGH",
            "DEPTFORD TOWNSHIP",
            "EAST GREENWICH TOWNSHIP",
            "ELK TOWNSHIP",
            "FRANKLIN TOWNSHIP",
            "GLASSBORO BOROUGH",
            "GREENWICH TOWNSHIP",
            "HARRISON TOWNSHIP",
            "LOGAN TOWNSHIP",
            "MANTUA TOWNSHIP",
            "MONROE TOWNSHIP",
            "NATIONAL PARK BOROUGH",
            "NEWFIELD BOROUGH",
            "PAULSBORO BOROUGH",
            "PITMAN BOROUGH",
            "SOUTH HARRISON TOWNSHIP",
            "SWEDESBORO BOROUGH",
            "WASHINGTON TOWNSHIP",
            "WENONAH BOROUGH",
            "WEST DEPTFORD TOWNSHIP",
            "WESTVILLE BOROUGH",
            "WOODBURY CITY",
            "WOODBURY HEIGHTS BOROUGH",
            "WOOLWICH TOWNSHIP"
        ],
        "HUDSON": [
            "BAYONNE CITY",
            "EAST NEWARK BOROUGH",
            "GUTTENBERG TOWN",
            "HARRISON TOWN",
            "HOBOKEN CITY",
            "JERSEY CITY",
            "KEARNY TOWN",
            "NORTH BERGEN TOWNSHIP",
            "SECAUCUS TOWN",
            "UNION CITY",
            "WEEHAWKEN TOWNSHIP",
            "WEST NEW YORK TOWN"
        ],
        "HUNTERDON": [
            "ALEXANDRIA TOWNSHIP",
            "BETHLEHEM TOWNSHIP",
            "BLOOMSBURY BOROUGH",
            "CALIFON BOROUGH",
            "CLINTON TOWN",
            "CLINTON TOWNSHIP",
            "DELAWARE TOWNSHIP",
            "EAST AMWELL TOWNSHIP",
            "FLEMINGTON BOROUGH",
            "FRANKLIN TOWNSHIP",
            "FRENCHTOWN BOROUGH",
            "GLEN GARDNER BOROUGH",
            "HAMPTON BOROUGH",
            "HIGH BRIDGE BOROUGH",
            "HOLLAND TOWNSHIP",
            "KINGWOOD TOWNSHIP",
            "LAMBERTVILLE CITY",
            "LEBANON BOROUGH",
            "LEBANON TOWNSHIP",
            "MILFORD BOROUGH",
            "RARITAN TOWNSHIP",
            "READINGTON TOWNSHIP",
            "STOCKTON BOROUGH",
            "TEWKSBURY TOWNSHIP",
            "UNION TOWNSHIP",
            "WEST AMWELL TOWNSHIP"
        ],
        "MERCER": [
            "EAST WINDSOR TOWNSHIP",
            "EWING TOWNSHIP",
            "HAMILTON TOWNSHIP",
            "HIGHTSTOWN BOROUGH",
            "HOPEWELL BOROUGH",
            "HOPEWELL TOWNSHIP",
            "LAWRENCE TOWNSHIP",
            "PENNINGTON BOROUGH",
            "PRINCETON",
            "ROBBINSVILLE TOWNSHIP",
            "TRENTON CITY",
            "WEST WINDSOR TOWNSHIP"
        ],
        "MIDDLESEX": [
            "CARTERET BOROUGH",
            "CRANBURY TOWNSHIP",
            "DUNELLEN BOROUGH",
            "EAST BRUNSWICK TOWNSHIP",
            "EDISON TOWNSHIP",
            "HELMETTA BOROUGH",
            "HIGHLAND PARK BOROUGH",
            "JAMESBURG BOROUGH",
            "METUCHEN BOROUGH",
            "MIDDLESEX BOROUGH",
            "MILLTOWN BOROUGH",
            "MONROE TOWNSHIP",
            "NEW BRUNSWICK CITY",
            "NORTH BRUNSWICK TOWNSHIP",
            "OLD BRIDGE TOWNSHIP",
            "PERTH AMBOY CITY",
            "PISCATAWAY TOWNSHIP",
            "PLAINSBORO TOWNSHIP",
            "SAYREVILLE BOROUGH",
            "SOUTH AMBOY CITY",
            "SOUTH BRUNSWICK TOWNSHIP",
            "SOUTH PLAINFIELD BOROUGH",
            "SOUTH RIVER BOROUGH",
            "SPOTSWOOD BOROUGH",
            "WOODBRIDGE TOWNSHIP"
        ],
        "MONMOUTH": [
            "ABERDEEN TOWNSHIP",
            "ALLENHURST BOROUGH",
            "ALLENTOWN BOROUGH",
            "ASBURY PARK CITY",
            "ATLANTIC HIGHLANDS BOROUGH",
            "AVON-BY-THE-SEA BOROUGH",
            "BELMAR BOROUGH",
            "BRADLEY BEACH BOROUGH",
            "BRIELLE BOROUGH",
            "COLTS NECK TOWNSHIP",
            "DEAL BOROUGH",
            "EATONTOWN BOROUGH",
            "ENGLISHTOWN BOROUGH",
            "FAIR HAVEN BOROUGH",
            "FARMINGDALE BOROUGH",
            "FREEHOLD BOROUGH",
            "FREEHOLD TOWNSHIP",
            "HAZLET TOWNSHIP",
            "HIGHLANDS BOROUGH",
            "HOLMDEL TOWNSHIP",
            "HOWELL TOWNSHIP",
            "INTERLAKEN BOROUGH",
            "KEANSBURG BOROUGH",
            "KEYPORT BOROUGH",
            "LAKE COMO BOROUGH",
            "LITTLE SILVER BOROUGH",
            "LOCH ARBOUR VILLAGE",
            "LONG BRANCH CITY",
            "MANALAPAN TOWNSHIP",
            "MANASQUAN BOROUGH",
            "MARLBORO TOWNSHIP",
            "MATAWAN BOROUGH",
            "MIDDLETOWN TOWNSHIP",
            "MILLSTONE TOWNSHIP",
            "MONMOUTH BEACH BOROUGH",
            "NEPTUNE CITY BOROUGH",
            "NEPTUNE TOWNSHIP",
            "OCEAN TOWNSHIP",
            "OCEANPORT BOROUGH",
            "RED BANK BOROUGH",
            "ROOSEVELT BOROUGH",
            "RUMSON BOROUGH",
            "SEA BRIGHT BOROUGH",
            "SEA GIRT BOROUGH",
            "SHREWSBURY BOROUGH",
            "SHREWSBURY TOWNSHIP",
            "SPRING LAKE BOROUGH",
            "SPRING LAKE HEIGHTS BOROUGH",
            "TINTON FALLS BOROUGH",
            "UNION BEACH BOROUGH",
            "UPPER FREEHOLD TOWNSHIP",
            "WALL TOWNSHIP",
            "WEST LONG BRANCH BOROUGH"
        ],
        "MORRIS": [
            "BOONTON TOWN",
            "BOONTON TOWNSHIP",
            "BUTLER BOROUGH",
            "CHATHAM BOROUGH",
            "CHATHAM TOWNSHIP",
            "CHESTER BOROUGH",
            "CHESTER TOWNSHIP",
            "DENVILLE TOWNSHIP",
            "DOVER TOWN",
            "EAST HANOVER TOWNSHIP",
            "FLORHAM PARK BOROUGH",
            "HANOVER TOWNSHIP",
            "HARDING TOWNSHIP",
            "JEFFERSON TOWNSHIP",
            "KINNELON BOROUGH",
            "LINCOLN PARK BOROUGH",
            "LONG HILL TOWNSHIP",
            "MADISON BOROUGH",
            "MENDHAM BOROUGH",
            "MENDHAM TOWNSHIP",
            "MINE HILL TOWNSHIP",
            "MONTVILLE TOWNSHIP",
            "MORRIS PLAINS BOROUGH",
            "MORRIS TOWNSHIP",
            "MORRISTOWN TOWN",
            "MOUNT ARLINGTON BOROUGH",
            "MOUNT OLIVE TOWNSHIP",
            "MOUNTAIN LAKES BOROUGH",
            "NETCONG BOROUGH",
            "PARSIPPANY-TROY HILLS TOWNSHIP",
            "PEQUANNOCK TOWNSHIP",
            "RANDOLPH TOWNSHIP",
            "RIVERDALE BOROUGH",
            "ROCKAWAY BOROUGH",
            "ROCKAWAY TOWNSHIP",
            "ROXBURY TOWNSHIP",
            "VICTORY GARDENS BOROUGH",
            "WASHINGTON TOWNSHIP",
            "WHARTON BOROUGH"
        ],
        "OCEAN": [
            "BARNEGAT LIGHT BOROUGH",
            "BARNEGAT TOWNSHIP",
            "BAY HEAD BOROUGH",
            "BEACH HAVEN BOROUGH",
            "BEACHWOOD BOROUGH",
            "BERKELEY TOWNSHIP",
            "BRICK TOWNSHIP",
            "EAGLESWOOD TOWNSHIP",
            "HARVEY CEDARS BOROUGH",
            "ISLAND HEIGHTS BOROUGH",
            "JACKSON TOWNSHIP",
            "LACEY TOWNSHIP",
            "LAKEHURST BOROUGH",
            "LAKEWOOD TOWNSHIP",
            "LAVALLETTE BOROUGH",
            "LITTLE EGG HARBOR TOWNSHIP",
            "LONG BEACH TOWNSHIP",
            "MANCHESTER TOWNSHIP",
            "MANTOLOKING BOROUGH",
            "OCEAN GATE BOROUGH",
            "OCEAN TOWNSHIP",
            "PINE BEACH BOROUGH",
            "PLUMSTED TOWNSHIP",
            "POINT PLEASANT BEACH BOROUGH",
            "POINT PLEASANT BOROUGH",
            "SEASIDE HEIGHTS BOROUGH",
            "SEASIDE PARK BOROUGH",
            "SHIP BOTTOM BOROUGH",
            "SOUTH TOMS RIVER BOROUGH",
            "STAFFORD TOWNSHIP",
            "SURF CITY BOROUGH",
            "TOMS RIVER TOWNSHIP",
            "TUCKERTON BOROUGH"
        ],
        "PASSAIC": [
            "BLOOMINGDALE BOROUGH",
            "CLIFTON CITY",
            "HALEDON BOROUGH",
            "HAWTHORNE BOROUGH",
            "LITTLE FALLS TOWNSHIP",
            "NORTH HALEDON BOROUGH",
            "PASSAIC CITY",
            "PATERSON CITY",
            "POMPTON LAKES BOROUGH",
            "PROSPECT PARK BOROUGH",
            "RINGWOOD BOROUGH",
            "TOTOWA BOROUGH",
            "WANAQUE BOROUGH",
            "WAYNE TOWNSHIP",
            "WEST MILFORD TOWNSHIP",
            "WOODLAND PARK BOROUGH"
        ],
        "SALEM": [
            "ALLOWAY TOWNSHIP",
            "CARNEYS POINT TOWNSHIP",
            "ELMER BOROUGH",
            "ELSINBORO TOWNSHIP",
            "LOWER ALLOWAYS CREEK TOWNSHIP",
            "MANNINGTON TOWNSHIP",
            "OLDMANS TOWNSHIP",
            "PENNS GROVE BOROUGH",
            "PENNSVILLE TOWNSHIP",
            "PILESGROVE TOWNSHIP",
            "PITTSGROVE TOWNSHIP",
            "QUINTON TOWNSHIP",
            "SALEM CITY",
            "UPPER PITTSGROVE TOWNSHIP",
            "WOODSTOWN BOROUGH"
        ],
        "SOMERSET": [
            "BEDMINSTER TOWNSHIP",
            "BERNARDS TOWNSHIP",
            "BERNARDSVILLE BOROUGH",
            "BOUND BROOK BOROUGH",
            "BRANCHBURG TOWNSHIP",
            "BRIDGEWATER TOWNSHIP",
            "FAR HILLS BOROUGH",
            "FRANKLIN TOWNSHIP",
            "GREEN BROOK TOWNSHIP",
            "HILLSBOROUGH TOWNSHIP",
            "MANVILLE BOROUGH",
            "MILLSTONE BOROUGH",
            "MONTGOMERY TOWNSHIP",
            "NORTH PLAINFIELD BOROUGH",
            "PEAPACK-GLADSTONE BOROUGH",
            "RARITAN BOROUGH",
            "ROCKY HILL BOROUGH",
            "SOMERVILLE BOROUGH",
            "SOUTH BOUND BROOK BOROUGH",
            "WARREN TOWNSHIP",
            "WATCHUNG BOROUGH"
        ],
        "SUSSEX": [
            "ANDOVER BOROUGH",
            "ANDOVER TOWNSHIP",
            "BRANCHVILLE BOROUGH",
            "BYRAM TOWNSHIP",
            "FRANKFORD TOWNSHIP",
            "FRANKLIN BOROUGH",
            "FREDON TOWNSHIP",
            "GREEN TOWNSHIP",
            "HAMBURG BOROUGH",
            "HAMPTON TOWNSHIP",
            "HARDYSTON TOWNSHIP",
            "HOPATCONG BOROUGH",
            "LAFAYETTE TOWNSHIP",
            "MONTAGUE TOWNSHIP",
            "NEWTON TOWN",
            "OGDENSBURG BOROUGH",
            "SANDYSTON TOWNSHIP",
            "SPARTA TOWNSHIP",
            "STANHOPE BOROUGH",
            "STILLWATER TOWNSHIP",
            "SUSSEX BOROUGH",
            "VERNON TOWNSHIP",
            "WALPACK TOWNSHIP",
            "WANTAGE TOWNSHIP"
        ],
        "UNION": [
            "BERKELEY HEIGHTS TOWNSHIP",
            "CLARK TOWNSHIP",
            "CRANFORD TOWNSHIP",
            "ELIZABETH CITY",
            "FANWOOD BOROUGH",
            "GARWOOD BOROUGH",
            "HILLSIDE TOWNSHIP",
            "KENILWORTH BOROUGH",
            "LINDEN CITY",
            "MOUNTAINSIDE BOROUGH",
            "NEW PROVIDENCE BOROUGH",
            "PLAINFIELD CITY",
            "RAHWAY CITY",
            "ROSELLE BOROUGH",
            "ROSELLE PARK BOROUGH",
            "SCOTCH PLAINS TOWNSHIP",
            "SPRINGFIELD TOWNSHIP",
            "SUMMIT CITY",
            "UNION TOWNSHIP",
            "WESTFIELD TOWN",
            "WINFIELD TOWNSHIP"
        ],
        "WARREN": [
            "ALLAMUCHY TOWNSHIP",
            "ALPHA BOROUGH",
            "BELVIDERE TOWN",
            "BLAIRSTOWN TOWNSHIP",
            "FRANKLIN TOWNSHIP",
            "FRELINGHUYSEN TOWNSHIP",
            "GREENWICH TOWNSHIP",
            "HACKETTSTOWN TOWN",
            "HARDWICK TOWNSHIP",
            "HARMONY TOWNSHIP",
            "HOPE TOWNSHIP",
            "INDEPENDENCE TOWNSHIP",
            "KNOWLTON TOWNSHIP",
            "LIBERTY TOWNSHIP",
            "LOPATCONG TOWNSHIP",
            "MANSFIELD TOWNSHIP",
            "OXFORD TOWNSHIP",
            "PHILLIPSBURG TOWN",
            "POHATCONG TOWNSHIP",
            "WASHINGTON BOROUGH",
            "WASHINGTON TOWNSHIP",
            "WHITE TOWNSHIP"
        ]
    }


def getDistrictCodes():
    return {
        "Atlantic": {
            "Absecon": "0101",
            "Atlantic City": "0102",
            "Brigantine": "0103",
            "Buena": "0104",
            "Buena Vista": "0105",
            "Corbin City": "0106",
            "Egg Harbor City": "0107",
            "Egg Harbor": "0108",
            "Estell Manor": "0109",
            "Folsom": "0110",
            "Galloway": "0111",
            "Hamilton": "0112",
            "Hammonton": "0113",
            "Linwood": "0114",
            "Longport": "0115",
            "Margate City": "0116",
            "Mullica": "0117",
            "Northfield": "0118",
            "Pleasantville": "0119",
            "Port Republic": "0120",
            "Somers Point": "0121",
            "Ventnor City": "0122",
            "Weymouth": "0123"
        },
        "Bergen": {
            "Allendale": "0201",
            "Alpine": "0202",
            "Bergenfield": "0203",
            "Bogota": "0204",
            "Carlstadt": "0205",
            "Cliffside Park": "0206",
            "Closter": "0207",
            "Cresskill": "0208",
            "Demarest": "0209",
            "Dumont": "0210",
            "Elmwood Park": "0211",
            "East Rutherford": "0212",
            "Edgewater": "0213",
            "Emerson": "0214",
            "Englewood": "0215",
            "Englewood Cliffs": "0216",
            "Fair Lawn": "0217",
            "Fairview": "0218",
            "Fort Lee": "0219",
            "Franklin Lakes": "0220",
            "Garfield": "0221",
            "Glen Rock": "0222",
            "Hackensack": "0223",
            "Harrington Park": "0224",
            "Hasbrouck Heights": "0225",
            "Haworth": "0226",
            "Hillsdale": "0227",
            "Ho-Ho-Kus": "0228",
            "Leonia": "0229",
            "Little Ferry": "0230",
            "Lodi": "0231",
            "Lyndhurst": "0232",
            "Mahwah": "0233",
            "Maywood": "0234",
            "Midland Park": "0235",
            "Montvale": "0236",
            "Moonachie": "0237",
            "New Milford": "0238",
            "North Arlington": "0239",
            "Northvale": "0240",
            "Norwood": "0241",
            "Oakland": "0242",
            "Old Tappan": "0243",
            "Oradell": "0244",
            "Palisades Park": "0245",
            "Paramus": "0246",
            "Park Ridge": "0247",
            "Ramsey": "0248",
            "Ridgefield": "0249",
            "Ridgefield Park Village": "0250",
            "Ridgewood Village": "0251",
            "River Edge": "0252",
            "River Vale": "0253",
            "Rochelle Park": "0254",
            "Rockleigh": "0255",
            "Rutherford": "0256",
            "Saddle Brook": "0257",
            "Saddle River": "0258",
            "South Hackensack": "0259",
            "Teaneck": "0260",
            "Tenafly": "0261",
            "Teterboro": "0262",
            "Upper Saddle River": "0263",
            "Waldwick": "0264",
            "Wallington": "0265",
            "Washington": "0266",
            "Westwood": "0267",
            "Woodcliff Lake": "0268",
            "Wood-Ridge": "0269",
            "Wyckoff": "0270"
        },
        "Burlington": {
            "Bass River": "0301",
            "Beverly": "0302",
            "Bordentown": "0304",
            "Burlington": "0306",
            "Chesterfield": "0307",
            "Cinnaminson": "0308",
            "Delanco": "0309",
            "Delran": "0310",
            "Eastampton": "0311",
            "Edgewater Park": "0312",
            "Evesham": "0313",
            "Fieldsboro": "0314",
            "Florence": "0315",
            "Hainesport": "0316",
            "Lumberton": "0317",
            "Mansfield": "0318",
            "Maple Shade": "0319",
            "Medford": "0320",
            "Medford Lakes": "0321",
            "Moorestown": "0322",
            "Mount Holly": "0323",
            "Mount Laurel": "0324",
            "New Hanover": "0325",
            "North Hanover": "0326",
            "Palmyra": "0327",
            "Pemberton": "0329",
            "Riverside": "0330",
            "Riverton": "0331",
            "Shamong": "0332",
            "Southampton": "0333",
            "Springfield": "0334",
            "Tabernacle": "0335",
            "Washington": "0336",
            "Westampton": "0337",
            "Willingboro": "0338",
            "Woodland": "0339",
            "Wrightstown": "0340"
        },
        "Camden": {
            "Audubon": "0401",
            "Audubon Park": "0402",
            "Barrington": "0403",
            "Bellmawr": "0404",
            "Berlin": "0406",
            "Brooklawn": "0407",
            "Camden": "0408",
            "Cherry Hill": "0409",
            "Chesilhurst": "0410",
            "Clementon": "0411",
            "Collingswood": "0412",
            "Gibbsboro": "0413",
            "Gloucester City": "0414",
            "Gloucester": "0415",
            "Haddon": "0416",
            "Haddonfield": "0417",
            "Haddon Heights": "0418",
            "Hi-Nella": "0419",
            "Laurel Springs": "0420",
            "Lawnside": "0421",
            "Lindenwold": "0422",
            "Magnolia": "0423",
            "Merchantville": "0424",
            "Mount Ephraim": "0425",
            "Oaklyn": "0426",
            "Pennsauken": "0427",
            "Pine Hill": "0428",
            "Pine Valley": "0429",
            "Runnemede": "0430",
            "Somerdale": "0431",
            "Stratford": "0432",
            "Tavistock": "0433",
            "Voorhees": "0434",
            "Waterford": "0435",
            "Winslow": "0436",
            "Woodlynne": "0437"
        },
        "Cape May": {
            "Avalon": "0501",
            "Cape May": "0502",
            "Cape May Point": "0503",
            "Dennis": "0504",
            "Lower": "0505",
            "Middle": "0506",
            "North Wildwood": "0507",
            "Ocean City": "0508",
            "Sea Isle City": "0509",
            "Stone Harbor": "0510",
            "Upper": "0511",
            "West Cape May": "0512",
            "West Wildwood": "0513",
            "Wildwood": "0514",
            "Wildwood Crest": "0515",
            "Woodbine": "0516"
        },
        "Cumberland": {
            "Bridgeton": "0601",
            "Commercial": "0602",
            "Deerfield": "0603",
            "Downe": "0604",
            "Fairfield": "0605",
            "Greenwich": "0606",
            "Hopewell": "0607",
            "Lawrence": "0608",
            "Maurice River": "0609",
            "Millville": "0610",
            "Shiloh": "0611",
            "Stow Creek": "0612",
            "Upper Deerfield": "0613",
            "Vineland": "0614"
        },
        "Essex": {
            "Belleville": "0701",
            "Bloomfield": "0702",
            "Caldwell": "0703",
            "Cedar Grove": "0704",
            "East Orange": "0705",
            "Essex Fells": "0706",
            "Fairfield": "0707",
            "Glen Ridge": "0708",
            "Irvington": "0709",
            "Livingston": "0710",
            "Maplewood": "0711",
            "Millburn": "0712",
            "Montclair": "0713",
            "Newark": "0714",
            "North Caldwell": "0715",
            "Nutley": "0716",
            "City of Orange": "0717",
            "Roseland": "0718",
            "South Orange Village": "0719",
            "Verona": "0720",
            "West Caldwell": "0721",
            "West Orange": "0722"
        },
        "Gloucester": {
            "Clayton": "0801",
            "Deptford": "0802",
            "East Greenwich": "0803",
            "Elk": "0804",
            "Franklin": "0805",
            "Glassboro": "0806",
            "Greenwich": "0807",
            "Harrison": "0808",
            "Logan": "0809",
            "Mantua": "0810",
            "Monroe": "0811",
            "National Park": "0812",
            "Newfield": "0813",
            "Paulsboro": "0814",
            "Pitman": "0815",
            "South Harrison": "0816",
            "Swedesboro": "0817",
            "Washington": "0818",
            "Wenonah": "0819",
            "West Deptford": "0820",
            "Westville": "0821",
            "Woodbury": "0822",
            "Woodbury Heights": "0823",
            "Woolwich": "0824"
        },
        "Hudson": {
            "Bayonne": "0901",
            "East Newark": "0902",
            "Guttenberg": "0903",
            "Harrison": "0904",
            "Hoboken": "0905",
            "Jersey City": "0906",
            "Kearny": "0907",
            "North Bergen": "0908",
            "Secaucus": "0909",
            "Union City": "0910",
            "Weehawken": "0911",
            "West New York": "0912"
        },
        "Hunterdon": {
            "Alexandria": "1001",
            "Bethlehem": "1002",
            "Bloomsbury": "1003",
            "Califon": "1004",
            "Clinton": "1006",
            "Delaware": "1007",
            "East Amwell": "1008",
            "Flemington": "1009",
            "Franklin": "1010",
            "Frenchtown": "1011",
            "Glen Gardner": "1012",
            "Hampton": "1013",
            "High Bridge": "1014",
            "Holland": "1015",
            "Kingwood": "1016",
            "Lambertville": "1017",
            "Lebanon": "1019",
            "Milford": "1020",
            "Raritan": "1021",
            "Readington": "1022",
            "Stockton": "1023",
            "Tewksbury": "1024",
            "Union": "1025",
            "West Amwell": "1026"
        },
        "Mercer": {
            "East Windsor": "1101",
            "Ewing": "1102",
            "Hamilton": "1103",
            "Hightstown": "1104",
            "Hopewell": "1106",
            "Lawrence": "1107",
            "Pennington": "1108",
            "Princeton": "1114",
            "Trenton": "1111",
            "Robbinsville": "1112",
            "West Windsor": "1113"
        },
        "Middlesex": {
            "Carteret": "1201",
            "Cranbury": "1202",
            "Dunellen": "1203",
            "East Brunswick": "1204",
            "Edison": "1205",
            "Helmetta": "1206",
            "Highland Park": "1207",
            "Jamesburg": "1208",
            "Metuchen": "1209",
            "Middlesex": "1210",
            "Milltown": "1211",
            "Monroe": "1212",
            "New Brunswick": "1213",
            "North Brunswick": "1214",
            "Old Bridge": "1215",
            "Perth Amboy": "1216",
            "Piscataway": "1217",
            "Plainsboro": "1218",
            "Sayreville": "1219",
            "South Amboy": "1220",
            "South Brunswick": "1221",
            "South Plainfield": "1222",
            "South River": "1223",
            "Spotswood": "1224",
            "Woodbridge": "1225"
        },
        "Monmouth": {
            "Aberdeen": "1301",
            "Allenhurst": "1302",
            "Allentown": "1303",
            "Asbury Park": "1304",
            "Atlantic Highlands": "1305",
            "Avon-by-the-Sea": "1306",
            "Belmar": "1307",
            "Bradley Beach": "1308",
            "Brielle": "1309",
            "Colts Neck": "1310",
            "Deal": "1311",
            "Eatontown": "1312",
            "Englishtown": "1313",
            "Fair Haven": "1314",
            "Farmingdale": "1315",
            "Freehold": "1317",
            "Hazlet": "1318",
            "Highlands": "1319",
            "Holmdel": "1320",
            "Howell": "1321",
            "Interlaken": "1322",
            "Keansburg": "1323",
            "Keyport": "1324",
            "Little Silver": "1325",
            "Loch Arbour Village": "1326",
            "Long Branch": "1327",
            "Manalapan": "1328",
            "Manasquan": "1329",
            "Marlboro": "1330",
            "Matawan": "1331",
            "Middletown": "1332",
            "Millstone": "1333",
            "Monmouth Beach": "1334",
            "Neptune": "1335",
            "Neptune City": "1336",
            "Ocean": "1337",
            "Oceanport": "1338",
            "Red Bank": "1339",
            "Roosevelt": "1340",
            "Rumson": "1341",
            "Sea Bright": "1342",
            "Sea Girt": "1343",
            "Shrewsbury": "1345",
            "Lake Como": "1346",
            "Spring Lake": "1347",
            "Spring Lake Heights": "1348",
            "Tinton Falls": "1349",
            "Union Beach": "1350",
            "Upper Freehold": "1351",
            "Wall": "1352",
            "West Long Branch": "1353"
        },
        "Morris": {
            "Boonton": "1402",
            "Butler": "1403",
            "Chatham": "1405",
            "Chester": "1407",
            "Denville": "1408",
            "Dover": "1409",
            "East Hanover": "1410",
            "Florham Park": "1411",
            "Hanover": "1412",
            "Harding": "1413",
            "Jefferson": "1414",
            "Kinnelon": "1415",
            "Lincoln Park": "1416",
            "Madison": "1417",
            "Mendham": "1419",
            "Mine Hill": "1420",
            "Montville": "1421",
            "Morris": "1422",
            "Morris Plains": "1423",
            "Morristown": "1424",
            "Mountain Lakes": "1425",
            "Mount Arlington": "1426",
            "Mount Olive": "1427",
            "Netcong": "1428",
            "Parsippany-Troy Hills": "1429",
            "Long Hill": "1430",
            "Pequannock": "1431",
            "Randolph": "1432",
            "Riverdale": "1433",
            "Rockaway": "1435",
            "Roxbury": "1436",
            "Victory Gardens": "1437",
            "Washington": "1438",
            "Wharton": "1439"
        },
        "Ocean": {
            "Barnegat": "1501",
            "Barnegat Light": "1502",
            "Bay Head": "1503",
            "Beach Haven": "1504",
            "Beachwood": "1505",
            "Berkeley": "1506",
            "Brick": "1507",
            "Toms River": "1508",
            "Eagleswood": "1509",
            "Harvey Cedars": "1510",
            "Island Heights": "1511",
            "Jackson": "1512",
            "Lacey": "1513",
            "Lakehurst": "1514",
            "Lakewood": "1515",
            "Lavallette": "1516",
            "Little Egg Harbor": "1517",
            "Long Beach": "1518",
            "Manchester": "1519",
            "Mantoloking": "1520",
            "Ocean": "1521",
            "Ocean Gate": "1522",
            "Pine Beach": "1523",
            "Plumsted": "1524",
            "Point Pleasant": "1525",
            "Point Pleasant Beach": "1526",
            "Seaside Heights": "1527",
            "Seaside Park": "1528",
            "Ship Bottom": "1529",
            "South Toms River": "1530",
            "Stafford": "1531",
            "Surf City": "1532",
            "Tuckerton": "1533"
        },
        "Passaic": {
            "Bloomingdale": "1601",
            "Clifton": "1602",
            "Haledon": "1603",
            "Hawthorne": "1604",
            "Little Falls": "1605",
            "North Haledon": "1606",
            "Passaic": "1607",
            "Paterson": "1608",
            "Pompton Lakes": "1609",
            "Prospect Park": "1610",
            "Ringwood": "1611",
            "Totowa": "1612",
            "Wanaque": "1613",
            "Wayne": "1614",
            "West Milford": "1615",
            "Woodland Park": "1616"
        },
        "Salem": {
            "Alloway": "1701",
            "Carneys Point": "1702",
            "Elmer": "1703",
            "Elsinboro": "1704",
            "Lower Alloways Creek": "1705",
            "Mannington": "1706",
            "Oldmans": "1707",
            "Penns Grove": "1708",
            "Pennsville": "1709",
            "Pilesgrove": "1710",
            "Pittsgrove": "1711",
            "Quinton": "1712",
            "Salem": "1713",
            "Upper Pittsgrove": "1714",
            "Woodstown": "1715"
        },
        "Somerset": {
            "Bedminster": "1801",
            "Bernards": "1802",
            "Bernardsville": "1803",
            "Bound Brook": "1804",
            "Branchburg": "1805",
            "Bridgewater": "1806",
            "Far Hills": "1807",
            "Franklin": "1808",
            "Green Brook": "1809",
            "Hillsborough": "1810",
            "Manville": "1811",
            "Millstone": "1812",
            "Montgomery": "1813",
            "North Plainfield": "1814",
            "Peapack-Gladstone": "1815",
            "Raritan": "1816",
            "Rocky Hill": "1817",
            "Somerville": "1818",
            "South Bound Brook": "1819",
            "Warren": "1820",
            "Watchung": "1821"
        },
        "Sussex": {
            "Andover": "1902",
            "Branchville": "1903",
            "Byram": "1904",
            "Frankford": "1905",
            "Franklin": "1906",
            "Fredon": "1907",
            "Green": "1908",
            "Hamburg": "1909",
            "Hampton": "1910",
            "Hardyston": "1911",
            "Hopatcong": "1912",
            "Lafayette": "1913",
            "Montague": "1914",
            "Newton": "1915",
            "Ogdensburg": "1916",
            "Sandyston": "1917",
            "Sparta": "1918",
            "Stanhope": "1919",
            "Stillwater": "1920",
            "Sussex": "1921",
            "Vernon": "1922",
            "Walpack": "1923",
            "Wantage": "1924"
        },
        "Union": {
            "Berkeley Heights": "2001",
            "Clark": "2002",
            "Cranford": "2003",
            "Elizabeth": "2004",
            "Fanwood": "2005",
            "Garwood": "2006",
            "Hillside": "2007",
            "Kenilworth": "2008",
            "Linden": "2009",
            "Mountainside": "2010",
            "New Providence": "2011",
            "Plainfield": "2012",
            "Rahway": "2013",
            "Roselle": "2014",
            "Roselle Park": "2015",
            "Scotch Plains": "2016",
            "Springfield": "2017",
            "Summit": "2018",
            "Union": "2019",
            "Westfield": "2020",
            "Winfield": "2021"
        },
        "Warren": {
            "Allamuchy": "2101",
            "Alpha": "2102",
            "Belvidere": "2103",
            "Blairstown": "2104",
            "Franklin": "2105",
            "Frelinghuysen": "2106",
            "Greenwich": "2107",
            "Hackettstown": "2108",
            "Hardwick": "2109",
            "Harmony": "2110",
            "Hope": "2111",
            "Independence": "2112",
            "Knowlton": "2113",
            "Liberty": "2114",
            "Lopatcong": "2115",
            "Mansfield": "2116",
            "Oxford": "2117",
            "Phillipsburg": "2119",
            "Pohatcong": "2120",
            "Washington": "2122",
            "White": "2123"
        }
    }


def getRangeFromString(string):
    try:
        if string == "":
            return []
        elif "," in string:
            if "-" in string:
                rng = []
                for x in string.split(","):
                    rng.extend(getRangeFromString(x.strip()))
                return rng
            return [float(i) for i in string.split(",")]
        elif "-" in string:
            start, end = string.split("-")
            return list(range(int(start), int(end) + 1))
        return [float(string)]
    except:
        print(f"Error in range ({string})")


def getBlockLotQual(label):
    print(f"Getting block lot qual for {label}")
    label = label
    block = label.split()[1]
    lot = label.split("Lot")[1].strip().replace("and", ",").replace("&", ",").replace(" ,", ',').replace(',,', ',')
    qual = ""
    pattern = re.compile(r'\b[a-zA-Z]\w*\b')
    result = pattern.findall(lot)
    if len(result) == 1:
        qual = result[0]
        print(f"Got qualifier {qual}")
        lot = lot.replace(qual, "").strip()[:-1]
    if len(lot.split()) == 2 and "," not in lot and "-" not in lot:
        qual = lot.split()[-1]
        print(f"Got qualifier {qual}")
        lot = lot.split()[0]
    return block, getRangeFromString(lot), qual


def processError():
    if os.path.isfile("error.txt"):
        with open("error.txt", "r") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip().split(",")
            print(line)
            getNJactb(line[0], line[1], line[2], line[3])


if __name__ == "__main__":
    # print(getBlockLotQual("Block 163.22        Lot 6, C2942"))
    # exit()
    # processAllJson()
    main()
    # driver = getChromeDriver()
    # getData(BeautifulSoup(driver.page_source, 'html.parser'), driver, "4362", "23")
    # getGoogleAddress("283 Landing Rd, Downe , Cumberland")
    # checkNJATCB()
    # getNJactb("Sussex","Stanhope","11701","14")
