import csv
import datetime
import os.path
import time
import traceback
from time import sleep

# import gspread
# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from oauth2client.service_account import ServiceAccountCredentials
# import PyPDF2

import openpyxl
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import json

t = 1
timeout = 10

# valid = {
#     "Case Status": "Active",
#     "Case Type": [
#         "In Rem Tax Foreclosure",
#         "In Personam Tax Foreclosure"
#     ],
#     "Docket Text": [
#         "fixing amount/time/place",
#         "Motion for final judgment",
#         "MISCELLANEOUS MOTION",
#         "Abandoned Property"
#     ],
#     "Venue": ["Bergen", "Essex", "Hudson", "Middlesex", "Monmouth", "Morris", "Passaic", "Somerset", "Union"],
# }
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

ss = 'ss'
notrequired = []
nrfile = 'notrequired.txt'
scrapedcsv = "NJ-Courts.csv"
# outcsv = "Out.csv"
debug = False
headless = False
images = True
maximize = False
incognito = False
encoding = 'utf8'
drivers = []
nj_url = 'https://portal.njcourts.gov/CIVILCaseJacketWeb/pages/civilCaseSearch.faces'
disclaimer = "https://portal.njcourts.gov/webcivilcj/CIVILCaseJacketWeb/pages/publicAccessDisclaimer.faces"

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

sheet = "https://docs.google.com/spreadsheets/d/1tAgPaFU1J5ObQWIl6AnQ69MauIsIOEP3BY6x_yGeRCI"
sheet_headers = "https://docs.google.com/spreadsheets/d/1ZPr8vrUAnnJZY1wUEBmpGNnNFP8ieEf4qKXqfMNghyM"

count = 1
# if debug:
#     fieldnames = """Docket Number
# Case Caption
# CourtBusinessName
# CourtNameType
# CourtFirstName
# CourtMiddleName
# CourtLastName
# CourtNameExtra
# StateTaxBusinessName
# StateTaxNameType
# StateTaxFirstName
# StateTaxMiddleName
# StateTaxLastName
# StateTaxNameExtra""".splitlines()
# else:
with open('fieldnames.txt') as ffile:
    fieldnames = ffile.read().splitlines()


def processHeaders():
    with open('headers.txt') as hfile:
        headers = hfile.readlines()
    data = {}
    for line in headers:
        line = line.strip().split("\t")
        if len(line) == 2 and line[0] != "" and line[1] != "":
            data[line[1]] = line[0]
    print(json.dumps(data, indent=4))
    with open('headers.json', 'w') as outfile:
        json.dump(data, outfile, indent=4)


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


def append(data):
    with open(scrapedcsv, 'a', newline='', encoding=encoding) as sfile:
        csv.DictWriter(sfile, fieldnames=fieldnames, extrasaction='ignore').writerow(data)


