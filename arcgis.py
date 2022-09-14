import os

import json

import requests


def getArcGis(county, district, block, lot):
    with open("arcgis.json") as f:
        districts = json.load(f)
    try:
        if district.upper() not in districts[county.upper()]:
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
        print(json.dumps(res, indent=4))
        return
    attrib = res['results'][0]['value']['features'][0]['attributes']
    for a in [k for k in attrib.keys()]:
        if attrib[a] is None:
            del attrib[a]
    print(json.dumps(attrib, indent=4))
    with open(f"json/{county}-{district}-{block}-{lot}.json", 'w') as outfile:
        json.dump(attrib, outfile, indent=4)


def main():
    if not os.path.isdir("json"):
        os.mkdir("json")
    getArcGis("MERCER", "Trenton City", '701', '7')


if __name__ == '__main__':
    main()
