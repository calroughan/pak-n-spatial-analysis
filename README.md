
# Supermarket Location Hotelling Equilibrium

5th November 2021

This repository contains the scripts used to generate a geospatial visualisation of the three major supermarket brands 
in Auckland, New Zealand.

Having read an introduction to Hotelling's model of spatial competition, I started thinking about how to visualise a 
spatial distribution of competitive brands. Auckland is dominated by three supermarket chains, hence I decided to use 
them for this project.

Isochrones are generated surrounding each store demonstrating the region that each store services, and the overlapping 
adjacency of supermarkets in high-density areas.

This can be applied to any city or region by changing the bounding box coordinates and the names of the brands to 
analyse.

This project utilises data from OpenStreetMap and open source tools including: 
- Openrouteservice is used to generate isochrones,
- The Overpass API is used to extract data from OpenStreetMap, and 
- Leaflet.js is used via Folium to generate the HTML data visualisation map.

Note that a free API key is required to use the ORS API. Store this in a secrets.py 


