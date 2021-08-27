import json
# import redis
import zmq
import time
import threading
import math
import random
import numpy as np
from collections import defaultdict
from datetime import timedelta
# from barycentric import   barycentric
# from rssi import rssiToDistance, rssiToDistanceVariance
# from cache import getCache
# from aggregate import getEdges
from pprint import PrettyPrinter
# from storeScale import getScale, getCoordinates

pp = PrettyPrinter(indent=2)

####################################################################################
## REDIS, ZMQ
####################################################################################

config  = None
with open('./aws_config.json', 'r') as f:
  config = json.load(f)

# print (config['zmqSockets']['broker']['xsub'])
# r = redis.Redis(charset="utf-8", decode_responses=True)

notifications = zmq.Context().socket(zmq.SUB)
notifications.setsockopt_string(zmq.SUBSCRIBE, config['notifications']['cacheUpdate'])
notifications.connect(config['zmqSockets']['broker']['xpub'])

notify = zmq.Context().socket(zmq.PUB)
notify.connect(config['zmqSockets']['broker']['xsub'])

# requests = zmq.Context().socket(zmq.REQ)
# requests.connect(config['zmqSockets']['serverRequests']['reqrep'])

####################################################################################
## State
####################################################################################

cache         = {}
history       = defaultdict(lambda: {})
deviceId = 'b9'
sysStartTime = time.time()*1000
checkpoints = { '1': [0,0], '2': [1,0], '3': [1,1], '4': [0,1], '5': [2,0], '6': [2,1], '7': [2,2], '8': [3,0], '9': [3,1], '10': [3,2]}
print ("Experiment Start:", sysStartTime, datetime.fromtimestamp(int(sysStartTime).strftime("%Y-%m-%d %H:%M:%S")))
####################################################################################
## UTILITIES
####################################################################################

def updateCache():
  global cache
  cache = getCache()  
  print('loaded cache version', cache['version'])
  # requests.send_string(config['notifications']['cacheRequest'])
  # cache = requests.recv_json()
  # if cache and 'version' in cache:
    # print('loaded cache version', cache['version'])

####################################################################################
## Methods
####################################################################################

def augmentGraph(edges, interval):
  # augment info
  rems = []
  for t in edges:
    for r in edges[t]:
      try:
        measuredPower = float(cache['devices'][t]['beacon']['measuredPower'])
        rssi          = float(edges[t][r]['mu'])
        sigma         = float(edges[t][r]['sigma'])
        period        = float(edges[t][r]['period'])
        location      = cache['devices'][r]['location']
        sigmaDistance = rssiToDistanceVariance(rssi, sigma, measuredPower)
        distance      = rssiToDistance(rssi, measuredPower)
        scale         = location['map']['scale']
        sigmaRadians  = sigmaDistance / scale**2
        edges[t][r] = {
          'measuredPower': measuredPower,
          'rssi': rssi,
          'sigma': sigma,
          'numObservations': interval / period,
          'location': location,
          'distance': distance,
          'sigmaDistance': sigmaDistance,
          'radians': distance / scale,
          'sigmaRadians': sigmaRadians
        }
      except:
        rems.append((t,r))
        continue

  # remove malformed edges
  for (t, r) in rems:
    del edges[t][r]

  # get edges not in the same map as closest
  rems = []
  for t, info in edges.items():
    try:
      if info:
        closest   = sorted(info.keys(), key=lambda r: info[r]['distance'])[0]
        location  = info[closest]['location']
        for r in info:
          if info[r]['location']['map']['id'] != location['map']['id']:
            rems.append((t,r))
    except:
      continue

  # remove receivers not in the same map as the closest
  for (t, r) in rems:
    del edges[t][r]

  # return augmented edges
  return edges

