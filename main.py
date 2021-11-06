import requests
import xml.etree.ElementTree as ET
import folium
import webbrowser
import time
from os import path
from openrouteservice import client

# Import my api key from secrets.py
from secrets import api_key


def query_overpass_for_supermarket_data(bbox):
    """
    Query the Overpass API to return all supermarket data within the specified bounding box.
    Return both nodes and ways.
    - Nodes are single points.
    - Ways are collections of nodes which may represent the exterior of a building, for example.
    Return this output as JSON as opposed to the default XML.

    This is a good introduction to the Overpass API format.
    https://gis.stackexchange.com/questions/187447/understanding-overpassturbo-query
    """

    url = f'https://overpass-api.de/api/interpreter?' \
          f'data=[out:json];' \
          f'(node["shop"="supermarket"]({",".join([str(x) for x in bbox])}););out;' \
          f'(way["shop"="supermarket"]({",".join([str(x) for x in bbox])}););out;' \
          f'>;' \
          f'out skel qt;'

    r = requests.get(url)
    return r.json()


def extract_supermarkets_of_interest(supermarkets, data):
    """
    The extracted data includes all supermarkets. For this analysis I'm only interested in the three main supermarkets
    hence this function generates a subset of supermarket nodes and ways that we have specified.

    The data can be returned as either 'nodes' or 'ways'. Nodes are single coordinates while ways are a set of nodes,
    A way might represent the exterior of a building, for example.

    This function checks if the node has a 'name' tag and if so then checks if the name is similar to any of the
    supermarkets of interest.

    Note that not all nodes follow the same structure, hence why some don't contain 'tags' or 'name'.

    """

    # Create a dict to store all supermarkets of interest extracted from OSM
    subset = {}

    for element in data['elements']:

        # Check that the element has a 'tags' dict and that the dict, if it exists, has the 'name' listed
        if 'tags' in element and 'name' in element['tags']:

            # Loop over the supermarkets of interest to check if any match the current name.
            for supermarket in supermarkets:

                if supermarket.lower() in element['tags']['name'].lower():

                    # If the element is a way, ie comprised of multiple nodes, then take the first node as the location
                    if 'nodes' in element:

                        subset[element['id']] = {
                            'name': supermarket.lower()
                            , 'display name': element['tags']['name']
                            , 'type': 'way'
                            , 'location': element['nodes'][0]
                        }

                    # If the element is a single node, store the location of the node
                    elif element['type'] == 'node':

                        subset[element['id']] = {
                            'name': supermarket.lower()
                            , 'display name': element['tags']['name']
                            , 'type': 'node'
                            , 'location': [element['lat'], element['lon']]
                        }

                    else:
                        print(f"Location {element['tags']['name']} does not appear to be readable")

    return subset


def query_overpass_for_node_location(data_subset):
    """
    The input subset contains the supermarkets of interest. Extract each point that is a 'way' such that we can query
    the Overpass API to return the coordinates of the first 'node' in the 'way'.
    An example of an Overpass API query with two nodes:
    "https://overpass-api.de/api/interpreter?node(id:266594227,259292638);out;"
    TODO add some error correction to the API request.
    Note that the API returns an XML response.
    """

    # Extract the 'ways' from all supermarkets
    way_nodes = gather_way_nodes(data_subset)
    way_locations = []

    # Query the API in batches of 100 nodes as to not overload the API.
    for i in range(0, len(way_nodes), 100):

        # Query the batch of nodes
        url = f"https://overpass-api.de/api/interpreter?" \
              f"node(id:{','.join(map(str, way_nodes[i:100 * (i + 1)]))});" \
              f"out;"
        r = requests.get(url)

        # XML tree output
        tree = ET.fromstring(r.text)
        way_locations.extend([x.attrib for x in tree.iter()][3:])

    return way_locations


def gather_way_nodes(data_subset):
    """
    Return a list of the first nodes of each 'way polygon' such that we can query the overpass API to return the
    location.
    """
    return [data_subset[key]['location'] for key in data_subset.keys() if data_subset[key]['type'] == 'way']


def join_way_data(data_subset, way_locations):
    """
    Join the Overpass API response to the location data.
    Note that the API responses are not always returned in the same order as the input request.
    """

    # Get the OSM IDs of each element in the API response
    way_keys = [x['id'] for x in way_locations]

    # Assign the API response coordinates to the data
    for key in data_subset.keys():
        if data_subset[key]['type'] == 'way':

            idx = way_keys.index(str(data_subset[key]['location']))
            data_subset[key]['location'] = [way_locations[idx]['lat'], way_locations[idx]['lon']]

    return data_subset


