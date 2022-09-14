import os.path

import json

import requests
from bs4 import BeautifulSoup


def search(block, lot, county, district):
    with open("njactb.json", "r") as jfile:
        disctricts = json.load(jfile)
    try:
        district_number = disctricts[county.upper()][district.upper()]
    except:
        print("Invalid District")
        return None
    print(f"Fetching records for {county}/{district}/{block}/{lot}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    data = {
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
    response = requests.post('http://tax1.co.monmouth.nj.us/cgi-bin/inf.cgi', headers=headers, data=data, verify=False)
    soup = BeautifulSoup(response.text, 'lxml')
    if len(soup.find_all("a")) > 0:
        print(f"Found {len(soup.find_all('a'))} record(s) for {block}/{lot}/{district}.")
        getInfo(f'https://tax1.co.monmouth.nj.us/cgi-bin/{soup.find_all("a")[0]["href"]}', county, district, block,lot)
    else:
        print("No data found!")


def getInfo(url, county, district, block,lot):
    # with open('monmouth.html', 'r') as f:
    #     content = f.read()
    print(f"Fetching data from {url}")
    content = requests.get(url).text
    soup = BeautifulSoup(content, 'lxml')
    data = {"URL": url}
    table = soup.find_all('table')
    for key, val in zip(table[0].find_all("font", {"color": "BLACK"}), soup.find_all("font", {"color": "FIREBRICK"})):
        if len(key.text.strip()) > 0 and len(val.text.strip()) > 0:
            data[key.text.strip()] = val.text.strip().replace("&nbsp", "")
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
    print(json.dumps(data, indent=4))
    with open(f"./json/{county}-{district}{block}-{lot}-{district}.json", "w") as jfile:
        json.dump(data, jfile, indent=4)


def main():
    logo()
    if not os.path.isdir("json"):
        os.mkdir("json")
    search("2634", "39", "Essex","NEWARK")


def logo():
    print(r"""
    .__   __.        __          ___   .___________.  ______ .______   
    |  \ |  |       |  |        /   \  |           | /      ||   _  \  
    |   \|  |       |  |       /  ^  \ `---|  |----`|  ,----'|  |_)  | 
    |  . `  | .--.  |  |      /  /_\  \    |  |     |  |     |   _  <  
    |  |\   | |  `--'  |     /  _____  \   |  |     |  `----.|  |_)  | 
    |__| \__|  \______/     /__/     \__\  |__|      \______||______/  
===========================================================================
      New Jersey Association of County Tax Boards (NJACTB) scraper by
                 https://github.com/evilgenius786
===========================================================================
[+] Works without browser
[+] CSV/JSON Output
[+] Input: Block, Lot and District
[+] Output: All tax data!!
___________________________________________________________________________
""")


if __name__ == '__main__':
    main()
# def getDistricts():
#     print("Fetching districts...")
#     dist = {}
#     for key, val in districts.items():
#         response = requests.get(
#             f"https://tax1.co.monmouth.nj.us/cgi-bin/prc6.cgi?&ms_user=monm&passwd=data&srch_type=0&adv=0&out_type=0&district={val}")
#         soup = BeautifulSoup(response.text, "lxml")
#         dist[key] = {}
#         for option in soup.find("select", {"name": "district"}).find_all("option"):
#             dist[key][option.text.strip()] = option["value"]
#         print(json.dumps(dist, indent=4))
#     with open("njactb.json", "w") as jfile:
#         json.dump(dist, jfile, indent=4)