def transmitterGraph(edges):
  d = defaultdict(lambda: {})
  for k, v in edges.items():
    receiverId      = v['receiverId']
    transmitterId   = v['transmitterId']
    beaconId        = cache['device'][transmitterId]['beaconId']
    measuredPower   = float(cache['beacon'][beaconId]['measuredPower'])
    rssi            = float(v['mu'])
    mapId           = cache['device'][receiverId]['mapId']
    scale           = float(cache['map'][mapId]['scale']) 
    distance        = rssiToDistance(rssi, measuredPower)
    # make dictionary
    d[transmitterId][receiverId] = {
      'distance': distance,
      'radians':  distance / scale,
      'scale':    scale,
      'lat':      float(cache['device'][receiverId]['lat']),
      'lng':      float(cache['device'][receiverId]['lng']),
      'mapId':    mapId
    }
  # remove nodes which are not in the same map as the closest node
  remove = set()
  for t in d.keys():
    closest = sorted(d[t].keys(), key=lambda x: d[t][x]['distance'])[0]
    mapId   = d[t][closest]['mapId']
    for r, v in d[t].items():
      if v['mapId'] != mapId:
        remove.add((t,r))
  # delete entries
  for (t, r) in remove:
    del d[t][r]
  return d

def calculateLocation(n, nbrsInfo):
  nbrs  = list(nbrsInfo.keys())
  _map        = nbrsInfo[nbrs[0]]['location']['map']
  pos   = barycentric(
    n,
    nbrs,
    nbrsInfo
  )
  return {
    'map': _map,
    'latLng': pos,
    'lat': pos[1,0],
    'lng': pos[0,0]
  }

def transmitterLocations(transmitters):
  return { t: calculateLocation(t, info) \
    for t, info in transmitters.items() \
    if cache['devices'][t]['type'] == 'mobile' and info}

def distance(a, b, scale):
  return scale * np.linalg.norm(a - b)

def checkBoundary(lng, lat):
  global cache
  i = 0
  contains = []
  while i< len(cache['maps']['actlab']['navMesh']['features']):
    pt1 = cache['maps']['mini_actlab']['navMesh']['features'][i]['geometry']['coordinates'][0][0]
    pt2 = cache['maps']['mini_actlab']['navMesh']['features'][i]['geometry']['coordinates'][0][1]
    pt3 = cache['maps']['mini_actlab']['navMesh']['features'][i]['geometry']['coordinates'][0][2]
    pt4 = cache['maps']['mini_actlab']['navMesh']['features'][i]['geometry']['coordinates'][0][3]
    minXpt = min(pt1[0], pt2[0], pt3[0], pt4[0])
    maxXpt = max(pt1[0], pt2[0], pt3[0], pt4[0])
    minYpt = min(pt1[1], pt2[1], pt3[1], pt4[1])
    maxYpt = max(pt1[1], pt2[1], pt3[1], pt4[1])
    i+=1
    contains.append(((lng > minXpt and lng < maxXpt) and (lat > minYpt and lat < maxYpt)))
  return contains

def shiftPtToSide(obstacleNum, lng, lat):
  global cache
  pt1 = cache['maps']['mini_actlab']['navMesh']['features'][obstacleNum]['geometry']['coordinates'][0][0]
  pt2 = cache['maps']['mini_actlab']['navMesh']['features'][obstacleNum]['geometry']['coordinates'][0][1]
  pt3 = cache['maps']['mini_actlab']['navMesh']['features'][obstacleNum]['geometry']['coordinates'][0][2]
  pt4 = cache['maps']['mini_actlab']['navMesh']['features'][obstacleNum]['geometry']['coordinates'][0][3]
  dist1 = math.sqrt((lng - pt1[0])**2 + (lat - pt1[1])**2)
  dist2 = math.sqrt((lng - pt2[0])**2 + (lat - pt2[1])**2)
  dist3 = math.sqrt((lng - pt3[0])**2 + (lat - pt3[1])**2)
  dist4 = math.sqrt((lng - pt4[0])**2 + (lat - pt4[1])**2)
  if dist1 == min(dist1, dist2, dist3, dist4):
    return [lng, pt1[1]]
  elif dist2 == min(dist1, dist2, dist3, dist4):
    return [lng, pt2[1]]
  elif dist3 == min(dist1, dist2, dist3, dist4):
    return [lng, pt3[1]]
  else:
    return [lng, pt4[1]]