def isochrone_params(mode, travel_time):
    """
    Create a dictionary of the isochrone parameters, including:
    - 'profile':    The transportation method.
                    Some options are: 'driving-chair', 'foot-walking', and 'cycling-regular'
    - 'range':      The maximum travel time from each node to the isochrone boundary
    - 'attributes': Return additional geographic information about the isochrones
    """

    params = {
        'profile': mode
        , 'range': [travel_time * 60]       # Convert the travel_time to seconds
        , 'attributes': ['total_pop']
    }
    return params


def generate_ors_isochrones(supermarket, params, ors, throttle_requests):
    """
    The standard ORS API facilitates 20 isochrone requests per minute, hence the program sleeps for 3 seconds per
    API call. Alternatively you can host your own ORS routing engine to avoid this bottleneck.
    """

    if throttle_requests:
        time.sleep(3)

    # Add supermarket coordinates to params and query ORS.
    params['locations'] = [list(reversed(supermarket['location']))]
    supermarket['isochrone'] = ors.isochrones(**params)

    return supermarket


def map_colours(supermarkets, colours):
    """
    Create a dictionary mapping each supermarket chain to its respective brand colours.
    Note that we're using lowercase supermarket names as the keys.
    """
    return dict(zip([supermarket.lower() for supermarket in supermarkets], colours))


def add_location_to_folium(map, supermarket, colour_dict):
    """
    Add the isochrones and a marker for each location to the map
    """

    folium.features.GeoJson(
        data=supermarket['isochrone']
        , style_function=lambda feature: dict(color=colour_dict[supermarket['name']])
    ).add_to(map)

    folium.map.Marker(
        supermarket['location']
        , icon=folium.Icon(
            color='lightgray'
            , icon_color=colour_dict[supermarket['name']]
            , icon='shopping-cart'
            , prefix='fa'
        )
        , popup=f"{supermarket['display name']}"
                f", Population: {int(supermarket['isochrone']['features'][0]['properties']['total_pop'])}"
    ).add_to(map)


if __name__ == '__main__':

    # Set this to true if not hosting your own OpenRouteService instance
    throttle_requests = True

    # Define a bounding box to extract all data from within. The order is: bottom lat, left lon, top lat, right lon
    bbox = [-37.1109295, 174.3876826, -36.670165, 175.082077]

    # Specify the points of interest
    supermarkets = ['Countdown', 'New World', 'Pak\'nSave']
    colours = ['green', 'red', 'yellow']

    # Transportation mode
    mode = 'driving-car'
    # mode = 'foot-walking'
    # mode = 'cycling-regular'
    # mode = 'wheelchair'

    # Travel time to the station (minutes)
    travel_time = 3

    # Get data from OpenStreetMap
    data = query_overpass_for_supermarket_data(bbox)

    # Extract the supermarkets that we're interested in
    data_subset = extract_supermarkets_of_interest(supermarkets, data)

    # Extract locations of the first node in each way
    way_locations = query_overpass_for_node_location(data_subset)

    # Join this these way locations to the supermarkets of interest
    data_subset = join_way_data(data_subset, way_locations)

    # Generate the API parameters
    params = isochrone_params(mode, travel_time)

    # Set up folium map.
    map_type = 'Stamen Toner'                                           # Monochromatic map
    # map_type = 'openstreetmap'                                        # Normal map

    m = folium.Map(
        tiles=map_type
        # , location=(data_subset[0]['location'])                       # Centre the map at the first supermarket
        , location=((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)   # Centre the map using the bounding box coords
        , zoom_start=11
    )

    colour_dict = map_colours(supermarkets, colours)

    # Loop over the stations and query the API for the isochrone data, then add each station to the map
    for idx, key in enumerate(data_subset.keys()):

        if idx % 20 == 0:
            print(f"Currently processing supermarket {idx} of {len(list(data_subset.keys()))}.")

        # Return an isochrone for the supermarket
        supermarket = generate_ors_isochrones(
            data_subset[key]
            , params
            , client.Client(key=api_key)        # The API key is stored in the secrets.py file
            , throttle_requests
        )

        # Add this point to the folium map
        add_location_to_folium(m, supermarket, colour_dict)

    map_name = 'Supermarkets.html'
    m.save(map_name)
    webbrowser.open(path.realpath(map_name), new=2)