def processJson(f):
    # with open('headers.json') as hfile:
    #     headers = json.load(hfile)
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
                if "Case Caption" in data and "Vs" in data["Case Caption"]:
                    name = data["Case Caption"].split("Vs")[1].strip()
                    updated_data['CourtBusinessName'] = name
                    updated_data.update(getName(name, "Court"))
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
                        updated_data['StateTaxMailingAddressCity'] = data['StateTax']['City State'].split(",")[
                            0].strip()
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
                        updated_data['StateTaxPropertyAddressCity'] = dist
                        updated_data['StateTaxPropertyAddressState'] = "NJ"
                        updated_data['StateTaxPropertyAddressZip'] = ""
                        updated_data['StateTaxPropertyAddressCounty'] = data['StateTax']['County']
                    except:
                        traceback.print_exc()
                    updated_data['StateTaxPropertyNormalizedAddress'] = getGoogleAddress(state_tax_prop_addr)
                if "ArcGis" in data and data["ArcGis"]:
                    if "CITY_STATE" not in data['ArcGis']:
                        updated_data['ArcGisMailingAddress'] = "Unknown"
                        continue
                    if "UNKNOWN" in data['ArcGis']['CITY_STATE'] or "UNKNOWN" in data['ArcGis']['ST_ADDRESS']:
                        updated_data['ArcGisMailingAddress'] = "Unknown"
                        continue
                    if "," not in data['ArcGis']['CITY_STATE']:
                        data['ArcGis']['CITY_STATE'] = data['ArcGis']['CITY_STATE'].replace(" ", ", ")
                    arcgis_mail_addr = f"{data['ArcGis']['ST_ADDRESS']}, {data['ArcGis']['CITY_STATE']}"
                    updated_data['ArcGisMailingAddress'] = arcgis_mail_addr
                    try:
                        updated_data['ArcGisMailingAddressStreet'] = data['ArcGis']['ST_ADDRESS'][0].strip()

                        updated_data['ArcGisMailingAddressCity'] = data['ArcGis']['CITY_STATE'].split(",")[0].strip()
                        updated_data['ArcGisMailingAddressState'] = data['ArcGis']['CITY_STATE'].split(",")[1].strip()
                        updated_data['ArcGisMailingAddressZip'] = data['ArcGis']['ZIP_CODE']
                    except:
                        print(data['ArcGis'])
                        traceback.print_exc()
                    updated_data['ArcGisMailingNormalizedAddress'] = getGoogleAddress(arcgis_mail_addr)
                    arcgis_prop_addr = f"{data['ArcGis']['PROP_LOC']}, {data['ArcGis']['MUN_NAME']}, {data['ArcGis']['COUNTY']}"
                    updated_data['ArcGisPropertyAddress'] = arcgis_prop_addr

                    try:
                        updated_data['ArcGisPropertyAddressStreet'] = data['ArcGis']['PROP_LOC']
                        updated_data['ArcGisPropertyAddressCity'] = data['ArcGis']['MUN_NAME']
                        for word in ['Twnshp', 'City', 'Boro', 'Twp']:
                            updated_data['ArcGisPropertyAddressCity'] = updated_data[
                                'ArcGisPropertyAddressCity'].replace(
                                word, '')
                        updated_data['ArcGisPropertyAddressState'] = "NJ"
                        updated_data['ArcGisPropertyAddressCounty'] = data['ArcGis']['COUNTY']
                        updated_data['ArcGisPropertyAddressZip'] = ""
                    except:
                        traceback.print_exc()
                    updated_data['ArcGisPropertyNormalizedAddress'] = getGoogleAddress(arcgis_prop_addr)
            except:
                print(f"Error processing {file} {property_}")
                traceback.print_exc()
                # input("Press any key...")
            newfile = f"./CSV_json/CSV-{f.replace('/', '_').replace('.json', '')}-{data['Label'].replace('/', '_')}.json"
            updated_data['Comments'] = updated_data.copy()
            # if debug:
            #     print(updated_data.keys())
            with open(newfile, 'w') as jfile:
                json.dump(updated_data, jfile, indent=4)
            append(updated_data)
    else:
        newfile = f"./CSV_json/CSV-{f}.json".replace("/", "_")
        updated_data = flatten_json(data)
        # updated_data = {}
        # for key, value in new_data.items():
        #     if key in headers:
        #         updated_data[headers[key]] = value
        updated_data['Comments'] = updated_data.copy()
        with open(newfile, 'w') as jfile:
            json.dump(updated_data, jfile, indent=4)
        append(updated_data)
    if not debug:
        convert(scrapedcsv)
        CategorizeJson(f)


def getApn(url):
    apn = url.split("&l02=")[1].replace("_________M", "").replace('____', '-0000-')
    return f"{apn[2:4]} {apn[4:]}"


def processAllJson():
    for f in os.listdir(jdir):
        if not f.endswith(".json"):
            continue
        processJson(f)


def convert(filename):
    wb = openpyxl.Workbook()
    ws = wb.active
    with open(filename, encoding=encoding) as f:
        reader = csv.reader(f, delimiter=',')
        for row in reader:
            ws.append(row)
    wb.save(filename.replace("csv", "xlsx"))


def CategorizeAllJson():
    for f in os.listdir(jdir):
        if not f.endswith(".json"):
            continue
        CategorizeJson(f)


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


