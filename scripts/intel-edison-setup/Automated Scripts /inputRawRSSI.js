zmq = require('zeromq');
config = require('./aws_config.json');
Rx = require('rxjs/Rx')

///////////////////////////////////////////////////////////////////////////////////////////////
// STATE
/////////////////////////////////////////////////////////////////////////////////////////////// 
var transmitterId = 'test'
var anchor = 'rpi10'
var counter = 1

///////////////////////////////////////////////////////////////////////////////////////////////
// SOCKETS
/////////////////////////////////////////////////////////////////////////////////////////////// 
rawData = zmq.socket('push')
rawData.setsockopt(zmq.ZMQ_SNDHWM, 2000);
rawData.connect(config.zmqSockets.rawRSSI.pushpull);

///////////////////////////////////////////////////////////////////////////////////////////////
// OBSERVABLES
/////////////////////////////////////////////////////////////////////////////////////////////// 
beacon$ = Rx.Observable.timer(1000, 2000)

///////////////////////////////////////////////////////////////////////////////////////////////
// FUNCTIONS
///////////////////////////////////////////////////////////////////////////////////////////////
between = function(min, max) {  
  return Math.floor(
    Math.random() * (max - min + 1) + min
  )
}

///////////////////////////////////////////////////////////////////////////////////////////////
// SUBSCRIPTION
///////////////////////////////////////////////////////////////////////////////////////////////
beacon$.subscribe(function() {
	time = (new Date()).getTime()
	rssi = between(-100, -40)
	console.log ("Sending raw rssi packets...")
	var message = {
	    time: time,
	    gattid: transmitterId,
	    anchorId: anchor,
	    rssi: rssi,
	    tags: 'rawRSSI'
  	};
  	return rawData.send(JSON.stringify(message));
})