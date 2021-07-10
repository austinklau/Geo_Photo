import json
import math
import requests
from geojson import Point, Feature

from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash

app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('APP_CONFIG_FILE', silent=True)

MAPBOX_ACCESS_KEY = app.config['MAPBOX_ACCESS_KEY']
MIN_DISTANCE_THRESHOLD = app.config['MIN_DISTANCE_THRESHOLD']
MAX_DISTANCE_THRESHOLD = app.config['MAX_DISTANCE_THRESHOLD']

x_origin = 19.8968
y_origin = 155.5828
count = 0

ROUTE = []


# Mapbox driving direction API call
# This can only handle 25 so must adapt
ROUTE_URL = "https://api.mapbox.com/directions/v5/mapbox/driving/{0}.json?access_token={1}&overview=full&geometries=geojson"

#ROUTE_URL = "https://api.mapbox.com/directions/v5/mapbox/driving/{0}.json?{2}&access_token={1}&overview=full&geometries=geojson"

# Distance between 2 pairs of points in meters
def distanceBetween(lat1, lon1, lat2, lon2):
    R = 6371300 # meters
    phi = lat1 * math.pi/180 # radians
    theta = lat2 * math.pi/180
    d_angle = (lat2-lat1) * math.pi/180
    d_lon = (lon2-lon1) * math.pi/180

    a = math.sin(d_angle/2) * math.sin(d_angle/2) + math.cos(phi) * math.cos(theta) * math.sin(d_lon/2) * math.sin(d_lon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = R * c; # in meters
    return d

# Calculate the center of a bunch of coordinates
def calcCenterPoint():
    size = len(ROUTE)
    r = math.pi/180
    # Average of x, y, z coords
    x = sum(math.cos(i["lat"]* r) * math.cos(i["long"]* r) for i in ROUTE) / size
    y = sum(math.cos(i["lat"]* r) * math.sin(i["long"]* r) for i in ROUTE) / size
    z = sum(math.sin(i["lat"]* r) for i in ROUTE) / size
    # x = sum(map(lambda i : math.cos(i["lat"]* r) * math.cos(i["lon"]* r), ROUTE)) / size
    
    # y = sum(map(lambda i : math.cos(i["lat"]* r) * math.sin(i["lon"]* r), ROUTE)) / size
    # z = sum(map(lambda i : math.sin(i["lat"]* r), ROUTE)) / size

    lon = math.atan2(y, x)
    hyp = math.sqrt(x*x+y*y)
    lat = math.atan2(z, hyp)

    global x_origin, y_origin
    x_origin = lat / r
    y_origin = lon / r


def create_route_url(start, stop):
    # Create a string with all the geo coordinates
    
    lat_longs = ";".join(["{0},{1}".format(ROUTE[i]["long"], ROUTE[i]["lat"]) for i in range(start, stop)])

    #radiuses
    # rad = "radiuses=".join("10000;" for i in range(start,stop))
    # print(rad)

    # Create a url with the geo coordinates and access token
    url = ROUTE_URL.format(lat_longs, MAPBOX_ACCESS_KEY)
    
    return url

    

# Use requests to run the mapbox route API request and return the results as a GeoJSON object:
def get_route_data():
    coord_data = []
    curr = 0
    size = len(ROUTE)
    while (curr < size - 1):
        # Get the route url
        end = curr + 25 if curr + 25 < size else size
        route_url = create_route_url(curr, end)
        curr = end-1
        # Perform a GET request to the route API
        result = requests.get(route_url)
        # Convert the return value to JSON
        data = result.json()
        if data["code"] != 'InvalidInput': # only take valid segments
        #add the coordinates to the chain
            coord_data.extend(data["routes"][0]["geometry"]["coordinates"])
        else:
             print(data["code"])

    #print(coord_data)
    return coord_data

# Create GeoJSON objects for markers
def create_stop_location_detail(latitude, longitude, date, index, route_index):
    point = Point([longitude, latitude])
    properties = {
        'icon': "campsite",
        'marker-color': '#3bb2d0',
        'marker-symbol': index,
        'route_index': route_index,
        'date' : date
    }
    feature = Feature(geometry = point, properties = properties)
    return feature

def create_stop_locations_details():
    stop_locations = []
    for route_index, location in enumerate(ROUTE):
        stop_location = create_stop_location_detail(
            location['lat'],
            location['long'],
            location['date'],
            len(stop_locations) + 1,
            route_index
        )
        stop_locations.append(stop_location)
    return stop_locations

# Processing dummy input for now...
@app.route('/', methods=["POST", "GET"])
def home():
    if request.method == "POST":
        #print(request.form["data"])
        data = json.loads(request.form["data"]) # convert the json
        #Get the data ready for mapping
        # global x_origin, y_origin
        # x_origin = sum(data[0])/len(data[0])
        # y_origin = sum(data[1])/len(data[1])
        for i in range(len(data[0])):
            # Take the first, or if distance is greater than ~25mi
            if i>0:
                dis = distanceBetween(ROUTE[-1]["lat"], -1 *ROUTE[-1]["long"], data[0][i], data[1][i]) # don't forget the -1 factor
            else:
                dis = MIN_DISTANCE_THRESHOLD + 1
            if (dis < 0):
                print(dis)
            if i == 0 or dis > MIN_DISTANCE_THRESHOLD:
                ROUTE.append({"lat": data[0][i], "long": -1 * data[1][i], "date": data[2][i]}) # don't forget the -1 factor
        # print(ROUTE)
        if (len(ROUTE) > 1): # Only render map if there are enough points
            return redirect(url_for("map"))
        return render_template("index.html")
    else:
        return render_template("index.html")


       
    
@app.route('/map')
def map():
    # Only allow loading of map page if ROUTE has been defined
    if len(ROUTE) == 0:
        return render_template("index.html")

    coord_data = get_route_data() 
    stop_locations = create_stop_locations_details()
    calcCenterPoint() # set the center of the map to this point
    print(len(ROUTE))

    return render_template('map.html', 
        ACCESS_KEY=MAPBOX_ACCESS_KEY,
        coord_data = coord_data,
        stop_locations = stop_locations,
        x_origin = x_origin,
        y_origin = y_origin
    )