def updateLocations(locations, delta):
  global history
  updates = set()
  for location in locations.items():
    _map = location['map']
     # create if not exist
    if (deviceId not in history) or \
    (deviceId in history and \
    distance(location['latLng'], history[deviceId]['location']['latLng'], _map['scale']) > delta):
      updates.add(deviceId)
    # update history
    history[deviceId].update({
      'location': {
        'map': _map,
        'latLng': location['latLng'],
        'lat': location['lat'],
        'lng': location['lng']
      }
    })
  return updates

def between_decimals(min, max): 
  return (random.random() * (max - min + 1) + min)


def processEdges(interval):
  # edges         = getEdges()
  now           = int(time.time() * 1000)
  # transmitters  = augmentGraph(edges, interval)
  # locations     = transmitterLocations(transmitters)
  _map = {
      "id": "actlab",
      "coordinates": [
        [-0.11997600023306632, 0.2390170498225217], 
        [0.36101917799351213, 0.2390170498225217], 
        [0.36101917799351213, -0.028774003760801747], 
        [-0.11997600023306632, -0.028774003760801747]
      ]
      "scale": 52
  }

  lng = between_decimals(-0.23397445680726037,0.09561538693682792)
  lat = between_decimals(-0.046691889369185446,0.1864239264343155)

  locations = { 
    deviceId: { 
      'map': _map, 
      'latLng': [[float("{0:.6f}".format(float(lng))), float("{0:.6f}".format(float(lat)))]], 
      'lat': lat, 
      'lng': lng 
    }
  }
  updates       = updateLocations(locations, delta=0)
  # deviceId = 'b2'

  history[deviceId].update({
      'location': {
        'map': _map,
        'lat': lat,
        'lng': lng
      }
  })


  # for deviceId in updates:
  # inObstacle = checkBoundary(lng, lat)
  # print (inObstacle.index(True))
  # if True in inObstacle:
    # shiftedPos = shiftPtToSide(inObstacle.index(True), lng, lat)
    # topic = config['notifications']['positionUpdate']
    # message = json.dumps({
    #     'id':     'b2',
    #     'lng':    shiftedPos[0],
    #     'lat':    shiftedPos[1],
    #     'map':    _map,
    #     # 'distance': 1,
    #     'time':   now
    #   })
    # notify.send_multipart([topic.encode('utf-8'), message.encode('utf-8')])
  # else:
  print ("Sending position data...")
  topic = config['notifications']['positionUpdate']
  message = json.dumps({
      'id':     deviceId,
      'lng':    history[deviceId]['location']['lng'],
      'lat':    history[deviceId]['location']['lat'],
      'map':    history[deviceId]['location']['map'],
      # 'distance': 1,
      'time':   now
    })
  print (message)
  # notify.send_string("Hello")
  notify.send_multipart([topic.encode('utf-8'), message.encode('utf-8')])

####################################################################################
## THREADS
####################################################################################

def listenForCacheUpdates():
  global cache
  while True:
    [topic, message] = notifications.recv_multipart()
    message = json.loads(message.decode())
    if message['version'] != cache['version']:
      updateCache()

def main():
  interval = 1
  # processEdges(interval*1000)
  start = sysStartTime
  timer = time.time()*1000
  exit = sysStartTime + 200000
  while timer < exit:
    while math.floor(timer-start) == 5:
      start+=5000
      # time.sleep(interval)
      try:
          processEdges(interval*1000)
          timer = time.time()*1000
      except:
        raise
    timer = time.time()*1000

####################################################################################
## BEGIN
####################################################################################

# update cache
# updateCache()

# listen for cache notifications
# t1 = threading.Thread(target=listenForCacheUpdates)
# t1.setDaemon(True)
# t1.start()

# main loop
main()