def getNJactb(county, district, block, lot, district_number=None):
    try:
        data = {"County": county, "District": district}
        print(f"Fetching records for {county}/{district}/{block}/{lot}")
        with open("njactb.json", "r") as jfile:
            disctricts = json.load(jfile)
        if district_number is None:
            try:
                if district.upper() not in disctricts[county.upper()].keys():
                    district = district.split()[0]
                district_number = disctricts[county.upper()][district.upper()]
            except:
                print(f"Invalid District {county}/{district}/{block}/{lot}")
                return None
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
            'qual': ''
        }
        response = requests.post('http://tax1.co.monmouth.nj.us/cgi-bin/inf.cgi', headers=headers, data=req_data,
                                 verify=False)
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


def getOcean(district, block, lot):
    try:
        print(f"Fetching records for Ocean/{district}/{block}/{lot}")
        headers = {'user-agent': 'Mozilla/5.0'}
        with open("ocean.json") as f:
            districts = json.load(f)
        found = False
        district_num = ""
        for key, val in districts.items():
            if key.upper() in district.upper() or district.upper() in key.upper():
                district = key
                district_num = val
                found = True
                break
        if not found or district_num == "":
            print(f"District {district} not found!")
            return
        url = 'https://tax.co.ocean.nj.us/frmTaxBoardTaxListSearch.aspx'
        s = requests.Session()
        soup = BeautifulSoup(s.get(url, headers=headers).content, 'lxml')
        req_data = {
            '__VIEWSTATE': soup.find("input", {"id": "__VIEWSTATE"})["value"],
            '__VIEWSTATEGENERATOR': soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
            '__EVENTVALIDATION': soup.find("input", {"id": "__EVENTVALIDATION"})["value"],
            'ctl00$LogoFreeholders$FreeholderHistory$FreeholderAccordion_AccordionExtender_ClientState': '-1',
            'ctl00$MainContent$cmbDistrict': district_num,
            'ctl00$MainContent$txtBlock': block,
            'ctl00$MainContent$txtLot': lot,
            'ctl00$MainContent$btnSearch': 'Search'
        }
        response = requests.post('https://tax.co.ocean.nj.us/frmTaxBoardTaxListSearch', headers=headers, data=req_data)
        soup = BeautifulSoup(response.content, 'lxml')
        ahrefs = soup.find("table", {"id": "MainContent_m_DataTable"}).find_all("a", {"target": "_blank"})
        print(f"Found {len(ahrefs)} records")
        href = "https://tax.co.ocean.nj.us/" + ahrefs[0]["href"]
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


def getArcGis(county, district, block, lot):
    try:
        attrib = {"County": county, "District": district}
        print(f"Fetching ARCGIS records for {county}/{district}/{block}/{lot}")
        with open("arcgis.json") as f:
            districts = json.load(f)
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
        if "," not in attrib['CITY_STATE']:
            city_State = attrib['CITY_STATE'].split()
            attrib['CITY_STATE'] = " ".join(city_State[:-1]) + f", {city_State[-1]}"
        with open(f"ArcGis/{county}-{district}-{block}-{lot}-ARCGIS.json", 'w') as outfile:
            json.dump(attrib, outfile, indent=4)
        return attrib
    except:
        print(f"Error {county}/{district}/{block}/{lot}")
        traceback.print_exc()
        return None


def isValidDocket(data):
    return True
    # for txt in valid["Docket Text"]:
    #     if txt.lower() in str(data).lower():
    #         return True
    # return False


def isValid(data):
    return True
    # if data["Case Status"].lower() != valid['Case Status'].lower():
    #     pprint(f"Case Status not active ({data['Case Status']})")
    #     return False
    # for ct in valid['Case Type']:
    #     if ct.lower() in data['Case Type'].lower():
    #         return True
    # pprint(f"Not required ({data['Docket Number']})")
    # return False


