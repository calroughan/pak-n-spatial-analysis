
"""Gist 1"""
import requests
import xml.etree.ElementTree as ET
import folium
import webbrowser
import time
from os import path
from openrouteservice import client

# Import my api key from secrets.py
from secrets import api_key

bbox = [-37.1109295, 174.3876826, -36.670165, 175.082077]

url = f'https://overpass-api.de/api/interpreter?' \
      f'data=[out:json];' \
      f'(node["shop"="supermarket"]({",".join([str(x) for x in bbox])}););out;' \
      f'(way["shop"="supermarket"]({",".join([str(x) for x in bbox])}););out;' \
      f'>;' \
      f'out skel qt;'

res = requests.get(url)
data = res.json()


""" Gist 2 """
# Example data output


""" Gist 3 """
supermarkets = ['Countdown', 'New World', 'Pak\'nSave']

# Create a dict to store all supermarkets of interest extracted from OSM
data_subset = {}

for element in data['elements']:

    # Check that the element has a 'tags' dict and that the dict, if it exists, has the 'name' listed
    if 'tags' in element and 'name' in element['tags']:

        # Loop over the supermarkets of interest to check if any match the current name.
        for supermarket in supermarkets:

            if supermarket.lower() in element['tags']['name'].lower():

                # If the element is a way, ie comprised of multiple nodes, then take the first node as the location
                if element['type'] == 'way':

                    data_subset[element['id']] = {
                        'name': supermarket.lower()
                        , 'display name': element['tags']['name']
                        , 'type': 'way'
                        , 'location': element['nodes'][0]
                    }

                # If the element is a single node, store the location of the node
                elif element['type'] == 'node':

                    data_subset[element['id']] = {
                        'name': supermarket.lower()
                        , 'display name': element['tags']['name']
                        , 'type': 'node'
                        , 'location': [element['lat'], element['lon']]
                    }

                else:
                    print(f"Location {element['tags']['name']} does not appear to be readable")


""" Gist 4 """
# An example of an Overpass API query with two nodes:
# https://overpass-api.de/api/interpreter?node(id:266594227,259292638);out;

# Extract the 'ways' from all supermarkets
way_nodes = [data_subset[key]['location'] for key in data_subset.keys() if data_subset[key]['type'] == 'way']

way_locations = []

# Query the API in batches of 100 nodes for speed.
for i in range(0, len(way_nodes), 100):

    # Query the batch of nodes
    url = f"https://overpass-api.de/api/interpreter?" \
          f"node(id:{','.join(map(str, way_nodes[i:100 * (i + 1)]))});" \
          f"out;"
    r = requests.get(url)

    # XML tree output
    tree = ET.fromstring(r.text)
    way_locations.extend([x.attrib for x in tree.iter()][3:])


""" Gist 5 """
# Get the OSM IDs of each element in the API response
way_keys = [x['id'] for x in way_locations]

# Assign the API response coordinates to the data
for key in data_subset.keys():
    if data_subset[key]['type'] == 'way':

        idx = way_keys.index(str(data_subset[key]['location']))
        data_subset[key]['location'] = [way_locations[idx]['lat'], way_locations[idx]['lon']]


""" Gist 6 """
# Generate the API parameters
params = {
    'profile': 'driving-car'
    # 'profile': 'foot-walking'
    # 'profile': 'cycling-regular'
    , 'range': [180]           # Three minutes in seconds
    , 'attributes': ['total_pop']
}

# Set this to true if not hosting your own Openrouteservice instance
throttle_requests = True


""" Gist 7 """
m = folium.Map(
    tiles='Stamen Toner'                                            # Monochromatic map
    # tiles='openstreetmap'                                         # Normal map
    , location=((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)   # Centre the map using the bounding box coords
    , zoom_start=11
)

# Create a dictionary mapping each supermarket chain to its respective brand colours.
# Note that we're using lowercase supermarket names as the keys.
supermarkets = ['Countdown', 'New World', 'Pak\'nSave']
colours = ['green', 'red', 'yellow']

colour_dict = dict(zip([supermarket.lower() for supermarket in supermarkets], colours))


""" Gist 8"""
# The API key is stored in the secrets.py file
ors = client.Client(key=api_key)

idx = 0

# Loop over the stations and query the API for the isochrone data, then add each station to the map
for key in data_subset.keys():

    idx += 1

    if idx > 5:
        break

    if throttle_requests:
        time.sleep(3)

    # Add supermarket coordinates to params and query ORS.
    params['locations'] = [list(reversed(data_subset[key]['location']))]
    data_subset[key]['isochrone'] = ors.isochrones(**params)

    # Add isochrone to the map
    folium.features.GeoJson(
        data=data_subset[key]['isochrone']
        , style_function=lambda feature: dict(color=colour_dict[data_subset[key]['name']])
    ).add_to(m)

    # Add a point marker to the map
    folium.map.Marker(
        data_subset[key]['location']
        , icon=folium.Icon(
            color='lightgray'
            , icon_color=colour_dict[data_subset[key]['name']]
            , icon='shopping-cart'
            , prefix='fa'
        )
        , popup=f"{data_subset[key]['display name']}"
                f", Population: {int(data_subset[key]['isochrone']['features'][0]['properties']['total_pop'])}"
    ).add_to(m)

m.save('Supermarkets.html')
webbrowser.open(path.realpath('Supermarkets.html'), new=2)
