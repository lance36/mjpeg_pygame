import os
import httplib
import base64
import StringIO
import time
import pygame
from pygame.locals import *
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt

#User Variables
mqtt_user = "user"
mqtt_pwd = "password"
mqtt_broker = "192.168.1.1"
mqtt_port = 1883
mqtt_topic = "home/doorbell/reed"
mqtt_topic2 = "home/doorbell/screen"

mjpeg_ip = "127.0.0.1"
mjpeg_url= "/html/cam_pic_new.php"
mjpeg_user = "user"
mjpeg_pwd = "password"


#Init GPIO 
GPIO.setwarnings(False) #Suppress warnings
GPIO.setmode(GPIO.BCM)
GPIO.setup(18, GPIO.OUT) 
tftstate = 0
screenontime = 30  #Seconds the screen stays on upon touch

# Init framebuffer/touchscreen environment variables
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV'		, '/dev/fb1')
os.putenv('SDL_MOUSEDRV'	, 'TSLIB')
os.putenv('SDL_MOUSEDEV'	, '/dev/input/touchscreen')

# MJPEG Handler
class Mjpeg():
	def __init__(self, ip=mjpeg_ip, username=mjpeg_user, password=mjpeg_pwd):
		self.IP = ip
		self.Username = username
		self.Password = password
		self.Connected = False
		
	def Connect(self):
		try:
			h = httplib.HTTP(self.IP)
			h.putrequest('GET',mjpeg_url)
			h.putheader('Authorization', 'Basic %s' % base64.encodestring('%s:%s' % (self.Username, self.Password))[:-1])
			h.endheaders()
			errcode, errmsg, headers = h.getreply()
			self.File = h.getfile()
			self.Connected = True
			return True
		except:
			print 'HTTP Unable to Connect'
			self.Connected = False
			return False
			
	def Update(self):
		if self.Connected:
			data = self.File.readline()
			while data[0:15] != 'Content-Length:': #Read until we have good data..
				data = self.File.readline()

			if data[0:15] == 'Content-Length:':
				count = int(data[15:]) # jpg Size in byte after 15 chars
				s = self.File.read(count)
				while s[0] != chr(0xff):
					s = s[1:]
				p = StringIO.StringIO(s)
				return p
			else:
				return None
		else:
			return None	


#MQTT STUFF
# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
		print("MQTT Connected with result code "+str(rc))

		# Subscribing in on_connect() means that if we lose the connection and
		# reconnect then subscriptions will be renewed.
		client.subscribe(mqtt_topic)
		client.subscribe(mqtt_topic2)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
		global tftstate
		global oldepoch
		if(msg.payload=="ON"):
			# print "Turning on Screen from MQTT..."
			turn_on_screen()
		if(msg.payload=="OFF"):
			turn_off_screen()

# Screen state handler
def turn_on_screen():
		global tftstate
		global oldepoch
		GPIO.output(18, 1)	
		tftstate = 1
		oldepoch = time.time()
		
def turn_off_screen():
		global tftstate
		global oldepoch
		global screen
		GPIO.output(18, 0)	
		tftstate = 0
		oldepoch = time.time()		
		screen.fill((0,0,0)) # Clear Screen
		pygame.display.update()
		
def time_passed(oldepoch):
    return time.time() - oldepoch >= screenontime
print "initializing screen... why the fuck does this suck? just hit Ctrl-C"
screen = pygame.display.set_mode((320,240), pygame.FULLSCREEN)
print "screen initialized"		

# init pygame
pygame.init()
pygame.mouse.set_visible(False)

#init MQTT
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(username=mqtt_user,password=mqtt_pwd)

try:
	client.loop_start() #Multithreaded mqtt network loop. this will also handle reconnection.
	client.connect(mqtt_broker, mqtt_port, 60)
except:
	print "Mqtt not available"


#init mJPEG
mjpeg = Mjpeg()

turn_on_screen()

print "Starting."


#Main Loop
while True:
	#Touchscreen handler:
	for event in pygame.event.get():
		if(event.type is MOUSEMOTION):
			if GPIO.input(18) == 0:
				turn_on_screen()
			else:
				turn_off_screen()
				
	if (tftstate):
		mjpeg.Connect()  # Do i have to do an HTTP GET every time? can't i just leave the connection open and take the images?
		frame = mjpeg.Update()
		surface = pygame.image.load(frame)
		imageres = pygame.transform.scale(surface,(320,240)) # How many resources is this costing? is there a better way?
		screen.blit(imageres,(0,0))
		pygame.display.update()
		if (time_passed(oldepoch)):
			GPIO.output(18, 0)
			tftstate = 0
	time.sleep(0.1)  # Dont hog CPU resources while idle