def processNjCourts():
    if not os.path.isfile("LastRun.json"):
        lastrun['StartNumber'] = int(input("Enter starting number: "))
        lastrun['EndNumber'] = int(input("Enter ending number: "))
        lastrun['StartYear'] = int(input("Enter starting year: "))
        lastrun['EndYear'] = int(input("Enter ending year: "))
        lastrun['CurrentYear'] = lastrun['StartYear']
        lastrun['CurrentNumber'] = lastrun['StartNumber']
        with open("LastRun.json", "w") as outfile:
            json.dump(lastrun, outfile, indent=4)
    else:
        print("Resuming from last run")
        print(json.dumps(lastrun, indent=4))
    num = range(lastrun['StartNumber'], lastrun['EndNumber'] + 1)
    year = range(lastrun['CurrentYear'], lastrun['EndYear'] + 1)
    driver = getChromeDriver()
    if "portal.njcourts.gov" not in driver.current_url:
        driver.get(nj_url)
        if "Enter user ID and password" in driver.page_source:
            driver.delete_all_cookies()
            driver.get(disclaimer)
        time.sleep(3)
        checkDisclaimer(driver)
    for y in year:
        for n in num:
            if y == lastrun['CurrentYear'] and n < lastrun['CurrentNumber']:
                print(f"Skipping {y}-{n}")
                continue
            if f"{y}-{n}" in notrequired:
                pprint(f"Number {n} Year {y} not required!")
                continue
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
            driver.get(nj_url)


def processBlockLot(data, row):
    print(f"Working on {row}")
    if row['county'] in ["Burlington", "Camden"]:
        data["StateTax"] = {}
    elif row['county'] == "Ocean":
        data["StateTax"] = getOcean(row['district'], row['block'], row['lot'])
    else:
        data["StateTax"] = getNJactb(row['county'], row['district'], row['block'], row['lot'])
    data['ArcGis'] = getArcGis(row['county'], row['district'], row['block'], row['lot'])


def SearchBlockLot():
    if os.path.isfile("block-lot.csv"):
        with open("block-lot.csv", 'r', encoding='utf-8-sig') as infile:
            # print(infile.read())
            reader = csv.DictReader(infile)
            data = {}
            for row in reader:
                processBlockLot(data, row)
    else:
        print("No block-lot.csv file found")


def initialize():
    global notrequired
    logo()
    for directory in [jdir, changeddir, 'StateTax', 'ArcGis', filter_dir, 'CSV_json',
                      # "notreq", ss
                      ]:
        if not os.path.isdir(directory):
            os.mkdir(directory)
    if not os.path.isfile(nrfile):
        with open(nrfile, 'w') as nfile:
            nfile.write("")
    if not os.path.isfile(scrapedcsv):
        with open(scrapedcsv, 'w', newline='', encoding=encoding) as sfile:
            csv.DictWriter(sfile, fieldnames=fieldnames).writeheader()
    with open(nrfile) as nfile:
        notrequired = nfile.read().splitlines()


def main():
    initialize()
    # CategorizeAllJson()
    # processAllJson()
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


def checkMax(driver):
    while "maximum number of concurrent users." in driver.page_source:
        pprint("Case Jacket Public Access has reached the maximum number "
               "of concurrent users. Please try again later.")
        driver.get(nj_url)
        time.sleep(1)


def fillInfo(driver, n, y):
    if f"{y}-{n}" in notrequired:
        pprint(f"Number {n} Year {y} not required!")
        return False
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
            driver.find_element(By.XPATH, '//*[@id="disclaimerform:button"]').click()
        except:
            pprint("Disclaimer captcha manually solved!")
        time.sleep(1)


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
    if not debug:
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
                county = tab_data["County"]
                district = tab_data["Municipality"].split("-")[1].strip()
                label = tab_data["Label"].split()
                block = label[1]
                lot = label[-1]
                if county in ["Burlington", "Camden"]:
                    tab_data["StateTax"] = {}
                elif county == "Ocean":
                    tab_data["StateTax"] = getOcean(district, block, lot)
                else:
                    tab_data["StateTax"] = getNJactb(county, district, block, lot,
                                                     tab_data["Municipality"].split("-")[0].strip())
                tab_data['ArcGis'] = getArcGis(county, district, block, lot)
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
            with open(jf.replace(jdir, "notreq") + ".json", 'w') as jfile:
                json.dump(data, jfile, indent=4)
    else:
        with open(nrfile, 'a') as nfile:
            nfile.write(f"{y}-{n}\n")
        notrequired.append(f"{y}-{n}")
        pprint(f"Not required {data['Docket Number']}")
        with open(jf.replace(jdir, "notreq") + ".json", 'w') as jfile:
            json.dump(data, jfile, indent=4)
    # if debug:
    #     return data
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


#
#
# def uploadCSV(sht, csv_file):
#     # global count
#     # if count % 5 == 0:
#     pprint("Uploading CSV..")
#     credentials = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', SCOPES)
#     client = gspread.authorize(credentials)
#     spreadsheet = client.open_by_url(sht)
#     with open(csv_file, 'r') as file_obj:
#         content = file_obj.read()
#         client.import_csv(spreadsheet.id, data=content)
#     pprint(f"{csv_file} uploaded to {sht}")
#     # count += 1
#
#
# def create():
#     spreadsheet_details = {
#         'properties': {
#             'title': 'NJ-Court'
#         }
#     }
#     credentials = service_account.Credentials.from_service_account_file('client_secret.json', scopes=SCOPES)
#     spreadsheet_service = build('sheets', 'v4', credentials=credentials)
#     drive_service = build('drive', 'v3', credentials=credentials)
#     sht = spreadsheet_service.spreadsheets().create(body=spreadsheet_details, fields='spreadsheetId').execute()
#     sheetId = sht.get('spreadsheetId')
#     pprint('Spreadsheet ID: {0}'.format(sheetId))
#     permission1 = {
#         'type': 'user',
#         'role': 'writer',
#         'emailAddress': '786hassan777@gmail.com'
#     }
#     drive_service.permissions().create(fileId=sheetId, body=permission1).execute()
#     # print(sheetId)
#

def waitCaptcha(driver):
    time.sleep(5)
    fillagain = False
    captchacount = 1
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


def pprint(msg):
    m = f'{str(datetime.datetime.now()).split(".")[0]} | {msg}'
    print(m)
    # with open("logs.txt", 'a') as logfile:
    #     logfile.write(m + "\n")


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


def click(driver, xpath, js=False):
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


def getChromeDriver(proxy=None):
    options = webdriver.ChromeOptions()
    if debug:
        # print("Connecting existing Chrome for debugging...")
        options.debugger_address = "127.0.0.1:9222"
    else:

        print("PDF Download directory: " + download_dir)
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
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
        options.add_argument('--user-data-dir=C:/Selenium/ChromeProfile')
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
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


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


def ValidityTest():
    for file in os.listdir("./test1"):
        with open(f"./test1/{file}") as jfile:
            data = json.load(jfile)
            # pprint(json.dumps(data, indent=4))
            if isValid(data):
                if isValidDocket(data):
                    print(f"Valid {file}")
                else:
                    print(f"Valid but Not required docket {file}")
            else:
                print(f"Not required {file}")


def getGoogleAddress(street, county="", district=""):
    addr = f"{street} {county} {district}"
    # if debug:
    print('Returning default address')
    return addr
    url = f"https://www.google.com/search?q={addr}"
    print(f"Getting Google Address {url}")
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
    soup = BeautifulSoup(requests.get(url, headers={'user-agent': ua}).text, 'lxml')
    try:
        address = f'{soup.find("div", class_="desktop-title-content").text}, {soup.find("span", class_="desktop-title-subcontent").text}'
        print(f"Found {address}")
        return address
    except:
        print(f"No address found {url}")
        # print(soup)
        return ""


def TranslateCodeToMunicipality(code):
    with open("Municipality.json") as jfile:
        data = json.load(jfile)
        if code in data:
            return data[code]
        else:
            print("Code not found!!")
            return code


# def pdftoText(file):
#     with open(file, 'rb') as pdfFileObj:
#         pdfReader = PyPDF2.PdfFileReader(pdfFileObj)
#         text = ""
#         for page in range(pdfReader.numPages):
#             pageObj = pdfReader.getPage(page)
#             text += (pageObj.extractText())
#         print(text)


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


def check():
    initialize()
    print("Testing mode...")
    n = "22"
    y = "22"
    driver = getChromeDriver()
    getData(BeautifulSoup(driver.page_source, 'lxml'), driver, n, y)


def getName(name: str, source: str):
    data = {f"{source}BusinessName": name}
    try:
        # print(f"Name length ({len(name.split())})")
        if len(name.strip().split()) == 1:
            return data
        name = name.replace("+", "&")
        if "," in name and ", " not in name:
            name = name.replace(",", ", ")
        if "&" in name:
            data[f'{source}NameExtra'] = name.split("&")[1].strip()
            name = name.split("&")[0].strip()
        if "/" in name:
            data[f'{source}NameExtra'] = name.split("/")[1].strip()
            name = name.split("/")[0].strip()
        for extra in ['Jr', 'Heirs', 'EST OF']:
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
            data[f'{source}FirstName'] = name.split()[0]
            data[f'{source}LastName'] = name.split()[-1]
        elif "His Heirs" in name:
            data[f'{source}NameExtra'] = "His Heirs"
            data[f'{source}FirstName'] = name.split()[-1]
            data[f'{source}LastName'] = name.split()[0]
        elif "vs state of" in name.lower():
            data[f'{source}NameType'] = "GOVT OWNED"
        elif "llc" in name.lower() or "inc" in name.lower():
            data[f'{source}NameType'] = "Company"
        elif "-" in name and len(name.split()) == 2:
            data[f"{source}FirstName"] = name.split()[0]
            data[f"{source}LastName"] = name.split()[1]
        elif len(name.split()) == 2:
            data[f"{source}FirstName"] = name.split()[1]
            data[f"{source}LastName"] = name.split()[0]
        elif len(name.split()) == 3 and len(name.strip().split()[1]) < 3:
            data[f"{source}FirstName"] = name.split()[0]
            data[f"{source}MiddleName"] = name.split()[1]
            data[f"{source}LastName"] = name.split()[2]
        elif len(name.split()) == 3 and len(name.split()[1]) > 2:
            data[f"{source}FirstName"] = name.split()[1]
            data[f"{source}LastName"] = name.split()[0]
            data[f"{source}MiddleName"] = name.split()[2]
        elif len(name.split()) > 1 and name.split()[1][-1] == "," and len(name.split(",")[0].split()) == 2 and len(
                name.split(",")[1].split()) == 2:
            data[f"{source}FirstName"] = name.split()[0].replace(",", "")
            data[f"{source}LastName"] = name.split()[1][:-1].replace(",", "")
            data[f"{source}MiddleName"] = name.split(",")[1].replace(",", "").strip()
        elif name.split()[0][-1] == ",":
            data[f'{source}FirstName'] = name.split()[0][:-1].replace(",", "")
            data[f'{source}LastName'] = name.split(",")[1].split()[0].replace(",", "")
            if len(name.split(",")[1].split()) > 2:
                data[f'{source}MiddleName'] = name.split(",")[1].split()[1].replace(",", "")
        print(json.dumps(data, indent=4))
    except:
        print(len(name.split()))
        traceback.print_exc()
        print(f"Error in name {name}")
        # input("Press enter...")
    return data


if __name__ == "__main__":
    # initialize()
    # with open('names.txt') as f:
    #     for n in f.read().splitlines():
    #         getCourtName(n)
    # rows=[]
    # with open('names.txt') as f:
    #     for n in f.read().splitlines():
    #         if "Blk" not in n:
    #             rows.append(getName(n, "Court"))
    # with open('names.csv', 'w', newline='') as f:
    #     writer = csv.DictWriter(f, fieldnames=["CourtBusinessName", "CourtNameType", "CourtFirstName", "CourtMiddleName", "CourtLastName", "CourtNameExtra"])
    #     writer.writeheader()
    #     writer.writerows(rows)
    # processAllJson()
    # input("Done")
    # if debug:
    #     check()
    # else:
    main()
